import serial
import time

encoding = 'utf-8'
voltage = 'volt'
current = 'curr'
frequency = 'freq'
output = 'outp'

class PowerSupply:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        self.port = serial.Serial(port=port, baudrate=baudrate, timeout=1)

