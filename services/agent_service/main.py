# services/agent_service/main.py
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index, hybrid_search
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk
from services.agent_service.graph import app


def setup_retrieval():
    """載入規範文件到 Qdrant + BM25"""
    rules_dir = repo_root / "docs/compliance_rules"
    all_chunks = []
    for md_file in sorted(rules_dir.glob("*.md")):
        raw = parse_document(str(md_file))
        chunks = semantic_chunk(raw)
        all_chunks.extend(chunks)
    for i, c in enumerate(all_chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(all_chunks)
    build_bm25_index(all_chunks)
    print(f"✅ {len(all_chunks)} 個規範 chunks 就緒\n")


def run_review(spec_path: str):
    with open(spec_path, encoding="utf-8") as f:
        spec_content = f.read()

    spec_name = Path(spec_path).name
    print(f"📋 開始審查：{spec_name}")
    print("=" * 50)

    result = app.invoke({
        "spec_content":         spec_content,
        "spec_name":            spec_name,
        "spec_sections":        [],
        "current_section_index": 0,
        "issues_found":         [],
        "final_report":         ""
    })

    print("\n" + "=" * 50)
    print("📊 審查報告")
    print("=" * 50)
    print(result["final_report"])

    return result


if __name__ == "__main__":
    print("🚀 IC Spec Guardian - Agent 測試")
    print("=" * 50)

    # 初始化檢索
    setup_retrieval()

    # 測試 1：合規 Spec（應該沒問題）
    print("\n【測試 1】合規 Spec")
    run_review("docs/test_specs/compliant_spec.md")

    print("\n" + "=" * 50)

    # 測試 2：違規 Spec（應該找到問題）
    print("\n【測試 2】違規 Spec")
    run_review("docs/test_specs/violation_spec.md")