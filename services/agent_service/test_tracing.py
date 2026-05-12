# services/agent_service/test_tracing.py
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk
from services.agent_service.tracing import traced_run_review, langfuse

def setup_retrieval():
    rules_dir = repo_root / "docs/compliance_rules"
    all_chunks = []
    for md_file in sorted(rules_dir.glob("*.md")):
        chunks = semantic_chunk(parse_document(str(md_file)))
        all_chunks.extend(chunks)
    for i, c in enumerate(all_chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(all_chunks)
    build_bm25_index(all_chunks)
    print(f"✅ {len(all_chunks)} 個規範 chunks 就緒\n")

if __name__ == "__main__":
    print("🔍 測試 Langfuse 追蹤...")
    setup_retrieval()

    spec_path = repo_root / "docs/test_specs/violation_spec.md"
    with open(spec_path, encoding="utf-8") as f:
        spec_content = f.read()

    print("🚀 執行審查（帶 Langfuse 追蹤）...")
    result = traced_run_review(spec_content, "violation_spec.md")

    print(f"\n✅ 審查完成")
    print(f"   發現問題：{len(result['issues_found'])} 個")
    print(f"\n📊 最終報告：")
    print(result["final_report"])

    # 確保 trace 送出
    langfuse.flush()
    print("\n✅ Langfuse trace 已送出，請去 https://cloud.langfuse.com 查看")