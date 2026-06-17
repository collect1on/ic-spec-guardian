# services/agent_service/mock_llm.py
"""
Mock LLM：測試 LangGraph 流程用，不呼叫真實 API
回傳預設的合規判斷結果，可設定 confidence 觸發 HITL
"""

# 預設每個章節的回傳結果
# key 是章節標題的關鍵字，value 是模擬的 LLM 判斷
MOCK_RESPONSES = {
    "AXI Interface": {
        "has_violation": True,
        "rule_id": "AXI-001",
        "description": "（Mock）AXI4 Master 只支援 INCR，缺少 WRAP",
        "suggestion": "（Mock）加入 WRAP burst 支援",
        "confidence": 0.5,   # ← 低信心，觸發 HITL
        "requires_human_review": True,
    },
    "Clock Domain": {
        "has_violation": True,
        "rule_id": "CLK-001",
        "description": "（Mock）只有一級 synchronizer",
        "suggestion": "（Mock）改成兩級",
        "confidence": 0.4,   # ← 低信心，觸發 HITL
        "requires_human_review": True,
    },
    "Power": {
        "has_violation": True,
        "rule_id": "RST-001",
        "description": "（Mock）reset 同時釋放",
        "suggestion": "（Mock）依序釋放",
        "confidence": 0.9,   # ← 高信心，自動標記
        "requires_human_review": False,
    },
    "default": {
        "has_violation": False,
        "rule_id": None,
        "description": "",
        "suggestion": "",
        "confidence": 0.95,
        "requires_human_review": False,
    }
}

def mock_compliance_llm_call(
    spec_section: str,
    relevant_rules: list[dict],
    section_heading: str = ""
) -> dict:
    """
    Mock 版合規判斷
    根據章節標題關鍵字回傳預設結果
    不呼叫任何外部 API
    """
    print(f"      🤖 [MOCK] 判斷章節：{section_heading}")

    for keyword, response in MOCK_RESPONSES.items():
        if keyword == "default":
            continue
        if keyword.lower() in section_heading.lower():
            result = response.copy()
            print(f"      🤖 [MOCK] 回傳：has_violation={result['has_violation']}, "
                  f"confidence={result['confidence']}")
            return result

    result = MOCK_RESPONSES["default"].copy()
    print(f"      🤖 [MOCK] 回傳：無違規")
    return result

from langfuse import observe

@observe(name="mock_compliance_check")
def traced_mock_compliance_llm_call(
    spec_section: str,
    relevant_rules: list[dict],
    section_heading: str = ""
) -> dict:
    return mock_compliance_llm_call(spec_section, relevant_rules, section_heading=section_heading)