"""
Minimal evaluation harness for the agent.
"""

import asyncio
import sys
from backend.core.agent import chat_with_agent
from backend.infrastructure.db import create_session, init_db

TEST_CASES = [
    {
        "question": "How does AI Grid handle image inputs, and is that different for scanned documents versus photos?",
        "expected_facts": ["deepseek-ocr", "GLM-OCR"],
    },
    {
        "question": "What is Qwen3-30B-A3B-Thinking used for?",
        "expected_facts": ["Qwen3-30B-A3B-Thinking", "reasoning"],
    },
    {
        "question": "Compare google/gemma-4-31B and Qwen3-30B-A3B-Thinking for a coding agent",
        "expected_facts": ["gemma-4-31B", "Qwen3-30B-A3B-Thinking", "throughput"],
    },
    {
        "question": "What is AI Grid's refund policy?",
        "expected_facts": [
            ("could not find", "does not contain", "no information", "not covered"),
            "documentation",
        ],
    },
    {
        "question": "Compare Qwen3-30B-A3B-Thinking, google/gemma-4-31B, and meta-models/Muse-Glimmer-30B for general reasoning tasks",
        "expected_facts": ["Qwen3-30B-A3B-Thinking", "gemma-4-31B", "Muse-Glimmer-30B"],
    },
    {
        "question": "What is the exact input price per million tokens for Qwen3-30B-A3B-Thinking?",
        "expected_facts": ["73", "Qwen3-30B-A3B-Thinking"],
    },
        {
        "question": "I'm a certified startup building a multilingual customer chatbot that also needs to process scanned invoices with OCR. Which AI Grid plan should I use, which models, and roughly what would 10 million input tokens per month cost me across all the models involved?",
        "expected_facts": [
            ("i do not have enough information", "does not contain", "could not find"),
        ],
        "forbidden_facts": ["GPT OSS 20B"],
    },
]

RUNS_PER_QUESTION = 3

# An expected fact that scores 0/RUNS_PER_QUESTION, or a forbidden fact that
# appears even once, fails the build in CI.
MIN_HIT_RATE = 1  # at least 1 hit out of RUNS_PER_QUESTION counts as a pass


def score_answer(answer: str, expected_facts: list[str], forbidden_facts: list[str] = None) -> dict:
    answer_lower = answer.lower()
    forbidden_facts = forbidden_facts or []

    def _label(fact) -> str:
        return fact[0] if isinstance(fact, (tuple, list)) else fact

    def _matches(fact) -> bool:
        alternatives = fact if isinstance(fact, (tuple, list)) else (fact,)
        return any(alt.lower() in answer_lower for alt in alternatives)

    results = {
        _label(fact): _matches(fact)
        for fact in expected_facts
    }

    for fact in forbidden_facts:
        results[f"{fact} (forbidden)"] = fact.lower() not in answer_lower

    return results

async def run_case(question: str, expected_facts: list[str], forbidden_facts: list[str] = None) -> bool:
    """Returns True if this case passed (every fact met MIN_HIT_RATE), False otherwise."""
    print(f"\n=== {question}")

    all_labels = [
        fact[0] if isinstance(fact, (tuple, list)) else fact
        for fact in expected_facts
    ] + [f"{fact} (forbidden)" for fact in (forbidden_facts or [])]
    fact_hits = {label: 0 for label in all_labels}

    for run_number in range(1, RUNS_PER_QUESTION + 1):
        session_id = await create_session()
        answer = await chat_with_agent(question, session_id)
        print(f"  [answer] {answer}\n")

        scores = score_answer(answer, expected_facts, forbidden_facts)
        for label, found in scores.items():
            if found:
                fact_hits[label] += 1

        print(f"  run {run_number}: {scores}")

    print("  --- summary ---")
    case_passed = True
    for label, hits in fact_hits.items():
        print(f"  {label}: {hits}/{RUNS_PER_QUESTION} runs")
        if hits < MIN_HIT_RATE:
            case_passed = False

    if not case_passed:
        print("  *** CASE FAILED (a fact never met the minimum hit rate) ***")

    return case_passed


async def main() -> int:
    await init_db()
    all_passed = True
    for case in TEST_CASES:
        case_passed = await run_case(
            case["question"],
            case["expected_facts"],
            case.get("forbidden_facts", []),
        )
        all_passed = all_passed and case_passed

    print("\n=== FINAL RESULT ===")
    print("PASSED" if all_passed else "FAILED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)