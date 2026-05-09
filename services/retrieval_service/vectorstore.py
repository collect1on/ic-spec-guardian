"""
Qdrant 向量資料庫操作（相容 qdrant-client >= 1.7.0）
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_ollama import OllamaEmbeddings
from typing import List

COLLECTION_NAME = "compliance_rules"
EMBEDDER = OllamaEmbeddings(model="nomic-embed-text")
client = QdrantClient(host="localhost", port=6333)

def init_collection():
    """建立 Qdrant Collection，若已存在則安全跳過"""
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )
        print(f"✅ Qdrant Collection '{COLLECTION_NAME}' 已建立")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"ℹ️ Collection '{COLLECTION_NAME}' 已存在，跳過建立")
        else:
            raise

def embed_text(text: str) -> List[float]:
    """呼叫 Ollama 產生 embedding"""
    return EMBEDDER.embed_query(text)

def upsert_chunks(chunks: list[dict]) -> list[dict]:
    """將 chunks 寫入 Qdrant"""
    points = []
    for i, chunk in enumerate(chunks):
        vec = embed_text(chunk["text"])
        points.append(PointStruct(
            id=i,
            vector=vec,
            payload={
                "text": chunk["text"],
                "source": chunk.get("source"),
                "heading": chunk.get("heading"),
                "rule_id": chunk.get("rule_id"),
                "chunk_id": chunk.get("chunk_id", f"chunk_{i}")
            }
        ))
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"✅ 成功 Upsert {len(points)} 個 chunks 至 Qdrant")
    return chunks

def vector_search(query: str, top_k: int = 10) -> list[dict]:
    """Dense Search：語意相似度檢索（相容 qdrant-client >= 1.7.0）"""
    query_vec = embed_text(query)
    
    # 🔧 新版 API: query_points 取代 search
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )
    
    # 🔧 新版回傳結構: response.points 而非直接 list
    points = response.points if hasattr(response, 'points') else []
    
    return [{"id": p.id, "score": p.score, **p.payload} for p in points]
