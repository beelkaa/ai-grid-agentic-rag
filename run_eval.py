"""
Minimal evaluation harness for the agent.
"""

import asyncio
from agent import chat_with_agent
from db import create_session, init_db

TEST_CASES = [
    {
        "question": "How does AI Grid handle image inputs, and is that different for scanned documents versus photos?",
        "expected_facts": ["deepseek-ocr", "GLM-OCR"],
    },
    {
        "question": "What is gpt-oss-120b used for?",
        "expected_facts": ["gpt-oss-120b", "reasoning"],
    },
    {
        "question": "Compare gpt-oss-120b and Qwen3-30B-A3B-Thinking for a coding agent",
        "expected_facts": ["gpt-oss-120b", "Qwen3", "throughput"],
    },
    {
        "question": "What is AI Grid's refund policy?",
        "expected_facts": ["could not find", "documentation"],
    },
    {
        "question": "Compare gpt-oss-120b, Qwen3-30B-A3B-Thinking, and google/gemma-4-31B for general reasoning tasks",
        "expected_facts": ["gpt-oss-120b", "Qwen3", "gemma"],
    },
    {
        "question": "What is the exact input price per million tokens for gpt-oss-120b?",
        "expected_facts": ["19", "gpt-oss-120b"],
    },
    {
        "question": "I'm a certified startup building a multilingual customer chatbot that also needs to process scanned invoices with OCR. Which AI Grid plan should I use, which models, and roughly what would 10 million input tokens per month cost me across all the models involved?",
        "expected_facts": ["gpt-oss-120b", "deepseek ocr"],
        "forbidden_facts": ["GPT OSS 20B"],
    },
]

RUNS_PER_QUESTION = 3


def score_answer(answer: str, expected_facts: list[str], forbidden_facts: list[str] = None) -> dict:
    """
    Check, case-insensitively, whether each expected fact appears
    somewhere in the answer text, and whether any forbidden fact
    incorrectly appears.

    True always means "as expected": present for expected_facts,
    absent for forbidden_facts.
    """
    answer_lower = answer.lower()
    forbidden_facts = forbidden_facts or []

    results = {
        fact: fact.lower() in answer_lower
        for fact in expected_facts
    }

    for fact in forbidden_facts:
        results[f"{fact} (forbidden)"] = fact.lower() not in answer_lower

    return results


async def run_case(question: str, expected_facts: list[str], forbidden_facts: list[str] = None) -> None:
    print(f"\n=== {question}")

    all_labels = expected_facts + [f"{f} (forbidden)" for f in (forbidden_facts or [])]
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
    for label, hits in fact_hits.items():
        print(f"  {label}: {hits}/{RUNS_PER_QUESTION} runs")


async def main():
    await init_db()
    for case in TEST_CASES:
        await run_case(
            case["question"],
            case["expected_facts"],
            case.get("forbidden_facts", []),
        )


if __name__ == "__main__":
    asyncio.run(main())