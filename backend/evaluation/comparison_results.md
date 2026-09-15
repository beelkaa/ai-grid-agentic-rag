# Classical RAG vs Agentic RAG: 30-Question Benchmark

## Objective

This descriptive engineering experiment compares the Classical RAG retrieve-once + generate-once reference implementation with the Agentic RAG ReAct, named-tool, iterative-retrieval, and reflection workload. It measures capability/flexibility against observed latency, token, tool, and chat-completion overhead; it does not claim universal superiority.

## Dataset and Protocol

The fixed dataset contains exactly 30 questions: 8 simple documentation retrieval, 6 model-specific, 4 cross-model comparison, 4 API/workflow, 3 embeddings/retrieval, 3 agentic/multi-step synthesis, and 2 unsupported/robustness questions. Each system runs every question three times: 30 x 3 x 2 = 180 planned runs and 180 expected raw rows.

Run completion: 180/180 runs completed, with 0 failures, 180 raw rows, 90 Classical RAG rows, 90 Agentic RAG rows, 180/180 complete token observations, and 0 duplicate `(system, question_id, run_number)` keys. The raw observations are retained in `comparison_runs.csv`; aggregate CSV and Markdown values are generated from the same run data. Reproduction requires the configured AI Grid API, the current ingested Qdrant corpus, the repository virtual environment, and `python -m backend.evaluation.compare`.

Held constant: exact question text, current ingested documentation corpus, Qdrant collection, embedding implementation/model, chat model, scorer, execution machine, and API environment. Not controlled: network conditions, remote API load, hosted model variability, and background local system load. The same evaluation-only latency boundary excludes PostgreSQL session/history/persistence overhead and includes retrieval, reasoning, generation, and Agentic reflection.

## Aggregate Results

| Metric | Classical RAG Baseline | Agentic RAG | Difference |
| ------ | ---------------------: | ----------: | ---------: |
| Latency seconds/query (mean, median, min, max, std, P95) | n=90; mean=0.505; median=0.223; min=0.166; max=8.427; std=1.004; p95=1.557 | n=90; mean=1.204; median=0.410; min=0.148; max=13.795; std=1.963; p95=4.932 | mean=+0.700; median=+0.187; min=-0.018; max=+5.367; std=+0.959; p95=+3.375 |
| Time to first token | Not measured — requires streaming Classical and Agentic implementations | Not measured — requires streaming Classical and Agentic implementations | N/A |
| Chat-completion calls/query | n=90; mean=1.000; median=1.000; min=1.000; max=1.000; std=0.000; p95=1.000 | n=90; mean=3.000; median=3.000; min=2.000; max=4.000; std=0.365; p95=4.000 | mean=+2.000; median=+2.000; min=+1.000; max=+3.000; std=+0.365; p95=+3.000 |
| Document retrieval calls/query | n=90; mean=1.000; median=1.000; min=1.000; max=1.000; std=0.000; p95=1.000 | n=90; mean=1.000; median=1.000; min=0.000; max=2.000; std=0.365; p95=2.000 | mean=+0.000; median=+0.000; min=-1.000; max=+1.000; std=+0.365; p95=+1.000 |
| Other tool calls/query | n=90; mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | n=90; mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | mean=+0.000; median=+0.000; min=+0.000; max=+0.000; std=+0.000; p95=+0.000 |
| Total tool invocations/query | n=90; mean=1.000; median=1.000; min=1.000; max=1.000; std=0.000; p95=1.000 | n=90; mean=1.000; median=1.000; min=0.000; max=2.000; std=0.365; p95=2.000 | mean=+0.000; median=+0.000; min=-1.000; max=+1.000; std=+0.365; p95=+1.000 |
| Agent reasoning turns/query | N/A — Classical RAG has no agent loop | n=90; mean=2.000; median=2.000; min=1.000; max=3.000; std=0.365; p95=3.000 | N/A |
| Input tokens/query | n=90; mean=2870; median=2944; min=2080; max=3067; std=215; p95=3045 | n=90; mean=7483; median=7458; min=2311; max=15135; std=2410; p95=15031 | mean=+4612; median=+4514; min=+231; max=+12068; std=+2195; p95=+11986 |
| Output tokens/query | n=90; mean=145; median=69; min=26; max=538; std=147; p95=447 | n=90; mean=328; median=242; min=80; max=991; std=251; p95=793 | mean=+183; median=+172; min=+54; max=+453; std=+104; p95=+346 |
| Total tokens/query | n=90; mean=3015; median=3053; min=2113; max=3582; std=289; p95=3433 | n=90; mean=7811; median=7680; min=2402; max=15920; std=2558; p95=15824 | mean=+4796; median=+4628; min=+289; max=+12338; std=+2270; p95=+12391 |
| Retrieved document characters/query | n=90; mean=4018.667; median=4173.500; min=1781.000; max=4307.000; std=494.956; p95=4307.000 | n=90; mean=4129.067; median=4190.000; min=0.000; max=8568.000; std=1577.350; p95=8547.000 | mean=+110.400; median=+16.500; min=-1781.000; max=+4261.000; std=+1082.395; p95=+4240.000 |
| Multi-step expected-fact hit rate | 27/27 (1.000) | 27/27 (1.000) | +0.000 |
| Single-step expected-fact hit rate | 138/192 (0.719) | 165/192 (0.859) | +0.141 |
| Expected-fact hit rate | 165/219 (0.753) | 192/219 (0.877) | +0.123 |
| Unsupported-response triggers/query | n=90; mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | n=90; mean=0.033; median=0.000; min=0.000; max=1.000; std=0.180; p95=0.000 | mean=+0.033; median=+0.000; min=+0.000; max=+1.000; std=+0.180; p95=+0.000 |
| Forbidden-fact violations/query | n=90; mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | n=90; mean=0.000; median=0.000; min=0.000; max=0.000; std=0.000; p95=0.000 | mean=+0.000; median=+0.000; min=+0.000; max=+0.000; std=+0.000; p95=+0.000 |

## Category-Level Results

| Category | Classical RAG | Agentic RAG | Difference |
| --- | ---: | ---: | ---: |
| Simple documentation retrieval | 30/33 (0.909) | 30/33 (0.909) | +0.000 |
| Model-specific questions | 30/33 (0.909) | 33/33 (1.000) | +0.091 |
| Cross-model comparison | 42/48 (0.875) | 42/48 (0.875) | +0.000 |
| API / workflow questions | 33/36 (0.917) | 36/36 (1.000) | +0.083 |
| Embeddings / retrieval | 9/27 (0.333) | 18/27 (0.667) | +0.333 |
| Agentic / multi-step synthesis | 15/36 (0.417) | 27/36 (0.750) | +0.333 |
| Unsupported / robustness | 6/6 (1.000) | 6/6 (1.000) | +0.000 |

## Metric Definitions and Limitations

- Chat-completion calls count the baseline completion and actual Agentic `reason()` plus `reflect()` calls. Embedding calls are excluded. Failed runs are recorded and excluded from completed-observation statistics.
- Document retrieval calls count actual `search_documents()` invocations; other tool calls count actual `list_available_models()` invocations; total tool invocations is their sum.
- Agent reasoning turns are actual `reason()` calls, including the final non-tool turn. Classical RAG has no agent loop, so it is N/A.
- Token counts use only API usage fields. Missing usage is never estimated; incomplete runs are marked and excluded from token aggregates.
- Retrieved document characters are measured from the strings returned by `search_documents()`. Agentic serialized tool-observation characters are retained separately in the raw CSV and are not treated as equivalent context.
- Expected-fact hit rate uses unchanged `score_answer()` substring matching and reports explicit fact/run denominators. Unsupported-response triggers mean reflection rejection or deprecated-model detection; they are not a semantic hallucination metric.
- TTFT is not measured because a fair comparison requires streaming implementations for both systems.

## Multi-Step Analysis

A case is multi-step only when its observed average `search_documents()` count across three Agentic runs exceeds 1. This run classified 2 multi-step case(s) (Q15, Q18) and 28 single-step case(s). Multi-step and single-step expected-fact results are reported in the aggregate table with denominators.

## Per-Case Results

| Question | Category | System | Expected-fact hit rate | Retrieval calls mean | Latency mean (s) | Total tokens mean | Status |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Q01 | Simple documentation retrieval | Classical RAG | 6/6 (1.000) | 1 | 1.538 | 2827 | 3/3 completed |
| Q01 | Simple documentation retrieval | Agentic RAG | 6/6 (1.000) | 1 | 2.125 | 6790 | 3/3 completed |
| Q02 | Simple documentation retrieval | Classical RAG | 6/6 (1.000) | 1 | 0.583 | 2664 | 3/3 completed |
| Q02 | Simple documentation retrieval | Agentic RAG | 6/6 (1.000) | 1 | 2.438 | 6935 | 3/3 completed |
| Q03 | Simple documentation retrieval | Classical RAG | 3/3 (1.000) | 1 | 0.256 | 3114 | 3/3 completed |
| Q03 | Simple documentation retrieval | Agentic RAG | 3/3 (1.000) | 1 | 1.827 | 7174 | 3/3 completed |
| Q04 | Simple documentation retrieval | Classical RAG | 0/3 (0.000) | 1 | 0.709 | 2991 | 3/3 completed |
| Q04 | Simple documentation retrieval | Agentic RAG | 3/3 (1.000) | 1 | 1.498 | 7199 | 3/3 completed |
| Q05 | Simple documentation retrieval | Classical RAG | 6/6 (1.000) | 1 | 0.638 | 2941 | 3/3 completed |
| Q05 | Simple documentation retrieval | Agentic RAG | 6/6 (1.000) | 1 | 0.426 | 6974 | 3/3 completed |
| Q06 | Simple documentation retrieval | Classical RAG | 3/3 (1.000) | 1 | 0.279 | 3057 | 3/3 completed |
| Q06 | Simple documentation retrieval | Agentic RAG | 3/3 (1.000) | 1 | 1.337 | 7648 | 3/3 completed |
| Q07 | Simple documentation retrieval | Classical RAG | 3/3 (1.000) | 1 | 0.451 | 3054 | 3/3 completed |
| Q07 | Simple documentation retrieval | Agentic RAG | 3/3 (1.000) | 1 | 1.883 | 7654 | 3/3 completed |
| Q08 | Simple documentation retrieval | Classical RAG | 3/3 (1.000) | 1 | 0.685 | 3052 | 3/3 completed |
| Q08 | Simple documentation retrieval | Agentic RAG | 0/3 (0.000) | 1 | 1.675 | 7463 | 3/3 completed |
| Q09 | Model-specific questions | Classical RAG | 6/6 (1.000) | 1 | 0.226 | 3127 | 3/3 completed |
| Q09 | Model-specific questions | Agentic RAG | 6/6 (1.000) | 1 | 1.923 | 7833 | 3/3 completed |
| Q10 | Model-specific questions | Classical RAG | 3/3 (1.000) | 1 | 0.586 | 3026 | 3/3 completed |
| Q10 | Model-specific questions | Agentic RAG | 3/3 (1.000) | 1 | 1.595 | 7634 | 3/3 completed |
| Q11 | Model-specific questions | Classical RAG | 6/6 (1.000) | 1 | 0.691 | 3101 | 3/3 completed |
| Q11 | Model-specific questions | Agentic RAG | 6/6 (1.000) | 1 | 2.297 | 7552 | 3/3 completed |
| Q12 | Model-specific questions | Classical RAG | 3/6 (0.500) | 1 | 0.657 | 3070 | 3/3 completed |
| Q12 | Model-specific questions | Agentic RAG | 6/6 (1.000) | 1 | 1.520 | 7702 | 3/3 completed |
| Q13 | Model-specific questions | Classical RAG | 9/9 (1.000) | 1 | 0.648 | 2991 | 3/3 completed |
| Q13 | Model-specific questions | Agentic RAG | 9/9 (1.000) | 1 | 2.333 | 7729 | 3/3 completed |
| Q14 | Model-specific questions | Classical RAG | 3/3 (1.000) | 1 | 0.205 | 3091 | 3/3 completed |
| Q14 | Model-specific questions | Agentic RAG | 3/3 (1.000) | 1 | 1.271 | 7697 | 3/3 completed |
| Q15 | Cross-model comparison | Classical RAG | 12/12 (1.000) | 1 | 2.983 | 3438 | 3/3 completed |
| Q15 | Cross-model comparison | Agentic RAG | 12/12 (1.000) | 2 | 4.981 | 15824 | 3/3 completed |
| Q16 | Cross-model comparison | Classical RAG | 9/9 (1.000) | 1 | 0.208 | 3176 | 3/3 completed |
| Q16 | Cross-model comparison | Agentic RAG | 9/9 (1.000) | 1 | 0.450 | 7951 | 3/3 completed |
| Q17 | Cross-model comparison | Classical RAG | 6/12 (0.500) | 1 | 0.537 | 3177 | 3/3 completed |
| Q17 | Cross-model comparison | Agentic RAG | 6/12 (0.500) | 1 | 0.409 | 7819 | 3/3 completed |
| Q18 | Cross-model comparison | Classical RAG | 15/15 (1.000) | 1 | 0.228 | 3582 | 3/3 completed |
| Q18 | Cross-model comparison | Agentic RAG | 15/15 (1.000) | 2 | 0.634 | 15920 | 3/3 completed |
| Q19 | API / workflow questions | Classical RAG | 12/12 (1.000) | 1 | 0.448 | 3257 | 3/3 completed |
| Q19 | API / workflow questions | Agentic RAG | 12/12 (1.000) | 1 | 0.393 | 7943 | 3/3 completed |
| Q20 | API / workflow questions | Classical RAG | 9/9 (1.000) | 1 | 0.222 | 3333 | 3/3 completed |
| Q20 | API / workflow questions | Agentic RAG | 9/9 (1.000) | 1 | 0.784 | 7625 | 3/3 completed |
| Q21 | API / workflow questions | Classical RAG | 9/9 (1.000) | 1 | 0.213 | 2843 | 3/3 completed |
| Q21 | API / workflow questions | Agentic RAG | 9/9 (1.000) | 1 | 0.387 | 6278 | 3/3 completed |
| Q22 | API / workflow questions | Classical RAG | 3/6 (0.500) | 1 | 0.194 | 2862 | 3/3 completed |
| Q22 | API / workflow questions | Agentic RAG | 6/6 (1.000) | 1 | 0.356 | 7141 | 3/3 completed |
| Q23 | Embeddings / retrieval | Classical RAG | 3/6 (0.500) | 1 | 0.280 | 2935 | 3/3 completed |
| Q23 | Embeddings / retrieval | Agentic RAG | 3/6 (0.500) | 1 | 0.398 | 7696 | 3/3 completed |
| Q24 | Embeddings / retrieval | Classical RAG | 0/9 (0.000) | 1 | 0.270 | 2673 | 3/3 completed |
| Q24 | Embeddings / retrieval | Agentic RAG | 6/9 (0.667) | 1 | 0.785 | 7801 | 3/3 completed |
| Q25 | Embeddings / retrieval | Classical RAG | 6/12 (0.500) | 1 | 0.215 | 2831 | 3/3 completed |
| Q25 | Embeddings / retrieval | Agentic RAG | 9/12 (0.750) | 1 | 0.372 | 8229 | 3/3 completed |
| Q26 | Agentic / multi-step synthesis | Classical RAG | 6/9 (0.667) | 1 | 0.313 | 2987 | 3/3 completed |
| Q26 | Agentic / multi-step synthesis | Agentic RAG | 9/9 (1.000) | 1 | 0.364 | 8156 | 3/3 completed |
| Q27 | Agentic / multi-step synthesis | Classical RAG | 3/12 (0.250) | 1 | 0.185 | 3385 | 3/3 completed |
| Q27 | Agentic / multi-step synthesis | Agentic RAG | 9/12 (0.750) | 1 | 0.455 | 8181 | 3/3 completed |
| Q28 | Agentic / multi-step synthesis | Classical RAG | 6/15 (0.400) | 1 | 0.216 | 3316 | 3/3 completed |
| Q28 | Agentic / multi-step synthesis | Agentic RAG | 9/15 (0.600) | 1 | 0.804 | 8941 | 3/3 completed |
| Q29 | Unsupported / robustness | Classical RAG | 3/3 (1.000) | 1 | 0.258 | 2441 | 3/3 completed |
| Q29 | Unsupported / robustness | Agentic RAG | 3/3 (1.000) | 0 | 0.168 | 2402 | 3/3 completed |
| Q30 | Unsupported / robustness | Classical RAG | 3/3 (1.000) | 1 | 0.218 | 2113 | 3/3 completed |
| Q30 | Unsupported / robustness | Agentic RAG | 3/3 (1.000) | 0 | 0.238 | 2429 | 3/3 completed |

## Interpretation

On this 30-question test set, Agentic RAG achieved higher expected-fact coverage (87.7% vs. 75.3%), at the cost of approximately 2.4x mean latency and 2.6x total token usage. The strongest category-level gains appeared in embeddings/retrieval and agentic/multi-step synthesis. Agentic RAG adds iterative tool-based orchestration and reflection, while Classical RAG uses one retrieval and one generation call. These findings demonstrate a measured capability/overhead trade-off rather than universal superiority or a production-quality guarantee.

The quality signal is expected-fact coverage from case-insensitive substring matching, not accuracy or semantic grounding. Unsupported-response triggers are implementation signals rather than a semantic hallucination metric. Only Q15 and Q18 were empirically multi-step under the defined `search_documents()` criterion. The experiment uses live hosted API/model behavior and uncontrolled network, remote-load, and local-load conditions, so it cannot establish statistical significance or broad generalization.

## Protected Files and Git Status

This evaluation-only update does not modify production Agentic RAG behavior, API routes, ingestion, infrastructure, PostgreSQL/Qdrant code, frontend, CI/CD, README, or `backend/evaluation/run.py`. The experiment remains on branch `experiment/30-question-benchmark`; no commit, merge, or push was performed. `PROJECT_DEEP_DIVE.md` and `INTERNSHIP_REPORT_SOURCE.md` remain pre-existing local untracked documentation files and are intentionally excluded.

## Recommended Future Experiment

Use a larger fixed dataset, retain raw per-run answers and metrics, record corpus/model versions, control concurrency and network conditions where possible, and implement equivalent streaming paths before measuring TTFT.
