# services/agent_service/prompts.py

COMPLIANCE_CHECK_PROMPT = """你是 IC 設計合規審查專家。

以下是從規範文件檢索到的相關規則：
{rules}

以下是待審查的 Spec 章節：
{spec_section}

請判斷這個章節是否違反上述規則。

重要規定：
- 每個判斷必須引用具體規則 ID（如 AXI-001）
- 如果規範文件中找不到對應規則，回答 has_violation: false 並標記 requires_human_review: true
- 不要憑空推斷，只根據提供的規則判斷

🔑 信心分數 (confidence) 評分標準（請嚴格遵守）：
- 1.0：字面完全違反規則，且無任何例外條款、效能妥協或歷史驗證說明。
- 0.7~0.9：明顯違規，但部分描述模糊或需額外上下文。
- 0.4~0.6：字面提及規則元素，但同時提出工程妥協、動態調整、Legacy 驗證、Debug 路徑或效能/功耗優化。此類情況必須標記 requires_human_review: true。
- 0.0~0.3：規則不適用或資訊嚴重不足。

請只輸出以下 JSON，不要有任何其他文字：
{{
  "has_violation": true or false,
  "rule_id": "規則ID 或 null",
  "description": "違規的具體描述 或 空字串",
  "suggestion": "修改建議 或 空字串",
  "confidence": 0.0 到 1.0,
  "requires_human_review": true or false
}}"""


REPORT_GENERATION_PROMPT = """你是 IC 設計合規審查專家。

以下是審查發現的所有問題：
{issues}

請產生一份清晰的審查報告，包含：
1. 總結（發現幾個問題，嚴重程度分布）
2. 每個問題的詳細說明
3. 建議的修改優先順序

請用繁體中文回答。"""