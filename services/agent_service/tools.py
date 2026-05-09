# services/agent_service/tools.py
import json
import os
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from services.retrieval_service.retriever import hybrid_search
from services.agent_service.prompts import COMPLIANCE_CHECK_PROMPT, REPORT_GENERATION_PROMPT
from dotenv import load_dotenv

load_dotenv()

# ── LLM 初始化 ──────────────────────────────────────────────
def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )

# ── Spec 解析 ────────────────────────────────────────────────
def split_into_sections(spec_content: str) -> list[dict]:
    """把 Spec 文字依標題切成章節"""
    sections = []
    current_heading = "Overview"
    current_lines = []

    for line in spec_content.split("\n"):
        if re.match(r"^#{1,3} ", line):
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    sections.append({
                        "heading": current_heading,
                        "text": text
                    })
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # 最後一個章節
    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append({
                "heading": current_heading,
                "text": text
            })

    return sections


# ── LLM 合規判斷 ─────────────────────────────────────────────
def compliance_llm_call(spec_section: str, relevant_rules: list[dict]) -> dict:
    """
    呼叫 LLM 判斷章節是否違規
    回傳結構化 dict
    """
    llm = get_llm()

    # 格式化規則文字
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

    # 解析 JSON
    return parse_llm_response(raw)


def parse_llm_response(raw: str) -> dict:
    """解析 LLM 輸出的 JSON，加上 Hallucination 控制"""
    # 清理可能的 markdown code block
    clean = re.sub(r"```json\s*|\s*```", "", raw).strip()

    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        # 解析失敗，標記需要人工審查
        return {
            "has_violation": False,
            "rule_id": None,
            "description": "",
            "suggestion": "",
            "confidence": 0.0,
            "requires_human_review": True,
            "parse_error": True
        }

    # Hallucination 控制 1：信心不足
    if result.get("confidence", 1.0) < 0.7:
        result["requires_human_review"] = True

    # Hallucination 控制 2：沒有規則 ID 但宣稱有違規
    if result.get("has_violation") and not result.get("rule_id"):
        result["has_violation"] = False
        result["requires_human_review"] = True

    return result


# ── 報告生成 ─────────────────────────────────────────────────
def format_report(issues: list[dict], spec_name: str = "待審查 Spec") -> str:
    """把所有 issues 彙整成可讀報告"""
    if not issues:
        return f"✅ {spec_name} 審查完成：未發現任何合規問題。"

    critical = [i for i in issues if i.get("severity") == "critical"]
    warning  = [i for i in issues if i.get("severity") != "critical"]

    lines = [
        f"⚠️ {spec_name} 審查報告",
        f"發現 {len(issues)} 個問題（Critical: {len(critical)}, Warning: {len(warning)}）",
        "=" * 50
    ]

    for i, issue in enumerate(issues, 1):
        lines += [
            f"\n[問題 {i}] {'🔴 Critical' if issue.get('severity') == 'critical' else '🟡 Warning'}",
            f"章節：{issue.get('section', 'N/A')}",
            f"違反規則：{issue.get('rule_violated', 'N/A')}",
            f"描述：{issue.get('description', 'N/A')}",
            f"建議：{issue.get('suggestion', 'N/A')}",
        ]
        if issue.get("requires_human_review"):
            lines.append("⚠️ 建議人工確認")

    return "\n".join(lines)