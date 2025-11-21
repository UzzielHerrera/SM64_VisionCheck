# 🔩 SM64 & SM66 Motor Test Documentation

***

## 🎯 Project Goal

The primary goal of this system is to create a robust, persistent, and configurable test rig for evaluating the dynamic performance and quality control of various AC and DC motors (specifically using encoder feedback) against standardized factory specifications.

The system is designed to run autonomously on a Raspberry Pi, allowing remote configuration and monitoring via a minimal graphical interface. The architecture prioritizes safety, thread-safety, and maintainability by strictly adhering to the Separation of Concerns (SoC) principle and utilizing Abstract Base Classes (ABCs) for the hardware interface.

***

## 🏗️ Architecture Overview

The system operates using a Persistent Worker Thread Architecture (non-GUI thread) that runs the core logic. This thread communicates asynchronously with the main GUI and is broken into several specialized files:

| Layer             | Files                              | Responsibility                                                                                  |
|-------------------|------------------------------------|-------------------------------------------------------------------------------------------------|
| **I/O & Config**  | `config.py`,`models.py`            | Defines hardware constants (pins) and the data model (motor profiles).                          |
| **HAL**           | `powersupply.py`, `motordriver.py` | Defines the hardware interface (ABCs) and concrete drivers for communication and motor control. |
| **Control Logic** | `test.py`                          | Contains the persistent Finite State Machine (FSM) that orchestrates the entire test sequence.  |
| **GUI**           | `gui.py`                           | Handles user interaction, profile management, and visual updates.                               |
| **Utility**       | `calibration.py`                   | Provides a standalone tool for generating calibration timing data.                              |

***

## ⚙️ Test Execution Lifecycle

The system operates using a Persistent Worker Thread Architecture (FSM) that runs the core test logic in a continuous loop.

1. **Setup:** (`MODEL_CHECK` → `MODEL_LOAD` → `MODEL_SETTING`) Triggered when the Operator selects a model in the GUI. The system initializes the specific drivers. The Power Supply is enabled and remains ON to allow for rapid consecutive testing.
2. **Idle:** (`TEST_WAITING`) The system awaits a physical start trigger (`START_SIGNAL`) or a new model selection.
3. **Initialization:** (`TEST_INIT`) Hardware drivers engage. The motor receives power via the `DCDriver` or `ACDriver`.
4. **Execution:** (`TEST_ACTIVE`) The system performs active polling of the sensor pin. The test concludes automatically once 7 edges are recorded.
5. **Teardown:** (`TEST_STOP`) Motor power is immediately removed to ensure safety.
6. **Verification:** (`TEST_ANALYZE`) Recorded timings are compared to the `calibration_table`.
   * Tolerance: ±10%
   * Output: Updates GUI (Green/Red) and sets `OK_SIGNAL` High on pass.
7. **Reset:** After a 200ms delay, the `PIN_BUSY_SIGNAL` drops to Low, and the FSM returns to the Idle state.
