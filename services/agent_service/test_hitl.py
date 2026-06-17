"""
本地驗證 Two-Stage HITL 流程
不需要 FastAPI，直接呼叫 graph
"""
import os, sys
from pathlib import Path

os.environ["USE_MOCK"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk
from services.agent_service.graph import app

repo_root = Path(__file__).resolve().parent.parent.parent

def setup():
    rules_dir = repo_root / "docs/compliance_rules"
    chunks = []
    for f in sorted(rules_dir.glob("*.md")):
        chunks.extend(semantic_chunk(parse_document(str(f))))
    for i, c in enumerate(chunks):
        c["id"] = i
    init_collection()
    upsert_chunks(chunks)
    build_bm25_index(chunks)
    print(f"✅ {len(chunks)} chunks 就緒\n")

if __name__ == "__main__":
    setup()

    spec_path = repo_root / "docs/test_specs/violation_spec.md"
    spec_content = spec_path.read_text(encoding="utf-8")

    thread_id = "test-hitl-001"
    config = {"configurable": {"thread_id": thread_id}}

    print("=" * 50)
    print("Stage 1+2：執行全量掃描")
    print("=" * 50)

    result = app.invoke({
        "spec_content":  spec_content,
        "spec_name":     "violation_spec.md",
        "spec_sections": [],
        "current_index": 0,
        "issues_found":  [],
        "final_report":  "",
    }, config)

    state = app.get_state(config)
    issues = state.values["issues_found"]

    pending = [i for i in issues if i["status"] == "pending_review"]
    violations = [i for i in issues if i["status"] == "violation"]

    print(f"\n掃描結果：{len(violations)} 個高信心違規，{len(pending)} 個待確認")

    if pending:
        print("\n" + "=" * 50)
        print("模擬工程師決策")
        print("=" * 50)

        # 模擬：全部確認為違規
        updated = []
        for issue in issues:
            if issue["status"] == "pending_review":
                print(f"  確認違規：{issue['section']} / {issue['rule_id']}")
                updated.append({**issue, "status": "confirmed", "human_note": "工程師確認"})
            else:
                updated.append(issue)

        app.update_state(config, {"issues_found": updated}, as_node="gate")
        check = app.get_state(config)
        for i in check.values["issues_found"]:
            print(f"  DEBUG status: {i['status']} | {i['section']} | {i.get('rule_id')}")
        print("\n" + "=" * 50)
        print("Stage 3：恢復執行，生成報告")
        print("=" * 50)

        result = app.invoke(None, config)

    print("\n📊 最終報告：")
    print(result.get("final_report", "（無報告）"))