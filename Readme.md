# 🔩 SM64 & SM66 Motor Test Documentation

***

## 🎯 Project Goal

The primary goal of this system is to create a robust, persistent, and configurable test rig for evaluating the dynamic performance and quality control of various AC and DC motors (specifically using encoder feedback).

The system runs autonomously on a Raspberry Pi, allowing remote configuration via a GUI. It features Advanced Computer Vision Inspection (tracking rotation, runout, and missing parts) and an Industrial-Grade Database Architecture (Store & Forward) to guarantee zero data loss and persistent traceability on the production floor. The architecture strictly adheres to the Separation of Concerns (SoC) principle using Abstract Base Classes (ABCs) and isolated background threads.
***

## 🏗️ Architecture Overview

The system operates using a Persistent Worker Thread Architecture that runs the core logic. This thread communicates asynchronously with the main GUI and is broken into several specialized files:

| Layer                    | Files                              | Responsibility                                                                                         |
|--------------------------|------------------------------------|--------------------------------------------------------------------------------------------------------|
| **I/O & Config**         | `config.py`,`models.py`            | Defines hardware constants (pins, ROI constraints) and the data model (motor profiles).                |
| **HAL**                  | `powersupply.py`, `motordriver.py` | Defines the hardware interface (ABCs) and concrete drivers for relays, H-Bridges, and serial PSU communication.      |
| **Vision System**        | `vision.py`                        | Handles OpenCV streaming, dynamic ROI alignment (Template Matching), Optical Flow tracking, Otsu thresholding, and USB Auto-Recovery.                                                                                                                     |
| **Database & Telemetry** | `equipments_connection.py`         | Manages MySQL communication, local SQLite buffering (Store & Forward), and asynchronous logging via a background daemon thread.                                                                                                                                                                                                                                                          |
| **Control Logic**        | `test.py`                          | Contains the persistent Finite State Machine (FSM) that orchestrates testing, telemetry cross-referencing, and hardware timing. |
| **GUI**                  | `gui.py`                           | Handles user interaction, profile management, and live video stream rendering.                                      |

***

## ⚙️ Test Execution Lifecycle

The system operates using a Persistent Worker Thread Architecture (FSM) that runs the core test logic in a continuous loop.

1. **Setup:** (`MODEL_CHECK` → `MODEL_LOAD` → `MODEL_SETTING`) Triggered when the Operator selects a model in the GUI. The system initializes the specific drivers and updates the active model in the database. The Power Supply is configured (Voltage, Frequency, Current Limits).
2. **Idle:** (`TEST_WAITING`) The system awaits a physical start trigger (`START_SIGNAL`) or a new model selection.
3. **Initialization:** (`TEST_INIT`) Hardware drivers engage. The motor receives power via the `DCDriver` or `ACDriver` and the Vision System creates its base tracking mask.
4. **Ramp Up(AC Only):** (`TEST_RAMP_SETUP`) If an AC motor is detected, the `ACDriver` takes control to perform a linear frequency ramp (e.g., 60Hz to 150Hz) over a defined `delta_t`.
5. **Execution:** (`TEST_PRESET` → `TEST_ACTIVE`) The Vision System actively polls the video stream:.
   * **Dynamic Allignment:** Locates the master template and offsets ROIs dynamically to compensate for mechanical fixture tolerances.
   * **Optical Flow:** Calculate _dx/dx_ vectors to determine rotation direction or `FAIL_JITTERING`.
   * **Otsu Thresholding:** Evaluates the `runouts_rois` for pixel invasion (`FAIL_RUNOUT`) or missing parts (`FAIL_ENDLESS_MISSING`).
6. **Teardown:** (`TEST_STOP`) Live electrical telemetry (Voltage and Current) is captured from the PSU. Motor power is immediately removed to ensure safety.
7. **Verification & Defect Classification:** (`TEST_ANALYZE`) The FSM correlates Vision results with Electrical Telemetry to pinpoint exact physical defects:
   * If _No Movement_ + _Current < Min Threshold_ = **Open Coil**.
   * If _No Movement_ + _Current >= Min Threshold_ = **Locked Rotor**.
   * If _Runout/Jiterring/Missing Part_ = **Assigned corresponding mechanical failure**.
   * Check correct rotation direction based on the current Model Profile (`CW/CWW`).
8. **Persistence:** The FSM compiles the results and pushes a payload to the Database Queue (`db.write_log`). Output signals (`OK_SIGNAL`, `BUSY_SIGNAL`) are updated.
9. **Reset:** After a delay, the `BUSY_SIGNAL` drops to Low, and the FSM returns to the Idle state.

***

## 📏 Calibration Mode Lifecycle

The system includes an interactive Calibration Mode (`calibrate_gui_safe`) to adapt to different camera positions or mechanical fixtures without modifying code.

1. **ROI Selection:** The system pauses the FSM and opens an OpenCV window.
2. **Mapping:** The operator draws:
   * **Rotation ROI:** Where the Optical Flow points will be tracked.
   * **Runout ROIs:** Safe zones where no moving parts should invade.
   * **Master Template:** A unique mechanical feature (e.g., a screw or edge) used as the anchor point.
3. **Persistence:** The ROIs and the Master Template image are saved locally (`vision_config.json` & `template_motor.png`). During runtime, the system searches for this template and dynamically shifts the ROIs to perfectly align with the current physical motor.