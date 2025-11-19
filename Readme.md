# 🔩 SM64 & SM66 Motor Test Documentation

***

## 🎯 Project Goal

The primary goal of this system is to create a robust, persistent, and configurable test rig for evaluating the dynamic performance and quality control of various AC and DC motors (specifically using encoder feedback) against standardized factory specifications.

The system is designed to run autonomously on a Raspberry Pi, allowing remote configuration and monitoring via a minimal graphical interface. The architecture prioritizes safety, thread-safety, and maintainability by strictly adhering to the Separation of Concerns (SoC) principle and utilizing Abstract Base Classes (ABCs) for the hardware interface.

***

## 🏗️ Architecture Overview

The system operates using a Persistent Worker Thread Architecture (non-GUI thread) that runs the core logic. This thread communicates asynchronously with the main GUI (expected to be in gui.py) and is broken into several specialized files:

| Layer             | Files                              | Responsibility |
|-------------------|------------------------------------|----------------|
| **I/O & Config**  | `config.py`,`models.py`            | Defines hardware constants (pins) and the data model (motor profiles).               |
| **HAL**           | `powersupply.py`, `motordriver.py` | Defines the hardware interface (ABCs) and concrete drivers for communication and motor control.               |
| **Control Logic** | `test.py`                          | Contains the persistent Finite State Machine (FSM) that orchestrates the entire test sequence.               |
| **Utility**       | `calibration.py`                    | Provides a standalone tool for generating master timing data.               |

***

## ⚙️ Test Execution Lifecycle (The Flow)

The system operates using a Persistent Worker Thread Architecture that runs the core test logic in a continuous loop.

1. **Wait for Profile:** The FSM blocks until the GUI sends a profile via the profile_queue.
2. **Wait for Start:** The FSM waits for the external `PIN_START_SIGNAL` to go HIGH.
3. **Initiate Test:** The system sets the `PIN_BUSY_SIGNAL` `HIGH` (after a brief delay).
4. **Power Application:** The motor driver (`DCDriver` or `ACDriver`) is engaged, applying power. The main Power Supply (PSU) remains ON between tests.
5. **Active Polling:** The FSM enters the `TEST_ACTIVE` loop, actively polling the `PIN_SENSOR` state in a tight loop and recording 7 edges.
6. **Analyze & Stop:** Upon detecting the target edge count, the FSM immediately removes power (`motor_driver.remove_power()`) and proceeds to the analysis phase.
7. **Pass/Fail Signaling:** The FSM compares recorded timing deltas to the model's calibration_table. If successful ($\pm 10\%$ tolerance), the `PIN_OK_SIGNAL` is set `HIGH`.
8. **Cleanup & Loop:** After a 200ms delay, the `PIN_BUSY_SIGNAL` is dropped `LOW`, the `PIN_OK_SIGNAL` is reset, and the FSM loops back to Wait for Profile/Start.
