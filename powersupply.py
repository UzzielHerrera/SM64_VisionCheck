import serial
import logging
import time
import math
from abc import ABC, abstractmethod
from config import PORTS, PARAMS

# --- Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- Power source contract
class PowerSource(ABC):
    @abstractmethod
    def request_control(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @abstractmethod
    def set_voltage(self, volts: float= 0.0):
        pass

    @abstractmethod
    def get_voltage(self):
        pass

    @abstractmethod
    def set_max_current(self, amps: float= 0.0):
        pass

    @abstractmethod
    def get_max_current(self):
        pass

    @abstractmethod
    def enable_output(self):
        pass

    @abstractmethod
    def disable_output(self):
        pass


# --- AC source contract
class ACSource(PowerSource):
    @abstractmethod
    def set_frequency(self, hertz: float= 0.0):
        pass

    @abstractmethod
    def get_frequency(self):
        pass

    @abstractmethod
    def frequency_ramp(self, start: float=0.0, stop: float=0.0, delta_t: float=0.0):
        pass


# --- DC source contract
class DCSource(PowerSource):
    pass


# --- BK common serial interface
class BK_Serial(PowerSource):
    def __init__(self, port: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.serial = serial.Serial(port=port, baudrate=115200, timeout=0.5)
            logger.info(f'PS: serial port opened to {port}')
        except Exception as e:
            logger.error(e)
            logger.critical('PS: using mock serial port')
            self.serial = None

    def _send_command(self, command: str):
        try:
            self.serial.reset_input_buffer()
            command += '\r\n'
            self.serial.write(command.encode('utf-8'))
            response = self.serial.readline().decode('utf-8').strip()

            if not response:
                logger.error(f'PS: timeout data transmitted->"{command[:-2]}"')
                return 0
            else:
                return response
        except Exception as e:
            logger.error(e)
            return 0

    def close_serial(self):
        try:
            if self.serial.is_open():
                self.serial.close()
        except Exception as e:
            logger.error("PS: Serial port closed")

    def request_control(self):
        """
        This command is used to switch to the remote control mode.
        :return:
        """
        self._send_command('SYST:REM')

    def cleanup(self):
        """
        This command is used to clear the error codes and information.
        :return:
        """
        self.disable_output()
        self._send_command('SYST:CLE')
        self.close_serial()

    def set_voltage(self, volts: float = 0.0):
        """
        This command is used to set a voltage output of the power supply.
        :param volts: voltage in volts
        :return:
        """
        self._send_command(f'VOLT {volts:0.2f}')

    def get_voltage(self):
        try:
            return float(self._send_command(f'VOLT?'))
        except Exception as e:
            logger.error(e)
            return 0.0

    def enable_output(self):
        """
        This command is used to drive the output relay of the power supply to ON.
        :return:
        """
        self._send_command('OUTP 1')

    def disable_output(self):
        """
        This command is used to drive the output relay of the power supply to OFF.
        :return:
        """
        self._send_command('OUTP 0')


# --- BK9801 serial interface
class BK9801(ACSource, BK_Serial):
    def __init__(self, port: str):
        super().__init__(port=port)

    def set_frequency(self, hertz: float = 0.0):
        """
        This command is used to set the output frequency value.
        :param hertz: frequency in hertz
        :return:
        """
        self._send_command(f'FREQ {hertz:0.2f}')

    def get_frequency(self):
        try:
            return float(self._send_command(f'FREQ?'))
        except Exception as e:
            logger.error(e)
            return 0.0

    def set_max_current(self, amps: float = 0.0):
        """
        This command is used to set the RMS current protection point (Irms-Protect).
        :param amps: amperage in amps
        :return:
        """
        self._send_command(f'CONF:PROT:CURR:RMS {amps:0.2f}')

    def get_max_current(self):
        try:
            return float(self._send_command(f'CONF:PROT:CURR:RMS?'))
        except Exception as e:
            logger.error(e)
            return 0.0

    def frequency_ramp(self, start: float=0.0, stop: float=1.0, delta_t: float=0.0):
        max_steps = PARAMS.PSU_RAMP_STEPS
        step_count = 0
        step_lapse_time = delta_t / max_steps

        if step_lapse_time < 0.05:
            step_lapse_time = 0.05
            max_steps = math.floor(delta_t / step_lapse_time)

        start_time = time.time()
        last_step_time = time.time()

        self.set_frequency(start)

        while step_count < max_steps:
            if time.time() - last_step_time > step_lapse_time:
                last_step_time = time.time()
                step_count += 1
                progress = step_count / max_steps
                current_freq = start + (progress * (stop - start))
                self.set_frequency(current_freq)

        self.set_frequency(stop)


# --- BK9201 serial interface
class BK9201(DCSource, BK_Serial):
    def __init__(self, port: str):
        super().__init__(port=port)

    def set_max_current(self, amps: float = 0.0):
        """
        This command is used to set the current protection point (I-Protect).
        :param amps: amperage in amps
        :return:
        """
        self._send_command(f'CURR {amps:0.2f}')

    def get_max_current(self):
        try:
            return float(self._send_command(f'CURR?'))
        except Exception as e:
            logger.error(e)
            return 0.0


if __name__ == '__main__':
    dc = BK9201(PORTS.DC_PSU_PORT)
    dc.request_control()
    dc.set_voltage(1.25)
    dc.set_max_current(0.05)
    dc.enable_output()
    time.sleep(3.0)
    dc.disable_output()


    ac = BK9801(PORTS.AC_PSU_PORT)
    ac.request_control()
    ac.set_voltage(12.0)
    ac.set_max_current(0.2)
    print(ac.get_voltage())
    ac.set_frequency(60.0)
    ac.enable_output()
    time.sleep(3.0)
    ac.disable_output()

