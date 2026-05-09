#!/usr/bin/env python3
"""
Retrieval Service 端對端測試（索引全部規範文件）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk
from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index, hybrid_search

def run_pipeline():
    print("="*50)
    print("🚀 IC Spec Guardian - Retrieval Pipeline Test")
    print("="*50)
    
    # 🔧 關鍵修改：解析所有規範文件
    rules_dir = Path("docs/compliance_rules")
    all_chunks = []
    
    for md_file in rules_dir.glob("*.md"):
        print(f"\n📂 解析: {md_file.name}")
        raw_chunks = parse_document(str(md_file))
        final_chunks = semantic_chunk(raw_chunks)
        print(f"   → {md_file.name}: {len(final_chunks)} chunks")
        all_chunks.extend(final_chunks)
    
    print(f"\n📊 總計: {len(all_chunks)} chunks")
    
    # 寫入 Qdrant
    print("\n💾 Step 2: 初始化 Qdrant & Upsert...")
    init_collection()
    
    # 為 chunks 補上 id 欄位（供 BM25 使用）
    for i, c in enumerate(all_chunks):
        c["id"] = i
    
    upsert_chunks(all_chunks)
    
    # 建立 BM25 索引
    print("\n🔍 Step 3: 建立 BM25 倒排索引...")
    build_bm25_index(all_chunks)
    
    # Hybrid Search 測試
    print("\n🧪 Step 4: Hybrid Search 測試")
    queries = [
        ("AXI4 Master 必須支援哪些 burst 模式？", "🔍 AXI 語意查詢"),
        ("AXI-001", "🔑 AXI 規則編號查詢"),
        ("cross clock domain synchronizer", "🔍 CDC 語意查詢"),
        ("CLK-001", "🔑 CLK 規則編號查詢"),
        ("reset duration 16 cycles", "🔍 Reset 語意+數字查詢"),
    ]
    
    for q, desc in queries:
        print(f"\n{desc}")
        print(f"Query: {q}")
        results = hybrid_search(q, top_k=3)
        for i, r in enumerate(results, 1):
            rule = r.get("rule_id", "N/A")
            heading = r.get("heading", "")[:60]
            print(f"   {i}. [{rule}] {heading} (Score: {r['score']:.3f})")
            
    print("\n✅ Retrieval Pipeline 測試完成！")

if __name__ == "__main__":
    run_pipeline()
