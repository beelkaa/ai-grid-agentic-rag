# AI GRID Assistant Frontend

This directory contains the React/Vite frontend for the AI GRID documentation assistant. It provides a floating chat widget that communicates with the FastAPI backend, displays streamed answers, and keeps each conversation associated with a PostgreSQL session.

For backend environment variables, Qdrant, ingestion, and the agent's ReAct loop, see the repository-level [README](../README.md).

## What the frontend does

The widget is implemented in `src/App.jsx` and includes:

- A collapsible floating assistant window and a full-screen mode.
- A responsive desktop and mobile layout.
- PostgreSQL-backed conversation sessions managed by the backend.
- Streaming answer rendering with a `Thinking` state while a request starts.
- Stop, retry, and copy actions for assistant responses.
- Markdown rendering for headings, lists, links, tables, and code blocks.
- KaTeX rendering for mathematical expressions in Markdown.
- Suggested documentation questions shown for a new conversation.

The frontend does not call AI Grid directly. API keys and database credentials stay on the backend.

## Requirements

Install the following tools:

- Node.js and npm. Using [NVM](https://github.com/nvm-sh/nvm) is recommended for Linux and WSL.
- Python and the backend virtual environment.
- Docker and Docker Compose for PostgreSQL and Qdrant.
- A configured backend with an AI Grid API key.

Check the installed versions:

```bash
node --version
npm --version
python3 --version
docker --version
docker compose version
```

### Installing Node.js with NVM

If NVM is not installed, run:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install --lts
nvm alias default 'lts/*'
```

Verify that the shell uses the NVM-managed executables:

```bash
command -v node
command -v npm
nvm current
```

On Linux or WSL, the paths should normally point into `~/.nvm/`. Avoid mixing an NVM installation with an unrelated Windows Node.js installation.

## Install frontend dependencies

From the frontend directory:

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm install
```

The main dependencies are:

| Package | Purpose |
| --- | --- |
| React and React DOM | UI rendering |
| Vite | Development server and production bundling |
| `marked` | Markdown parsing |
| `marked-katex-extension` and KaTeX | Mathematical expression rendering |
| Oxlint | JavaScript and React linting |

## Run the application locally

The frontend requires the backend and its data services to be running. Use separate terminals for Docker services, the backend, and the frontend.

### 1. Start PostgreSQL and Qdrant

From the repository root:

```bash
cd /home/belkacem/agentic-rag
docker compose up -d
docker compose ps
```

The compose file exposes PostgreSQL at `localhost:5432` for chat sessions and Qdrant at `localhost:6333` for document retrieval.

Check their health:

```bash
curl http://localhost:6333/healthz
docker compose exec -T postgres pg_isready -U postgres -d agentic_rag
```

The local Qdrant data is stored in `qdrant_storage/`. The backend must also have a populated `documents` collection before documentation questions can be answered reliably. See the root README for ingestion instructions.

### 2. Start the FastAPI backend

In another terminal:

```bash
cd /home/belkacem/agentic-rag
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend is available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

Test the backend directly:

```bash
curl -i -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  --data '{"question":"What is AI GRID?"}'
```

The backend normally responds as a streamed `text/plain` response and sends the session ID in the `X-Session-Id` response header. The frontend reads both the stream and that header. If streaming cannot start, the backend can return JSON containing `answer` and `session_id`.

### 3. Start the Vite development server

In a third terminal:

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm run dev -- --host 0.0.0.0
```

Open <http://localhost:5173/> in a browser.

### How the Vite proxy works

The frontend sends requests to `/api/chat`. In development, `vite.config.js` rewrites that path and proxies it to `http://localhost:8000/chat`:

```text
Browser:  http://localhost:5173/api/chat
Vite:     removes /api
Backend:  http://localhost:8000/chat
```

This keeps the backend URL out of frontend request code and avoids local cross-origin issues. Test the proxy directly with:

```bash
curl -i -X POST http://localhost:5173/api/chat \
  -H 'Content-Type: application/json' \
  --data '{"question":"What is AI GRID?"}'
```

## Frontend commands

Run these commands from `ai-grid-widget/`:

```bash
# Start Vite with hot module replacement
npm run dev

# Check the frontend with Oxlint
npm run lint

# Create the production bundle
npm run build

# Serve the production bundle locally
npm run preview
```

The production build is written to `dist/`. `dist/` and `node_modules/` are ignored by Git.

Stop Vite with `Ctrl+C` in its terminal. This does not stop FastAPI or the Docker containers. Stop the backend separately with `Ctrl+C`, and stop PostgreSQL and Qdrant with:

```bash
cd /home/belkacem/agentic-rag
docker compose down
```

## Request and response lifecycle

When a user submits a question:

1. `App.jsx` sends `POST /api/chat` with the question and the current `session_id`, if one exists.
2. Vite proxies the request to FastAPI during development.
3. FastAPI creates a session when necessary and starts the backend agent.
4. The backend streams answer text. The frontend progressively updates the assistant message as chunks arrive.
5. FastAPI returns the session ID in `X-Session-Id`; the frontend stores it for the next question.
6. The completed exchange is saved by the backend in PostgreSQL.

The browser never receives the AI Grid API key, Langfuse credentials, PostgreSQL password, or Qdrant credentials.

## Troubleshooting

### The widget does not load or shows a blank page

1. Open browser developer tools with `F12`.
2. Check **Console** for JavaScript or rendering errors.
3. Check **Network** for failed JavaScript, CSS, or `/api/chat` requests.
4. Confirm that Vite is running at `http://localhost:5173/`.
5. Run `npm run build` to catch bundling errors.

The primary files for UI behavior and appearance are:

```text
src/App.jsx       # Components, state, requests, streaming, and interactions
src/App.css       # Widget layout and component styles
src/index.css     # Global styles and font configuration
src/main.jsx      # React application entry point
```

### The request fails or the widget cannot connect

Confirm that FastAPI is running and that the proxy works:

```bash
curl -i http://localhost:8000/docs
curl -i -X POST http://localhost:5173/api/chat \
  -H 'Content-Type: application/json' \
  --data '{"question":"What is AI GRID?"}'
```

If the proxy target needs to change, edit `vite.config.js`. The current target is `http://localhost:8000`.

### The backend returns an error

Inspect the FastAPI terminal and verify the supporting services:

```bash
cd /home/belkacem/agentic-rag
docker compose ps
docker compose logs postgres
docker compose logs qdrant
curl http://localhost:6333/collections
```

Also confirm that the root `.env` contains the required AI Grid and PostgreSQL variables. The frontend itself does not read `.env` values.

### The answer is empty or stops unexpectedly

Check the `/api/chat` response in the browser Network panel. The expected development response is streamed text. Also check that:

- FastAPI is reachable on port `8000`.
- The backend has an available AI Grid model and API key.
- The `documents` Qdrant collection exists for documentation questions.
- PostgreSQL is available so the session can be created and saved.

## Production build and iframe integration

Build the static frontend:

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm run build
```

Copy the contents of `dist/` to the directory served by your web server, for example:

```bash
scp -r dist/* user@ai-grid-vm:/var/www/ai-grid-assistant/
```

The widget can be embedded in another page with an iframe:

```html
<iframe
  src="/ai-grid-assistant/"
  title="AI GRID Assistant"
  style="position: fixed; right: 24px; bottom: 24px; width: 430px; height: 680px; border: 0; z-index: 9999;"
></iframe>
```

For production, configure the web server so the frontend can reach FastAPI through a secure reverse proxy. Do not expose backend secrets in the frontend bundle. Configure HTTPS, authentication, CORS or same-origin routing, and appropriate rate limits at the deployment boundary.

## Complete quick start

Terminal 1, services and backend:

```bash
cd /home/belkacem/agentic-rag
docker compose up -d
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2, frontend:

```bash
cd /home/belkacem/agentic-rag/ai-grid-widget
npm install
npm run dev -- --host 0.0.0.0
```

Then open <http://localhost:5173/>.
