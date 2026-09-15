"""Descriptive comparison of a Classical RAG baseline and Agentic RAG.

The experiment holds constant the TEST_CASES, ingested corpus, Qdrant
collection, embedding implementation/model, chat model, scoring function,
execution machine, and API environment. It does not control network
conditions, remote API load, hosted model variability, or background local
system load. Runs are sequential live observations, not an isolated benchmark.

The Classical RAG implementation is a retrieve-once, generate-once reference
architecture. The Agentic RAG evaluation path reproduces the existing
run_agent() plus reflect() workload for a fresh question without invoking the
production chat entry point's PostgreSQL session/history/persistence work.
This keeps the latency boundary equivalent: the timer starts immediately
before retrieval/generation work and stops after the final answer decision.

TTFT is not measured. Both compared paths are blocking/non-streaming; a fair
measurement requires streaming implementations for both systems.
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
from backend.evaluation.run import RUNS_PER_QUESTION, TEST_CASES, score_answer


RESULTS_DIR = Path(__file__).resolve().parent
RAW_CSV_PATH = RESULTS_DIR / "comparison_runs.csv"
CSV_PATH = RESULTS_DIR / "comparison_results.csv"
MARKDOWN_PATH = RESULTS_DIR / "comparison_results.md"


def _usage_totals(usage: dict | None) -> tuple[int | None, int | None, int | None]:
    if not usage:
        return None, None, None
    return (
        usage.get("prompt_tokens", usage.get("input")),
        usage.get("completion_tokens", usage.get("output")),
        usage.get("total_tokens", usage.get("total")),
    )


def _fresh_agent_messages(question: str) -> list[dict]:
    with open(agent_module.config.agent.system_prompt_path, "r", encoding="utf-8") as prompt_file:
        system_prompt = prompt_file.read()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]


async def _run_agentic_answer(question: str) -> dict:
    """Run the production ReAct/reflection workload without database overhead."""
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
    agent_module.AVAILABLE_TOOLS = {
        "search_documents": counted_search_documents,
        "list_available_models": counted_list_available_models,
    }

    started_at = time.perf_counter()
    try:
        messages = _fresh_agent_messages(question)
        results = await agent_module.run_agent(
            max_iterations=agent_module.config.agent.max_iterations,
            messages=messages,
            base_url=os.getenv("AI_GRID_BASE_URL"),
            api_key=os.getenv("AI_GRID_API_KEY"),
            model=os.getenv("DEFAULT_MODEL_LABEL"),
        )
        raw_answer = results["answer"]
        verdict = await agent_module.reflect(
            question,
            results["context"],
            raw_answer,
            [],
            os.getenv("AI_GRID_BASE_URL"),
            os.getenv("AI_GRID_API_KEY"),
            os.getenv("DEFAULT_MODEL_LABEL"),
        )
        deprecated_model_name = agent_module._contains_deprecated_model_name(raw_answer)
        answer = (
            raw_answer
            if verdict.get("sufficient") and not deprecated_model_name
            else agent_module._validated_answer(raw_answer, {"sufficient": False})
        )
    finally:
        agent_module.reason = original_reason
        agent_module.reflect = original_reflect
        agent_module._update_generation_usage = original_update_usage
        agent_module.AVAILABLE_TOOLS = original_tools

    latency_seconds = time.perf_counter() - started_at
    input_tokens = [record[0] for record in usage_records]
    output_tokens = [record[1] for record in usage_records]
    total_tokens = [record[2] for record in usage_records]
    usage_complete = (
        len(usage_records) == reason_calls + reflect_calls
        and all(value is not None for record in usage_records for value in record)
    )

    return {
        "answer": answer,
        "latency_seconds": latency_seconds,
        "llm_calls": reason_calls + reflect_calls,
        "document_retrieval_calls": len(document_contexts),
        "other_tool_calls": len(other_tool_outputs),
        "total_tool_calls": len(document_contexts) + len(other_tool_outputs),
        "reasoning_turns": reason_calls,
        "input_tokens": sum(input_tokens) if usage_complete else None,
        "output_tokens": sum(output_tokens) if usage_complete else None,
        "total_tokens": sum(total_tokens) if usage_complete else None,
        "usage_complete": usage_complete,
        "retrieved_document_chars": sum(len(context) for context in document_contexts),
        "tool_observation_chars": len(results["context"]),
        "reflection_rejected": reflect_rejected,
        "deprecated_model_name": deprecated_model_name,
    }


def _fact_label(fact) -> str:
    return fact[0] if isinstance(fact, (tuple, list)) else fact


def _raw_row(case: dict, approach: str, run_number: int, result: dict) -> dict:
    scores = score_answer(result["answer"], case["expected_facts"], case.get("forbidden_facts", []))
    expected_labels = [_fact_label(fact) for fact in case["expected_facts"]]
    fact_hits = {label: bool(scores[label]) for label in expected_labels}
    answer_lower = result["answer"].lower()
    forbidden_count = sum(
        answer_lower.count(fact.lower()) for fact in case.get("forbidden_facts", [])
    )
    return {
        "system": approach,
        "case_id": TEST_CASES.index(case) + 1,
        "question": case["question"],
        "run_number": run_number,
        "latency_seconds": result["latency_seconds"],
        "llm_calls": result["llm_calls"],
        "document_retrieval_calls": result["document_retrieval_calls"],
        "other_tool_calls": result["other_tool_calls"],
        "total_tool_calls": result["total_tool_calls"],
        "reasoning_turns": result["reasoning_turns"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "total_tokens": result["total_tokens"],
        "token_usage_complete": result["usage_complete"],
        "retrieved_document_chars": result["retrieved_document_chars"],
        "tool_observation_chars": result["tool_observation_chars"],
        "fact_hits": json.dumps(fact_hits, sort_keys=True),
        "fact_hit_count": sum(fact_hits.values()),
        "expected_fact_count": len(expected_labels),
        "expected_facts": json.dumps(expected_labels),
        "forbidden_fact_violations": forbidden_count,
        "forbidden_facts": json.dumps(case.get("forbidden_facts", [])),
        "reflection_rejected": result["reflection_rejected"],
        "deprecated_model_name": (
            result["deprecated_model_name"]
            or agent_module._contains_deprecated_model_name(result["answer"])
        ),
        "unsupported_response_trigger": (
            result["reflection_rejected"]
            or result["deprecated_model_name"]
            or agent_module._contains_deprecated_model_name(result["answer"])
        ),
    }


async def _collect_raw_rows() -> list[dict]:
    raw_rows = []
    for case in TEST_CASES:
        for approach, answer_function in (
            ("Classical RAG", naive_rag_answer),
            ("Agentic RAG", _run_agentic_answer),
        ):
            for run_number in range(1, RUNS_PER_QUESTION + 1):
                result = await answer_function(case["question"])
                print(f"\n=== case {TEST_CASES.index(case) + 1} | {approach} | run {run_number}")
                print(f"[answer] {result['answer']}\n")
                raw_rows.append(_raw_row(case, approach, run_number, result))
    return raw_rows


RAW_FIELDS = [
    "system", "case_id", "question", "run_number", "latency_seconds",
    "llm_calls", "document_retrieval_calls", "other_tool_calls",
    "total_tool_calls", "reasoning_turns", "input_tokens", "output_tokens",
    "total_tokens", "token_usage_complete", "retrieved_document_chars",
    "tool_observation_chars", "fact_hits", "fact_hit_count",
    "expected_fact_count", "expected_facts", "forbidden_fact_violations",
    "forbidden_facts", "reflection_rejected", "deprecated_model_name",
    "unsupported_response_trigger",
]


def _write_raw_rows(rows: list[dict]) -> None:
    with RAW_CSV_PATH.open("w", newline="", encoding="utf-8") as raw_file:
        writer = csv.DictWriter(raw_file, fieldnames=RAW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _values(rows: list[dict], system: str, key: str) -> list[float]:
    return [row[key] for row in rows if row["system"] == system and row[key] is not None]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _stats(rows: list[dict], system: str, key: str) -> dict | None:
    values = _values(rows, system, key)
    if not values or len(values) != RUNS_PER_QUESTION * len(TEST_CASES):
        return None
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "std": statistics.pstdev(values),
        "p95": _percentile(values, 0.95),
    }


def _format_stats(stats: dict | None, decimals: int = 3) -> str:
    if stats is None:
        return "Not measured — incomplete API observations"
    return "; ".join(
        f"{label}={stats[label]:.{decimals}f}"
        for label in ("mean", "median", "min", "max", "std", "p95")
    )


def _difference_stats(baseline: dict | None, agentic: dict | None, decimals: int = 3) -> str:
    if baseline is None or agentic is None:
        return "N/A"
    return "; ".join(
        f"{label}={agentic[label] - baseline[label]:+.{decimals}f}"
        for label in ("mean", "median", "min", "max", "std", "p95")
    )


def _fact_rate(rows: list[dict], system: str, case_ids: set[int] | None = None) -> tuple[int, int, float]:
    selected = [row for row in rows if row["system"] == system and (case_ids is None or row["case_id"] in case_ids)]
    hits = sum(row["fact_hit_count"] for row in selected)
    total = sum(row["expected_fact_count"] for row in selected)
    return hits, total, hits / total if total else 0.0


def _multi_step_case_ids(rows: list[dict]) -> tuple[set[int], set[int]]:
    agentic = [row for row in rows if row["system"] == "Agentic RAG"]
    multi = {
        case_id for case_id in {row["case_id"] for row in agentic}
        if statistics.mean(
            [row["document_retrieval_calls"] for row in agentic if row["case_id"] == case_id]
        ) > 1
    }
    all_cases = {row["case_id"] for row in rows}
    return multi, all_cases - multi


def _metric_rows(rows: list[dict]) -> list[dict]:
    multi_cases, single_cases = _multi_step_case_ids(rows)
    metrics = []

    def add_stats(label: str, key: str, decimals: int = 3, baseline_key: str | None = None):
        baseline_stats = _stats(rows, "Classical RAG", baseline_key or key)
        agentic_stats = _stats(rows, "Agentic RAG", key)
        metrics.append((label, _format_stats(baseline_stats, decimals), _format_stats(agentic_stats, decimals), _difference_stats(baseline_stats, agentic_stats, decimals), baseline_stats, agentic_stats))

    add_stats("Mean / median / min / max / std / P95 latency (seconds/query)", "latency_seconds")
    metrics.append(("Time to first token", "Not measured — requires streaming Classical and Agentic implementations", "Not measured — requires streaming Classical and Agentic implementations", "N/A", None, None))
    add_stats("Chat-completion calls/query", "llm_calls")
    add_stats("Document retrieval calls/query", "document_retrieval_calls")
    add_stats("Other tool calls/query", "other_tool_calls")
    add_stats("Total tool invocations/query", "total_tool_calls")
    reasoning_stats = _stats(rows, "Agentic RAG", "reasoning_turns")
    metrics.append(("Reasoning turns/query", "Not applicable — Classical RAG has no agent loop", _format_stats(reasoning_stats), "N/A", None, reasoning_stats))
    add_stats("Input tokens/query", "input_tokens", 0)
    add_stats("Output tokens/query", "output_tokens", 0)
    add_stats("Total tokens/query", "total_tokens", 0)
    baseline_context_stats = _stats(rows, "Classical RAG", "retrieved_document_chars")
    metrics.append(("Baseline retrieved document characters/query", _format_stats(baseline_context_stats), "Not applicable — agentic context is reported separately", "N/A", baseline_context_stats, None))
    agentic_context_stats = _stats(rows, "Agentic RAG", "retrieved_document_chars")
    observation_stats = _stats(rows, "Agentic RAG", "tool_observation_chars")
    metrics.append(("Agentic retrieved document characters/query", "Not applicable — baseline context is already reported separately", _format_stats(agentic_context_stats), "N/A", None, agentic_context_stats))
    metrics.append(("Agentic tool-observation characters/query", "Not applicable — baseline has no tool observations", _format_stats(observation_stats), "N/A", None, observation_stats))

    for label, case_ids in (("Multi-step expected-fact hit rate", multi_cases), ("Single-step expected-fact hit rate", single_cases)):
        baseline_hits, baseline_total, baseline_rate = _fact_rate(rows, "Classical RAG", case_ids)
        agentic_hits, agentic_total, agentic_rate = _fact_rate(rows, "Agentic RAG", case_ids)
        metrics.append((label, f"{baseline_hits}/{baseline_total} ({baseline_rate:.3f})", f"{agentic_hits}/{agentic_total} ({agentic_rate:.3f})", f"{agentic_rate - baseline_rate:+.3f}", None, None))

    baseline_hits, baseline_total, baseline_rate = _fact_rate(rows, "Classical RAG")
    agentic_hits, agentic_total, agentic_rate = _fact_rate(rows, "Agentic RAG")
    metrics.append(("Expected-fact hit rate", f"{baseline_hits}/{baseline_total} ({baseline_rate:.3f})", f"{agentic_hits}/{agentic_total} ({agentic_rate:.3f})", f"{agentic_rate - baseline_rate:+.3f}", None, None))
    add_stats("Unsupported-response triggers/query", "unsupported_response_trigger")
    add_stats("Forbidden-fact violations/query", "forbidden_fact_violations")
    return metrics


def _write_aggregate_csv(rows: list[dict]) -> None:
    fields = ["Metric", "Classical RAG Baseline", "Agentic RAG", "Difference"]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as results_file:
        writer = csv.DictWriter(results_file, fieldnames=fields)
        writer.writeheader()
        for metric, baseline, agentic, difference, _, _ in _metric_rows(rows):
            writer.writerow({"Metric": metric, "Classical RAG Baseline": baseline, "Agentic RAG": agentic, "Difference": difference})


def _write_markdown(rows: list[dict]) -> None:
    multi_cases, single_cases = _multi_step_case_ids(rows)
    lines = [
        "This is a descriptive engineering comparison of the Classical RAG retrieve-then-generate baseline and the Agentic RAG workload over the same seven TEST_CASES, with three runs per case.",
        "",
        "Latency boundary: each timer starts immediately before that system's retrieval/generation workload and stops after its final answer decision. The agentic evaluation path runs the existing ReAct `run_agent()` and blocking `reflect()` logic, but excludes PostgreSQL session creation, history loading, and message persistence so both systems measure answer-generation work rather than unrelated database overhead.",
        "",
        "Held constant: TEST_CASES, ingested corpus, Qdrant collection, embedding implementation/model, chat model, scoring function, execution machine, and API environment. Not controlled: network conditions, remote API load, hosted model variability, and background local system load.",
        "",
        "The baseline is specifically a retrieve-once + generate-once reference architecture; it does not represent every Classical RAG system. All statistics are descriptive; no inferential statistical test is performed. Values use six-decimal internal measurements and are displayed to three decimals for continuous metrics and whole tokens for token metrics.",
        "",
        "| Metric | Classical RAG Baseline | Agentic RAG | Difference |",
        "| ------ | ---------------------: | ----------: | ---------: |",
    ]
    for metric, baseline, agentic, difference, _, _ in _metric_rows(rows):
        lines.append(f"| {metric} | {baseline} | {agentic} | {difference} |")

    lines.extend([
        "",
        "## Metric Definitions",
        "",
        "- Chat-completion calls count actual `reason()` and `reflect()` completion requests for Agentic RAG and the single baseline completion. Embedding requests are not chat-completion calls. Calls are counted when the wrapped function begins; failed runs are not silently converted into measurements.",
        "- Document retrieval calls count actual `search_documents()` invocations. Other tool calls count actual `list_available_models()` invocations. Total tool invocations is their sum.",
        "- Agentic reasoning turns are actual `reason()` calls, including the final non-tool turn. Classical RAG has no agent loop and is therefore not applicable.",
        "- Token metrics use only API usage fields. A run is incomplete for token aggregation if any completion usage field is missing; no token estimate is substituted.",
        "- Retrieved document characters count the actual strings returned by `search_documents()`. Agentic tool-observation characters are reported separately because serialized observations are not equivalent to raw document context.",
        "- Expected-fact hit rate uses the unchanged `score_answer()` substring matcher, with explicit fact/run denominators. Unsupported-response triggers mean reflection rejection or deprecated-model detection; they are not a semantic hallucination rate.",
        "- TTFT is not measured because the baseline has no equivalent streaming implementation. A fair TTFT experiment requires streaming implementations for both systems.",
        "",
        "## Multi-step Retrieval",
        "",
        f"The protocol classifies a case as multi-step only when its observed average `search_documents()` count across three Agentic RAG runs is greater than 1. This run observed {len(multi_cases)} multi-step case(s) and {len(single_cases)} single-step case(s): multi-step cases {sorted(multi_cases) or 'none'}, single-step cases {sorted(single_cases) or 'none'}.",
        "",
        "## Per-case Findings",
        "",
        "| Case | System | Expected-fact hit rate | Document retrieval calls (mean) | Latency mean (s) | Total tokens mean |",
        "| ---- | ------ | ----------------------: | -------------------------------: | ---------------: | ----------------: |",
    ])
    for case_id in range(1, len(TEST_CASES) + 1):
        for system in ("Classical RAG", "Agentic RAG"):
            selected = [row for row in rows if row["case_id"] == case_id and row["system"] == system]
            hits, total, rate = _fact_rate(selected, system)
            retrieval_mean = statistics.mean(row["document_retrieval_calls"] for row in selected)
            latency_mean = statistics.mean(row["latency_seconds"] for row in selected)
            token_values = [row["total_tokens"] for row in selected if row["total_tokens"] is not None]
            token_text = f"{statistics.mean(token_values):.0f}" if len(token_values) == len(selected) else "Not measured"
            lines.append(f"| {case_id} | {system} | {hits}/{total} ({rate:.3f}) | {retrieval_mean:.3f} | {latency_mean:.3f} | {token_text} |")

    lines.extend([
        "",
        "## Discussion",
        "",
        "The raw per-run dataset is `comparison_runs.csv`; the aggregate CSV and this report are generated from the same in-memory rows. The experiment measures observed efficiency overhead, tool behavior, token usage, and expected-fact matching under this configuration. It does not establish general performance superiority or semantic grounding superiority.",
        "",
        "Agentic RAG's additional capability is iterative document retrieval, optional other-tool use, and reflection. The measured cost of that architecture is represented by its latency, chat-completion calls, tool calls, reasoning turns, and token statistics in the table. Whether that overhead produces a quality advantage is determined only by the displayed expected-fact hit rates and the small supplied test set.",
        "",
        "The seven-case, three-run experiment is too small for broad statistical generalization. Live hosted-model behavior, network variance, remote load, and uncontrolled local load remain limitations.",
        "",
        "## Recommended Future Experiment",
        "",
        "Use a larger fixed test set, preserve raw per-run records, control concurrency and network conditions where possible, record model/corpus versions, and implement equivalent streaming paths before comparing TTFT.",
    ])
    MARKDOWN_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    rows = await _collect_raw_rows()
    _write_raw_rows(rows)
    _write_aggregate_csv(rows)
    _write_markdown(rows)
    print("\n=== FINAL COMPARISON TABLE ===")
    print("Metric | Classical RAG Baseline | Agentic RAG | Difference")
    for metric, baseline, agentic, difference, _, _ in _metric_rows(rows):
        print(f"{metric} | {baseline} | {agentic} | {difference}")


if __name__ == "__main__":
    asyncio.run(main())
