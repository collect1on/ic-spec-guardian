"""
Semantic Chunker: 語意分塊策略（Ollama 本地版）
"""
import sys
import os
from pathlib import Path

# 🔧 關鍵修復：確保 repo 根目錄在 sys.path 中
# 這樣無論從哪裡執行，都能用絕對路徑 import
repo_root = Path(__file__).resolve().parent.parent.parent  # 往上三層: services/chunking_service -> repo root
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from langchain_ollama import OllamaEmbeddings
from langchain_experimental.text_splitter import SemanticChunker


def get_embeddings():
    """使用本地 Ollama nomic-embed-text"""
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434"
    )


def semantic_chunk(chunks: list[dict], min_chars: int = 200) -> list[dict]:
    """
    對 parser 輸出的 chunks 做語意細切
    策略：規則 chunk (有 rule_id) 保持完整，長段落才細切
    """
    result = []
    splitter = None  # lazy init
    
    for chunk in chunks:
        text = chunk["text"]
        
        # 策略 1: 有 rule_id → 保持完整（規則邊界優先）
        if chunk.get("rule_id"):
            result.append(chunk)
            continue
        
        # 策略 2: 短 chunk → 保持完整
        if len(text) < min_chars:
            result.append(chunk)
            continue
        
        # 策略 3: 長且無結構 → 語意細切
        if splitter is None:
            embeddings = get_embeddings()
            splitter = SemanticChunker(
                embeddings,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=90
            )
        
        sub_texts = splitter.split_text(text)
        for i, sub_text in enumerate(sub_texts):
            result.append({
                "text": sub_text,
                "heading": chunk["heading"],
                "source": chunk["source"],
                "rule_id": chunk.get("rule_id"),
                "chunk_id": f"{chunk['chunk_id']}_sub{i}",
                "sub_index": i,
                "is_semantic_split": True
            })
    
    return result


if __name__ == "__main__":
    # 🔧 關鍵修復：用絕對路徑 import，避免 relative import 問題
    from services.chunking_service.parser import parse_document
    
    test_file = repo_root / "docs/compliance_rules/axi_interface_standard.md"
    print(f"📄 解析: {test_file}")
    raw_chunks = parse_document(str(test_file))
    print(f"   → 原始 chunks: {len(raw_chunks)}")
    
    print("\n🔍 語意分塊中（使用 Ollama nomic-embed-text）...")
    final_chunks = semantic_chunk(raw_chunks)
    
    print(f"\n📊 結果:")
    print(f"   原始: {len(raw_chunks)} → 細切後: {len(final_chunks)}")
    
    print(f"\n📋 預覽:")
    for i, c in enumerate(final_chunks[:3], 1):
        print(f"\n[Chunk {i}] {c['heading']}")
        print(f"   Rule ID: {c.get('rule_id', 'N/A')}")
        print(f"   字數: {len(c['text'])}")
        print(f"   內容: {c['text'][:100]}...")
