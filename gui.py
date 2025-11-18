from tkinter import *
import time
import threading
import logging

# Equipments information
equipment_name = 'TS111125'
sw_version = 'v25.11.18'

# Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
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

class GUI(Tk):
    def __init__(self):
        logger.info('Initializing TkInter')
        super().__init__()
        logger.info('Drawing GUI')
        self.__draw__()

    def __draw__(self):
        self.title(f'{equipment_name}_{sw_version}')
        self['bg'] = root_bg_color
        self['width'] = 800
        self['height'] = 400


if __name__ == '__main__':
    logger.info('Initializing GUI')
    app = GUI()
    logger.info('Running GUI mainloop')
    app.mainloop()