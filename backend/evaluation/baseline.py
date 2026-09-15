import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from backend.config.loader import load_config
from backend.infrastructure.embeddings import get_embeddings
from backend.infrastructure.vector_store import client


load_dotenv()

config = load_config(str(Path(__file__).resolve().parents[1] / "config" / "config.yaml"))


async def naive_rag_answer(question: str) -> dict:
    """Answer one question with a single retrieve-then-generate pass."""
    started_at = time.perf_counter()

    question_vector = await get_embeddings(question)
    results = client.query_points(
        collection_name=config.retrieval.collection_name,
        query=question_vector,
        limit=config.retrieval.top_k,
    )

    context = "\n".join(
        f'{point.payload["text"]} (Source: {point.payload["url"]})'
        for point in results.points
    )

    with open(config.agent.system_prompt_path, "r", encoding="utf-8") as prompt_file:
        system_prompt = prompt_file.read()

    user_prompt = f"""Retrieved documentation:
{context}

Question:
{question}

Answer using only the retrieved documentation. If the documentation does not contain enough information, say so clearly and do not guess."""

    api_key = os.getenv("AI_GRID_API_KEY")
    base_url = os.getenv("AI_GRID_BASE_URL")
    model = os.getenv("DEFAULT_MODEL_LABEL")

    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": config.agent.temperature,
            },
            timeout=config.timeouts.http_seconds,
        )
    response.raise_for_status()
    response_data = response.json()
    usage = response_data.get("usage") or {}
    input_tokens = usage.get("prompt_tokens", usage.get("input"))
    output_tokens = usage.get("completion_tokens", usage.get("output"))
    total_tokens = usage.get("total_tokens", usage.get("total"))
    answer = response_data["choices"][0]["message"]["content"]

    return {
        "answer": answer,
        "llm_calls": 1,
        "latency_seconds": time.perf_counter() - started_at,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "context_chars": len(context),
        "retrieval_calls": 1,
        "document_retrieval_calls": 1,
        "other_tool_calls": 0,
        "total_tool_calls": 1,
        "search_iterations": 1,
        "reasoning_turns": None,
        "reflection_rejected": False,
        "deprecated_model_name": False,
        "usage_complete": all(value is not None for value in (
            input_tokens,
            output_tokens,
            total_tokens,
        )),
        "retrieved_document_chars": len(context),
        "tool_observation_chars": None,
    }