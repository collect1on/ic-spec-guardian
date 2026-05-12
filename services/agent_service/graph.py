# services/agent_service/graph.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
import sys
from pathlib import Path
from services.agent_service.tracing import traced_compliance_llm_call
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))
from services.agent_service.tracing import traced_compliance_llm_call
from services.retrieval_service.retriever import hybrid_search
from services.agent_service.tools import (
    split_into_sections,
    compliance_llm_call,
    format_report
)

# ── State 定義 ───────────────────────────────────────────────
class ReviewState(TypedDict):
    # 輸入
    spec_content: str
    spec_name: str

    # 過程
    spec_sections: list[dict]
    current_section_index: int
    issues_found: Annotated[list, operator.add]

    # 輸出
    final_report: str

# ── 節點定義 ─────────────────────────────────────────────────
def parse_spec_node(state: ReviewState) -> dict:
    """Node 1：把 Spec 切成章節"""
    sections = split_into_sections(state["spec_content"])
    print(f"   📄 解析完成：{len(sections)} 個章節")
    return {
        "spec_sections": sections,
        "current_section_index": 0
    }


# def check_compliance_node(state: ReviewState) -> dict:
#     """Node 2：對當前章節做合規檢查"""
#     idx = state["current_section_index"]
#     section = state["spec_sections"][idx]

#     print(f"   🔍 檢查章節 [{idx+1}/{len(state['spec_sections'])}]：{section['heading']}")

#     # 搜尋相關規則
#     relevant_rules = hybrid_search(section["text"], top_k=3)

#     # LLM 判斷
#     result = compliance_llm_call(section["text"], relevant_rules)

#     issues = []
#     if result.get("has_violation"):
#         severity = "critical" if result.get("confidence", 0) > 0.8 else "warning"
#         issues.append({
#             "section":              section["heading"],
#             "rule_violated":        result.get("rule_id"),
#             "description":          result.get("description"),
#             "suggestion":           result.get("suggestion"),
#             "severity":             severity,
#             "confidence":           result.get("confidence"),
#             "requires_human_review": result.get("requires_human_review", False)
#         })
#         print(f"      ⚠️  發現違規：{result.get('rule_id')}")
#     else:
#         print(f"      ✅ 無違規")

#     return {
#         "issues_found": issues,
#         "current_section_index": idx + 1
#     }

def check_compliance_node(state: ReviewState) -> dict:
    idx = state["current_section_index"]
    section = state["spec_sections"][idx]

    print(f"   🔍 檢查章節 [{idx+1}/{len(state['spec_sections'])}]：{section['heading']}")

    relevant_rules = hybrid_search(section["text"], top_k=3)

    # 換成 traced 版本
    #result = traced_compliance_llm_call(section["text"], relevant_rules)
    result = traced_compliance_llm_call(
    section["text"],
    relevant_rules,
    section_heading=section["heading"]  # 新增這個
    )
    issues = []
    if result.get("has_violation"):
        severity = "critical" if result.get("confidence", 0) > 0.8 else "warning"
        issues.append({
            "section":               section["heading"],
            "rule_violated":         result.get("rule_id"),
            "description":           result.get("description"),
            "suggestion":            result.get("suggestion"),
            "severity":              severity,
            "confidence":            result.get("confidence"),
            "requires_human_review": result.get("requires_human_review", False)
        })
        print(f"      ⚠️  發現違規：{result.get('rule_id')}")
    else:
        print(f"      ✅ 無違規")

    return {
        "issues_found":          issues,
        "current_section_index": idx + 1
    }
def generate_report_node(state: ReviewState) -> dict:
    """Node 3：彙整所有問題，產出報告"""
    report = format_report(state["issues_found"], state.get("spec_name", "Spec"))
    return {"final_report": report}


# ── 條件分支 ─────────────────────────────────────────────────
def should_continue_checking(state: ReviewState) -> str:
    """還有章節：繼續 / 全部查完：產出報告"""
    if state["current_section_index"] < len(state["spec_sections"]):
        return "continue"
    return "done"


# ── 建立 Graph ───────────────────────────────────────────────
def build_graph():
    workflow = StateGraph(ReviewState)

    workflow.add_node("parse_spec",       parse_spec_node)
    workflow.add_node("check_compliance", check_compliance_node)
    workflow.add_node("generate_report",  generate_report_node)

    workflow.set_entry_point("parse_spec")
    workflow.add_edge("parse_spec", "check_compliance")
    workflow.add_conditional_edges(
        "check_compliance",
        should_continue_checking,
        {
            "continue": "check_compliance",
            "done":     "generate_report"
        }
    )
    workflow.add_edge("generate_report", END)

    return workflow.compile()

app = build_graph()