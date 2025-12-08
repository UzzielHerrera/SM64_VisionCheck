# SM64 Change Log

## V25.12.08
### Changed
* **AC Motor Test Logic (`test.py`):**
    * **Frequency Ramp Implementation:** Modified the test sequence for AC motors to include a linear frequency ramp. Upon energization, the power supply now transitions smoothly from the model's `start_freq` to `end_freq` over the defined `delta_t` before initiating the encoder measurement phase.

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