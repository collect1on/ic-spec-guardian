# evaluation/agent_eval.py
"""
Agent 合規審查評測框架
評測目標：LangGraph Agent 的違規偵測能力
指標：Precision、Recall、F1
與 RAGAS 的關係：
  - RAGAS 驗證「規則找得到嗎」（檢索品質）
  - 本評測驗證「違規判斷得對嗎」（推理品質）
"""
import sys
import json
from pathlib import Path
from datetime import datetime

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from services.retrieval_service.vectorstore import init_collection, upsert_chunks
from services.retrieval_service.retriever import build_bm25_index
from services.chunking_service.parser import parse_document
from services.chunking_service.chunker import semantic_chunk
from services.agent_service.graph import app

# ── Ground Truth 定義 ────────────────────────────────────────
# 這是你的 ground truth：每份 Spec 應該找到哪些違規
GROUND_TRUTH = [
    {
        "spec_file":           "docs/test_specs/violation_spec.md",
        "spec_name":           "violation_spec",
        "expected_rule_ids":   {"AXI-001", "CLK-001", "RST-001"},
        "expected_clean":      {"Overview", "1. Overview"},  # 這些章節應該無違規
        "description":         "包含 3 個明確違規的測試 Spec"
    },
    {
        "spec_file":           "docs/test_specs/compliant_spec.md",
        "spec_name":           "compliant_spec",
        "expected_rule_ids":   set(),  # 完全合規，不應有任何違規
        "expected_clean":      None,   # 全部章節都應該無違規
        "description":         "完全合規的測試 Spec，不應有任何 Critical 違規"
    }
]

# ── 初始化檢索 ───────────────────────────────────────────────
def setup_retrieval():
    print("📂 載入規範文件...")
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

# ── 跑 Agent ─────────────────────────────────────────────────
def run_agent(spec_file: str) -> dict:
    with open(repo_root / spec_file, encoding="utf-8") as f:
        spec_content = f.read()
    return app.invoke({
        "spec_content":          spec_content,
        "spec_name":             Path(spec_file).name,
        "spec_sections":         [],
        "current_section_index": 0,
        "issues_found":          [],
        "final_report":          ""
    })

# ── 計算指標 ─────────────────────────────────────────────────
def compute_metrics(
    found_rule_ids: set,
    expected_rule_ids: set
) -> dict:
    """
    Precision = 找到的違規中，真正是違規的比例（避免誤報）
    Recall    = 實際違規中，被找到的比例（避免漏報）
    F1        = 兩者的調和平均
    """
    tp = len(found_rule_ids & expected_rule_ids)  # 正確找到
    fp = len(found_rule_ids - expected_rule_ids)  # 誤報（找到但不應該）
    fn = len(expected_rule_ids - found_rule_ids)  # 漏報（應該找到但沒找到）

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
        "tp":        tp,
        "fp":        fp,
        "fn":        fn,
    }

# ── 評測單一 Spec ────────────────────────────────────────────
def evaluate_one(case: dict) -> dict:
    print(f"\n{'='*50}")
    print(f"📋 評測：{case['spec_name']}")
    print(f"   {case['description']}")
    print(f"   預期違規：{case['expected_rule_ids'] or '無'}")
    print(f"{'='*50}")

    # 跑 Agent
    result = run_agent(case["spec_file"])
    issues = result["issues_found"]

    # 提取 Agent 找到的 rule_id
    found_rule_ids = {
        i["rule_violated"]
        for i in issues
        if i.get("rule_violated") and i.get("severity") == "critical"
    }

    # 計算指標
    metrics = compute_metrics(found_rule_ids, case["expected_rule_ids"])

    # 詳細分析
    correctly_found = found_rule_ids & case["expected_rule_ids"]
    missed          = case["expected_rule_ids"] - found_rule_ids
    false_alarms    = found_rule_ids - case["expected_rule_ids"]

    # 顯示結果
    print(f"\n📊 結果")
    print(f"   找到的違規：{found_rule_ids or '無'}")
    print(f"   正確找到：  {correctly_found or '無'}  ✅")
    print(f"   漏報：      {missed or '無'}  ❌")
    print(f"   誤報：      {false_alarms or '無'}  ⚠️")
    print(f"\n   Precision : {metrics['precision']:.3f}")
    print(f"   Recall    : {metrics['recall']:.3f}")
    print(f"   F1        : {metrics['f1']:.3f}")

    return {
        "spec_name":       case["spec_name"],
        "description":     case["description"],
        "expected":        list(case["expected_rule_ids"]),
        "found":           list(found_rule_ids),
        "correctly_found": list(correctly_found),
        "missed":          list(missed),
        "false_alarms":    list(false_alarms),
        "metrics":         metrics,
        "all_issues":      issues,
    }

# ── 儲存報告 ─────────────────────────────────────────────────
def save_report(results: list[dict]):
    report_dir = repo_root / "evaluation/reports"
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = report_dir / f"agent_eval_{timestamp}.json"

    # 計算整體指標（所有 case 的平均）
    avg_precision = sum(r["metrics"]["precision"] for r in results) / len(results)
    avg_recall    = sum(r["metrics"]["recall"]    for r in results) / len(results)
    avg_f1        = sum(r["metrics"]["f1"]        for r in results) / len(results)

    report = {
        "timestamp": timestamp,
        "summary": {
            "total_specs":     len(results),
            "avg_precision":   round(avg_precision, 4),
            "avg_recall":      round(avg_recall, 4),
            "avg_f1":          round(avg_f1, 4),
        },
        "details": results
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 報告已儲存：{report_path}")
    return report

# ── 主流程 ───────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("🧪 IC Spec Guardian - Agent 合規審查評測")
    print("=" * 55)
    print("""
評測說明：
  RAGAS 評測  → 驗證「規則找得到嗎」（檢索品質）
  本評測      → 驗證「違規判斷得對嗎」（推理品質）
""")

    setup_retrieval()

    # 逐一評測每個 Spec
    results = []
    for case in GROUND_TRUTH:
        result = evaluate_one(case)
        results.append(result)

    # 整體摘要
    print(f"\n{'='*55}")
    print("📊 整體評測摘要")
    print(f"{'='*55}")

    avg_precision = sum(r["metrics"]["precision"] for r in results) / len(results)
    avg_recall    = sum(r["metrics"]["recall"]    for r in results) / len(results)
    avg_f1        = sum(r["metrics"]["f1"]        for r in results) / len(results)

    print(f"  評測 Spec 數量：{len(results)}")
    print(f"  平均 Precision：{avg_precision:.3f}  {'█' * int(avg_precision * 20)}")
    print(f"  平均 Recall   ：{avg_recall:.3f}  {'█' * int(avg_recall * 20)}")
    print(f"  平均 F1       ：{avg_f1:.3f}  {'█' * int(avg_f1 * 20)}")

    # 判斷是否通過
    if avg_recall >= 0.8 and avg_precision >= 0.8:
        print(f"\n✅ Agent 評測通過（Recall ≥ 0.8，Precision ≥ 0.8）")
    else:
        print(f"\n❌ Agent 評測未通過，建議檢查 prompt 或規則文件")
        if avg_recall < 0.8:
            print(f"   → Recall 偏低（{avg_recall:.3f}），可能有漏報")
        if avg_precision < 0.8:
            print(f"   → Precision 偏低（{avg_precision:.3f}），可能有誤報")

    # 存報告
    save_report(results)

    # 對照 RAGAS 結果說明
    print(f"""
{'='*55}
📌 評測層次說明
{'='*55}
  RAGAS context_recall    = 1.000  → 規則檢索完整
  RAGAS faithfulness      = 0.954  → 答案忠實於規則
  Agent violation recall  = {avg_recall:.3f}  → 違規偵測能力
  Agent violation precision = {avg_precision:.3f}  → 誤報控制能力

  兩層評測共同保證系統品質：
  「找得到規則」且「判斷得對違規」
""")


if __name__ == "__main__":
    main()