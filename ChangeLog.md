# SM64 Change Log

## v25.11.18

## Added

* **Created new Hardware Abstraction Layer (HAL) modules.**
* This new architecture separates all hardware control from the main test logic.
* Added **`powersupply.py`** to manage power generation:
    * Includes `PowerSource`, `ACSource`, `DCSource` abstract classes.
    * Contains implementations for `BK_Serial`, `BK9801`, and `BK9201`.
* Added **`motordriver.py`** to manage power application:
    * Includes `MotorDriver` abstract class.
    * Contains implementations for `ACDriver` (relay) and the threaded `DCDriver` (H-bridge).

## v25.11.17

### Added
* **Initial Model Control Module.**
* Implemented persistent motor models. The application now saves and loads test profiles.
* Created `MotorModel` class to define the structure for motor test profiles.
* Created `ModelManager` class to handle loading, saving, adding and retrieving `MotorModel` objects from `models.json` file.

## v25.11.12 (Pre-Release)

### Added
- Historical placeholder entry marking the start of internal development and the introduction of the base station firmware.