# SM64 Change Log

## V26.01.08
### Fixed
* **Tooling Actuator Adjustments:** Fixed a bug where tooling position would not show.

## V26.01.06
### Added
* **Tooling Actuator Control:** Integrated GPIO logic for `TOOLING_NEAR_POS` and `TOOLING_FAR_POS` to automate test fixture engagement.
    * **Engage:** The tooling moves to the **Near** position immediately after the AC frequency ramp sequence (`TEST_RAMP_SETUP`) completes.
    * **Retract:** The tooling automatically returns to the **Far** position during the data analysis phase (`TEST_ANALYZE`) or upon test cancellation (`TEST_CANCEL`).
    * **Manual Override:** Implemented a new command (`manual:toggle_tooling`) in the Manual Mode handler, allowing operators to toggle the tooling position directly via the GUI.

### Changed
* **FSM State Management:** Replaced string literals with an `IntEnum` class (`State`) to define system states, eliminating the use of raw strings for state tracking.
* **State Transition Logic:** Implemented a state setting mechanism (via `set_state` logic/wrapper) that automatically logs the state name upon transition, removing the need for manual logging in every step.

## V25.12.16
### Added
* **Automated Data Logging (`test.py`):** Implemented a robust results logging system for traceability and quality control.
    * **CSV Persistence:** Test results are now automatically saved to a logs/ directory using monthly rotating files (e.g., test_results_2025-12.csv).
    * **Detailed Metrics:** The log captures `Timestamp`, `Model_Name`, `Status`, `Reason`, and the specific measured durations for `Short`, `Medium`, and `Long` pulses.
    * **Helper Logic:** Added `log_test_result()` to handle safe file I/O within the `TEST_ANALYZE` state.
* **GUI Session Statistics:** Integrated real-time counters into the main interface to track session performance.
    * **Pass/Fail Tracking:** Displays the total number of Passed and Failed tests.
    * **Dynamic Updates:** Counters increment automatically based on the status messages received from the FSM worker thread (`passed`/`failed`).

### Changed
* **Code Maintenance:** Standardized all inline code comments to the `# --- Comment.` format to ensure consistent style and improved readability throughout the file.
* **Granular Tolerance Logic (`test.py`):** Refactored the calibration and analysis algorithms to support specific tolerance thresholds for each pulse type, replacing the single global tolerance approach.
    * **Calibration:** `motor_calibrate` now calculates the maximum deviation independently for `Short`, `Medium`, and `Long` pulses. It returns a dictionary containing specific keys (`short_tolerance`, `medium_tolerance`, `long_tolerance`).
    * **Analysis:** `motor_analyze` was updated to validate each measured pulse against its specific category's tolerance. This prevents false positives/negatives where mechanical variance differs between short and long pulses.

## V25.12.15
### Added
* **Calibration Logic (`motor_calibrate`):** Implemented a dedicated calibration function that processes a continuous stream of pulse data (defined by `CALIBRATION_TARGET_EDGES`).
    * **Auto-Sorting:** The algorithm automatically splits the recorded edges into groups of three (triplets) and sorts them to identify Short, Medium, and Long pulses regardless of the start phase.
    * **Dynamic Tolerance:** Tolerance is now automatically calculated based on the maximum deviation detected across all captured cycles, plus a safety offset (`TOLERANCE_OFFSET`).

### Changed
* Updated `Readme.md` documentation file.
* **FSM Calibration Flow:** Refactored the `MANUAL_MODE` and `TEST_ANALYZE` states to support the new calibration routine.
    * The system now captures a larger dataset (e.g., 12 edges) in a single run during calibration mode, distinct from the standard test edge count.
    * Calibration results are now emitted via the GUI queue for persistence.

## V25.12.09
### Added
* **Motor Analysis Algorithm (`test.py`):**
    * **Pulse Duration Calculation:** Implemented logic to extract precise pulse widths from the `edge_record` by calculating the delta between consecutive rising and falling edges.
    * **Sequence Auto-Synchronization:** The analyzer now automatically identifies the starting phase of the rotation (Long, Medium, or Short) by matching the first detected pulse against the `calibration_table`.
    * **Cyclic Validation:** Enforced a strict cyclic order check (Long → Medium → Short) to detect reverse rotation (wrong sequence) and timing violations (Fast/Slow motor) with a configurable tolerance (e.g., ±5%).
* **Bidirectional Serial Logic:** Added a protected method `_request_command` to the `BK_Serial` class. This method handles the specific workflow of sending a query command and waiting for a response (Write -> Read), preventing blocking issues on commands that do not return data.

### Changed
* **Serial Write Optimization:** Refactored `_send_command` in `BK_Serial` to be a "fire-and-forget" operation (Write only). It no longer attempts to read a response line, eliminating timeouts when sending configuration commands (e.g., VOLT 12).
* **Getter Implementation:** Updated all data retrieval methods (`get_voltage`, `get_frequency`, `get_max_current`) in both `BK9801` and `BK9201` classes to utilize the new `_request_command` method, ensuring reliable data capture.

### Fixed
* **Power Supply Serial Interface:** Resolved a reference error in the `close_serial` method that prevented the serial port from closing properly during the cleanup phase.
* **AC Test Loop (`test.py`):** Fixed a bug where the test execution loop would repeat incorrectly after the frequency ramp sequence due to missing variable resets. The state machine now correctly initializes test variables after the ramp setup through `TEST_PRESET` state.

## V25.12.08
### Added
* **AC Source Driver:** Implemented `frequency_ramp` method within the `ACSource` class to encapsulate linear frequency interpolation logic.
* **AC Motor Test Logic (`test.py`):** Added new state `TEST_RAMP_SETUP`. This state orchestrates the linear frequency ramp from model's `start_freq` to `end_freq` over the defined `delta_t` using the driver's capability.

## V25.12.01
### Added
* **Session Persistence:** Implemented functionality to automatically save the currently selected motor profile and restore it upon application restart.

## V25.11.29
### Added
* **Manual Control Mode:**
    * Implemented a comprehensive manual control interface (`ManualController`) and corresponding FSM logic (`MANUAL_MODE`).
    * **HAL Integration:** The manual control logic was implemented using the **Hardware Abstraction Layer (HAL)** classes (`MotorDriver`, `PowerSource`) rather than direct GPIO manipulation.
    * **Context Awareness:** Manual activation of the power supply automatically retrieves and applies the voltage and current limits from the currently active `MotorModel`.

## V25.11.24
### Changed
* **GUI Stop Button Logic (`gui.py`):**
    * Implemented **"Long Press"** functionality for application shutdown.
    * **Single Click:** Immediately cancels the current motor test sequence via `stop_test()`.
    * **Hold (>3s):** Triggers a full application shutdown (`on_close`).
    * Added visual feedback on the button text while holding to indicate the countdown status.
* **Model Selector GUI (`gui.py`):**
    * **Implemented "Safe Delete Mode":** Replaced the direct delete action with a toggleable delete mode to prevent accidental data loss.
    * **Visual Feedback:** Model buttons change appearance (light red background + cursor change) when Delete Mode is active to clearly indicate a destructive action.
    * **Interactive Logic:** Clicking a model button now has context-aware behavior:
        * *Normal Mode:* Loads the profile into the FSM.
        * *Delete Mode:* Triggers a confirmation popup (`messagebox`) to permanently remove the profile.
    * **Safety Auto-Reset:** The interface automatically reverts to Normal Mode after a successful deletion to prevent multiple accidental deletions.

## V25.11.20
### Added
* **Created Main User Interface Module (`gui.py`).**
* Implemented the primary Tkinter-based Graphical User Interface for the test.
* **Key Features:**
    * **Real-time Status:** Visual feedback for test states (READY, TESTING, PASS, FAIL) with color-coded indicators.
    * **Model Management:** Integrated `ModelCreator` popup window to Create, Save, and Delete motor profiles directly from the UI.
    * **Thread Orchestration:** Automatically initializes and manages the persistent FSM worker thread and a console input thread.
    * **Queue Polling:** Implemented a non-blocking `check_queue` loop to update the UI based on asynchronous worker messages.
    * **Safety:** Handles graceful shutdown, ensuring the worker thread and hardware drivers are stopped safely when the window is closed.

## V25.11.19
### Added
* Added Readme.md file to document test sequence procedure and goal
* **Created Core Test FSM Logic (`test.py`)**
  * Implemented the final, highly robust test sequencer architecture within the new `test.py` module.
  * The worker thread now operates as a **Persistent Worker Thread** in a continuous loop, ready for multiple test cycles.
  * Integrated all core features: Dynamic profile switching, waiting for external start signal, managing Busy and OK signals, and executing final cleanup routines.
* **Created Configuration Module (`config.py`).**
  * Implemented a new configuration file to eliminate hardcoded values ("magic numbers") across the project.
  * The module defines three key configuration classes:
      * **`PINS`**: Centralizes all Raspberry Pi GPIO pin mappings (Relays, H-Bridge, Sensors, Signals).
      * **`PORTS`**: Defines serial communication ports (e.g., Power Supply COM ports).
      * **`TEST_PARAMS`**: Stores global test constants (Timeouts, Target Edges, Debounce times).

### Changed
* Updated the `MotorModel` class in `models.py` to include a `calibration_table` and `max_current` attributes.
* Motor profiles now serialize and store their specific calibration timing data (the `calibration_table`) directly in the JSON file.
* Implemented model deletion capability. The `ModelManager` now includes a `delete_model(name)` method

## v25.11.18

### Added
* **Created Hardware Abstraction Layer (HAL) modules.**
  * This new architecture separates all hardware control from the main test logic.
  * Added **`powersupply.py`** to manage power generation:
      * Includes `PowerSource`, `ACSource`, `DCSource` abstract classes.
      * Contains implementations for `BK_Serial`, `BK9801`, and `BK9201`.
  * Added **`motordriver.py`** to manage power application:
      * Includes `MotorDriver` abstract class.
      * Contains implementations for `ACDriver` (relay) and the threaded `DCDriver` (H-bridge).

## v25.11.17

### Added
* **Created Model Control Module.**
  * Implemented persistent motor models. The application now saves and loads test profiles.
  * Created `MotorModel` class to define the structure for motor test profiles.
  * Created `ModelManager` class to handle loading, saving, adding and retrieving `MotorModel` objects from `models.json` file.

## v25.11.12 (Pre-Release)
### Added
- Historical placeholder entry marking the start of internal development and the introduction of the base station firmware.