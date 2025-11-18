import time
import logging
from queue import Queue
from threading import Event
from models import MotorModel, ModelManager
from powersupply import PowerSource, BK9801, BK9201
from motordriver import MotorDriver, ACDriver, DCDriver

# Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def test_fsm(gui_queue: Queue, stop_flag: Event, model: MotorModel):
    """
    Main test function. It must run in a separate thread.
    It controls the test logic, hardware through HAL and send status messages to the GUI via the queue.
    :param gui_queue:
    :param stop_flag:
    :param model:
    :return:
    """
    current_state = 'STARTING'
    source_control: PowerSource = None
    motor_driver: MotorDriver = None

    # Hardware Pin configuration
    AC_PSU_PORT = 'COM4'
    DC_PSU_PORT = 'COM5'
    PIN_AC_RELAY = 14
    PIN_DC_RELAY = 15
    PIN_H_EN = 8
    PIN_H_POS = 25
    PIN_H_NEG = 7


if __name__ == "__main__":
    pass