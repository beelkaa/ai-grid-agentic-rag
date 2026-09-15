This is a descriptive engineering comparison of the Classical RAG retrieve-then-generate baseline and the Agentic RAG workload over the same seven TEST_CASES, with three runs per case.

Latency boundary: each timer starts immediately before that system's retrieval/generation workload and stops after its final answer decision. The agentic evaluation path runs the existing ReAct `run_agent()` and blocking `reflect()` logic, but excludes PostgreSQL session creation, history loading, and message persistence so both systems measure answer-generation work rather than unrelated database overhead.

Held constant: TEST_CASES, ingested corpus, Qdrant collection, embedding implementation/model, chat model, scoring function, execution machine, and API environment. Not controlled: network conditions, remote API load, hosted model variability, and background local system load.

The baseline is specifically a retrieve-once + generate-once reference architecture; it does not represent every Classical RAG system. All statistics are descriptive; no inferential statistical test is performed. Values use six-decimal internal measurements and are displayed to three decimals for continuous metrics and whole tokens for token metrics.

| Metric | Classical RAG Baseline | Agentic RAG | Difference |
| ------ | ---------------------: | ----------: | ---------: |
| Mean / median / min / max / std / P95 latency (seconds/query) | mean=0.224; median=0.205; min=0.175; max=0.594; std=0.085; p95=0.268 | mean=0.628; median=0.400; min=0.331; max=1.904; std=0.418; p95=1.527 | mean=+0.405; median=+0.195; min=+0.156; max=+1.310; std=+0.333; p95=+1.259 |
| Time to first token | Not measured — requires streaming Classical and Agentic implementations | Not measured — requires streaming Classical and Agentic implementations | N/A |
| Chat-completion calls/query | mean=1.000; median=1.000; min=1.000; max=1.000; std=0.000; p95=1.000 | mean=3.286; median=3.000; min=3.000; max=4.000; std=0.452; p95=4.000 | mean=+2.286; median=+2.000; min=+2.000; max=+3.000; std=+0.452; p95=+3.000 |
| Document retrieval calls/query | mean=1.000; median=1.000; min=1.000; max=1.000; std=0.000; p95=1.000 | mean=1.143; median=1.000; min=1.000; max=2.000; std=0.350; p95=2.000 | mean=+0.143; median=+0.000; min=+0.000; max=+1.000; std=+0.350; p95=+1.000 |
| Other tool calls/query | mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | mean=0.143; median=0.000; min=0.000; max=1.000; std=0.350; p95=1.000 | mean=+0.143; median=+0.000; min=+0.000; max=+1.000; std=+0.350; p95=+1.000 |
| Total tool invocations/query | mean=1.000; median=1.000; min=1.000; max=1.000; std=0.000; p95=1.000 | mean=1.286; median=1.000; min=1.000; max=2.000; std=0.452; p95=2.000 | mean=+0.286; median=+0.000; min=+0.000; max=+1.000; std=+0.452; p95=+1.000 |
| Reasoning turns/query | Not applicable — Classical RAG has no agent loop | mean=2.286; median=2.000; min=2.000; max=3.000; std=0.452; p95=3.000 | N/A |
| Input tokens/query | mean=2913; median=2981; min=2459; max=3042; std=191; p95=3042 | mean=8639; median=7337; min=5788; max=14957; std=2998; p95=14957 | mean=+5726; median=+4356; min=+3329; max=+11915; std=+2807; p95=+11915 |
| Output tokens/query | mean=284; median=246; min=16; max=639; std=214; p95=639 | mean=541; median=498; min=56; max=1096; std=364; p95=1096 | mean=+256; median=+252; min=+40; max=+457; std=+151; p95=+457 |
| Total tokens/query | mean=3197; median=3227; min=2475; max=3670; std=353; p95=3670 | mean=9180; median=7478; min=5844; max=15850; std=3261; p95=15850 | mean=+5983; median=+4251; min=+3369; max=+12180; std=+2908; p95=+12180 |
| Baseline retrieved document characters/query | mean=4088.143; median=4210.000; min=3229.000; max=4293.000; std=352.552; p95=4293.000 | Not applicable — agentic context is reported separately | N/A |
| Agentic retrieved document characters/query | Not applicable — baseline context is already reported separately | mean=4526.286; median=4248.000; min=3232.000; max=8535.000; std=1691.148; p95=8535.000 | N/A |
| Agentic tool-observation characters/query | Not applicable — baseline has no tool observations | mean=4859.143; median=4545.000; min=3318.000; max=9107.000; std=1824.463; p95=9107.000 | N/A |
| Multi-step expected-fact hit rate | 9/9 (1.000) | 9/9 (1.000) | +0.000 |
| Single-step expected-fact hit rate | 36/36 (1.000) | 36/36 (1.000) | +0.000 |
| Expected-fact hit rate | 45/45 (1.000) | 45/45 (1.000) | +0.000 |
| Unsupported-response triggers/query | mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | mean=0.143; median=0.000; min=0.000; max=1.000; std=0.350; p95=1.000 | mean=+0.143; median=+0.000; min=+0.000; max=+1.000; std=+0.350; p95=+1.000 |
| Forbidden-fact violations/query | mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | mean=+0.000; median=+0.000; min=+0.000; max=+0.000; std=+0.000; p95=+0.000 |

## Metric Definitions

- Chat-completion calls count actual `reason()` and `reflect()` completion requests for Agentic RAG and the single baseline completion. Embedding requests are not chat-completion calls. Calls are counted when the wrapped function begins; failed runs are not silently converted into measurements.
- Document retrieval calls count actual `search_documents()` invocations. Other tool calls count actual `list_available_models()` invocations. Total tool invocations is their sum.
- Agentic reasoning turns are actual `reason()` calls, including the final non-tool turn. Classical RAG has no agent loop and is therefore not applicable.
- Token metrics use only API usage fields. A run is incomplete for token aggregation if any completion usage field is missing; no token estimate is substituted.
- Retrieved document characters count the actual strings returned by `search_documents()`. Agentic tool-observation characters are reported separately because serialized observations are not equivalent to raw document context.
- Expected-fact hit rate uses the unchanged `score_answer()` substring matcher, with explicit fact/run denominators. Unsupported-response triggers mean reflection rejection or deprecated-model detection; they are not a semantic hallucination rate.
- TTFT is not measured because the baseline has no equivalent streaming implementation. A fair TTFT experiment requires streaming implementations for both systems.

## Multi-step Retrieval

The protocol classifies a case as multi-step only when its observed average `search_documents()` count across three Agentic RAG runs is greater than 1. This run observed 1 multi-step case(s) and 6 single-step case(s): multi-step cases [3], single-step cases [1, 2, 4, 5, 6, 7].

## Per-case Findings

| Case | System | Expected-fact hit rate | Document retrieval calls (mean) | Latency mean (s) | Total tokens mean |
| ---- | ------ | ----------------------: | -------------------------------: | ---------------: | ----------------: |
| 1 | Classical RAG | 6/6 (1.000) | 1.000 | 0.220 | 3227 |
| 1 | Agentic RAG | 6/6 (1.000) | 1.000 | 0.381 | 7411 |
| 2 | Classical RAG | 6/6 (1.000) | 1.000 | 0.218 | 3115 |
| 2 | Agentic RAG | 6/6 (1.000) | 1.000 | 0.598 | 8099 |
| 3 | Classical RAG | 9/9 (1.000) | 1.000 | 0.194 | 3670 |
| 3 | Agentic RAG | 9/9 (1.000) | 2.000 | 1.069 | 15850 |
| 4 | Classical RAG | 6/6 (1.000) | 1.000 | 0.188 | 2475 |
| 4 | Agentic RAG | 6/6 (1.000) | 1.000 | 0.359 | 5844 |
| 5 | Classical RAG | 9/9 (1.000) | 1.000 | 0.199 | 3497 |
| 5 | Agentic RAG | 9/9 (1.000) | 1.000 | 1.040 | 12119 |
| 6 | Classical RAG | 6/6 (1.000) | 1.000 | 0.206 | 3076 |
| 6 | Agentic RAG | 6/6 (1.000) | 1.000 | 0.397 | 7457 |
| 7 | Classical RAG | 3/3 (1.000) | 1.000 | 0.340 | 3319 |
| 7 | Agentic RAG | 3/3 (1.000) | 1.000 | 0.554 | 7478 |

## Discussion

The raw per-run dataset is `comparison_runs.csv`; the aggregate CSV and this report are generated from the same in-memory rows. The experiment measures observed efficiency overhead, tool behavior, token usage, and expected-fact matching under this configuration. It does not establish general performance superiority or semantic grounding superiority.

Agentic RAG's additional capability is iterative document retrieval, optional other-tool use, and reflection. The measured cost of that architecture is represented by its latency, chat-completion calls, tool calls, reasoning turns, and token statistics in the table. Whether that overhead produces a quality advantage is determined only by the displayed expected-fact hit rates and the small supplied test set.

The seven-case, three-run experiment is too small for broad statistical generalization. Live hosted-model behavior, network variance, remote load, and uncontrolled local load remain limitations.

## Recommended Future Experiment

Use a larger fixed test set, preserve raw per-run records, control concurrency and network conditions where possible, record model/corpus versions, and implement equivalent streaming paths before comparing TTFT.
