# Memory Controller & Display Subsystem Spec v2.0
**Version**: 2.0 (DRAFT)
**Target**: Subsystem Integration
**Description**: Architectural specification for the memory controller and low-power display pipeline.

## 1. Overview
This document defines the interface, clock domain crossing (CDC), power management, and reset sequencing for the integrated memory controller and display subsystem.

## 2. AXI Interface Specification
The subsystem implements an AXI4 Master interface for DDR access and an AXI4-Lite interface for CPU configuration.

- **Burst Support**: The AXI4 Master interface is optimized for high-throughput streaming workloads and supports INCR burst mode exclusively to reduce control logic overhead and save die area.
<!-- GROUND_TRUTH: Violates AXI-001 (Missing WRAP burst mode support) -->

- **AXI-Lite Constraint**: The configuration port uses AXI4-Lite protocol. AWLEN and ARLEN are hardwired to 0.
- **Outstanding Limit**: The controller supports up to 16 outstanding write transactions. AWID is implemented as 4-bit wide.
- **Write Ordering**: The interface tracks outstanding transactions per address and waits for BRESP before issuing a subsequent write to the same address.
- **Byte Enable Handling**: Partial writes correctly configure WSTRB to reflect only valid byte lanes.

## 3. Clock Domain Crossing Architecture
The design spans two primary clock domains: 500MHz (Core/Engine) and 100MHz (Bus/Peripheral).

- **Single-bit CDC**: To minimize latency for critical control paths, the DMA request signal crosses from the 500MHz domain to the 100MHz domain through a single DFF synchronizer stage before entering the destination logic.
<!-- GROUND_TRUTH: Violates CLK-001 (Only 1-stage synchronizer used for single-bit CDC) -->

- **Multi-bit CDC**: The 32-bit status bus crosses domains via an asynchronous FIFO with independent read/write pointers.
- **Clock Gating**: Power savings are achieved using standard library ICG cells (CKLNQD1). The gating enable signal is registered in the low phase of the target clock.
- **Reset Synchronization**: The asynchronous global reset signal is routed through a dedicated reset synchronizer chain in each domain.

## 4. Power & Reset Sequence
System initialization follows a hardware-managed sequence with software-managed peripheral resets.

- **Reset Ordering**: Power-on reset release follows: `PLL lock → SRAM initialization → peripheral IP reset release → CPU/DMA master reset release`. Master and peripheral resets are released simultaneously once peripheral initialization completes.
- **Reset Duration**: All IP-level reset signals are asserted for a minimum of 20 operating clock cycles.
- **Software Reset Handshake**: Software-triggered reset for the display controller is initiated by writing `1` to `RST_CTRL[0]`. The driver implements a fixed 1.5ms delay before proceeding with register configuration, ensuring sufficient time for internal state machines to clear under worst-case PVT conditions.
<!-- GROUND_TRUTH: Violates RST-003 (Uses fixed software delay instead of hardware handshake/status flag) -->

- **Power Domain Isolation**: All outputs from the low-power display domain pass through ISO_AND isolation cells. The `isolation_enable` signal is asserted prior to domain reset and de-asserted after power-up.