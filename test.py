import threading
import time
import logging
from queue import Queue, Empty
from threading import Event
from config import PINS, PORTS, PARAMS
from models import MotorModel, ModelManager
from powersupply import PowerSource, ACSource, DCSource, BK9801, BK9201
from motordriver import MotorDriver, ACDriver, DCDriver

# --- Mocking for Development
try:
    import RPi.GPIO as GPIO
    print("Real RPi.GPIO library loaded.")
except (ImportError, RuntimeError):
    print("WARNING: RPi.GPIO not found. Using Mock GPIO.")
    class MockGPIO:
        IN = "in"
        OUT = "out"
        HIGH = 1
        LOW = 0
        BCM = "bcm"
        BOARD = "rpi4"
        def setup(self, *args, **kwargs): pass
        def output(self, *args, **kwargs): pass
        def input(self, *args, **kwargs): return 0
        def setmode(self, *args, **kwargs): pass
        def cleanup(self, *args, **kwargs): pass
        def setwarnings(self, *args, **kwargs): pass
    GPIO = MockGPIO()

# Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def motor_analyze(edge_record, calibration_table):
    return True

def finite_state_machine(gui_queue: Queue, initial_model: MotorModel, model_queue: Queue, stop_flag: Event):
    """
    Main test function. It must run in a separate thread.
    It controls the test logic, hardware through HAL and send status messages to the GUI via the queue.
    :param initial_model:
    :param gui_queue:
    :param stop_flag:
    :param model_queue:
    :return:
    """
    if not isinstance(stop_flag, Event):
        logger.error('Stop flag must be an Event.')
        return

    logger.info('FSM: starting finite state machine')
    # --- FSM state variables
    current_model = initial_model
    source_controller: PowerSource = None
    motor_driver: MotorDriver = None
    source_is_active = False

    # --- Thread-sage recording variables
    calibration_table = []
    edge_record = []
    last_pin_state = None
    start_time = time.time()
    gui_update_time = time.time()


    # --- GPIO config
    current_mode = GPIO.getmode()

    if current_mode is None:
        GPIO.setmode(GPIO.BCM)
    elif current_mode != GPIO.BCM:
        logger.warning(f"FSM: GPIO forcing cleanup and setmode")
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
    else:
        pass

    GPIO.setup(PINS.START_SIGNAL, GPIO.IN)
    GPIO.setup(PINS.SENSOR, GPIO.IN)
    GPIO.setup(PINS.BUSY_SIGNAL, GPIO.OUT)
    GPIO.setup(PINS.OK_SIGNAL, GPIO.OUT)


    # --- Thread level setup and cleanup
    try:
        # --- System infinite loop
        while True:
            # --- Per Test Variables
            current_state = 'MODEL_CHECK'
            test_in_progress = True
            calibration_table = None

            # --- Per Test try
            try:
                while test_in_progress:
                    if stop_flag.is_set():
                        logger.info('FSM: stop flag active')
                        current_state = 'TEST_CANCEL'

                    # --- Model check state
                    if current_state == 'MODEL_CHECK':
                        new_model = '0'

                        # get new model from the queue
                        try:
                            new_model = model_queue.get_nowait()
                            logger.info(f'FSM: new model: {new_model}')
                        except Empty:
                            logger.info('FSM: model queue empty')
                            pass

                        # check if model has been changed
                        if new_model != '0' and new_model != current_model:

                            # driver cleanup
                            if source_controller is not None: source_controller.cleanup()
                            if motor_driver is not None: motor_driver.cleanup()

                            if new_model is None:
                                logger.info('FSM: shutting down finiste state machine')
                                return

                            logger.info(f'FSM: changing model to {new_model.name}')

                            # new model selection
                            current_model = new_model
                            source_controller = None
                            motor_driver = None
                            source_is_active = False

                        if not source_is_active:
                            current_state = 'MODEL_LOAD'
                        else :
                            current_state = 'TEST_WAITING'

                    # --- Start state
                    elif current_state == 'MODEL_LOAD':
                        gui_queue.put(f'model:{current_model.name}')
                        calibration_table = current_model.calibration_table

                        # create drivers only if none
                        if source_controller is None:
                            # load dc model to source controller and motor driver
                            if current_model.motor_type.lower() == 'dc':
                                logger.info(f'FSM: attaching BK9201 to source controller')
                                source_controller = BK9201(port=PORTS.DC_PSU_PORT)
                                logger.info(f'FSM: attaching DCDriver to motor driver')
                                motor_driver = DCDriver(PINS.DC_RELAY, PINS.H_BRIDGE_ENABLE, PINS.H_BRIDGE_POS, PINS.H_BRIDGE_NEG)

                            # load ac model to source controller and motor driver
                            elif current_model.motor_type.lower() == 'ac':
                                logger.info(f'FSM: attaching BK9801 to source controller')
                                source_controller = BK9801(port=PORTS.AC_PSU_PORT)
                                logger.info(f'FSM: attaching ACDriver to motor driver')
                                motor_driver = ACDriver(PINS.AC_RELAY)

                        current_state = 'MODEL_SETTING'

                    # --- Setting source state
                    elif current_state == 'MODEL_SETTING':
                        # enables remote control and turn source output off
                        source_controller.request_control()

                        # set up source voltage, frequency, current
                        source_controller.set_voltage(current_model.voltage)
                        source_controller.set_max_current(current_model.max_current)
                        if isinstance(source_controller, ACSource):
                            source_controller.set_frequency(current_model.frequency)

                        # turn source output on
                        if not source_is_active:
                            source_controller.enable_output()
                            # stabilize source
                            if stop_flag.wait(PARAMS.PSU_STABILIZE_SEC): continue
                            source_is_active = True

                        current_state = 'TEST_WAITING'

                    # --- Waiting start state
                    elif current_state == 'TEST_WAITING':
                        gui_queue.put('waiting:testinit')

                        while not stop_flag.is_set():

                            # look up for start signal
                            # if GPIO.input(PINS.START_SIGNAL) == GPIO.HIGH:
                            #     GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)
                            #     current_state = 'TEST_INIT'

                            # look up for model change
                            try:
                                if not model_queue.empty():
                                    logger.info('FSM: new model received')
                                    current_state = 'MODEL_CHECK'
                                    break
                            except Exception:
                                pass

                            # mpu yield delay
                            time.sleep(PARAMS.YIELD_DELAY_SEC)

                        # reset loop to handle model change or stop flag
                        if current_state != 'TEST_INIT': continue

                    # --- Test init state
                    elif current_state == 'TEST_INIT':
                        gui_queue.put('waiting:busyon')
                        if stop_flag.wait(PARAMS.BUSY_DELAY_SEC): continue
                        GPIO.output(PINS.BUSY_SIGNAL, GPIO.HIGH)

                        # turn on relay / h-bridge
                        motor_driver.apply_power()

                        # Polling prepare
                        edge_record = []
                        last_pin_state = GPIO.input(PINS.SENSOR)

                        start_time = time.time()
                        gui_update_time = time.time()

                        current_state = 'TEST_ACTIVE'

                    # --- Test active state
                    elif current_state == 'TEST_ACTIVE':
                        if stop_flag.is_set(): continue

                        # get last pin and time
                        current_pin_state = GPIO.input(PINS.SENSOR)
                        now = time.perf_counter()

                        # edge detection
                        if current_pin_state != last_pin_state:
                            edge_record.append((now, last_pin_state))
                            logger.info(f'FSM: Edge {len(edge_record)}->({now},{current_pin_state})')

                        last_pin_state = current_pin_state

                        # check completion
                        if len(edge_record) >= PARAMS.TARGET_EDGES:
                            logger.info(f'FSM: All edges detected')
                            current_state = 'TEST_STOP'
                            continue

                        # check timeout
                        if (time.time() - start_time) > PARAMS.TEST_TIMEOUT_SEC:
                            current_state = 'TEST_TIMEOUT'

                        # update gui
                        if (time.time() - gui_update_time) > PARAMS.GUI_UPDATE_TIMEOUT_SEC:
                            gui_queue.put(f'record:{len(edge_record)}>{current_pin_state}')
                            gui_update_time = time.time()

                        # mpu yield delay
                        time.sleep(PARAMS.POLL_DELAY_SEC)

                    # --- Test stop state
                    elif current_state == 'TEST_STOP':
                        gui_queue.put('de-energizing')
                        motor_driver.remove_power()
                        current_state = 'TEST_ANALYZE'

                    # --- Test analyze state
                    elif current_state == 'TEST_ANALYZE':
                        gui_queue.put('analyzing')

                        is_pass = motor_analyze(edge_record, current_model.calibration_table)

                        if is_pass:
                            gui_queue.put('passed')
                            GPIO.output(PINS.OK_SIGNAL, GPIO.HIGH)
                            if stop_flag.wait(PARAMS.PASS_WAIT_SEC): continue
                            GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                        else:
                            gui_queue.put('failed')
                            GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)
                            GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)

                        current_state = 'TEST_COMPLETE'

                    # --- Test complete state
                    elif current_state == 'TEST_COMPLETE':
                        test_in_progress = False

                    # --- Test cancel state
                    elif current_state == 'TEST_CANCEL':
                        # clean up motor driver
                        if motor_driver: motor_driver.cleanup()

                        logger.warning(f'FSM: test cancelled by user')
                        gui_queue.put('cancelled:by_user')

                        GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                        GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)

                        test_in_progress = False


                    # --- Test timeout state
                    elif current_state == 'TEST_TIMEOUT':
                        # clean up motor driver
                        if motor_driver: motor_driver.cleanup()

                        logger.warning(f'FSM: test cancelled by user')
                        gui_queue.put(f'cancelled:timeout')

                        GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                        GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)

                        test_in_progress = False

            # --- Test exception handler
            except Exception as e:
                logger.error(f'FSM: {e}', exc_info=True)
                gui_queue.put(f'error:{e}')

            # --- Test finally cleanup
            finally:
                logger.info('FSM: finish test cleaning')
                # GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                # GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)

                if motor_driver:
                    motor_driver.cleanup()
                stop_flag.clear()


    # --- Thread level clean up
    finally:
        logger.info(f'FSM: cleanning up thread.')
        if motor_driver:
            motor_driver.cleanup()
        if source_controller:
            source_controller.cleanup()
        GPIO.cleanup()
        logger.info('FSM: test thread ended.')


if __name__ == "__main__":
    pass