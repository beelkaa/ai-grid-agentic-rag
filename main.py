from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from agent import chat_with_agent, stream_chat_with_agent
from db import init_db, create_tables, create_session
from ingest_real_content import run_ingestion

app = FastAPI()

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[int] = None

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    if not session_id:
        session_id = await create_session()

    question = request.question
    stream = stream_chat_with_agent(question, session_id)
    try:
        first_chunk = await anext(stream)
    except Exception:
        # Preserve the established JSON response when streaming cannot start.
        answer = await chat_with_agent(question, session_id)
        return {"answer": answer, "session_id": session_id}

    async def answer_stream():
        yield first_chunk
        async for chunk in stream:
            yield chunk

    return StreamingResponse(
        answer_stream(),
        media_type="text/plain",
        headers={"X-Session-Id": str(session_id)},
    )

@app.on_event("startup")
async def startup():
    await init_db()
    await create_tables()

@app.post("/ingest")
async def ingest():
    count = await run_ingestion()
    return{"status": "done", "chunk_ingested": count}