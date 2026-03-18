### --- config.py
# This file holds all configuration constants for the test
import os


class PINS:
    """ BCM pins for the test gpio. """
    # --- Test stand pins.
    START_SIGNAL = 22   # Input: pin to start the test.
    BUSY_SIGNAL = 6     # Output: pin to show test is running.
    OK_SIGNAL = 13      # Output: pin for pass/fail result.
    TOOLING_DOWN = 9    # Input: pin for tooling down signal.

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
    TEST_TIMEOUT_SEC = 9.0
    VISION_TIMEOUT_SEC = 7.0
    VISION_STABLE_TIME_SEC = 3.0
    VISION_TARGET_FPS = 28.0
    VISION_MAX_VIDEO_LOGS = 600
    VISION_ENDLESS_DETECTION = 50
    VISION_LEFT_SENSE_DETECTION = -0.25
    VISION_RIGHT_SENSE_DETECTION = 0.25
    VISION_MIN_TRUST = 0.7
    VISION_RUNOUT_PIXEL_TOLERANCE = 50
    VISION_FAILED_FRAMES_THRESHOLD = 10
    VISION_MAX_DY_SPIKE = 5.0
    VISION_MAX_DX_SPIKE = 5.0

    # --- PSU parameters.
    PSU_STABILIZE_SEC = 4.0
    PSU_OUTPUT_STABILIZE_SEC = 0.5
    PSU_RAMP_STEPS = 10
    PSU_MIN_MOTOR_CURRENT_MA = 1.0

    # --- Wait times (in seconds).
    MOTOR_STABILIZE_SEC = 1.5
    MOTOR_RAMP_STEPS = 10
    GUI_UPDATE_TIMEOUT_SEC = 0.300
    YIELD_DELAY_SEC = 0.05
    MANUAL_YIELD_DELAY_SEC = 0.05
    POLL_DELAY_SEC = 0.005
    BUSY_DELAY_SEC = 0.1
    PASS_WAIT_SEC = 0.1
    DEBOUNCE_SEC = 0.010

    # --- Directories.
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
