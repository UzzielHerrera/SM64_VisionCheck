from abc import ABC, abstractmethod
import serial
import time

encoding = 'utf-8'
voltage = 'volt'
current = 'curr'
frequency = 'freq'
output = 'outp'

# Generic power source interface
class PowerSource(ABC):
    @abstractmethod
    def request_control(self):
        pass

    @abstractmethod
    def set_voltage(self, volts: float= 0.0):
        pass

    @abstractmethod
    def set_max_current(self, amps: float= 0.0):
        pass

    @abstractmethod
    def enable_output(self):
        pass

    @abstractmethod
    def disable_output(self):
        pass

    @abstractmethod
    def cleanup(self):
        self.disable_output()


# AC source interface
class ACSource(PowerSource):
    @abstractmethod
    def set_frequency(self, hertz: float= 0.0):
        pass


# DC source interface
class DCSource(PowerSource):
    pass


# BK9801 serial interface
class BK9801(ACSource):
    pass


# BK9201 serial interface
class BK9201(DCSource):
    pass


if __name__ == '__main__':
    pass
