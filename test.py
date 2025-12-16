import os
import csv
import time
import logging
from datetime import datetime
from queue import Queue, Empty
from threading import Event
from models import MotorModel
from config import PINS, PORTS, PARAMS
from powersupply import PowerSource, ACSource, BK9801, BK9201
from motordriver import MotorDriver, ACDriver, DCDriver

# --- Mocking for Development.
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
        def getmode(self, *args, **kwargs): return 0
        def cleanup(self, *args, **kwargs): pass
        def setwarnings(self, *args, **kwargs): pass
    GPIO = MockGPIO()

# --- Log handler setup.
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def motor_analyze(edge_record, calibration_table):
    """
    Analysis edge record data to give a pass/fail status.
    :param edge_record: list of 'PARAMS.TEST_TARGET_EDGES' number of edge dicts [{'time': float, 'state': int}, ...]
    :param calibration_table: calibration table dict {'long': float, 'medium': float, 'short': float, 'tolerance': float}
    :return: tuple of dict ({'status': 'PASS'|'FAIL', 'reason': str}, {'long': float, 'medium': float, 'short': float})
    """
    null_record = {'long': 0.0, 'medium': 0.0, 'short': 0.0}
    logger.info(f'FSM: Motor analyzing {edge_record}:{calibration_table}')
    try:

        # --- Safe record length.
        if len(edge_record) != PARAMS.TEST_TARGET_EDGES:
            return {'status': 'FAIL', 'reason': 'Invalid edge count'}, null_record

        # --- Extract pulse duration.
        analysis_times = [nxt['time'] - cur['time'] for cur, nxt in zip(edge_record, edge_record[1:]) if cur['state']]
        if analysis_times != PARAMS.TEST_TARGET_PULSES:
            return {'status': 'FAIL', 'reason': 'No edges found'}, null_record
        logger.debug(f'FSM: Extacted times: {[f"{t:0.3f}" for t in analysis_times]}')

        sorted_times = sorted(analysis_times)
        log_record = {'long': sorted_times[2], 'medium': sorted_times[1], 'short': sorted_times[0]}

        # --- Start index detection.
        sequence_names = ['long', 'medium', 'short']
        nominal_times = [calibration_table[x] for x in sequence_names]

        start_index = -1
        first_delta = analysis_times[0]

        for i, nominal_time in enumerate(nominal_times):
            lower_limit = nominal_time * (1 - calibration_table['tolerance'])
            upper_limit = nominal_time * (1 + calibration_table['tolerance'])
            if lower_limit <= first_delta <= upper_limit:
                start_index = i
                break

        if start_index == -1:
            return {'status': 'FAIL', 'reason': f'First data "{first_delta:0.2f}" out of range'}, log_record

        # --- Validate Full Sequence.
        current_sequence_index = start_index

        for i, measured_time in enumerate(analysis_times):
            expected_type = sequence_names[current_sequence_index]
            nominal_time = nominal_times[current_sequence_index]

            lower_limit = nominal_time * (1 - calibration_table['tolerance'])
            upper_limit = nominal_time * (1 + calibration_table['tolerance'])

            if measured_time < lower_limit:
                return {'status': 'FAIL', 'reason': f'Fast motor in segment {expected_type} (Value: {measured_time:0.2f})'}, log_record

            if measured_time > upper_limit:
                return {'status': 'FAIL', 'reason': f'Slow motor in segment {expected_type} (Value: {measured_time:0.2f})'}, log_record

            current_sequence_index = (current_sequence_index + 1) % len(sequence_names)

        return {'status': 'PASS', 'reason': 'Sequence and timing correct'}, log_record
    except Exception as e:
        logger.error(f'FSM: {e}')
        return {'status': 'FAIL', 'reason': str(e)}, null_record

def motor_calibrate(edge_record):
    """
    Analysis edge record data to give a calibration table.
    :param edge_record: list of 'PARAMS.CALIBRATION_TARGET_EDGES' number of edge dicts [{'time': float, 'state': int}, ...]
    :return: calibration table as dict {'long': float, 'medium': float, 'short': float, 'tolerance': float}
    """
    # --- Empty calibration.
    null_calibration = {'long': 0.0, 'medium': 0.0, 'short': 0.0, 'tolerance': 0.0}
    logger.info(f'FSM: Motor calibrating -> {edge_record}')
    try:

        # --- Safe record length.
        if len(edge_record) != PARAMS.CALIBRATION_TARGET_EDGES:
            return null_calibration

        # --- Extract pulse duration.
        analysis_times = [nxt['time'] - cur['time'] for cur, nxt in zip(edge_record, edge_record[1:]) if cur['state']]
        if not analysis_times:
            return null_calibration
        logger.debug(f'FSM: Extacted times: {[f"{t:0.3f}" for t in analysis_times]}')

        if len(analysis_times) != PARAMS.CALIBRATION_TARGET_PULSES:
            return null_calibration

        # --- Divide and sort in groups of pulses.
        cycles = []
        for i in range(0, 12, 3):
            cycle_group = analysis_times[i:i+3]
            cycles.append(sorted(cycle_group))

        # --- Separate in category.
        short_values = [c[0] for c in cycles]
        medium_values = [c[1] for c in cycles]
        long_values = [c[2] for c in cycles]

        # --- Calculate mean values.
        short_avg = sum(short_values) / len(short_values)
        medium_avg = sum(medium_values) / len(medium_values)
        long_avg = sum(long_values) / len(long_values)

        # --- Calculate max deviation.
        max_deviation = 0.0

        for value in short_values:
            dev = abs(value - short_avg) / short_avg
            if dev > max_deviation:
                max_deviation = dev

        for value in medium_values:
            dev = abs(value - medium_avg) / medium_avg
            if dev > max_deviation:
                max_deviation = dev

        for value in long_values:
            dev = abs(value - long_avg) / long_avg
            if dev > max_deviation:
                max_deviation = dev

        calibration_tolerance = max_deviation + PARAMS.TOLERANCE_OFFSET

        # --- Return values.
        return {
            'long': float(f'{long_avg:0.3f}'),
            'medium': float(f'{medium_avg:0.3f}'),
            'short': float(f'{medium_avg:0.3f}'),
            'tolerance': float(f'{calibration_tolerance:0.2f}'),
        }

    except Exception as e:
        logger.error(f'FSM: {e}')
        return null_calibration

def log_test_results(model_name, status, reason, metrics):
    try:
        # --- Create folder container.
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        filename = os.path.join(log_dir, f'test_log_{datetime.now().strftime("%Y_%m_%d")}.csv')
        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as csvfile:
            headers = ['Timestamp', 'Model', 'Status', 'Reason', 'Short_Record', 'Medium_Record', 'Long_Record']
            writer = csv.DictWriter(csvfile, fieldnames=headers)

            # --- Create headers if file is written for the first time.
            if not file_exists:
                writer.writeheader()

            # --- Write log entry.
            writer.writerow({
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Model': model_name,
                'Status': status,
                'Reason': reason,
                'Short_Record': f'{metrics.get("short", 0):0.3f}',
                'Medium_Record': f'{metrics.get("medium", 0):0.3f}',
                'Long_Record': f'{metrics.get("long", 0):0.3f}'
            })

        logger.info(f'LOG: "{filename}" updated')
    except Exception as e:
        logger.error(f'LOG: {e}')

def finite_state_machine(gui_queue: Queue, initial_model: MotorModel, fsm_queue: Queue, stop_flag: Event):
    """
    Main test function. It must run in a separate thread.
    It controls the test logic, hardware through HAL and send status messages to the GUI via the queue.
    :param initial_model: initial MotorModel
    :param gui_queue: communication Queue that connects  FSM->GUI
    :param stop_flag: Event to emulate E-Stop signal
    :param fsm_queue: communication Queue that connects  GUI->FSM
    :return:
    """
    logger.info('FSM: starting finite state machine')
    # --- FSM state variables
    current_model = initial_model
    source_controller: PowerSource = None
    motor_driver: MotorDriver = None
    source_is_active = False

    # --- Calibration variables.
    is_calibrating = False

    # --- Recording variables.
    edge_record = []
    last_pin_state = None
    start_time = time.time()
    gui_update_time = time.time()

    # --- Manual mode variables.
    manual_source_active = False
    manual_driver_active = False

    # --- Manual mode command handler.
    def handle_manual_cmd(command, source_ctrl: PowerSource, motor_drv: MotorDriver):
        nonlocal manual_source_active, manual_driver_active

        if not source_ctrl or not motor_drv:
            return 'error:no_model'

        if command == 'manual:toggle_source':
            if manual_source_active:
                source_ctrl.disable_output()
                manual_source_active = False
                return 'source:Off'
            else:
                source_ctrl.request_control()
                source_ctrl.set_voltage(current_model.voltage)
                source_ctrl.set_max_current(current_model.max_current)
                if isinstance(source_ctrl, ACSource):
                    source_ctrl.set_frequency(current_model.start_freq)
                source_ctrl.enable_output()
                manual_source_active = True
                return 'source:On'
        elif command == 'manual:toggle_driver':
            if manual_driver_active:
                motor_drv.remove_power()
                manual_driver_active = False
                return 'driver:Off'
            else:
                if not manual_source_active:
                    return 'error:source_off'
                motor_drv.apply_power()
                manual_driver_active = True
                return 'driver:On'
        elif command == 'manual:toggle_busy':
            state = GPIO.input(PINS.BUSY_SIGNAL)
            GPIO.output(PINS.BUSY_SIGNAL, not state)
            return f'busy:{state}'
        elif command == 'manual:toggle_ok':
            state = GPIO.input(PINS.OK_SIGNAL)
            GPIO.output(PINS.OK_SIGNAL, not state)
            return f'ok:{state}'

        return 'error:unknown'

    # --- GPIO config.
    current_rpi_mode = GPIO.getmode()
    if current_rpi_mode is None:
        GPIO.setmode(GPIO.BCM)
    elif current_rpi_mode != GPIO.BCM:
        logger.warning(f"FSM: GPIO forcing cleanup and setmode")
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
    else:
        pass

    # --- GPIO setup.
    GPIO.setup(PINS.START_SIGNAL, GPIO.IN)
    GPIO.setup(PINS.SENSOR, GPIO.IN)
    GPIO.setup(PINS.BUSY_SIGNAL, GPIO.OUT)
    GPIO.setup(PINS.OK_SIGNAL, GPIO.OUT)


    # --- Thread level setup and cleanup.
    try:
        # --- System infinite loop.
        while True:
            # --- Per Test Variables.
            current_state = 'MODEL_CHECK'
            test_in_progress = True

            # --- Per Test try.
            try:
                while test_in_progress:
                    # --- Emergency stop pressed.
                    if stop_flag.is_set():
                        logger.info('FSM: stop flag active')
                        current_state = 'TEST_CANCEL'

                    # --- Manual Mode state.
                    if current_state == 'MANUAL_MODE':
                        # --- Get current inputs state.
                        start_value = GPIO.input(PINS.START_SIGNAL)
                        sensor_value = GPIO.input(PINS.SENSOR)
                        busy_value = GPIO.input(PINS.BUSY_SIGNAL)
                        ok_value = GPIO.input(PINS.OK_SIGNAL)

                        scr_value = 1 if manual_source_active else 0
                        drv_value = 1 if manual_driver_active else 0
                        gui_queue.put(f'manual_status:{start_value}, {sensor_value}, {busy_value}, {ok_value}, {scr_value}, {drv_value}')

                        try:
                            # --- Check for command in the queue and handle it.
                            cmd = fsm_queue.get_nowait()
                            if cmd == 'cmd:manual_exit':
                                logger.info('FSM: exiting manual mode')
                                if motor_driver: motor_driver.remove_power()
                                if source_controller: source_controller.disable_output()
                                GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                                GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)
                                manual_source_active = False
                                manual_driver_active = False
                                current_state = 'MODEL_CHECK'
                            elif isinstance(cmd, str) and cmd.startswith('manual:'):
                                response = handle_manual_cmd(cmd, source_controller, motor_driver)
                                logger.info(f'FSM: manual action {response}')
                        except Empty:
                            pass

                        time.sleep(PARAMS.MANUAL_YIELD_DELAY_SEC)

                    # --- Model check state.
                    if current_state == 'MODEL_CHECK':
                        new_model = '0'

                        # --- Get new model from the queue.
                        try:
                            new_model = fsm_queue.get_nowait()
                            logger.info(f'FSM: new model: {new_model}')
                        except Empty:
                            logger.info('FSM: model queue empty')
                            pass

                        # --- Check if model is a manual mode command.
                        if isinstance(new_model, str) and new_model == 'cmd:manual_enter':
                            logger.info('FSM: entering Manual Mode')

                            manual_source_active = False
                            manual_driver_active = False
                            current_state = 'MANUAL_MODE'
                            continue

                        if isinstance(new_model, str) and new_model == 'cmd:calibration_enter':
                            logger.info('FSM: entering Calibration mode')
                            is_calibrating = True
                            continue

                        # --- Check if model has been changed.
                        if new_model != '0' and new_model != current_model:
                            if new_model is None:
                                logger.info('FSM: shutting down finite state machine')
                                return

                            # --- Driver cleanup.
                            if source_controller is not None: source_controller.cleanup()
                            if motor_driver is not None: motor_driver.cleanup()

                            logger.info(f'FSM: changing model to {new_model.name}')

                            # --- New model selection.
                            current_model = new_model
                            source_controller = None
                            motor_driver = None
                            source_is_active = False

                        if not source_is_active:
                            current_state = 'MODEL_LOAD'
                        else :
                            current_state = 'TEST_WAITING'

                    # --- Model load state.
                    elif current_state == 'MODEL_LOAD':
                        gui_queue.put(f'model:{current_model.name}')

                        # --- Create drivers only if none.
                        if source_controller is None:
                            # --- Load dc model to source controller and motor driver.
                            if current_model.motor_type.lower() == 'dc':
                                logger.info(f'FSM: attaching BK9201 to source controller')
                                source_controller = BK9201(port=PORTS.DC_PSU_PORT)
                                logger.info(f'FSM: attaching DCDriver to motor driver')
                                motor_driver = DCDriver(PINS.DC_RELAY, PINS.H_BRIDGE_ENABLE, PINS.H_BRIDGE_POS, PINS.H_BRIDGE_NEG)

                            # --- Load ac model to source controller and motor driver.
                            elif current_model.motor_type.lower() == 'ac':
                                logger.info(f'FSM: attaching BK9801 to source controller')
                                source_controller = BK9801(port=PORTS.AC_PSU_PORT)
                                logger.info(f'FSM: attaching ACDriver to motor driver')
                                motor_driver = ACDriver(PINS.AC_RELAY)

                        current_state = 'MODEL_SETTING'

                    # --- Model setting source state.
                    elif current_state == 'MODEL_SETTING':
                        # --- Enables remote control and turn source output off.
                        source_controller.request_control()

                        # --- Set up source voltage, frequency, current.
                        source_controller.set_voltage(current_model.voltage)
                        source_controller.set_max_current(current_model.max_current)

                        if isinstance(source_controller, ACSource):
                            source_controller.set_frequency(current_model.start_freq)

                        # --- Turn source output on.
                        if not source_is_active:
                            source_controller.enable_output()
                            if stop_flag.wait(PARAMS.PSU_STABILIZE_SEC): continue
                            source_is_active = True

                        current_state = 'TEST_WAITING'

                    # --- Waiting start state.
                    elif current_state == 'TEST_WAITING':
                        gui_queue.put('waiting:testinit')

                        while not stop_flag.is_set():

                            # --- Look up for start signal.
                            if GPIO.input(PINS.START_SIGNAL) == GPIO.HIGH:
                                # --- Anti debounce check.
                                if stop_flag.wait(PARAMS.DEBOUNCE_SEC): continue
                                if GPIO.input(PINS.START_SIGNAL) == GPIO.HIGH:
                                    logger.info(f'FSM: starting test')
                                    GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)
                                    current_state = 'TEST_INIT'
                                    break

                            # --- Look up for model change.
                            try:
                                if not fsm_queue.empty():
                                    logger.info('FSM: new model received')
                                    current_state = 'MODEL_CHECK'
                                    break
                            except:
                                pass

                            # --- MPU yield delay.
                            time.sleep(PARAMS.YIELD_DELAY_SEC)

                        # --- Reset loop to handle model change or stop flag.
                        if current_state != 'TEST_INIT': continue

                    # --- Test init state.
                    elif current_state == 'TEST_INIT':
                        gui_queue.put('waiting:busyon')
                        GPIO.output(PINS.BUSY_SIGNAL, GPIO.HIGH)

                        # --- Turn on relay / h-bridge.
                        motor_driver.apply_power()

                        # --- AC power source ramp setup.
                        if isinstance(source_controller, ACSource) and current_model.motor_type.lower() == 'ac':
                            current_state = 'TEST_RAMP_SETUP'
                            continue

                        # --- DC power source test preset.
                        current_state = 'TEST_PRESET'

                    # --- Test Power Source Ramp.
                    elif current_state == 'TEST_RAMP_SETUP':
                        gui_queue.put('waiting:ramp')
                        source_controller.frequency_ramp(current_model.start_freq, current_model.end_freq, current_model.delta_t)
                        current_state = 'TEST_PRESET'

                    # --- Test variable pre-set.
                    elif current_state == 'TEST_PRESET':
                        # --- Polling prepare.
                        edge_record = []
                        last_pin_state = GPIO.input(PINS.SENSOR)
                        start_time = time.time()
                        gui_update_time = time.time()
                        current_state = 'TEST_ACTIVE'

                    # --- Test active state.
                    elif current_state == 'TEST_ACTIVE':
                        if stop_flag.is_set(): continue

                        # --- Get last pin and time.
                        current_pin_state = GPIO.input(PINS.SENSOR)
                        now = time.perf_counter()

                        # --- Edge detection.
                        if current_pin_state != last_pin_state:
                            record = {'time': now, 'state': current_pin_state}
                            edge_record.append(record)
                            logger.info(f'FSM: Edge {len(edge_record)}->({now},{current_pin_state})')

                        last_pin_state = current_pin_state

                        # --- Check completion.
                        if ((not is_calibrating and len(edge_record) >= PARAMS.TEST_TARGET_EDGES) or
                                (is_calibrating and len(edge_record) >= PARAMS.CALIBRATION_TARGET_EDGES)):
                            logger.info(f'FSM: All edges detected')
                            current_state = 'TEST_STOP'
                            continue

                        # --- Check timeout.
                        if ((not is_calibrating and (time.time() - start_time) > PARAMS.TEST_TIMEOUT_SEC) or
                                (is_calibrating and (time.time() - gui_update_time) > PARAMS.CALIBRATION_TIMEOUT_SEC)):
                            logger.info('FSM: Test timed out')
                            current_state = 'TEST_STOP'

                        # --- Update gui.
                        if (time.time() - gui_update_time) > PARAMS.GUI_UPDATE_TIMEOUT_SEC:
                            gui_queue.put(f'record:{len(edge_record)}>{current_pin_state}')
                            gui_update_time = time.time()

                        # --- MPU yield delay.
                        time.sleep(PARAMS.POLL_DELAY_SEC)

                    # --- Test stop state.
                    elif current_state == 'TEST_STOP':
                        gui_queue.put('de-energizing')
                        motor_driver.remove_power()
                        if isinstance(source_controller, ACSource) and current_model.motor_type.lower() == 'ac':
                            source_controller.set_frequency(current_model.start_freq)
                        current_state = 'TEST_ANALYZE'

                    # --- Test analyze state.
                    elif current_state == 'TEST_ANALYZE':
                        gui_queue.put('analyzing')

                        # --- Get pass or fail result if not calibrating.
                        if not is_calibrating:
                            results, records = motor_analyze(edge_record, current_model.calibration_table)

                            # --- Log to results.
                            log_test_results(
                                model_name=current_model.model_name,
                                status=results['status'],
                                reason=results['reason'],
                                metrics=records,
                            )

                            # --- Pass handling.
                            if results['status'] == 'PASS':
                                logger.info(f'FSM: Test results: {results['status']}')
                                gui_queue.put('passed')
                                GPIO.output(PINS.OK_SIGNAL, GPIO.HIGH)
                                if stop_flag.wait(PARAMS.PASS_WAIT_SEC): continue
                                GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)

                            # --- Fail handling.
                            else:
                                logger.info(f'FSM: Test results: {results['status']} reason: {results['reason']}')
                                gui_queue.put('failed')
                                GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)
                                GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)

                        # --- Save calibration data to model if calibrating.
                        if is_calibrating:
                            calibration_data = motor_calibrate(edge_record)
                            logger.info(f'FSM: Calibration results: "{calibration_data}"')
                            gui_queue.put(('calibrated', calibration_data))
                            GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)
                            GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)

                        current_state = 'TEST_COMPLETE'

                    # --- Test complete state.
                    elif current_state == 'TEST_COMPLETE':
                        test_in_progress = False
                        is_calibrating = False

                    # --- Test cancel state.
                    elif current_state == 'TEST_CANCEL':
                        # --- Clean up motor driver.
                        if motor_driver: motor_driver.cleanup()

                        logger.warning(f'FSM: test cancelled by user')
                        gui_queue.put('cancelled:by_user')

                        # --- Reset outputs.
                        GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                        GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)

                        test_in_progress = False


                    # --- Test timeout state.
                    elif current_state == 'TEST_TIMEOUT':
                        # --- Clean up motor driver.
                        if motor_driver: motor_driver.cleanup()

                        logger.warning(f'FSM: test cancelled by timeout')
                        gui_queue.put(f'cancelled:timeout')

                        GPIO.output(PINS.BUSY_SIGNAL, GPIO.LOW)
                        GPIO.output(PINS.OK_SIGNAL, GPIO.LOW)

                        test_in_progress = False

            # --- Test exception handler.
            except Exception as e:
                logger.error(f'FSM: {e}', exc_info=True)
                gui_queue.put(f'error:{e}')

            # --- Test finally cleanup.
            finally:
                logger.info('FSM: finish test cleaning')
                if motor_driver:
                    motor_driver.cleanup()
                stop_flag.clear()

    # --- Thread level clean up.
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