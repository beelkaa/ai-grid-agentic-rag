import asyncio
from pathlib import Path

from backend.ingestion.scraper import scrape_all, chunk_text, load_sources, generate_chunk_id
from backend.infrastructure.embeddings import get_embeddings
from backend.infrastructure.vector_store import add_documents


async def run_ingestion():
    sources_path = Path(__file__).resolve().parents[1] / "config" / "sources.yaml"
    sources = load_sources(str(sources_path))
    docs = scrape_all(sources)

    all_chunks = []
    for doc in docs:
        chunks = chunk_text(doc["text"])
        for chunk in chunks:
            all_chunks.append({
                "id": generate_chunk_id(doc["url"], chunk),
                "text": chunk,
                "category": doc["category"],
                "url": doc["url"]
            })
  
    vectors = []
    valid_chunks = []
    for chunk in all_chunks:
        try:
            vector = await get_embeddings(chunk["text"])
            vectors.append(vector)
            valid_chunks.append(chunk)
        except Exception as e:
            print(f"Skipping embedding for chunk from {chunk['url']}: {e}")

    add_documents(valid_chunks, vectors)
    return len(valid_chunks)


if __name__ == "__main__":
    asyncio.run(run_ingestion())