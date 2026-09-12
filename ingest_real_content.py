import asyncio
from scraper import scrape_all, chunk_text, load_sources, generate_chunk_id
from embeddings import get_embeddings
from vector_store import add_documents


async def run_ingestion():
    sources = load_sources("config/sources.yaml")
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