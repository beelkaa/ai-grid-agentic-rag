# AI Grid Agentic RAG Assistant

A custom agentic RAG assistant for AI Grid documentation, with a FastAPI backend, Qdrant retrieval, PostgreSQL conversation history, and a React/Vite chat widget.

## Architecture Overview

The assistant implements a ReAct loop directly in `agent.py`; it does not use LangChain or LangGraph.

1. **Reason**: the hosted AI Grid LLM receives the system prompt and conversation history. It decides whether to answer immediately or request a tool call.
2. **Act**: the backend executes the requested tool. The available tools are `search_documents` for semantic retrieval and `list_available_models` for the live model catalog.
3. **Observe**: the tool result is appended to the conversation as a tool message linked to the original tool call.
4. **Reflect**: after the non-streaming agent run, a separate model call reviews the draft answer against the retrieved context and recent conversation.

The reflection step is a strict sufficiency gate. It returns structured JSON with `sufficient` and `missing` fields. If the answer is not sufficiently grounded, the backend replaces it with a fixed message saying that the official documentation does not contain enough information. The agent is limited to the configured maximum number of iterations and forces a final answer if that limit is reached.

> **Streaming note:** the `/chat` endpoint normally uses `stream_chat_with_agent`, which streams the final model output. The current streaming path does not call `reflect()`; the reflection gate is applied by `chat_with_agent` when the backend falls back to its non-streaming response path.

## Tech Stack

| Component | Tool or library |
| --- | --- |
| API server | FastAPI, Uvicorn |
| Agent orchestration | Hand-written Python ReAct loop in `agent.py` |
| Hosted inference | AI Grid OpenAI-compatible chat completions API |
| Embeddings | AI Grid embeddings API using `Alibaba-NLP/gte-Qwen2-7B-instruct` |
| Vector database | Qdrant (`qdrant-client`) |
| Relational database | PostgreSQL 16 with `asyncpg` |
| Retrieval | Cosine similarity, top 5 configured results, optional category filter |
| Web scraping and chunking | `requests`, BeautifulSoup, YAML source configuration |
| Observability | Langfuse tracing and generation usage reporting |
| Backend configuration | YAML with Pydantic validation, `python-dotenv` |
| Frontend | React 19, Vite 8 |
| Frontend rendering | `marked`, KaTeX, `marked-katex-extension` |
| Frontend linting | Oxlint |
| Evaluation | `run_eval.py`, keyword-based expected/forbidden fact checks |

## Project Structure

```text
.
├── agent.py                    # Tools, ReAct loop, reflection, chat entry points
├── db.py                       # PostgreSQL pool, sessions, and message persistence
├── embeddings.py               # AI Grid embedding API client
├── ingest_real_content.py      # Scrape, chunk, embed, and upsert documentation
├── main.py                     # FastAPI /chat and /ingest endpoints
├── scraper.py                  # Source loading, HTML extraction, and chunking
├── vector_store.py             # Qdrant client, collection, and document upserts
├── run_eval.py                 # Repeated evaluation cases and fact scoring
├── requirements.txt             # Pinned Python dependencies
├── docker-compose.yml           # PostgreSQL and Qdrant services
├── config/
│   ├── config.yaml             # Models, agent limits, retrieval, and timeouts
│   ├── categories.yaml          # Retrieval category definitions
│   ├── sources.yaml             # Documentation URLs to ingest
│   └── loader.py                # Pydantic-backed YAML loader
├── prompt/
│   └── system.txt              # Grounding, search, safety, and response policy
├── ai-grid-widget/
│   ├── src/App.jsx              # Chat UI, streaming, retry, stop, and copy actions
│   ├── src/App.css              # Widget styling and responsive layout
│   ├── src/index.css             # Global styles and fonts
│   ├── src/main.jsx              # React entry point
│   ├── public/                  # Static icons and favicon
│   ├── package.json             # Frontend scripts and dependencies
│   ├── vite.config.js           # /api proxy to FastAPI
│   └── FRONTEND_DOCUMENTATION.md # Frontend setup and integration notes
├── scratch/                    # Small manual API and integration experiments
├── qdrant_storage/             # Local Qdrant data, ignored by Git
└── postgres_data/              # Local database data, ignored by Git
```

## Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Node.js and npm
- An AI Grid API key with access to chat completions and embeddings
- Network access to the configured AI Grid documentation URLs for ingestion

### Environment variables

There is currently no `.env.example` file. Create a `.env` file in the project root. The backend loads it with `python-dotenv`.

```dotenv
# Required hosted AI Grid inference settings
AI_GRID_API_KEY=your-ai-grid-api-key
AI_GRID_BASE_URL=https://your-ai-grid-api-base-url
DEFAULT_MODEL_LABEL=Qwen/Qwen3.8-27B

# Required PostgreSQL connection settings
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agentic_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Optional Langfuse tracing settings
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
```

`AI_GRID_BASE_URL` should be the API base URL used by the project, without a duplicated path. The code appends `/chat/completions`, `/embeddings`, and `/models` to it. `DEFAULT_MODEL_LABEL` controls chat inference; the embedding model is currently fixed in `embeddings.py`. Qdrant is currently configured directly as `localhost:6333` in `vector_store.py`, so it has no environment variable in the current implementation.

### Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start PostgreSQL and Qdrant

From the repository root:

```bash
docker compose up -d
docker compose ps
```

The compose file exposes PostgreSQL on `localhost:5432` and Qdrant on `localhost:6333`. PostgreSQL uses the values in `.env`, or these compose defaults:

- Database: `agentic_rag`
- User: `postgres`
- Password: `postgres`

Useful health checks:

```bash
curl http://localhost:6333/healthz
docker compose exec -T postgres pg_isready -U postgres -d agentic_rag
```

### Prepare the vector collection and ingest documentation

The configured sources are in `config/sources.yaml`. Ingestion fetches each page, removes common non-content HTML elements, chunks text into approximately 800-character pieces, generates embeddings through AI Grid, and upserts the chunks into the `documents` Qdrant collection.

The current code expects the `documents` collection to already exist. If it is not already present in your Qdrant data, create it with the configured 3584-dimensional cosine vector settings before running ingestion, or call the existing `create_collection_if_not_exists()` helper from a setup script.

With the backend dependencies active, start FastAPI and call the ingestion endpoint:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
curl -X POST http://localhost:8000/ingest
```

Alternatively, run the ingestion module directly:

```bash
python ingest_real_content.py
```

### Start the backend

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API is available at `http://localhost:8000`. Interactive API documentation is at `http://localhost:8000/docs`.

The main endpoints are:

- `POST /chat` with `{"question": "...", "session_id": 123}`. Omit `session_id` to create a new PostgreSQL session. Normal responses stream as `text/plain` and include `X-Session-Id`; startup failures can fall back to JSON with `answer` and `session_id`.
- `POST /ingest` to scrape and index the configured sources.

### Start the React widget

In a separate terminal:

```bash
cd ai-grid-widget
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173/`. Vite proxies `/api/*` to the backend, so the widget sends `/api/chat` to FastAPI's `/chat` endpoint.

Frontend checks and production build:

```bash
cd ai-grid-widget
npm run lint
npm run build
npm run preview
```

The production bundle is generated in `ai-grid-widget/dist/`. See [ai-grid-widget/FRONTEND_DOCUMENTATION.md](ai-grid-widget/FRONTEND_DOCUMENTATION.md) for iframe integration notes and additional troubleshooting commands.

## How the Agent Works

For a normal documentation question, `chat_with_agent()` loads the session's recent messages from PostgreSQL and prepends `prompt/system.txt`. It then calls the configured AI Grid chat model with the available tools and `tool_choice: "auto"`.

- If the model can answer from the conversation, it can return text directly.
- If the question needs AI Grid-specific facts, the system prompt tells it to request `search_documents`. The tool embeds the query, searches Qdrant, optionally filters by `company`, `getting-started`, `models`, or `pricing`, and returns text with source URLs.
- For questions asking which models are available or supported, `_is_model_catalog_question()` bypasses the ReAct loop and calls the AI Grid `/models` endpoint directly, then formats the returned IDs.
- The model can search repeatedly, up to `agent.max_iterations` (5 by default). If the limit is reached, the backend makes a final model call with `tool_choice: "none"`.
- In the non-streaming path, `reflect()` checks completeness, grounding, unsupported names, and off-topic content. An insufficient verdict rejects the draft and returns the fixed documentation-insufficiency response.
- The streaming path exposes only final answer text to the widget and persists the completed exchange to PostgreSQL. Obvious off-topic questions are rejected early in that path.

The assistant is grounded by `prompt/system.txt`, which instructs it to use official AI Grid documentation, separate facts from recommendations, cover multi-part questions, and avoid inventing unsupported information.

## Running Evaluations

`run_eval.py` initializes PostgreSQL and runs seven representative questions. Each case is executed three times by default (`RUNS_PER_QUESTION = 3`) to expose inconsistent answers.

Run it from the repository root with the backend environment active and PostgreSQL, Qdrant, the `documents` collection, and the AI Grid API available:

```bash
source venv/bin/activate
python run_eval.py
```

The cases cover OCR and image inputs, model capabilities and comparisons, refund-policy uncertainty, pricing, plan/model recommendations, and a forbidden model-name regression. `score_answer()` performs case-insensitive substring checks for expected facts and verifies that forbidden facts do not appear. The script prints every answer, each run's boolean fact scores, and a `hits/3` summary for every fact.

This is a lightweight behavioral harness, not a semantic evaluator. A passing keyword score does not prove that an answer is fully correct, well cited, or safe.

## Known Limitations and Not Implemented

- The agent orchestration is custom Python; LangChain and LangGraph are intentionally not used.
- The streaming path currently skips `reflect()`, so the strict answer-sufficiency gate only applies to the non-streaming `chat_with_agent()` path.
- Only the first tool call in a model response is executed, even if a response contains multiple tool calls.
- Tool names and arguments are trusted from the model response; unknown tools or malformed JSON are not converted into user-friendly errors.
- The embedding model is hard-coded in `embeddings.py`, while the chat model is selected with `DEFAULT_MODEL_LABEL`.
- Qdrant connection details are hard-coded to `localhost:6333`, and collection creation is not wired into startup or ingestion.
- Ingestion is synchronous in its scraping and upsert orchestration, has no scheduled refresh, and skips chunks whose embedding requests fail.
- Scraped chunks are simple paragraph groups capped at approximately 800 characters; there is no reranking, deduplication policy, or document versioning.
- PostgreSQL tables are created at startup, but there are no migrations, authentication, authorization, rate limits, or multi-tenant isolation.
- The API has no explicit CORS configuration and is intended to be used locally or behind a properly configured reverse proxy.
- Evaluation is based on substring presence/absence and does not measure retrieval precision, citation correctness, latency, or token cost.
- API keys, database credentials, and Langfuse credentials must remain on the backend and must never be placed in the React frontend.

## Stopping Services

```bash
docker compose down
```

This stops PostgreSQL and Qdrant containers. Their persistent data remains in the configured Docker volume and local `qdrant_storage/` directory unless those are removed separately.
