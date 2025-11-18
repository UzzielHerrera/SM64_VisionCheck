from abc import ABC, abstractmethod
import serial
import time
import logging
import logging.handlers

# Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Power source contract
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


# AC source contract
class ACSource(PowerSource):
    @abstractmethod
    def set_frequency(self, hertz: float= 0.0):
        pass

    @abstractmethod
    def get_frequency(self):
        pass


# DC source contract
class DCSource(PowerSource):
    pass


# BK common serial interface
class BK_Serial(PowerSource):
    def __init__(self, port: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.serial = serial.Serial(port=port, baudrate=9600, timeout=1)
            logger.info(f'Serial port opened to {port}')
        except Exception as e:
            logger.error(e)
            logger.critical('Using mock serial port')
            self.serial = None

    def _send_command(self, command: str):
        try:
            self.serial.reset_input_buffer()
            self.serial.write(command.encode('utf-8') + b'\r\n')
            response = self.serial.readline().decode('utf-8').strip()

            if not response:
                logger.error(f'TimeOut: data_transmitted->"{command}"')
                return 0
            else:
                return response
        except Exception as e:
            logger.error(e)
            return 0

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
        self._send_command('SYST:CLE')

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


# BK9801 serial interface
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

# BK9201 serial interface
class BK9201(DCSource, BK_Serial):
    def __init__(self, port: str):
        super().__init__(port=port)


if __name__ == '__main__':
    dc = BK9201('COM4')
    ac = BK9801('COM5')
