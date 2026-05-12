# services/agent_service/tracing.py
"""
Langfuse 4.x 埋點：追蹤所有 LLM 呼叫的 latency、token、cost
使用 @observe decorator + get_client() API
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from langfuse import Langfuse, observe, get_client
from langchain_google_genai import ChatGoogleGenerativeAI
from services.agent_service.prompts import COMPLIANCE_CHECK_PROMPT
from services.agent_service.tools import parse_llm_response

# ── Langfuse 初始化 ──────────────────────────────────────────
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )

# ── 帶追蹤的合規判斷 ─────────────────────────────────────────
@observe(name="compliance_llm_call")
def traced_compliance_llm_call(
    spec_section: str,
    relevant_rules: list[dict]
) -> dict:
    """
    帶 Langfuse 追蹤的合規判斷
    每次呼叫都會記錄：latency、input、output、metadata
    """
    client = get_client()
    client.update_current_generation(
        metadata={
            "section_length": len(spec_section),
            "rules_count":    len(relevant_rules),
            "model":          "gemini-2.5-flash",
        }
    )

    llm = get_llm()

    rules_text = "\n\n---\n\n".join([
        f"規則 {r.get('rule_id', 'N/A')}：{r.get('text', '')}"
        for r in relevant_rules
    ])

    prompt = COMPLIANCE_CHECK_PROMPT.format(
        rules=rules_text,
        spec_section=spec_section
    )

    response = llm.invoke(prompt)
    raw = (getattr(response, "content", None) or str(response)).strip()
    result = parse_llm_response(raw)

    # 記錄輸出結果
    client.update_current_generation(
        output={
            "has_violation":         result.get("has_violation"),
            "rule_id":               result.get("rule_id"),
            "confidence":            result.get("confidence"),
            "requires_human_review": result.get("requires_human_review"),
        }
    )

    return result


# ── 帶追蹤的完整審查流程 ─────────────────────────────────────
@observe(name="spec_review_full")
def traced_run_review(spec_content: str, spec_name: str) -> dict:
    """
    最外層 trace，包含完整審查流程
    Langfuse 會自動追蹤所有子 span
    """
    from services.agent_service.graph import app

    client = get_client()
    client.update_current_generation(
        metadata={
            "spec_name":     spec_name,
            "spec_length":   len(spec_content),
            "spec_sections": spec_content.count("\n##"),
        },
        #tags=["compliance_check"]
    )

    start = time.time()

    result = app.invoke({
        "spec_content":          spec_content,
        "spec_name":             spec_name,
        "spec_sections":         [],
        "current_section_index": 0,
        "issues_found":          [],
        "final_report":          ""
    })

    latency = time.time() - start

    # 記錄整體結果
    client.update_current_generation(
        output={
            "total_issues":    len(result["issues_found"]),
            "latency_seconds": round(latency, 2),
            "has_violations":  len(result["issues_found"]) > 0,
        }
    )

    return result