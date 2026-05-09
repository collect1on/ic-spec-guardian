"""
Hybrid Search 實作：BM25 + Vector + RRF
"""
import re
from rank_bm25 import BM25Okapi
from .vectorstore import client, COLLECTION_NAME, embed_text, vector_search

_bm25_index = None
_bm25_corpus = []
_bm25_ids = []

def _tokenize(text: str) -> list[str]:
    """基礎分詞：保留英文單字與中文字元"""
    return re.findall(r'\b\w+\b|[^\x00-\x7F]', text.lower())

def build_bm25_index(chunks: list[dict]):
    """從 chunks 建立 BM25 倒排索引"""
    global _bm25_index, _bm25_corpus, _bm25_ids
    _bm25_corpus = [c["text"] for c in chunks]
    _bm25_ids = [c.get("id", i) for i, c in enumerate(chunks)]
    tokenized_corpus = [_tokenize(t) for t in _bm25_corpus]
    _bm25_index = BM25Okapi(tokenized_corpus)
    print(f"✅ BM25 索引已建立，語料數：{len(_bm25_corpus)}")

def bm25_search(query: str, top_k: int = 10) -> list[dict]:
    """Sparse Search：關鍵字匹配檢索"""
    if _bm25_index is None:
        raise RuntimeError("BM25 索引尚未初始化，請先執行 build_bm25_index()")
    
    query_tokens = _tokenize(query)
    scores = _bm25_index.get_scores(query_tokens)
    
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    # 🔧 回傳格式與 vector_search 一致：id, score, text + payload 欄位
    results = []
    for i in ranked_indices:
        if scores[i] > 0:
            # 從原始 chunks 找對應 payload（簡化：用索引對應）
            idx = _bm25_ids.index(i) if i in _bm25_ids else None
            results.append({
                "id": _bm25_ids[i] if i < len(_bm25_ids) else i,
                "score": float(scores[i]),
                "text": _bm25_corpus[i]
                # 可視需求補上 heading/rule_id 等欄位
            })
    return results

def reciprocal_rank_fusion(
    dense: list, sparse: list, top_k: int, k: int = 60
) -> list[dict]:
    """RRF 合併：score = 1/(k+rank+1)"""
    fusion_scores = {}
    
    for rank, doc in enumerate(dense):
        fusion_scores[doc["id"]] = fusion_scores.get(doc["id"], 0) + 1 / (k + rank + 1)
    for rank, doc in enumerate(sparse):
        fusion_scores[doc["id"]] = fusion_scores.get(doc["id"], 0) + 1 / (k + rank + 1)
        
    sorted_ids = sorted(fusion_scores.keys(), key=lambda x: fusion_scores[x], reverse=True)
    
    # 合併 payload（以 dense 為主）
    doc_lookup = {d["id"]: d for d in dense}
    for s in sparse:
        doc_lookup.setdefault(s["id"], s)
        
    return [doc_lookup[sid] for sid in sorted_ids[:top_k]]

def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """Hybrid Search 統一入口"""
    dense_res = vector_search(query, top_k=top_k * 2)
    sparse_res = bm25_search(query, top_k=top_k * 2)
    return reciprocal_rank_fusion(dense_res, sparse_res, top_k)
