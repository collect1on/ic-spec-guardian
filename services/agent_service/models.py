# services/agent_service/models.py
from typing import TypedDict, Annotated
import operator

class ComplianceIssue(TypedDict):
    section: str          # 哪個章節
    rule_violated: str    # 違反哪條規則 (e.g. "AXI-001")
    description: str      # 違規描述
    suggestion: str       # 修改建議
    severity: str         # "critical" or "warning"
    confidence: float     # 0.0-1.0
    requires_human_review: bool

class ReviewState(TypedDict):
    # 輸入
    spec_content: str
    
    # 解析後的章節列表
    spec_sections: list[dict]  # [{"heading": str, "text": str}]
    
    # 迴圈計數器
    current_section_index: int
    
    # 累積的問題（Annotated + operator.add 讓每次迴圈可以 append）
    issues_found: Annotated[list[ComplianceIssue], operator.add]
    
    # 最終報告
    final_report: str