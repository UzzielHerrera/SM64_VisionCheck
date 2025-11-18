import logging
from threading import Thread, Event
import time
from abc import ABC, abstractmethod

# --- Mocking for Development ---
try:
    import RPi.GPIO as GPIO
    print("Real RPi.GPIO library loaded.")
except (ImportError, RuntimeError):
    print("WARNING: RPi.GPIO not found. Using Mock GPIO.")
    class MockGPIO:
        OUT = "out"
        HIGH = 1
        LOW = 0
        BCM = "bcm"
        BOARD = "rpi4"
        def setup(self, *args, **kwargs): print(f"MOCK_GPIO: setup({args}, {kwargs})")
        def output(self, *args, **kwargs): print(f"MOCK_GPIO: output({args}, {kwargs})")
        def setmode(self, *args, **kwargs): print(f"MOCK_GPIO: setmode({args}, {kwargs})")
        def cleanup(self, *args, **kwargs): print(f"MOCK_GPIO: cleanup()")
        def setwarnings(self, *args, **kwargs): print(f"MOCK_GPIO: setwarnings({args}, {kwargs})")
    GPIO = MockGPIO()

# GPIO initial configuration
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

# Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Motor driver contracts
class MotorDriver(ABC):
    @abstractmethod
    def apply_power(self):
        pass

    @abstractmethod
    def remove_power(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

# AC Motor driver implementation
class ACDriver(MotorDriver):
    def __init__(self, ac_relay_pin: int) -> None:
        self.relay_pin = ac_relay_pin
        GPIO.setup(self.relay_pin, GPIO.OUT)
        self.remove_power()
        logger.info(f'ACDriver initialized on pin {self.relay_pin}')

    def apply_power(self):
        logger.info(f'ACDriver closing relay (Pin {self.relay_pin} HIGH)')
        GPIO.output(self.relay_pin, GPIO.HIGH)

    def remove_power(self):
        logger.info(f'ACDriver opening relay (Pin {self.relay_pin} LOW)')
        GPIO.output(self.relay_pin, GPIO.LOW)

    def cleanup(self):
        self.remove_power()


class DCDriver(MotorDriver):
    def __init__(self, dc_relay_pin: int, h_bridge_enable: int, h_bridge_pos_pin: int, h_bridge_neg_pin: int) -> None:
        self.relay_pin = dc_relay_pin
        self.en_pin = h_bridge_enable
        self.pos_pin = h_bridge_pos_pin
        self.neg_pin = h_bridge_neg_pin

        self.pins = [self.relay_pin, self.en_pin, self.pos_pin, self.neg_pin]
        for pin in self.pins:
            GPIO.setup(pin, GPIO.OUT)

        self.signal_thread = None
        self.stop_signal_event = Event()

        self.remove_power()
        logger.info(f"DCDriver (Threaded) initialized on pins {self.pins}")

    def _set_off(self):
        GPIO.output(self.en_pin, GPIO.LOW)
        GPIO.output(self.pos_pin, GPIO.LOW)
        GPIO.output(self.neg_pin, GPIO.LOW)

    def _set_no_signal(self):
        """
        Sets H-Bridge to a no signal or brake state.
        :return:
        """
        GPIO.output(self.en_pin, GPIO.HIGH)
        GPIO.output(self.pos_pin, GPIO.LOW)
        GPIO.output(self.neg_pin, GPIO.LOW)

    def _set_positive(self):
        """
        Sets H-Bridge to a positive state.
        :return:
        """
        GPIO.output(self.en_pin, GPIO.HIGH)
        GPIO.output(self.pos_pin, GPIO.HIGH)
        GPIO.output(self.neg_pin, GPIO.LOW)

    def _set_negative(self):
        """
        Sets H-Bridge to a negative state.
        :return:
        """
        GPIO.output(self.en_pin, GPIO.HIGH)
        GPIO.output(self.pos_pin, GPIO.LOW)
        GPIO.output(self.neg_pin, GPIO.HIGH)

    def _signal_loop(self):
        logger.info("DCDriver H-Bridge loop started")
        step_duration_sec = 0.0625 # 62.5ms

        signal_steps = [self._set_no_signal, self._set_positive, self._set_no_signal, self._set_negative]

        current_step_index = 0
        next_step_time = time.perf_counter()

        while not self.stop_signal_event.is_set():
            now = time.perf_counter()
            if now >= next_step_time:
                signal_steps[current_step_index]()
                next_step_time += step_duration_sec
                current_step_index = (current_step_index + 1) % 4
            time.sleep(0.001)

        logger.info(f"DCDriver H-Bridge loop ended")
        self._set_off()

    def apply_power(self):
        """
        Start signal generation thread and enables the DC relay
        :return:
        """
        if self.signal_thread is None:
            self.stop_signal_event.clear()
            self.signal_thread = Thread(target=self._signal_loop, daemon=True)
            self.signal_thread.start()

            logger.info(f'DCDriver closing relay (Pin {self.relay_pin} HIGH) ')
            GPIO.output(self.relay_pin, GPIO.HIGH)
        else:
            logger.warning('DCDriver signal thread already running')

    def remove_power(self):
        """
        Stops signal generation thread and disables the DC relay
        :return:
        """
        if self.signal_thread is not None:
            self.stop_signal_event.set()

            self.signal_thread.join(timeout=0.5)
            self.signal_thread = None

        self._set_off()
        logger.info(f'DCDriver opening relay (Pin {self.relay_pin} LOW)')
        GPIO.output(self.relay_pin, GPIO.LOW)

    def cleanup(self):
        self.remove_power()

if __name__ == "__main__":
    dc = DCDriver(0,1,2,3)
    dc.apply_power()
    time.sleep(2)
    dc.remove_power()
    time.sleep(2)

    ac = ACDriver(0)
    ac.apply_power()
    time.sleep(2)
    ac.remove_power()

