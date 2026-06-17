# services/agent_service/tracing.py
"""
Langfuse 4.x 埋點
追蹤：每次 LLM 呼叫的 latency、token 用量、合規判斷結果
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
        model="gemini-2.5-flash-lite",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )

# ── 帶完整追蹤的合規判斷 ─────────────────────────────────────
@observe(name="compliance_llm_call")
def traced_compliance_llm_call(
    spec_section: str,
    relevant_rules: list[dict],
    section_heading: str = ""
) -> dict:
    """
    帶 Langfuse 追蹤的單次合規判斷
    追蹤：latency、input/output token、判斷結果
    """
    client = get_client()

    llm = get_llm()

    rules_text = "\n\n---\n\n".join([
        f"規則 {r.get('rule_id', 'N/A')}：{r.get('text', '')}"
        for r in relevant_rules
    ])

    prompt = COMPLIANCE_CHECK_PROMPT.format(
        rules=rules_text,
        spec_section=spec_section
    )

    # 計時
    start = time.time()
    response = llm.invoke(prompt)
    latency = round(time.time() - start, 2)

    # 抽取 token 資訊
    usage = response.usage_metadata or {}
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens  = usage.get("total_tokens", 0)

    raw = (getattr(response, "content", None) or str(response)).strip()
    result = parse_llm_response(raw)

    # 寫進 Langfuse
    # client.update_current_generation(
    #     metadata={
    #         "section_heading": section_heading,
    #         "section_length":  len(spec_section),
    #         "rules_count":     len(relevant_rules),
    #         "model":           "gemini-2.5-flash",
    #         "latency_seconds": latency,
    #     },
    #     usage={
    #         "input":  input_tokens,
    #         "output": output_tokens,
    #         "total":  total_tokens,
    #         "unit":   "TOKENS",
    #     },
    #     output={
    #         "has_violation":         result.get("has_violation"),
    #         "rule_id":               result.get("rule_id"),
    #         "confidence":            result.get("confidence"),
    #         "requires_human_review": result.get("requires_human_review"),
    #     }
    # )
    
    
    client.update_current_generation(
    model="gemini-2.5-flash", 
    metadata={
        "section_heading": section_heading,
        "section_length":  len(spec_section),
        "rules_count":     len(relevant_rules),
        #"model":           "gemini-2.5-flash",
        "latency_seconds": latency,
    },
    usage_details={
        "input":  input_tokens,
        "output": output_tokens,
        "total":  total_tokens,
    },
    output={
        "has_violation":         result.get("has_violation"),
        "rule_id":               result.get("rule_id"),
        "confidence":            result.get("confidence"),
        "requires_human_review": result.get("requires_human_review"),
    }
)

    # 印出即時數字
    print(f"      📊 tokens: input={input_tokens}, output={output_tokens}, "
          f"latency={latency}s")

    return result


# ── 帶完整追蹤的審查流程 ─────────────────────────────────────
@observe(name="spec_review_full")
def traced_run_review(spec_content: str, spec_name: str) -> dict:
    """
    完整審查流程追蹤
    包含：總 latency、總 token、發現問題數
    """
    from services.agent_service.graph import app

    client = get_client()

    start = time.time()

    result = app.invoke({
        "spec_content":          spec_content,
        "spec_name":             spec_name,
        "spec_sections":         [],
        "current_section_index": 0,
        "issues_found":          [],
        "final_report":          ""
    })

    latency = round(time.time() - start, 2)

    client.update_current_generation(
        metadata={
            "spec_name":       spec_name,
            "spec_length":     len(spec_content),
            "total_issues":    len(result["issues_found"]),
            "latency_seconds": latency,
        },
        output={
            "total_issues":   len(result["issues_found"]),
            "has_violations": len(result["issues_found"]) > 0,
        }
    )

    print(f"\n📊 總 latency：{latency} 秒")

    return result

