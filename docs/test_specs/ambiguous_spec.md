# Memory Controller & Display Subsystem Spec v2.1 (PRE-RELEASE)
**Version**: 2.1-DRAFT
**Target**: Subsystem Integration
**Description**: Architectural specification for the memory controller and low-power display pipeline with performance optimizations.

# Overview
This document defines the interface, clock domain crossing (CDC), power management, and reset sequencing for the integrated memory controller and display subsystem. Several design choices deviate from standard implementation to meet aggressive power/performance targets for the next-gen mobile SoC.

## 1. AXI Interface Specification
The subsystem implements an AXI4 Master interface for DDR access and an AXI4-Lite interface for CPU configuration.

- **Burst Support**: The AXI4 Master interface nominally supports both INCR and WRAP burst modes. However, for the high-throughput video encoding path, WRAP mode is **disabled by a runtime firmware toggle** to reduce buffer allocation complexity. WRAP is only enabled for legacy DMA paths via register configuration.
- **AXI-Lite Constraint**: The configuration port uses AXI4-Lite protocol with AWLEN/ARLEN hardwired to 0 for normal operation. For silicon debug and JTAG access, the controller allows **burst transfers up to AWLEN=3** to accelerate register dump operations. This path is isolated from production firmware.
- **Outstanding Limit**: The controller supports up to 16 outstanding write transactions. AWID is implemented as 4-bit wide, but the interconnect ID remapping table is configured to share IDs across different stream channels.

## 2. Clock Domain Crossing Architecture
The design spans two primary clock domains: 500MHz (Core/Engine) and 100MHz (Bus/Peripheral).

- **Single-bit CDC**: General control signals use a standard 2-stage DFF synchronizer clocked by the destination domain. However, the **fast interrupt request line (`irq_fast`)** uses a single FF stage followed by an asynchronous reset flip-flop to meet a <2ns latency budget. This approach was inherited from a previous tape-out (T-7nm node) and has shown zero metastability issues in field returns over 3 years.
- **Multi-bit CDC**: The 32-bit status bus crosses domains via Gray code encoding on the pointer, but the status payload uses a **3-stage synchronizer array** instead of an async FIFO, justified by the low toggle rate (<100kHz) and synchronized update protocol.

## 3. Power & Reset Sequence
System initialization follows a hardware-managed sequence with dynamic software adjustments.

- **Reset Ordering**: Power-on reset release follows the standard sequence. However, the CPU reset may be released **2 cycles after peripheral ready assertion** to overlap cache initialization, reducing boot time by 15%.
- **Software Reset Handshake**: Software-triggered reset for the display controller uses a **dynamic delay mechanism**. Instead of polling a hardware flag, the driver calculates a wait time based on on-chip thermal sensor and VDD rail voltage readings, ensuring the delay always exceeds 16 cycles under worst-case PVT corners. Fixed delay tables are bypassed.
- **Power Domain Isolation**: Outputs from the low-power display domain use custom isolation cells that clamp to **High-Z state** during power-down, rather than fixed 0/1. This is enabled by a new 4nm process library feature that prevents leakage current through clamp diodes. Standard isolation enable timing is followed.