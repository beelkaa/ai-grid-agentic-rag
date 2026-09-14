import asyncio
import httpx
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from backend.infrastructure.embeddings import get_embeddings
from backend.infrastructure.vector_store import client
from backend.infrastructure.db import save_message, get_messages
from backend.config.loader import load_config
from typing import Any, Optional
from collections.abc import AsyncIterator
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langfuse import Langfuse, observe as langfuse_observe



load_dotenv()

config = load_config(str(Path(__file__).resolve().parents[1] / "config" / "config.yaml"))

_background_tasks: set[asyncio.Task] = set()

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

def _update_generation_usage(model: str, usage: Optional[dict[str, Any]]) -> None:
    if not usage:
        return

    prompt_tokens = int(usage.get("prompt_tokens", usage.get("input", 0)) or 0)
    completion_tokens = int(usage.get("completion_tokens", usage.get("output", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", usage.get("total", prompt_tokens + completion_tokens)) or 0)

    try:
        langfuse.update_current_generation(
            model=model,
            usage_details={
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": total_tokens,
            },
        )
    except Exception:
        return

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Recherche des documents pertinents dans la base de connaissances AI Grid",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "La requête de recherche"},
                    "category": {
                        "type": "string",
                        "description": (
                            "Optional category to restrict the search to. "
                            "'company': AI Grid's business info — GPU hosting plans (IAAS), PAAS subscription plans, general pricing tiers, mission, FAQ. "
                            "'getting-started': platform overview, framework integration guides (LangChain, LangGraph, LlamaIndex). "
                            "'models': model specifications and capabilities. "
                            "'pricing': per-token API pricing for individual models (input/output cost per million tokens). "
                            "Leave empty to search all categories."
                        )
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_models",
            "description": (
                "List the models currently available from the AI Grid API. Use this only for questions asking which models are available, "
                "supported, or in the model catalog. For model capabilities or pricing, use search_documents instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

DEPRECATED_MODEL_NAMES = ("gpt oss 20b", "gpt-oss-120b")


def _contains_deprecated_model_name(text: str) -> bool:
    """Deterministic backstop: catches known stale/deprecated model names
    even if the LLM-based reflect() judge misses them on a given run."""
    normalized = text.lower()
    return any(name in normalized for name in DEPRECATED_MODEL_NAMES)


def _is_pricing_question(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in (
        "price", "pricing", "cost", "per token", "per million tokens",
    ))


def _tools_for_messages(messages: list[dict]) -> list[dict]:
    latest_user_message = next(
        (message["content"] for message in reversed(messages) if message.get("role") == "user"),
        "",
    )
    if _is_pricing_question(latest_user_message):
        return [
            tool for tool in TOOLS
            if tool["function"]["name"] != "list_available_models"
        ]
    return TOOLS

@langfuse_observe()
async def search_documents(query: str, category: Optional[str] = None) -> str:
    question_vector = await get_embeddings(query)

    query_filter = None
    if category:
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category))]
        )

    results = client.query_points(
        collection_name=config.retrieval.collection_name,
        query=question_vector,
        limit=config.retrieval.top_k,
        query_filter=query_filter
    )

    retrieved_texts = []
    for point in results.points:
        retrieved_texts.append(f'{point.payload["text"]} (Source: {point.payload["url"]})')

    return "\n".join(retrieved_texts)


@langfuse_observe()
async def list_available_models() -> str:
    api_key = os.getenv("AI_GRID_API_KEY")
    base_url = os.getenv("AI_GRID_BASE_URL")

    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=config.timeouts.http_seconds,
        )
    response.raise_for_status()
    models = response.json().get("data", [])
    return json.dumps([
        {"id": model.get("id"), "owned_by": model.get("owned_by")}
        for model in models
    ])

@langfuse_observe(as_type="generation")
async def reason(
    messages: list,
    base_url: str,
    api_key: str,
    model: str,
    force_final: bool = False,
) -> dict:
    """
    Ask the model what to do next, given the conversation so far.

    This is the "Reason" step of the ReAct loop: it sends the full
    message history to the AI Grid API and lets the model decide
    whether to respond directly or call a tool (e.g. search_documents).
    It does NOT execute any tool itself — that's act()'s job.

    Args:
        messages: the conversation history so far (list of role/content dicts)

    Returns:
        The raw model message (dict) — may contain either plain text
        content or a "tool_calls" field if the model wants to act.
    """
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": config.agent.temperature,
                "tools": _tools_for_messages(messages),
                "tool_choice": "none" if force_final else "auto",
            },
            timeout=config.timeouts.http_seconds
        )
    response.raise_for_status()
    # AI Grid follows the OpenAI-style response format:
    # the actual message is nested in choices[0]
    response_data = response.json()
    _update_generation_usage(model, response_data.get("usage"))
    message = response_data["choices"][0]["message"]
    return message


@langfuse_observe(as_type="generation")
async def stream_reason(
    messages: list,
    base_url: str,
    api_key: str,
    model: str,
    force_final: bool = False,
) -> AsyncIterator[dict]:
    """Stream one model turn while keeping tool-call details internal."""
    tool_calls = {}
    content_parts = []

    async with httpx.AsyncClient() as http_client:
        async with http_client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": config.agent.temperature,
                "tools": _tools_for_messages(messages),
                "tool_choice": "none" if force_final else "auto",
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            timeout=config.timeouts.http_seconds,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                _update_generation_usage(model, chunk.get("usage"))
                choices = chunk.get("choices") or []
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})
                content = delta.get("content")
                if content:
                    content_parts.append(content)
                    yield {"type": "content", "text": content}

                for tool_call in delta.get("tool_calls", []):
                    index = tool_call["index"]
                    accumulated = tool_calls.setdefault(index, {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    accumulated["id"] += tool_call.get("id", "")
                    function = tool_call.get("function", {})
                    accumulated["function"]["name"] += function.get("name", "")
                    accumulated["function"]["arguments"] += function.get("arguments", "")

    yield {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": "".join(content_parts),
            **({"tool_calls": list(tool_calls.values())} if tool_calls else {}),
        },
    }


AVAILABLE_TOOLS = {
    "search_documents": search_documents,
    "list_available_models": list_available_models,
}

@langfuse_observe()
async def act(tool_call: dict) -> str:
    """
    Execute the tool the model asked for and return the result as a string.

    This is the "Act" step: looks up the requested tool by name,
    parses its arguments, calls it, and serializes the result to JSON
    so it can be re-injected into the conversation as an observation.
    """
    tool_name = tool_call["function"]["name"]
    raw_arguments = tool_call["function"]["arguments"]
    arguments = json.loads(raw_arguments)

    function_to_call = AVAILABLE_TOOLS[tool_name]
    result = await function_to_call(**arguments)
    return json.dumps(result)

def observe_step(messages: list, model_message: dict, result: str) -> list:
    """
    Update the conversation history with the model's tool call
    and the result of executing it (the "Observe" step of ReAct).

    Args:
        messages: the conversation history so far
        model_message: the raw message returned by reason() (contains tool_calls)
        result: the JSON string returned by act()

    Returns:
        The updated messages list, ready for the next reason() call.
    """
    # add the model's own turn (it requested a tool call)
    messages.append(model_message)

    # add the tool's result, linked back to the request via tool_call_id
    new_message = {
        "role": "tool",
        "tool_call_id": model_message["tool_calls"][0]["id"],
        "content": result
    }
    messages.append(new_message)

    return messages


async def run_agent(max_iterations: int, messages: list, base_url: str, api_key: str, model: str) -> str:
    """
    Run the full Reason -> Act -> Observe loop until the model gives
    a final text answer, or until max_iterations is reached.
    """
    search_iterations = 0
    for i in range(max_iterations):
        model_message = await reason(messages, base_url, api_key, model)

        if "tool_calls" not in model_message or not model_message["tool_calls"]:
            break

        tool_call = model_message["tool_calls"][0]
        search_iterations += 1
        result = await act(tool_call)
        messages = observe_step(messages, model_message, result)

    else:
        model_message = await reason(messages, base_url, api_key, model, force_final=True)

    context_pieces = [m["content"] for m in messages if m["role"] == "tool"]
    context = "\n".join(context_pieces)

    return {
        "answer": model_message["content"],
        "context": context,
        "search_iterations": search_iterations,
    }


async def stream_agent(
    max_iterations: int,
    messages: list,
    base_url: str,
    api_key: str,
    model: str,
) -> AsyncIterator[dict]:
    """Run ReAct while exposing only final-answer content to the caller."""
    search_iterations = 0

    for _ in range(max_iterations):
        final_message = None
        async for event in stream_reason(messages, base_url, api_key, model):
            if event["type"] == "content":
                yield {"type": "token", "text": event["text"]}
            else:
                final_message = event["message"]

        if not final_message.get("tool_calls"):
            context = "\n".join(m["content"] for m in messages if m["role"] == "tool")
            yield {
                "type": "complete",
                "answer": final_message["content"],
                "context": context,
                "search_iterations": search_iterations,
            }
            return

        tool_call = final_message["tool_calls"][0]
        search_iterations += 1
        result = await act(tool_call)
        messages = observe_step(messages, final_message, result)

    final_message = None
    async for event in stream_reason(messages, base_url, api_key, model, force_final=True):
        if event["type"] == "content":
            yield {"type": "token", "text": event["text"]}
        else:
            final_message = event["message"]

    yield {
        "type": "complete",
        "answer": final_message["content"] if final_message else "",
        "context": "\n".join(m["content"] for m in messages if m["role"] == "tool"),
        "search_iterations": search_iterations,
    }

@langfuse_observe(as_type="generation")
async def reflect(question: str, context: str, answer: str, history: list[dict], base_url: str, api_key: str, model: str) -> dict:
    """
    Judge whether the draft answer fully and accurately addresses the
    question, using only the retrieved context. No tools — just a
    structured verdict.
    """
    conversation = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in history[-6:]
    ) or "(no previous conversation)"

    prompt = f"""You are reviewing a draft answer before it's shown to the user.

Original question: {question}

Previous conversation:
{conversation}

Retrieved documentation used to answer it:
{context}

Draft answer:
{answer}

Check whether the draft fully and accurately addresses every part of the question. For a new documentation question, use only the retrieved documentation above. For a follow-up request for more detail or code, the previous conversation is also valid grounding: preserve and extend the previously established answer instead of rejecting its model names or code merely because they are not repeated in the latest retrieval.
Look specifically for: missing sub-questions, claims not supported by the available documentation or prior answer, or confusion between similar terms (e.g. a pricing tier name mistaken for an actual model name).
Pay close attention to any model, plan, or product name mentioned in the draft answer — if that exact name does not clearly and unambiguously appear as a distinct entity in the retrieved documentation (for example, it could be a quota label, a plan tier, or a typo/variant of a real model name), flag it as a potential naming issue rather than assuming it's correct.

This is a strict gate, not a general quality opinion. Return sufficient=false when the context is empty, irrelevant, or does not directly support an answer to a new AI Grid documentation question. Greetings, thanks, small talk, and follow-up requests for more detail or code about the immediately preceding AI Grid discussion may use that conversation context without a new retrieval; mark them sufficient when the draft naturally continues the discussion and does not introduce unsupported claims. Questions about how the assistant can help also do not require retrieved documentation. Do not use general world knowledge to approve an answer. Questions about weather, sports, cooking, or other non-AI-Grid topics must be marked insufficient.

Respond with only a JSON object in this exact shape, no other text:
{{"sufficient": true or false, "missing": "description of what's missing or wrong, or empty string if sufficient"}}"""

    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=config.timeouts.http_seconds
        )

    response.raise_for_status()
    response_data = response.json()
    _update_generation_usage(model, response_data.get("usage"))
    verdict_text = response_data["choices"][0]["message"]["content"]
    print(f"[reflect debug] raw content: {repr(verdict_text)}")
    
    verdict_text = verdict_text.strip()
    if verdict_text.startswith("```"):
        verdict_text = verdict_text.strip("`")
        verdict_text = verdict_text.removeprefix("json").strip()

    return json.loads(verdict_text)


async def _check_answer_quality(
    question: str, context: str, answer: str, history: list[dict],
    base_url: str, api_key: str, model: str,
) -> None:
    """Run reflect() after a streamed answer has already been sent.
    Purely observational - logs to console and Langfuse, never changes
    what the user already saw.
    """
    try:
        verdict = await reflect(question, context, answer, history, base_url, api_key, model)
        if _contains_deprecated_model_name(answer):
            print("[streaming reflection] deterministic backstop caught deprecated model name")
        elif not verdict.get("sufficient"):
            print(f"[streaming reflection] insufficient: {verdict.get('missing', '')}")
    except Exception as e:
        print(f"[streaming reflection] failed: {e}")


def _validated_answer(answer: str, verdict: dict) -> str:
    if verdict.get("sufficient"):
        return answer

    return "I do not have enough information in the official AI Grid documentation to answer that question accurately."


def _is_model_catalog_question(question: str) -> bool:
    normalized = question.lower()
    catalog_phrases = (
        "which models are available",
        "which models do you support",
        "what models are available",
        "available models",
        "models are available",
        "supported models",
        "models are supported",
        "list of models",
        "model catalog",
    )
    return any(phrase in normalized for phrase in catalog_phrases)


def _format_available_models(raw_models: str) -> str:
    models = json.loads(raw_models)
    lines = ["Available AI Grid models:", ""]
    lines.extend(f"- {model['id']}" for model in models if model.get("id"))
    return "\n".join(lines)


def _is_obviously_off_topic(question: str) -> bool:
    normalized = question.lower()
    return any(term in normalized for term in (
        "weather", "forecast", "sports", "football", "soccer", "basketball",
        "recipe", "cooking", "restaurant",
    ))


@langfuse_observe()
async def chat_with_agent(question: str, session_id: int) -> str:
    """
    Entry point used by the API: loads conversation history, runs the
    ReAct loop, then persists the new exchange to Postgres.
    """

    api_key = os.getenv("AI_GRID_API_KEY")
    base_url = os.getenv("AI_GRID_BASE_URL")
    model = os.getenv("DEFAULT_MODEL_LABEL")

    if _is_model_catalog_question(question):
        answer = _format_available_models(await list_available_models())
        await save_message(session_id, "user", question)
        await save_message(session_id, "assistant", answer)
        return answer

    history = await get_messages(session_id)
    with open(config.agent.system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    messages = [
        {"role": "system", "content": system_prompt},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    results = await run_agent(
        max_iterations=config.agent.max_iterations,
        messages=messages,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )

    answer = results["answer"]
    context = results["context"]

    verdict = await reflect(question, context, answer, history, base_url, api_key, model)
    if not verdict.get("sufficient") or _contains_deprecated_model_name(answer):
        print(f"[reflection] insufficient: {verdict.get('missing', '')}")
        answer = _validated_answer(answer, {"sufficient": False})

    await save_message(session_id, "user", question)
    await save_message(session_id, "assistant", answer)

    return answer


@langfuse_observe()
async def stream_chat_with_agent(question: str, session_id: int) -> AsyncIterator[str]:
    """Stream the final answer and persist the completed exchange afterward."""
    api_key = os.getenv("AI_GRID_API_KEY")
    base_url = os.getenv("AI_GRID_BASE_URL")
    model = os.getenv("DEFAULT_MODEL_LABEL")

    if _is_model_catalog_question(question):
        answer = _format_available_models(await list_available_models())
        yield answer
        await save_message(session_id, "user", question)
        await save_message(session_id, "assistant", answer)
        return

    if _is_obviously_off_topic(question):
        answer = _validated_answer("", {"sufficient": False})
        yield answer
        await save_message(session_id, "user", question)
        await save_message(session_id, "assistant", answer)
        return

    history = await get_messages(session_id)
    with open(config.agent.system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": question},
    ]

    answer_parts = []
    completed = None
    async for event in stream_agent(config.agent.max_iterations, messages, base_url, api_key, model):
        if event["type"] == "token":
            answer_parts.append(event["text"])
        else:
            completed = event

    answer = "".join(answer_parts)
    if not answer and completed:
        answer = completed["answer"]

    context = completed["context"] if completed else ""

    search_iterations = completed.get("search_iterations", 0) if completed else 0
    if search_iterations > 0:
        verdict = await reflect(question, context, answer, history, base_url, api_key, model)
        if not verdict.get("sufficient") or _contains_deprecated_model_name(answer):
            answer = _validated_answer(answer, {"sufficient": False})
        yield answer
    else:
        yield answer
        task = asyncio.create_task(
            _check_answer_quality(question, context, answer, history, base_url, api_key, model)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    await save_message(session_id, "user", question)
    await save_message(session_id, "assistant", answer)