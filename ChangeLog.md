# SM64 Change Log

## v25.11.18

## Added

* **Initial Power Supply Control Module.**
* Created an extensible, object-oriented architecture for handling power supplies.
* Implemented Abstract Base Classes (ABCs) (`PowerSource`, `ACSource`, `DCSource`) to define a standard "contract" for all future power supply drivers.
* Added a `BK_Serial` base class to hold all common RS232 logic for BK Precision models, eliminating code duplication.
* Added initial drivers for:
    * **`BK9801`** (AC Source)
    * **`BK9201`** (DC Source)

## v25.11.17

### Added
* **Initial Model Control Module.**
* Implemented persistent motor models. The application now saves and loads test profiles.
* Created `MotorModel` class to define the structure for motor test profiles.
* Created `ModelManager` class to handle loading, saving, adding and retrieving `MotorModel` objects from `models.json` file.

## v25.11.12 (Pre-Release)

### Added
- Historical placeholder entry marking the start of internal development and the introduction of the base station firmware.