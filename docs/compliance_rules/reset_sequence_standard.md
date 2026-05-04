# Reset Sequence and Power-On Initialization Standard v1.2
**Document Owner**: SoC Integration Team
**Last Updated**: 2024-Q1
**Applicability**: All subsystem and IP-level reset sequence design

---

## RST-001 Reset Sequence Ordering
**類別**：Reset
**嚴重程度**：Critical

**規定**：
多個 IP 的 reset 釋放必須遵循以下強制順序：
1. Clock 穩定（PLL lock）
2. Memory（SRAM / register file）初始化完成
3. Peripheral IP reset 釋放
4. Master IP（CPU / DMA）reset 釋放

Master IP 的 reset 不得在 Peripheral IP 完成 reset 之前釋放。

**違規範例**：
"The CPU reset and peripheral reset are released simultaneously after PLL lock."
"The DMA engine reset is released 10 clock cycles after PLL lock, before the DMAC register interface is initialized."

**合規範例**：
"The CPU reset is released only after all peripheral IPs have completed their reset sequence and asserted their ready signals. The sequence is: PLL lock → peripheral reset release → peripheral ready → CPU reset release."

**原因**：
若 Master 在 Peripheral 尚未準備好前開始執行，初始化程式碼對 Peripheral 暫存器的第一筆存取將失敗，導致系統啟動失敗或進入不確定狀態。

---

## RST-002 Reset Assert Duration
**類別**：Reset
**嚴重程度**：Warning

**規定**：
IP 的 reset 信號必須至少保持 assert 狀態 16 個目的時鐘週期，以確保所有內部狀態機和暫存器完全復位。

**違規範例**：
"The IP reset is asserted for 2 clock cycles before being released."

**合規範例**：
"The IP reset is asserted for a minimum of 16 clock cycles of the IP's operating clock before de-assertion."

**原因**：
部分內部狀態機（如多級 pipeline）需要多個時鐘週期才能達到確定的初始狀態，過短的 reset pulse 可能導致狀態機停留在未定義的中間狀態。

---

## RST-003 Software-Triggered Reset Completion Handshake
**類別**：Reset
**嚴重程度**：Warning

**規定**：
軟體觸發的 IP reset（透過暫存器寫入）完成後，硬體必須提供 reset_done 狀態旗標供軟體輪詢或 interrupt 通知，禁止要求軟體以固定等待時間判斷 reset 是否完成。

**違規範例**：
"After writing 1 to RST_CTRL[0], software must wait 1ms before accessing any IP registers."

**合規範例**：
"After writing 1 to RST_CTRL[0], hardware will clear RST_CTRL[0] and set RST_STATUS[0] when the reset sequence is complete. Software polls RST_STATUS[0] before accessing IP registers."

**原因**：
固定等待時間在不同溫度、電壓、製程角（PVT corner）下不可靠，且浪費 CPU 時間；硬體握手機制是唯一可靠的做法。

---

## RST-004 Isolation Cell Requirement During Power Domain Reset
**類別**：Reset / Power
**嚴重程度**：Critical

**規定**：
當一個 power domain 處於 reset 或 power-off 狀態時，該 domain 的所有輸出信號必須經過 isolation cell 箝位（clamp）為固定值（通常為 0 或 1），防止 X 狀態或浮接信號傳播至 always-on domain。

**違規範例**：
"The video encoder power domain outputs are directly connected to the display controller inputs without isolation cells."

**合規範例**：
"All outputs from the video encoder power domain pass through ISO_AND isolation cells. The isolation enable signal is asserted before the power domain reset is asserted and de-asserted after power-up is complete."

**原因**：
Power domain 在 reset 或掉電期間其輸出為未定義狀態（X 或浮接），若無 isolation cell 隔離，X 狀態將傳播至 always-on domain，可能導致系統級功能錯誤或不必要的功耗。
