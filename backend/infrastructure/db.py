import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

async def create_tables():
    async with pool.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

async def save_message(session_id: int, role: str, content: str):
    async with pool.acquire() as connection:
        await connection.execute(
            "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
            session_id, role, content
        )

async def get_messages(session_id: int) -> list[dict]:
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT role, content FROM messages WHERE session_id = $1 ORDER BY created_at, id",
            session_id
        )
        return [{"role": row["role"], "content": row["content"]} for row in rows]

async def session_exists(session_id: int) -> bool:
    async with pool.acquire() as connection:
        return await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM sessions WHERE id = $1)",
            session_id
        )

async def list_sessions() -> list[dict]:
    async with pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT
                sessions.id,
                COALESCE(
                    NULLIF(SUBSTRING(first_user.content FROM 1 FOR 40), ''),
                    'New chat'
                ) AS title,
                COALESCE(last_message.created_at, sessions.created_at) AS last_updated
            FROM sessions
            LEFT JOIN LATERAL (
                SELECT content
                FROM messages
                WHERE session_id = sessions.id AND role = 'user'
                ORDER BY created_at, id
                LIMIT 1
            ) AS first_user ON TRUE
            LEFT JOIN LATERAL (
                SELECT created_at
                FROM messages
                WHERE session_id = sessions.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            ) AS last_message ON TRUE
            ORDER BY last_updated DESC
        """)
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "last_updated": row["last_updated"],
            }
            for row in rows
        ]

async def delete_session(session_id: int) -> bool:
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                "DELETE FROM messages WHERE session_id = $1",
                session_id
            )
            deleted = await connection.fetchrow(
                "DELETE FROM sessions WHERE id = $1 RETURNING id",
                session_id
            )
            return deleted is not None
    
async def create_session() -> int:
    async with pool.acquire() as connection:
        row = await connection.fetchrow("INSERT INTO sessions DEFAULT VALUES RETURNING id")
        return row["id"]