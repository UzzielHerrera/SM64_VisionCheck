# SM64 Change Log

## V25.11.19
### Added
* **Core Test FSM Logic (`test.py`)**
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