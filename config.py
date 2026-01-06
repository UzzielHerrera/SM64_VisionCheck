### --- config.py
# This file holds all configuration constants for the test

class PINS:
    """ BCM pins for the test gpio. """
    # --- Test stand pins.
    START_SIGNAL = 22   # Input: pin to start the test.
    SENSOR = 10         # Input: pin for the edge laser sensor.
    BUSY_SIGNAL = 6     # Output: pin to show test is running.
    OK_SIGNAL = 13      # Output: pin for pass/fail result.
    TOOLING_DOWN = 9    # Input: pin for tooling down signal.
    TOOLING_FAR_POS = 19    # Output: pin to move the tooling to far position.
    TOOLING_NEAR_POS = 26   # Output: pin to move the tooling to near position.

    # --- AC motor driver pins.
    AC_RELAY = 23

    # --- DC motor driver pins.
    DC_RELAY = 24
    H_BRIDGE_NEG = 25
    H_BRIDGE_ENABLE = 8
    H_BRIDGE_POS = 7


class PORTS:
    """ Serial ports for drivers. """
    AC_PSU_PORT = '/dev/serial/by-id/usb-FTDI_UT232R_FT6AHHXL-if00-port0'
    DC_PSU_PORT = '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'


class PARAMS:
    """ Parameters that define the test execution. """
    # --- Test and calibration parameters.
    TEST_TARGET_EDGES = 7
    CALIBRATION_TARGET_EDGES = 25
    TEST_TARGET_PULSES = 3
    CALIBRATION_TARGET_PULSES = 12
    TEST_TIMEOUT_SEC = 10.0
    CALIBRATION_TIMEOUT_SEC = 35.0

    # --- PSU parameters.
    PSU_STABILIZE_SEC = 1.5
    PSU_RAMP_STEPS = 10

    # --- Wait times (in seconds).
    MOTOR_STABILIZE_SEC = 2.0
    MOTOR_RAMP_STEPS = 10
    GUI_UPDATE_TIMEOUT_SEC = 0.300
    YIELD_DELAY_SEC = 0.05
    MANUAL_YIELD_DELAY_SEC = 0.05
    POLL_DELAY_SEC = 0.005
    BUSY_DELAY_SEC = 0.2
    PASS_WAIT_SEC = 0.2
    DEBOUNCE_SEC = 0.010

    # --- Analysis.
    TOLERANCE_OFFSET = 0.05
