# SM64 Change Log

## V26.03.03
### Added
* **Power Supply Current Reading:** Added the `get_actual_current` method to the `PowerSource` abstract base class in `powersupply.py`. Implemented the logic in the `BK_Serial` class, which handles both DC and AC power supplies identically.
* **Motor Current Testing:** Integrated current monitoring into the test sequence. The system now captures `initial_motor_current` (measured after the motor stabilization time) and `final_motor_current` (measured immediately before de-energizing the driver controller).
* **Current Logging:** The results log now records the new measurements under the headers `Initial_Current_mA` and `Final_Current_mA`.
* **Automated Failure Video Recording:** Implemented a continuous video buffer system in `vision.py` using two new methods: `save_video` and `_write_video_thread`. When a test fails, the system automatically saves the last frames as an MP4 file named with the format: `[Timestamp]_[ModelName]_[FailureType].mp4`.
* **Video Log Auto-Cleanup:** Added a storage management routine within `_write_video_thread` that automatically deletes the oldest video files when the directory exceeds the new `VISION_MAX_VIDEO_LOGS` parameter defined in `config.py`.
* **Otsu's Thresholding Mask:** Implemented dynamic image thresholding (Otsu's method) to filter out the dark background. This eliminates false tracking points that previously caused drift in spin calculations and false positive runout detections.
* **Real-time Diagnostics Overlay:** The live video feed now displays the current computed Otsu threshold value alongside the real-time FPS counter.
* **Mask Debugging Tool:** Added a `debug_mask` toggle in `vision.py`. When enabled, it visually renders the binary threshold mask (in black and white) directly in the GUI to aid in lighting and threshold calibration.

### Fixed
* **Results Log Path Resolution:** Fixed a bug where the results log file was not opening reliably by updating its path generation to use the absolute `BASE_DIR` reference.

## V26.02.26
### Added
* **Real-time FPS Display:** Added an on-screen overlay to the video feed to monitor the current frames per second (FPS) of the vision processing loop.

### Changed
* **Dynamic File Paths:** Updated file path handling for configuration and data files (`models.json`, `settings.json`, `vision_config.json`). The system now calculates an absolute `BASE_DIR` from the python script's location, preventing path-related errors when executing from different directories.
* **GUI Layout Restructure:** Reorganized and updated the positioning of user interface elements within `gui.py` for better usability and flow.
* **Optical Flow Tracking Improvements:** Optimized Lucas-Kanade tracking in `vision.py`. Implemented proactive point repopulation (generating new points before the pool depletes) and added a 15% dynamic exclusion margin inside the ROI to aggressively eliminate old points and prevent tracking drift at the edges.

### Removed
* **Legacy Tooling Hardware Logic:** Completely removed logic, configuration, and usages related to the physical tooling movements and encoder sensor from `test.py` and `config.py` (specifically removing GPIO definitions for `SENSOR`, `TOOLING_FAR_POS`, and `TOOLING_NEAR_POS`).
* **Manual Tooling Controls:** Removed the "Toggle Tooling" functionality from the Manual Controller interface in `gui.py` as part of the hardware cleanup.

## V26.02.16
### Added
* **VisionSystem Class:** Implemented a modular, object-oriented class in `vision.py` to handle all computer vision tasks.
* **Background Processing:** Image capture and mathematical analysis (Lucas-Kanade optical flow) now run in a dedicated background daemon thread to prevent UI freezing.
* **Thread-Safe GUI Rendering:** Introduced a producer-consumer model using a thread-locked `latest_frame` variable. The Tkinter GUI now polls this variable to render the video feed, eliminating `cv2.imshow` threading conflicts.
* **Interactive ROI Calibration:** Added a visual calibration routine allowing the user to graphically select the Rotation Zone (Green) and Runout Zones (Red) directly from the live video feed.
* **Direction Attribute:** Added a direction field (string: 'CW' or 'CCW') in `models.py`. This attribute serves as the ground truth to validate the optical flow detection results against the expected product rotation.

### Changed
* **FSM Integration:** Refactored the `TEST_ACTIVE` state in the Finite State Machine (`test.py`). It now utilizes a non-blocking "Trigger & Poll" pattern to initiate the vision test and asynchronously check for results (`PASS`, `FAIL`, or `TIMEOUT`).
* **Calibration Workflow:** Replaced the previous logic-based calibration with the new interactive visual ROI selection method on `gui.py`.

### Removed
* **Legacy Calibration Logic:** Removed calibration procedures from the `TEST_ANALYZE` state in `test.py` as hardware encoder calibration is no longer required.
* **Legacy Encoder Functions:** Deleted `motor_analyze` and `motor_calibrate` functions from `test.py`.
* **Hardware Dependencies:** Removed all logic related to reading physical GPIO pins for encoders, fully migrating the system to software-based optical flow detection.
* **Calibration Model:** Removed the Calibration table from `models.py` as the legacy hardware encoder calibration is no longer required.
* **Obsolete Configuration Parameters:** Removed `TEST_TARGET_EDGES`, `TEST_TARGET_PULSES`, `CALIBRATION_TARGET_EDGES`, `CALIBRATION_TARGET_PULSES`, and `CALIBRATION_TIMEOUT` from `config.py` as they are no longer used by the new vision system.

## V26.02.05
### Added
* **Computer Vision Module (`vision.py`):** Introduced a standalone prototype for non-contact rotation detection using OpenCV.
    * **Algorithm:** Implements Lucas-Kanade Optical Flow to track the linear movement of worm gear threads and determine rotation direction (CW/CCW).
    * **Robust Tracking:** Features a dynamic Point Management System that automatically culls tracking points reaching the ROI edges and respawns new features to maintain continuous flow detection.
    * **Status:** Currently serves as a development placeholder and testing ground for vision logic before integration into the main FSM.

## V26.02.04 (Architecture Change)
### Added
* Historical placeholder entry marking the start of internal development of the **Computer Vision** system firmware.

### Deprecated
* **Physical Sensor Logic:** The current FSM and HAL implementations relying on physical contact sensors (`GPIO` edge detection) are deprecated and will no longer be maintained.
    * **Reason:** Unresolvable mechanical reliability issues in the test fixture.
    * **Future Work:** Development will shift towards a non-contact **Computer Vision** system to validate motor rotation and speed.

## V26.01.22
### Changed
* **Calibration Pulse Processing (`motor_calibrate`):** Enhanced the pulse extraction logic to handle data arrays more robustly.
    * **Modulo Truncation:** Implemented a filter to strictly process complete triplets. Any trailing pulses that do not form a full cycle (remainder of len % 3) are now automatically discarded instead of causing the calibration to fail.
    * **Dynamic Iteration:** Replaced the hardcoded loop limit (12) with a dynamic range, allowing the system to process as many complete cycles as defined by `CALIBRATION_TARGET_PULSES` without index errors.
* **Tooling Actuator Timing(`test.py`):** Optimized the test sequence by shifting the tooling engagement (`TOOLING_NEAR_POS`) earlier in the process.
  * The tooling now engages during the `TEST_INIT` state, specifically after 25% of the `MOTOR_STABILIZE_TIME` delay has elapsed.
  * This ensures the fixture is fully secured before the AC frequency ramp (`TEST_RAMP_SETUP`) begins, rather than waiting for the ramp to complete.

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