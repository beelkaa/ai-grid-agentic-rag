from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def get_embeddings(text: str) -> list[float]:
    """
    Get embeddings for the given text using the AI Grid API.

    Args:
        text (str): The input text to get embeddings for.
    """
    api_key = os.getenv("AI_GRID_API_KEY")
    base_url = os.getenv("AI_GRID_BASE_URL")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "Alibaba-NLP/gte-Qwen2-7B-instruct",
                "input": text
            }
        )
    return response.json()["data"][0]["embedding"]