import RPi.GPIO as GPIO
import time
import threading
import logging
import logging.handlers

# Equipments information
equipment_name = 'TS111125'
sw_version = 'v25.11.12'

# Log handler
logger = logging.getLogger('SpinCheck')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Color constants
pass_color = '#57da50'
fail_color = '#ff3300'
process_color = '#ffcc00'
disable_color = '#f3f3f3'
root_bg_color = '#ff9999'
frame_bg_color = '#ffffff'



GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)