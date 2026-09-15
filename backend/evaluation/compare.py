"""Final 30-question Classical RAG versus Agentic RAG experiment.

This evaluation holds constant the exact questions, documentation corpus, Qdrant
collection, embedding implementation/model, chat model, scorer, execution
machine, and API environment. Network conditions, hosted API load, model
variability, and background local load are not isolated. Results are descriptive
engineering observations, not a controlled scientific benchmark.

Latency starts immediately before retrieval/generation work and stops after the
final answer decision. The Agentic path runs the existing ReAct and reflection
workload without production PostgreSQL session/history/persistence overhead.
TTFT is not measured because neither compared path has an equivalent streaming
implementation.
"""

import asyncio
import csv
import json
import math
import os
import statistics
import time
from pathlib import Path

import backend.core.agent as agent_module
from backend.evaluation.baseline import naive_rag_answer
from backend.evaluation.run import RUNS_PER_QUESTION, score_answer


RESULTS_DIR = Path(__file__).resolve().parent
RAW_CSV_PATH = RESULTS_DIR / "comparison_runs.csv"
CSV_PATH = RESULTS_DIR / "comparison_results.csv"
MARKDOWN_PATH = RESULTS_DIR / "comparison_results.md"

FINAL_TEST_CASES = [
    {"question_id": "Q01", "category": "Simple documentation retrieval", "question": "What is AIGrid's API base URL for OpenAI-compatible requests?", "expected_facts": ["https://app.ai-grid.io/v1", "OpenAI-compatible"]},
    {"question_id": "Q02", "category": "Simple documentation retrieval", "question": "Which authentication method does AIGrid use for API requests?", "expected_facts": ["Bearer", "API key"]},
    {"question_id": "Q03", "category": "Simple documentation retrieval", "question": "What endpoint is used for chat completions on AIGrid?", "expected_facts": ["/v1/chat/completions"]},
    {"question_id": "Q04", "category": "Simple documentation retrieval", "question": "What endpoint is used to generate embeddings on AIGrid?", "expected_facts": ["/v1/embeddings"]},
    {"question_id": "Q05", "category": "Simple documentation retrieval", "question": "What does AIGrid recommend for browser applications instead of calling the inference API directly?", "expected_facts": [("backend", "server-side"), "API key"]},
    {"question_id": "Q06", "category": "Simple documentation retrieval", "question": "What model identifier should be used for google/gemma-4-31B?", "expected_facts": ["google/gemma-4-31B"]},
    {"question_id": "Q07", "category": "Simple documentation retrieval", "question": "What is the throughput listed for google/gemma-4-31B?", "expected_facts": ["580 tokens/sec"]},
    {"question_id": "Q08", "category": "Simple documentation retrieval", "question": "What is the input price listed for google/gemma-4-31B?", "expected_facts": ["73 DA / 1M tokens"]},
    {"question_id": "Q09", "category": "Model-specific questions", "question": "What is Qwen3-30B-A3B-Thinking designed to be good at?", "expected_facts": ["Reasoning", ("planning", "analysis")]},
    {"question_id": "Q10", "category": "Model-specific questions", "question": "What is the throughput of Qwen3-30B-A3B-Thinking?", "expected_facts": ["660 tokens/sec"]},
    {"question_id": "Q11", "category": "Model-specific questions", "question": "What are the input and output prices of Qwen3-30B-A3B-Thinking?", "expected_facts": ["73 DA / 1M tokens", "148 DA / 1M tokens"]},
    {"question_id": "Q12", "category": "Model-specific questions", "question": "Does Qwen3-30B-A3B-Thinking support tools and coding?", "expected_facts": ["Tools", "Code"]},
    {"question_id": "Q13", "category": "Model-specific questions", "question": "What is Qwen/Qwen3.8-27B intended for?", "expected_facts": ["assistants", "analysis", ("code", "coding")]},
    {"question_id": "Q14", "category": "Model-specific questions", "question": "Does Qwen/Qwen3.8-27B have published throughput information?", "expected_facts": ["No throughput info"]},
    {"question_id": "Q15", "category": "Cross-model comparison", "question": "Compare google/gemma-4-31B and Qwen3-30B-A3B-Thinking for coding and tool use. Which capabilities are documented for each?", "expected_facts": ["google/gemma-4-31B", "Qwen3-30B-A3B-Thinking", "Tools", "Code"]},
    {"question_id": "Q16", "category": "Cross-model comparison", "question": "Which is faster according to the documented throughput: google/gemma-4-31B or Qwen3-30B-A3B-Thinking?", "expected_facts": ["580 tokens/sec", "660 tokens/sec", "Qwen3-30B-A3B-Thinking"]},
    {"question_id": "Q17", "category": "Cross-model comparison", "question": "Compare the input and output prices of google/gemma-4-31B and Qwen3-30B-A3B-Thinking.", "expected_facts": ["google/gemma-4-31B", "Qwen3-30B-A3B-Thinking", "73 DA / 1M tokens", "148 DA / 1M tokens"]},
    {"question_id": "Q18", "category": "Cross-model comparison", "question": "For a coding assistant that needs reasoning and tool use, what differences are documented between google/gemma-4-31B and Qwen3-30B-A3B-Thinking?", "expected_facts": ["google/gemma-4-31B", "Qwen3-30B-A3B-Thinking", "Tools", "Code", "Reasoning"]},
    {"question_id": "Q19", "category": "API / workflow questions", "question": "How do I send a basic chat-completion request to AIGrid using raw HTTP?", "expected_facts": ["/v1/chat/completions", "Authorization: Bearer", "model", "messages"]},
    {"question_id": "Q20", "category": "API / workflow questions", "question": "How do I request streaming responses from the AIGrid chat-completions endpoint?", "expected_facts": ["/v1/chat/completions", "stream", ("streaming response", "streamed response", "SSE")]},
    {"question_id": "Q21", "category": "API / workflow questions", "question": "What three things does the AIGrid quickstart say are required before making a model request?", "expected_facts": ["endpoint", "model id", ("instance key", "API key")]},
    {"question_id": "Q22", "category": "API / workflow questions", "question": "What is the recommended architecture for keeping AIGrid API keys out of a browser application?", "expected_facts": [("backend", "server-side"), ("not be exposed", "proxy backend", "client-side") ]},
    {"question_id": "Q23", "category": "Embeddings / retrieval", "question": "What is Alibaba-NLP/gte-Qwen2-7B-instruct used for on AIGrid?", "expected_facts": ["Embeddings", "semantic search"]},
    {"question_id": "Q24", "category": "Embeddings / retrieval", "question": "What kinds of workflows does AIGrid recommend embeddings for?", "expected_facts": ["semantic search", ("document retrieval", "retrieval"), "clustering"]},
    {"question_id": "Q25", "category": "Embeddings / retrieval", "question": "What is the difference between the AIGrid embeddings endpoint and the chat-completions endpoint?", "expected_facts": ["/v1/embeddings", "/v1/chat/completions", ("embeddings", "vector representation"), ("chat", "generation")]},
    {"question_id": "Q26", "category": "Agentic / multi-step synthesis", "question": "A developer wants to build an AIGrid documentation assistant that can answer both documentation questions and current model-availability questions. What API capabilities would be relevant?", "expected_facts": [("documentation", "retrieval"), ("/models", "model catalog"), "chat completions"]},
    {"question_id": "Q27", "category": "Agentic / multi-step synthesis", "question": "A developer wants an assistant that can retrieve documentation, choose tools dynamically, and handle multi-step questions. Which AIGrid capabilities and API patterns are relevant?", "expected_facts": ["documentation retrieval", "tool calling", "chat completions", ("iterative", "agent workflow", "multi-step reasoning")]},
    {"question_id": "Q28", "category": "Agentic / multi-step synthesis", "question": "How would you combine AIGrid's embeddings API, vector retrieval, and chat-completions API to build a documentation RAG assistant?", "expected_facts": ["embeddings", ("vector retrieval", "semantic search", "retrieval"), "/v1/embeddings", "/v1/chat/completions", ("retrieved context", "context used", "documentation context")]},
    {"question_id": "Q29", "category": "Unsupported / robustness", "question": "Does the AIGrid documentation provide a current weather forecast for Algiers?", "expected_facts": [("not enough information", "do not have enough information", "does not provide", "does not contain", "cannot answer", "unsupported")], "forbidden_facts": ["sunny", "rain", "temperature", "°C"]},
    {"question_id": "Q30", "category": "Unsupported / robustness", "question": "What is the exact throughput of a model that is not documented in the AIGrid model library?", "expected_facts": [("not enough information", "does not contain", "cannot answer", "cannot provide", "unsupported")], "forbidden_facts": ["tokens/sec", "tokens per second"]},
]

RAW_FIELDS = [
    "system", "question_id", "category", "question", "run_number", "status", "error",
    "answer", "latency_seconds", "llm_calls", "document_retrieval_calls",
    "other_tool_calls", "total_tool_calls", "reasoning_turns", "input_tokens",
    "output_tokens", "total_tokens", "token_usage_complete", "retrieved_document_chars",
    "tool_observation_chars", "fact_hits", "fact_hit_count", "expected_fact_count",
    "expected_facts", "forbidden_fact_violations", "forbidden_facts",
    "reflection_rejected", "deprecated_model_name", "unsupported_response_trigger",
]


def _usage_totals(usage: dict | None) -> tuple[int | None, int | None, int | None]:
    if not usage:
        return None, None, None
    return (usage.get("prompt_tokens", usage.get("input")), usage.get("completion_tokens", usage.get("output")), usage.get("total_tokens", usage.get("total")))


def _fresh_agent_messages(question: str) -> list[dict]:
    with open(agent_module.config.agent.system_prompt_path, "r", encoding="utf-8") as prompt_file:
        system_prompt = prompt_file.read()
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]


async def _run_agentic_answer(question: str) -> dict:
    reason_calls = 0
    reflect_calls = 0
    reflect_rejected = False
    usage_records = []
    document_contexts = []
    other_tool_outputs = []
    original_reason = agent_module.reason
    original_reflect = agent_module.reflect
    original_update_usage = agent_module._update_generation_usage
    original_tools = agent_module.AVAILABLE_TOOLS.copy()

    async def counted_reason(*args, **kwargs):
        nonlocal reason_calls
        reason_calls += 1
        return await original_reason(*args, **kwargs)

    async def counted_reflect(*args, **kwargs):
        nonlocal reflect_calls, reflect_rejected
        reflect_calls += 1
        verdict = await original_reflect(*args, **kwargs)
        reflect_rejected = reflect_rejected or not verdict.get("sufficient")
        return verdict

    async def counted_search_documents(*args, **kwargs):
        result = await original_tools["search_documents"](*args, **kwargs)
        document_contexts.append(result)
        return result

    async def counted_list_available_models(*args, **kwargs):
        result = await original_tools["list_available_models"](*args, **kwargs)
        other_tool_outputs.append(result)
        return result

    def counted_update_usage(model, usage):
        usage_records.append(_usage_totals(usage))
        original_update_usage(model, usage)

    agent_module.reason = counted_reason
    agent_module.reflect = counted_reflect
    agent_module._update_generation_usage = counted_update_usage
    agent_module.AVAILABLE_TOOLS = {"search_documents": counted_search_documents, "list_available_models": counted_list_available_models}
    started_at = time.perf_counter()
    try:
        results = await agent_module.run_agent(agent_module.config.agent.max_iterations, _fresh_agent_messages(question), os.getenv("AI_GRID_BASE_URL"), os.getenv("AI_GRID_API_KEY"), os.getenv("DEFAULT_MODEL_LABEL"))
        raw_answer = results["answer"]
        verdict = await agent_module.reflect(question, results["context"], raw_answer, [], os.getenv("AI_GRID_BASE_URL"), os.getenv("AI_GRID_API_KEY"), os.getenv("DEFAULT_MODEL_LABEL"))
        deprecated = agent_module._contains_deprecated_model_name(raw_answer)
        answer = raw_answer if verdict.get("sufficient") and not deprecated else agent_module._validated_answer(raw_answer, {"sufficient": False})
    finally:
        agent_module.reason = original_reason
        agent_module.reflect = original_reflect
        agent_module._update_generation_usage = original_update_usage
        agent_module.AVAILABLE_TOOLS = original_tools

    usage_complete = len(usage_records) == reason_calls + reflect_calls and all(value is not None for record in usage_records for value in record)
    return {
        "answer": answer,
        "latency_seconds": time.perf_counter() - started_at,
        "llm_calls": reason_calls + reflect_calls,
        "document_retrieval_calls": len(document_contexts),
        "other_tool_calls": len(other_tool_outputs),
        "total_tool_calls": len(document_contexts) + len(other_tool_outputs),
        "reasoning_turns": reason_calls,
        "input_tokens": sum(record[0] for record in usage_records) if usage_complete else None,
        "output_tokens": sum(record[1] for record in usage_records) if usage_complete else None,
        "total_tokens": sum(record[2] for record in usage_records) if usage_complete else None,
        "usage_complete": usage_complete,
        "retrieved_document_chars": sum(len(context) for context in document_contexts),
        "tool_observation_chars": len(results["context"]),
        "reflection_rejected": reflect_rejected,
        "deprecated_model_name": deprecated,
    }


def _fact_label(fact) -> str:
    return fact[0] if isinstance(fact, (tuple, list)) else fact


def _failed_result(error: Exception) -> dict:
    return {"answer": "", "latency_seconds": None, "llm_calls": None, "document_retrieval_calls": None, "other_tool_calls": None, "total_tool_calls": None, "reasoning_turns": None, "input_tokens": None, "output_tokens": None, "total_tokens": None, "usage_complete": False, "retrieved_document_chars": None, "tool_observation_chars": None, "reflection_rejected": None, "deprecated_model_name": None, "error": f"{type(error).__name__}: {error}"}


def _raw_row(case: dict, system: str, run_number: int, result: dict, status: str = "completed") -> dict:
    answer = result.get("answer", "")
    scores = score_answer(answer, case["expected_facts"], case.get("forbidden_facts", []))
    labels = [_fact_label(fact) for fact in case["expected_facts"]]
    fact_hits = {label: bool(scores[label]) for label in labels}
    answer_lower = answer.lower()
    forbidden_count = sum(answer_lower.count(fact.lower()) for fact in case.get("forbidden_facts", []))
    deprecated = result.get("deprecated_model_name")
    if status == "completed":
        deprecated = bool(deprecated or agent_module._contains_deprecated_model_name(answer))
    reflection_rejected = result.get("reflection_rejected")
    trigger = (reflection_rejected or deprecated) if status == "completed" else None
    return {
        "system": system, "question_id": case["question_id"], "category": case["category"], "question": case["question"], "run_number": run_number, "status": status, "error": result.get("error", ""), "answer": answer,
        "latency_seconds": result.get("latency_seconds"), "llm_calls": result.get("llm_calls"), "document_retrieval_calls": result.get("document_retrieval_calls"), "other_tool_calls": result.get("other_tool_calls"), "total_tool_calls": result.get("total_tool_calls"), "reasoning_turns": result.get("reasoning_turns"), "input_tokens": result.get("input_tokens"), "output_tokens": result.get("output_tokens"), "total_tokens": result.get("total_tokens"), "token_usage_complete": result.get("usage_complete", False), "retrieved_document_chars": result.get("retrieved_document_chars"), "tool_observation_chars": result.get("tool_observation_chars"), "fact_hits": json.dumps(fact_hits, sort_keys=True), "fact_hit_count": sum(fact_hits.values()), "expected_fact_count": len(labels), "expected_facts": json.dumps(labels), "forbidden_fact_violations": forbidden_count, "forbidden_facts": json.dumps(case.get("forbidden_facts", [])), "reflection_rejected": reflection_rejected, "deprecated_model_name": deprecated, "unsupported_response_trigger": trigger,
    }


async def _collect_raw_rows() -> list[dict]:
    rows = []
    for case in FINAL_TEST_CASES:
        for system, function in (("Classical RAG", naive_rag_answer), ("Agentic RAG", _run_agentic_answer)):
            for run_number in range(1, RUNS_PER_QUESTION + 1):
                try:
                    result = await function(case["question"])
                    status = "completed"
                except Exception as error:
                    result = _failed_result(error)
                    status = "failed"
                print(f"\n=== {case['question_id']} | {system} | run {run_number}")
                print(f"[answer] {result.get('answer', '')}\n" if status == "completed" else f"[failure] {result['error']}\n")
                rows.append(_raw_row(case, system, run_number, result, status))
    return rows


def _write_raw_rows(rows: list[dict]) -> None:
    with RAW_CSV_PATH.open("w", newline="", encoding="utf-8") as raw_file:
        writer = csv.DictWriter(raw_file, fieldnames=RAW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _successful(rows: list[dict], system: str, key: str) -> list[float]:
    return [float(row[key]) for row in rows if row["system"] == system and row["status"] == "completed" and row[key] not in (None, "")]


def _percentile(values: list[float], percentile: float) -> float:
    return sorted(values)[max(0, math.ceil(percentile * len(values)) - 1)]


def _stats(rows: list[dict], system: str, key: str) -> dict | None:
    values = _successful(rows, system, key)
    if not values:
        return None
    return {"n": len(values), "mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values), "std": statistics.pstdev(values), "p95": _percentile(values, 0.95)}


def _format_stats(stats: dict | None, decimals: int = 3) -> str:
    if stats is None:
        return "Not measured — no completed observations"
    return "; ".join(f"{key}={stats[key]:.{decimals}f}" if key != "n" else f"n={stats[key]}" for key in ("n", "mean", "median", "min", "max", "std", "p95"))


def _difference(baseline: dict | None, agentic: dict | None, decimals: int = 3) -> str:
    if baseline is None or agentic is None:
        return "N/A"
    return "; ".join(f"{key}={agentic[key] - baseline[key]:+.{decimals}f}" for key in ("mean", "median", "min", "max", "std", "p95"))


def _fact_rate(rows: list[dict], system: str, question_ids: set[str] | None = None) -> tuple[int, int, float]:
    selected = [row for row in rows if row["system"] == system and row["status"] == "completed" and (question_ids is None or row["question_id"] in question_ids)]
    hits = sum(int(row["fact_hit_count"]) for row in selected)
    total = sum(int(row["expected_fact_count"]) for row in selected)
    return hits, total, hits / total if total else 0.0


def _multi_step_ids(rows: list[dict]) -> tuple[set[str], set[str]]:
    agentic = [row for row in rows if row["system"] == "Agentic RAG" and row["status"] == "completed"]
    ids = {row["question_id"] for row in agentic}
    multi = {question_id for question_id in ids if statistics.mean(int(row["document_retrieval_calls"]) for row in agentic if row["question_id"] == question_id) > 1}
    return multi, ids - multi


def _metric_rows(rows: list[dict]) -> list[tuple[str, str, str, str]]:
    metrics = []
    def add(label, key, decimals=3):
        baseline = _stats(rows, "Classical RAG", key)
        agentic = _stats(rows, "Agentic RAG", key)
        metrics.append((label, _format_stats(baseline, decimals), _format_stats(agentic, decimals), _difference(baseline, agentic, decimals)))
    add("Latency seconds/query (mean, median, min, max, std, P95)", "latency_seconds")
    metrics.append(("Time to first token", "Not measured — requires streaming Classical and Agentic implementations", "Not measured — requires streaming Classical and Agentic implementations", "N/A"))
    add("Chat-completion calls/query", "llm_calls")
    add("Document retrieval calls/query", "document_retrieval_calls")
    add("Other tool calls/query", "other_tool_calls")
    add("Total tool invocations/query", "total_tool_calls")
    reasoning = _stats(rows, "Agentic RAG", "reasoning_turns")
    metrics.append(("Agent reasoning turns/query", "N/A — Classical RAG has no agent loop", _format_stats(reasoning), "N/A"))
    add("Input tokens/query", "input_tokens", 0)
    add("Output tokens/query", "output_tokens", 0)
    add("Total tokens/query", "total_tokens", 0)
    add("Retrieved document characters/query", "retrieved_document_chars")
    multi, single = _multi_step_ids(rows)
    for label, ids in (("Multi-step expected-fact hit rate", multi), ("Single-step expected-fact hit rate", single), ("Expected-fact hit rate", None)):
        b_hits, b_total, b_rate = _fact_rate(rows, "Classical RAG", ids)
        a_hits, a_total, a_rate = _fact_rate(rows, "Agentic RAG", ids)
        metrics.append((label, f"{b_hits}/{b_total} ({b_rate:.3f})", f"{a_hits}/{a_total} ({a_rate:.3f})", f"{a_rate - b_rate:+.3f}"))
    add("Unsupported-response triggers/query", "unsupported_response_trigger")
    add("Forbidden-fact violations/query", "forbidden_fact_violations")
    return metrics


def _category_rows(rows: list[dict]) -> list[tuple[str, str, str, str]]:
    categories = []
    for category in dict.fromkeys(case["category"] for case in FINAL_TEST_CASES):
        ids = {case["question_id"] for case in FINAL_TEST_CASES if case["category"] == category}
        b_hits, b_total, b_rate = _fact_rate(rows, "Classical RAG", ids)
        a_hits, a_total, a_rate = _fact_rate(rows, "Agentic RAG", ids)
        categories.append((category, f"{b_hits}/{b_total} ({b_rate:.3f})", f"{a_hits}/{a_total} ({a_rate:.3f})", f"{a_rate - b_rate:+.3f}"))
    return categories


def _write_reports(rows: list[dict]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["Metric", "Classical RAG Baseline", "Agentic RAG", "Difference"])
        writer.writerows(_metric_rows(rows))

    multi, single = _multi_step_ids(rows)
    lines = [
        "# Classical RAG vs Agentic RAG: 30-Question Benchmark",
        "",
        "## Objective",
        "",
        "This descriptive engineering experiment compares the Classical RAG retrieve-once + generate-once reference implementation with the Agentic RAG ReAct, named-tool, iterative-retrieval, and reflection workload. It measures capability/flexibility against observed latency, token, tool, and chat-completion overhead; it does not claim universal superiority.",
        "",
        "## Dataset and Protocol",
        "",
        "The fixed dataset contains exactly 30 questions: 8 simple documentation retrieval, 6 model-specific, 4 cross-model comparison, 4 API/workflow, 3 embeddings/retrieval, 3 agentic/multi-step synthesis, and 2 unsupported/robustness questions. Each system runs every question three times: 30 x 3 x 2 = 180 planned runs and 180 expected raw rows.",
        "",
        "Held constant: exact question text, current ingested documentation corpus, Qdrant collection, embedding implementation/model, chat model, scorer, execution machine, and API environment. Not controlled: network conditions, remote API load, hosted model variability, and background local system load. The same evaluation-only latency boundary excludes PostgreSQL session/history/persistence overhead and includes retrieval, reasoning, generation, and Agentic reflection.",
        "",
        "## Aggregate Results",
        "",
        "| Metric | Classical RAG Baseline | Agentic RAG | Difference |",
        "| ------ | ---------------------: | ----------: | ---------: |",
    ]
    lines.extend(f"| {metric} | {baseline} | {agentic} | {difference} |" for metric, baseline, agentic, difference in _metric_rows(rows))
    lines.extend(["", "## Category-Level Results", "", "| Category | Classical RAG | Agentic RAG | Difference |", "| --- | ---: | ---: | ---: |"])
    lines.extend(f"| {category} | {baseline} | {agentic} | {difference} |" for category, baseline, agentic, difference in _category_rows(rows))
    lines.extend([
        "",
        "## Metric Definitions and Limitations",
        "",
        "- Chat-completion calls count the baseline completion and actual Agentic `reason()` plus `reflect()` calls. Embedding calls are excluded. Failed runs are recorded and excluded from completed-observation statistics.",
        "- Document retrieval calls count actual `search_documents()` invocations; other tool calls count actual `list_available_models()` invocations; total tool invocations is their sum.",
        "- Agent reasoning turns are actual `reason()` calls, including the final non-tool turn. Classical RAG has no agent loop, so it is N/A.",
        "- Token counts use only API usage fields. Missing usage is never estimated; incomplete runs are marked and excluded from token aggregates.",
        "- Retrieved document characters are measured from the strings returned by `search_documents()`. Agentic serialized tool-observation characters are retained separately in the raw CSV and are not treated as equivalent context.",
        "- Expected-fact hit rate uses unchanged `score_answer()` substring matching and reports explicit fact/run denominators. Unsupported-response triggers mean reflection rejection or deprecated-model detection; they are not a semantic hallucination metric.",
        "- TTFT is not measured because a fair comparison requires streaming implementations for both systems.",
        "",
        "## Multi-Step Analysis",
        "",
        f"A case is multi-step only when its observed average `search_documents()` count across three Agentic runs exceeds 1. This run classified {len(multi)} multi-step case(s) ({', '.join(sorted(multi)) or 'none'}) and {len(single)} single-step case(s). Multi-step and single-step expected-fact results are reported in the aggregate table with denominators.",
        "",
        "## Per-Case Results",
        "",
        "| Question | Category | System | Expected-fact hit rate | Retrieval calls mean | Latency mean (s) | Total tokens mean | Status |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for case in FINAL_TEST_CASES:
        for system in ("Classical RAG", "Agentic RAG"):
            selected = [row for row in rows if row["question_id"] == case["question_id"] and row["system"] == system]
            completed = [row for row in selected if row["status"] == "completed"]
            hits, total, rate = _fact_rate(completed, system)
            retrieval = statistics.mean(int(row["document_retrieval_calls"]) for row in completed) if completed else None
            latency = statistics.mean(float(row["latency_seconds"]) for row in completed) if completed else None
            tokens = [int(row["total_tokens"]) for row in completed if row["total_tokens"] not in (None, "")]
            lines.append(f"| {case['question_id']} | {case['category']} | {system} | {hits}/{total} ({rate:.3f}) | {retrieval if retrieval is not None else 'N/A'} | {latency:.3f} | {statistics.mean(tokens):.0f} | {len(completed)}/{len(selected)} completed |" if completed else f"| {case['question_id']} | {case['category']} | {system} | 0/0 (N/A) | N/A | N/A | N/A | 0/{len(selected)} completed |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "The result is an efficiency/capability trade-off under this configuration. Agentic RAG adds iterative tool-based orchestration and reflection, while Classical RAG uses one retrieval and one generation call. Similar expected-fact performance should be reported as such; this small live experiment cannot establish a general quality advantage, production superiority, or broad statistical generalization.",
        "",
        "## Recommended Future Experiment",
        "",
        "Use a larger fixed dataset, retain raw per-run answers and metrics, record corpus/model versions, control concurrency and network conditions where possible, and implement equivalent streaming paths before measuring TTFT.",
    ])
    MARKDOWN_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    rows = await _collect_raw_rows()
    _write_raw_rows(rows)
    _write_reports(rows)
    print("\n=== FINAL 30-QUESTION COMPARISON ===")
    for metric, baseline, agentic, difference in _metric_rows(rows):
        print(f"{metric} | {baseline} | {agentic} | {difference}")


if __name__ == "__main__":
    asyncio.run(main())
