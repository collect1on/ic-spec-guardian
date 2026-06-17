#from langgraph.graph import StateGraph, END, interrupt
import operator, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated


from services.agent_service.tracing import langfuse   # 加這行


from services.retrieval_service.retriever import hybrid_search
from services.agent_service.tools import (
    split_into_sections, format_report
)
from langgraph.config import get_config
from services.agent_service.notifier import send_failure_email, send_success_email
class ReviewState(TypedDict):
    spec_content: str
    spec_name: str
    spec_sections: list[dict]
    current_index: int
    issues_found: Annotated[list, operator.add]
    final_report: str

# ── Stage 1: Node 1 ──────────────────────────────────────────
def parse_spec_node(state: ReviewState) -> dict:
    sections = split_into_sections(state["spec_content"])
    print(f"   📄 解析完成：{len(sections)} 個章節")
    return {"spec_sections": sections, "current_index": 0}

# ── Stage 1: Node 2 (loop, never pauses) ────────────────────
def check_compliance_node(state: ReviewState) -> dict:
    idx = state["current_index"]
    section = state["spec_sections"][idx]
    print(f"   🔍 [{idx+1}/{len(state['spec_sections'])}] {section['heading']}")

    relevant_rules = hybrid_search(section["text"], top_k=3)
    # relevant_rules = [r for r in relevant_rules if r.get("rule_id")]

    # # 如果過濾後完全沒有規則，直接跳過
    # if not relevant_rules:
    #     print(f"      ⏭️  跳過（無相關規則）")
    #     return {
    #         "current_index": idx + 1,
    #         "issues_found": [{
    #             "section":     section["heading"],
    #             "rule_id":     None,
    #             "description": "",
    #             "suggestion":  "",
    #             "confidence":  1.0,
    #             "status":      "auto_passed",
    #         }]
    #     }
    import os
    if os.getenv("USE_MOCK", "false").lower() == "true":
        from services.agent_service.mock_llm import mock_compliance_llm_call
      
        result = mock_compliance_llm_call(
            section["text"], relevant_rules, section_heading=section["heading"]
        )
        # trace = langfuse.trace(name="mock_compliance_check")
        # trace.span(
        #     name=section["heading"],
        #     input={"section": section["text"][:200]},
        #     output=result,
        #     metadata={"mock": True, "confidence": result.get("confidence")}
        # )    
        langfuse.flush()
    else:
        from services.agent_service.tracing import traced_compliance_llm_call
        result = traced_compliance_llm_call(
            section["text"], relevant_rules, section_heading=section["heading"]
        )

    # 根據信心分數標記 status，絕不在這裡 interrupt
    if not result.get("has_violation"):
        status = "auto_passed"
    elif result.get("confidence", 0) >= 0.75:
        status = "violation"
    else:
        status = "pending_review"
        
        
    # has_violation = result.get("has_violation")
    # confidence = result.get("confidence", 0)

    # if has_violation and confidence >= 0.75:
    #     status = "violation"
    # elif has_violation and confidence < 0.75:
    #     status = "pending_review"
    # elif not has_violation and confidence < 0.75:
    #     status = "pending_review"   # ← 補上這個盲點
    # else:                            # not has_violation and confidence >= 0.75
    #     status = "auto_passed"

    issue = {
        "section":     section["heading"],
        "rule_id":     result.get("rule_id"),
        "description": result.get("description", ""),
        "suggestion":  result.get("suggestion", ""),
        "confidence":  result.get("confidence", 0),
        "status":      status,
    }

    if status == "violation":
        print(f"      🔴 高信心違規：{result.get('rule_id')}")
    elif status == "pending_review":
        print(f"      🟡 低信心，待人工確認：{result.get('rule_id')}")
    else:
        print(f"      ✅ 無違規")

    return {"current_index": idx + 1, "issues_found": [issue]}

# ── Stage 2: 審查門控 ────────────────────────────────────────
def human_review_gate(state: ReviewState) -> dict:
    pending = [i for i in state["issues_found"] if i["status"] == "pending_review"]

    if not pending:
        print("   ✅ 無待審項目，直接生成報告")
        send_success_email()
        return {}

    print(f"   ⏸️  {len(pending)} 項待人工確認，凍結狀態...")
    send_failure_email()
    # interrupt() 凍結整個 graph，回傳給呼叫者
    # 外部系統拿到 thread_id 後，工程師決策完，再 invoke(None) 恢復
    interrupt({
        "pending_items": pending,
        "message": f"發現 {len(pending)} 項低信心違規，請逐一確認"
    })
    return {}

# ── Stage 3: 生成報告 ────────────────────────────────────────
# def generate_report_node(state: ReviewState) -> dict:
#     # 只報告 violation（含人工確認過的），跳過 auto_passed 和被否決的
#     reportable = [
#         i for i in state["issues_found"]
#         if i["status"] in ("violation", "confirmed")
#     ]
#     pending_left = [
#         i for i in state["issues_found"]
#         if i["status"] == "pending_review"
#     ]
#     if pending_left:
#         print(f"   ⚠️  警告：仍有 {len(pending_left)} 項未處理，標記為需人工跟進")

#     report = format_report(reportable, state.get("spec_name", "Spec"))
#     return {"final_report": report}
# def generate_report_node(state: ReviewState) -> dict:
#     # 去重：同 section + rule_id 只保留一筆
#     seen = set()
#     unique_issues = []
#     for issue in state["issues_found"]:
#         key = (issue.get("section"), issue.get("rule_id"))
#         if key not in seen:
#             seen.add(key)
#             unique_issues.append(issue)

#     reportable = [
#         i for i in unique_issues
#         if i["status"] in ("violation", "confirmed")
#     ]
#     pending_left = [
#         i for i in unique_issues
#         if i["status"] == "pending_review"
#     ]
#     if pending_left:
#         print(f"   ⚠️  警告：仍有 {len(pending_left)} 項未處理，標記為需人工跟進")

#     report = format_report(reportable, state.get("spec_name", "Spec"))
#     return {"final_report": report}

def generate_report_node(state: ReviewState) -> dict:
    priority = {"confirmed": 4, "violation": 3, "pending_review": 2, "auto_passed": 1}
    
    merged = {}
    for issue in state["issues_found"]:
        key = (issue.get("section"), issue.get("rule_id"))
        existing = merged.get(key)
        if existing is None or priority.get(issue["status"], 0) > priority.get(existing["status"], 0):
            merged[key] = issue

    unique_issues = list(merged.values())

    reportable = [i for i in unique_issues if i["status"] in ("violation", "confirmed")]
    pending_left = [i for i in unique_issues if i["status"] == "pending_review"]

    if pending_left:
        print(f"   ⚠️  警告：仍有 {len(pending_left)} 項未處理")

    report = format_report(reportable, state.get("spec_name", "Spec"))
    return {"final_report": report}
# ── 路由 ─────────────────────────────────────────────────────
def route_after_check(state: ReviewState) -> str:
    if state["current_index"] < len(state["spec_sections"]):
        return "continue"
    return "gate"

# ── 建立 Graph ───────────────────────────────────────────────
def build_graph(checkpointer=None):
    workflow = StateGraph(ReviewState)

    workflow.add_node("parse",  parse_spec_node)
    workflow.add_node("check",  check_compliance_node)
    workflow.add_node("gate",   human_review_gate)
    workflow.add_node("report", generate_report_node)

    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "check")
    workflow.add_conditional_edges(
        "check", route_after_check,
        {"continue": "check", "gate": "gate"}
    )
    workflow.add_edge("gate", "report")
    workflow.add_edge("report", END)

    return workflow.compile(checkpointer=checkpointer)

memory = MemorySaver()
app = build_graph(checkpointer=memory)