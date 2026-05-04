# Clock Domain Crossing Design Standard v1.4
**Document Owner**: Digital Design Methodology Team
**Last Updated**: 2024-Q1
**Applicability**: All synchronous digital logic with multiple clock domains

---

## CLK-001 Synchronizer Requirement for Single-bit Signals
**類別**：Clock
**嚴重程度**：Critical

**規定**：
跨時鐘域的單 bit 控制信號（enable、valid、request 等）必須經過至少兩級 D flip-flop synchronizer，且兩級 FF 必須使用目的時鐘域的時鐘驅動。

**違規範例**：
"The request signal is directly connected from the 200MHz domain to the 100MHz domain."
"The enable signal passes through a single FF before entering the 400MHz clock domain."

**合規範例**：
"The request signal passes through a 2-stage synchronizer clocked by the destination 100MHz clock before entering the 100MHz domain."

**原因**：
單級 synchronizer 無法將亞穩態（metastability）發生機率降至可接受水準（< 1 failure per 10 years），兩級為業界最低標準。

---

## CLK-002 Multi-bit Signal CDC Handling
**類別**：Clock
**嚴重程度**：Critical

**規定**：
跨時鐘域的多 bit 資料信號（data bus、counter value 等）禁止直接使用 multi-bit synchronizer，必須採用以下其中一種方式：
（a）Gray code encoding（適用於連續遞增/遞減的計數器）
（b）Handshake protocol（適用於一般控制信號）
（c）Async FIFO（適用於資料流）

**違規範例**：
"The 32-bit data bus is synchronized using a 2-stage synchronizer array in the destination clock domain."

**合規範例（方法 a）**：
"The 8-bit read pointer is Gray-coded before crossing to the write clock domain, then binary-decoded after synchronization."

**合規範例（方法 c）**：
"Data transfer between the 200MHz producer and 100MHz consumer is implemented using an asynchronous FIFO with independent read/write pointers."

**原因**：
多 bit 信號各 bit 的亞穩態解析時間不同，直接同步會導致接收端採樣到中間過渡狀態，造成資料錯誤。

---

## CLK-003 Clock Gating Enable Signal Timing
**類別**：Clock
**嚴重程度**：Critical

**規定**：
Clock gating cell 的 enable 信號必須在被門控時鐘的低電位期間穩定（即 enable 信號相對於被門控時鐘的 setup/hold window 必須在時鐘低電位期間）。Enable 信號必須由 ICG（Integrated Clock Gating）cell 驅動，不得使用純組合邏輯門控時鐘。

**違規範例**：
"The clock is gated using: gated_clk = clk AND enable, where enable is combinational logic output."

**合規範例**：
"The clock is gated using a library ICG cell (CKLNQD1) with the enable signal registered in the low phase of the clock."

**原因**：
組合邏輯門控時鐘會產生 glitch，導致後級 FF 誤觸發；ICG cell 利用 latch 特性確保時鐘切換只在低電位發生，消除 glitch。

---

## CLK-004 Async Reset Synchronization
**類別**：Clock / Reset
**嚴重程度**：Critical

**規定**：
非同步 reset 信號在釋放（de-assert）時必須經過 reset synchronizer（至少兩級 FF），確保 reset 的釋放與目的時鐘同步。Reset 的 assert 可以是非同步的。

**違規範例**：
"The global reset signal is directly de-asserted asynchronously across all clock domains simultaneously."

**合規範例**：
"Each clock domain has a dedicated reset synchronizer. The reset synchronizer asserts reset asynchronously and de-asserts reset synchronously with the local clock after two FF stages."

**原因**：
非同步 reset 釋放可能在不同 FF 的 recovery time 邊界發生，導致部分邏輯退出 reset 而其他邏輯仍在 reset 狀態，造成系統狀態不一致（reset distribution skew 問題）。
