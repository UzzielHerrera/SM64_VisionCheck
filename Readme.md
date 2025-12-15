# 🔩 SM64 & SM66 Motor Test Documentation

***

## 🎯 Project Goal

The primary goal of this system is to create a robust, persistent, and configurable test rig for evaluating the dynamic performance and quality control of various AC and DC motors (specifically using encoder feedback).

The system runs autonomously on a Raspberry Pi, allowing remote configuration via a GUI. It features auto-calibration capabilities, soft-start frequency ramping for AC motors, and strictly adheres to the Separation of Concerns (SoC) principle using Abstract Base Classes (ABCs) for hardware abstraction.
***

## 🏗️ Architecture Overview

The system operates using a Persistent Worker Thread Architecture (non-GUI thread) that runs the core logic. This thread communicates asynchronously with the main GUI and is broken into several specialized files:

| Layer             | Files                              | Responsibility                                                                                         |
|-------------------|------------------------------------|--------------------------------------------------------------------------------------------------------|
| **I/O & Config**  | `config.py`,`models.py`            | Defines hardware constants (pins) and the data model (motor profiles).                                 |
| **HAL**           | `powersupply.py`, `motordriver.py` | Defines the hardware interface (ABCs) and concrete drivers for communication and motor control.        |
| **Control Logic** | `test.py`                          | Contains the persistent Finite State Machine (FSM) that orchestrates testing and calibration routines. |
| **GUI**           | `gui.py`                           | Handles user interaction, profile management, and visual updates.                                       |

***

## ⚙️ Test Execution Lifecycle

The system operates using a Persistent Worker Thread Architecture (FSM) that runs the core test logic in a continuous loop.

1. **Setup:** (`MODEL_CHECK` → `MODEL_LOAD` → `MODEL_SETTING`) Triggered when the Operator selects a model in the GUI. The system initializes the specific drivers. The Power Supply is enabled and remains ON to allow for rapid consecutive testing.
2. **Idle:** (`TEST_WAITING`) The system awaits a physical start trigger (`START_SIGNAL`) or a new model selection.
3. **Initialization:** (`TEST_INIT`) Hardware drivers engage. The motor receives power via the `DCDriver` or `ACDriver`.
4. **Ramp Up(AC Only):** (`TEST_RAMP_SETUP`) If an AC motor is detected, the `ACDriver` takes control to perform a linear frequency ramp (e.g., 60Hz to 150Hz) over a defined `delta_t`.
5. **Execution:** (`TEST_PRESET` → `TEST_ACTIVE`) The system performs active polling of the sensor pin. The test concludes automatically once 7 edges are recorded (represents 3 full pulses + start edge).
6**Teardown:** (`TEST_STOP`) Motor power is immediately removed to ensure safety. For AC motors, the frequency is reset to the start value for the next cycle.
7**Verification:** (`TEST_ANALYZE`) Recorded timings are analyzed against the model's `calibration_table` dictionary.
   * **AutoSync:** Detects start phase (Long, Medium or Short).
   * **Cyclic Check:** Verifies the sequence order (L→M→S).
   * **Tolerance:** Checks against the model-specific `tolerance` (default or calibrated).
   * Output: Updates GUI (Green/Red) and sets `OK_SIGNAL` High on pass.
8**Reset:** After a delay, the `BUSY_SIGNAL` drops to Low, and the FSM returns to the Idle state.

***

## 📏 Calibration Mode Lifecycle

The system now includes and integrated **Calibration Mode** triggered vua the GUI (`cmd:calibration_enter`). This replaces manual timing entry.

1. **Capture:** The system runs a modified test cycle that captures 25 cycles (4 full cycles of Long→Medium→Short pulses).
2. **Processing:**
   * **Auto-Sorting:** The algorithm groups pulses into triplets and sorts them ascendingly. This identifies Short, Medium, and Long pulses regardless of the motor's starting position. 
   * **Averaging:** Calculates the mean time for each pulse type over the 4 cycles.
   * **Dynamic Tolerance:** Calculates the maximum deviation found during the test and applies a safety offset (`TOLERANCE_OFFSET`) to generate a custom tolerance for this specific motor model.
3. **Persistence:** The FSM sends a dictionary object `{'long': x, 'medium': y, 'short': z, 'tolerance': t}` directly to the GUI via the queue. The GUI saves this structure via `ModelManager`.