# AXI Interface Design Standard v2.1
**Document Owner**: SoC Architecture Team
**Last Updated**: 2024-Q1
**Applicability**: All AXI4 / AXI4-Lite / AXI4-Stream interfaces in MTK internal IP

---

## AXI-001 Burst Mode Support
**類別**：Interface
**嚴重程度**：Critical

**規定**：
所有 AXI4 Master 介面必須同時支援 INCR 和 WRAP 兩種 burst 模式。

**違規範例**：
"The master interface supports INCR burst mode only."

**合規範例**：
"The master interface supports both INCR and WRAP burst modes as required by AXI4 specification."

**原因**：
公司 legacy cache IP（L2C-310）使用 WRAP burst 進行 cache line fill，若 Master 不支援 WRAP 模式將導致與 cache 子系統不相容，產生功能錯誤。

---

## AXI-002 AXI4-Lite AWLEN / ARLEN Constraint
**類別**：Interface
**嚴重程度**：Critical

**規定**：
使用 AXI4-Lite 介面時，AWLEN 與 ARLEN 必須固定為 0，禁止使用任何 burst 傳輸。

**違規範例**：
"The AXI-Lite configuration interface supports burst transfers with AWLEN up to 15 for efficient register block access."

**合規範例**：
"The AXI-Lite configuration interface uses single-beat transfers only. AWLEN and ARLEN are tied to 0."

**原因**：
AXI4-Lite 協定規格明確禁止 burst 傳輸，AWLEN ≠ 0 屬於協定違規，會導致 interconnect 行為未定義。

---

## AXI-003 Outstanding Transaction Limit
**類別**：Interface
**嚴重程度**：Warning

**規定**：
AXI4 Master 介面的最大 outstanding write transaction 數量不得超過 16（即 AWID 空間不得超過 4-bit）。

**違規範例**：
"The master supports up to 256 outstanding write transactions with 8-bit AWID."

**合規範例**：
"The master supports up to 16 outstanding write transactions. AWID is 4-bit wide."

**原因**：
公司標準 interconnect（NIC-400）的 transaction ID table 每個 Master port 僅分配 16 個 entry，超過將導致 interconnect 拒絕新的 transaction。

---

## AXI-004 Write Response Ordering
**類別**：Interface
**嚴重程度**：Critical

**規定**：
AXI4 Master 在收到前一筆 write transaction 的 BRESP 之前，不得對相同位址發出第二筆 write transaction。

**違規範例**：
"The master may issue multiple write transactions to the same address without waiting for BRESP, relying on the interconnect to maintain order."

**合規範例**：
"The master tracks outstanding write transactions per address and waits for BRESP before issuing a subsequent write to the same address."

**原因**：
不同 outstanding write 到相同位址在通過 interconnect 時順序無法保證，可能導致最終寫入值錯誤。

---

## AXI-005 WSTRB Usage for Partial Write
**類別**：Interface
**嚴重程度**：Warning

**規定**：
進行 partial write（不對齊或小於資料總線寬度的寫入）時，Master 必須正確設定 WSTRB，不得將未使用的 byte lane 的 WSTRB 設為 1。

**違規範例**：
"For all write transactions, WSTRB is set to all-ones (0xFF for 64-bit bus) regardless of actual byte enables."

**合規範例**：
"WSTRB reflects the valid byte lanes for each write beat. For a 32-bit write on a 64-bit bus, only the corresponding 4 bits of WSTRB are asserted."

**原因**：
WSTRB 全 1 且資料未填入的 byte lane 可能覆蓋相鄰記憶體內容，導致資料損毀。
