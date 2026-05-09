# tests/test_agent.py
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk
from services.agent_service.graph import app


def setup():
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


def run_agent(spec_path: str) -> dict:
    with open(spec_path, encoding="utf-8") as f:
        spec_content = f.read()
    return app.invoke({
        "spec_content":          spec_content,
        "spec_name":             Path(spec_path).name,
        "spec_sections":         [],
        "current_section_index": 0,
        "issues_found":          [],
        "final_report":          ""
    })


def test_violation_spec_finds_issues():
    """違規 Spec 必須找到至少 2 個問題"""
    setup()
    result = run_agent("docs/test_specs/violation_spec.md")
    issues = result["issues_found"]

    assert len(issues) >= 2, \
        f"應該找到至少 2 個違規，實際找到 {len(issues)} 個"

    rule_ids = [i["rule_violated"] for i in issues]
    assert "AXI-001" in rule_ids, \
        f"應該找到 AXI-001 違規，實際找到：{rule_ids}"


def test_compliant_spec_has_no_critical():
    """合規 Spec 不應有 Critical 問題"""
    setup()
    result = run_agent("docs/test_specs/compliant_spec.md")
    issues = result["issues_found"]

    critical_issues = [i for i in issues if i.get("severity") == "critical"]
    assert len(critical_issues) == 0, \
        f"合規 Spec 不應有 Critical 問題，實際發現：{critical_issues}"


def test_report_is_generated():
    """報告必須被產生，不能是空的"""
    setup()
    result = run_agent("docs/test_specs/violation_spec.md")
    assert result["final_report"], "final_report 不能是空的"
    assert len(result["final_report"]) > 50, "報告內容太短"


if __name__ == "__main__":
    print("🧪 執行 Agent Integration Tests")
    print("=" * 40)

    tests = [
        test_violation_spec_finds_issues,
        test_compliant_spec_has_no_critical,
        test_report_is_generated,
    ]

    passed = 0
    for test in tests:
        try:
            test()
            print(f"✅ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}：{e}")

    print(f"\n結果：{passed}/{len(tests)} 通過")