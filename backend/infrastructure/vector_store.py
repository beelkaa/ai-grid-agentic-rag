from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(host="localhost", port=6333)

def create_collection_if_not_exists():
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if "documents" not in collection_names:
        client.create_collection(
            collection_name="documents",
            vectors_config=VectorParams(size=3584, distance=Distance.COSINE),
        )

def add_documents(chunks: list[dict], embeddings: list[list[float]]):
    points = [
        PointStruct(id=chunks[i]["id"], 
                    vector=embeddings[i],
                      payload={
                            "text": chunks[i]["text"],
                            "category": chunks[i]["category"],
                            "url": chunks[i]["url"]
                        })
        for i in range(len(chunks))
    ]
    client.upsert(collection_name="documents", points=points)
