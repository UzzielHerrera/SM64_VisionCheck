### --- config.py
# This file holds all configuration constants for the test

class PINS:
    """ BCM pins for the test gpio """
    # Test stand pins
    START_SIGNAL = 22   # Input: pin to start the test
    SENSOR = 10         # Input: pin for the edge laser sensor
    BUSY_SIGNAL = 6     # Output: pin to show test is running
    OK_SIGNAL = 13      # Output: pin for pass/fail result

    # AC motor driver pins
    AC_RELAY = 23

    # DC motor driver pins
    DC_RELAY = 24
    H_BRIDGE_NEG = 25
    H_BRIDGE_ENABLE = 8
    H_BRIDGE_POS = 7


class PORTS:
    """ Serial ports """
    AC_PSU_PORT = '/dev/serial/by-id/usb-FTDI_UT232R_FT6AHHXL-if00-port0'
    DC_PSU_PORT = '/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'


class PARAMS:
    """ Parameters that define the test execution """
    TARGET_EDGES = 7        # Number of sensor edges to detect
    TEST_TIMEOUT_SEC = 20.0
    GUI_UPDATE_TIMEOUT_SEC = 0.25
    DEBOUNCE_MS = 20
    PSU_STABILIZE_SEC = 1.5
    PSU_RAMP_STEPS = 10

    # Wait times (in seconds)
    YIELD_DELAY_SEC = 0.05
    MANUAL_YIELD_DELAY_SEC = 0.05
    POLL_DELAY_SEC = 0.002
    BUSY_DELAY_SEC = 0.2
    PASS_WAIT_SEC = 0.2

    # Analysis
    TOLERANCE = 0.10
