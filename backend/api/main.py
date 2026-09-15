from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from backend.core.agent import chat_with_agent, stream_chat_with_agent
from backend.infrastructure.vector_store import create_collection_if_not_exists
from backend.infrastructure.db import (
    init_db,
    create_tables,
    create_session,
    delete_session,
    get_messages,
    list_sessions,
    session_exists,
)
from backend.ingestion.run import run_ingestion

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
        media_type="text/event-stream",
        headers={"X-Session-Id": str(session_id)},
    )

@app.on_event("startup")
async def startup():
    await init_db()
    await create_tables()
    create_collection_if_not_exists()

@app.post("/ingest")
async def ingest():
    count = await run_ingestion()
    return{"status": "done", "chunk_ingested": count}

@app.get("/sessions")
async def sessions():
    return await list_sessions()

@app.get("/sessions/{session_id}/messages")
async def session_messages(session_id: int):
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return await get_messages(session_id)

@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session_endpoint(session_id: int):
    if not await delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")