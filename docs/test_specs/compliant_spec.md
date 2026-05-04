# Memory Controller & Display Subsystem Spec v2.0
**Version**: 2.0
**Target**: Subsystem Integration
**Description**: Architectural specification for the memory controller and low-power display pipeline.

## 1. Overview
This document defines the interface, clock domain crossing (CDC), power management, and reset sequencing for the integrated memory controller and display subsystem. All design choices strictly adhere to company internal design standards.

## 2. AXI Interface Specification
The subsystem implements an AXI4 Master interface for DDR access and an AXI4-Lite interface for CPU configuration.

- **Burst Support**: The AXI4 Master interface supports both INCR and WRAP burst modes as required by the AXI4 specification.
- **AXI-Lite Constraint**: The configuration port uses AXI4-Lite protocol. AWLEN and ARLEN are hardwired to 0 to enforce single-beat transfers only.
- **Outstanding Limit**: The controller supports up to 16 outstanding write transactions. AWID is implemented as 4-bit wide.
- **Write Ordering**: The interface tracks outstanding transactions per address and waits for BRESP before issuing a subsequent write to the same address, ensuring deterministic memory ordering.
- **Byte Enable Handling**: Partial writes correctly configure WSTRB to reflect only valid byte lanes. Unused byte lanes are strictly de-asserted to prevent unintended memory corruption.

## 3. Clock Domain Crossing Architecture
The design spans two primary clock domains: 500MHz (Core/Engine) and 100MHz (Bus/Peripheral).

- **Single-bit CDC**: All single-bit control signals (e.g., `valid`, `ready`, `req`) crossing from the 500MHz domain to the 100MHz domain pass through a 2-stage DFF synchronizer clocked exclusively by the 100MHz destination clock.
- **Multi-bit CDC**: The 32-bit status bus crosses domains via an asynchronous FIFO with independent read/write pointers and full/empty handshake signals.
- **Clock Gating**: Power savings are achieved using standard library ICG cells (CKLNQD1). The gating enable signal is registered in the low phase of the target clock to eliminate glitches.
- **Reset Synchronization**: The asynchronous global reset signal is routed through a dedicated reset synchronizer chain in each domain. De-assertion is synchronized to the local clock to prevent recovery/remetime violations.

## 4. Power & Reset Sequence
System initialization follows a deterministic hardware-managed sequence.

- **Reset Ordering**: Power-on reset release strictly follows: `PLL lock → SRAM/register file initialization → peripheral IP reset release → peripheral asserts ready → CPU/DMA master reset release`. Master IPs never begin execution before peripheral readiness is confirmed.
- **Reset Duration**: All IP-level reset signals are asserted for a minimum of 20 operating clock cycles to guarantee full state machine clearance.
- **Software Reset Handshake**: Software-triggered reset is initiated by writing `1` to `RST_CTRL[0]`. Hardware automatically clears `RST_CTRL[0]` and sets `RST_STATUS[0]` upon completion. Software polls `RST_STATUS[0]` before resuming register access. Fixed software delays are strictly prohibited.
- **Power Domain Isolation**: All outputs from the low-power display domain pass through ISO_AND isolation cells. The `isolation_enable` signal is asserted prior to domain reset and de-asserted only after power-up and clock stabilization are confirmed.