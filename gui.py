import os
import logging
from config import PARAMS
from logging.handlers import RotatingFileHandler

# --- Logger handler setup.
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    log_file_path = os.path.join(PARAMS.BASE_DIR, 'app.log')
    file_handler = RotatingFileHandler(filename=log_file_path, maxBytes=20 * 1024 * 1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

import queue
import threading
from tkinter import *
from functools import partial
from PIL import Image, ImageTk
from vision import vision_system
from tkinter import ttk, messagebox
from test import finite_state_machine
from models import MotorModel, ModelManager

# --- Equipments information.
equipment_name = 'TS111125'
sw_version = 'v26.03.05'

# --- Color constants.
pass_color = '#57da50'
fail_color = '#ff3300'
darker_fail_color = '#8B0000'
fail_text_color = '#ffffff'
process_color = '#ffcc00'
disable_color = '#f3f3f3'
disable_text_color = '#888888'
ready_text_color = '#000000'
root_bg_color = '#A3D0FF'
frame_bg_color = '#ffffff'
text_color = '#333333'
highlight_color = '#007acc'

# --- Fonts constants.
title_font = ("Arial", 22, "bold")
subtitle_font = ("Arial", 16)
text_font = ("Arial", 12)

class ModelCreator(Toplevel):
    def __init__(self, parent, manager, callback):
        # --- Top level initialization.
        super().__init__(parent)

        # --- Setup.
        self.title(f'{equipment_name}_{sw_version}_ModelCreator')

        # --- Fullscreen inherit.
        if parent.attributes('-fullscreen'):
            self.after(250, self.__force_fullscreen)
        else:
            self['width'] = 800
            self['height'] = 480

        # --- Grab focus.
        self.transient(parent)
        self.grab_set()
        self.focus_set()

        self.manager = manager
        self.callback = callback

        # --- Form fields.
        Label(self, text="Name:").pack(pady=5)
        self.entry_name = Entry(self)
        self.entry_name.pack()

        Label(self, text="Type (AC/DC):").pack(pady=5)
        self.combo_type = ttk.Combobox(self, values=["AC", "DC"], state="readonly")
        self.combo_type.current(0)
        self.combo_type.pack()

        Label(self, text="Voltage (V):").pack(pady=5)
        self.entry_volt = Entry(self)
        self.entry_volt.pack()

        Label(self, text="Max Current (A):").pack(pady=5)
        self.entry_curr = Entry(self)
        self.entry_curr.pack()

        Label(self, text="Start Frequency (Hz):").pack(pady=5)
        self.entry_sfreq = Entry(self)
        self.entry_sfreq.insert(0, "0.0")
        self.entry_sfreq.pack()

        Label(self, text="End Frequency (Hz):").pack(pady=5)
        self.entry_efreq = Entry(self)
        self.entry_efreq.insert(0, "0.0")
        self.entry_efreq.pack()

        Label(self, text="Ramp Time (s):").pack(pady=5)
        self.entry_delta_t = Entry(self)
        self.entry_delta_t.insert(0, "0.0")
        self.entry_delta_t.pack()


        Button(self, text='Guardar modelo', command=self.save, bg=pass_color).pack(pady=20)
        Button(self, text='Cancelar', command=self.destroy, bg=fail_color).pack(pady=20)

    def save(self):
        """ Save the model for persistence. """
        try:
            name = self.entry_name.get()
            m_type = self.combo_type.get()
            volt = float(self.entry_volt.get())
            curr = float(self.entry_curr.get())
            sfreq = float(self.entry_sfreq.get())
            efreq = float(self.entry_efreq.get())
            delta_t = float(self.entry_delta_t.get())

            if not name: raise ValueError("Name is required")

            # --- Create new model (calibration table starts empty, requires calibration).
            new_model = MotorModel(name, m_type, volt, curr, sfreq, efreq, delta_t, calibration_table=[])
            self.manager.add_model(new_model)

            messagebox.showinfo("Success", f"Profile '{name}' saved!")
            self.callback()  # Refresh main list
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid Input: {e}")

    def __force_fullscreen(self):
        """ Force fullscreen mode. """
        self.attributes('-fullscreen', True)
        self.update_idletasks()


class ModelSelector(Toplevel):
    def __init__(self, parent, manager, on_select_callback):
        super().__init__(parent)
        self.title(f'{equipment_name}_{sw_version}_ModelSelector')
        self.manager = manager
        self.on_select_callback = on_select_callback

        # --- Fullscreen inherit.
        if parent.attributes('-fullscreen'):
            self.after(250, self.__force_fullscreen)
        else:
            self['width'] = 800
            self['height'] = 480

        # --- Grab focus.
        self.transient(parent)
        self.grab_set()
        self.focus_set()

        self['bg'] = root_bg_color
        self.delete_mode = False

        # --- Variables setup.
        screen_width = 800
        screen_height = 480
        offset = 15
        header_width = screen_width - 2 * offset
        header_height = 40
        commands_height = 60
        models_y = offset + header_height + offset
        models_height = screen_height - models_y - offset - commands_height - offset

        # --- Header drawing section.
        header = Frame(self, bg=frame_bg_color, width=header_width, height=header_height)
        header.place(x=offset, y=offset, anchor='nw')
        self.lbl_title = Label(header, bg=frame_bg_color, text='Seleccionar modelo', font= title_font)
        self.lbl_title.place(x=int(header_width/2),y=3,anchor='n')

        # --- Commands drawing section.
        commands = Frame(self, bg=frame_bg_color, width=header_width, height=commands_height)
        commands.place(x=offset, y=screen_height - offset, anchor='sw')


        self.btn_toggle_delete = Button(commands, bg=fail_color, fg=fail_text_color, text="MODO BORRAR",
                                        command=self.toggle_delete_mode, width=20, height=2)
        self.btn_toggle_delete.place(x=header_width - offset, y=5, anchor='ne')

        Button(commands, bg=pass_color, fg=fail_text_color, text="NUEVO MODELO", width=20,
                height=2, command=self.open_creator).place(x=offset, y=5, anchor='nw')

        Button(commands, bg=fail_color, fg=fail_text_color, text="CANCELAR", width=20,
                height=2, command=self.destroy, justify='center').place(x=int(header_width/2),y=5, anchor='n')


        # --- Models drawing section.
        self.models_selector = Frame(self, bg=frame_bg_color, width=header_width, height=models_height)
        self.models_selector.place(x=int(screen_width / 2), y=models_y, anchor='n')

        self.refresh_models()

    def __force_fullscreen(self):
        """ Force fullscreen mode. """
        self.attributes('-fullscreen', True)
        self.update_idletasks()

    def toggle_delete_mode(self):
        """ Toggle delete mode. """
        self.delete_mode = not self.delete_mode

        if self.delete_mode:
            self.btn_toggle_delete.config(text='CANCELAR BORRAR', bg=fail_color, fg=fail_text_color)
            self.lbl_title.config(text='Borrar modelo')
        else:
            self.btn_toggle_delete.config(text='MODO BORRAR', bg=disable_color, fg=ready_text_color)
            self.lbl_title.config(text='Seleccionar modelo')

        self.refresh_models()

    def refresh_models(self):
        """ Refresh models draw list. """
        for widget in self.models_selector.winfo_children():
            widget.destroy()

        names = self.manager.get_all_names()

        if not names:
            Label(self.models_selector, text='No hay modelos guardados', bg=fail_color).place(x=10, y=10, anchor='nw')
            return

        rows = 4
        if self.delete_mode:
            btn_bg = fail_color
        else:
            btn_bg = frame_bg_color

        # --- Create a button for every model.
        for i, name in enumerate(names):
            row_index = i % rows
            col_index = i // rows
            # partial(func, arg) allows us to pass the specific name to the function
            btn = Button(self.models_selector, text=name, font=subtitle_font,
                            bg=btn_bg, height=2, width=13,
                            command=partial(self.on_model_clicked, name))
            btn.grid(row=row_index, column=col_index, padx=5, pady=5, sticky='nsew')

    def on_model_clicked(self, name):
        """ Triggered when a model button is pressed. """
        # --- Delete selected model.
        if self.delete_mode:
            # --- Show confirmation window.
            if messagebox.askyesno('Confirmar Borrado', f'¿Estás seguro de ELIMINAR permanentemente el modelo "{name}"'):
                success = self.manager.delete_model(name)
                if success:
                    self.toggle_delete_mode()
                else:
                    messagebox.showerror('Error', f'No se pudo borrar el modelo "{name}"')

        # --- Load selected model.
        else:
            logger.info(f'ModelSelector: user picked "{name}"')
            self.on_select_callback(name)
            self.destroy()

    def open_creator(self):
        """ Opens the creator window. """
        ModelCreator(self, self.manager, self.refresh_models)


class ManualController(Toplevel):
    def __init__(self, parent, send_command_callback, current_model_name, model_type):
        super().__init__(parent)
        self.title(f'{equipment_name}_{sw_version}_ManualControl:{current_model_name},{model_type}')
        self.send_command = send_command_callback
        self['bg'] = root_bg_color
        self.protocol('WM_DELETE_WINDOW', self.close_manual_mode)

        # --- Fullscreen inherit.
        if parent.attributes('-fullscreen'):
            self.after(250, self.__force_fullscreen)
        else:
            self['width'] = 800
            self['height'] = 480

        # --- Grab focus.
        self.transient(parent)
        self.grab_set()
        self.focus_set()

        # --- Start manual mode in the FSM.
        self.send_command('cmd:manual_enter')

        # --- GUI variables.
        screen_width = 800
        screen_height = 480

        offset = 15
        header_width = screen_width - 2 * offset
        header_height = 40

        main_y = offset + header_height + offset
        main_height = screen_height - main_y - offset

        cmd_width = int((screen_width - 3 * offset) / 2)
        cmd_height = main_height
        cmd_center = int(cmd_width / 2)

        status_width = int((screen_width - 3 * offset) / 2)
        status_height = main_height

        # --- Header drawing section.
        header_frame = Frame(self, width=header_width, height=header_height, bg=frame_bg_color)
        header_frame.place(x=offset, y=offset, anchor='nw')
        Label(header_frame, text=f"MODO MANUAL -> {current_model_name},{model_type}", font=title_font, bg=frame_bg_color,
                fg=text_color).place(x=int(header_width/2), y=3, anchor='n')

        # --- Command drawing section.
        cmd_frame = Frame(self, width=cmd_width, height=cmd_height, bg=frame_bg_color)
        cmd_frame.place(x=offset, y=main_y, anchor='nw')
        Label(cmd_frame, text="--- Comandos ---", font=subtitle_font,
                bg=frame_bg_color).place(x=int(status_width / 2), y=5, anchor='n')

        self.btn_source = self.create_toggle_btn(cmd_frame, 'Fuente', 'manual:toggle_source', cmd_center, 3*offset)
        self.btn_driver = self.create_toggle_btn(cmd_frame, 'Motor', 'manual:toggle_driver', cmd_center, 8*offset)
        self.btn_busy = self.create_toggle_btn(cmd_frame, 'BUSY', 'manual:toggle_busy', cmd_center, 13*offset)
        self.btn_ok = self.create_toggle_btn(cmd_frame, 'OK', 'manual:toggle_ok', cmd_center, 18*offset)
        self.btn_tooling = self.create_toggle_btn(cmd_frame, 'TOOLING', 'manual:toggle_tooling', cmd_center, 23*offset)

        # --- Status drawing section.
        status_frame = Frame(self, width=status_width, height=status_height, bg=frame_bg_color)
        status_frame.place(x=screen_width - offset, y=main_y, anchor='ne')
        Label(status_frame, text="--- Estado ---", font=subtitle_font,
                bg=frame_bg_color).place(x=int(status_width / 2), y=5, anchor='n')

        Button(status_frame, bg=fail_color, fg=fail_text_color, text="CANCELAR", width=20, height=2, command=self.close_manual_mode,
                justify='center', font=subtitle_font).place(x=int(status_width / 2), y=status_height - offset, anchor='s')

        self.led_start = self.create_led(status_frame, 'Start signal', offset, 4*offset)
        self.led_sensor = self.create_led(status_frame, 'Sensor signal', offset, 8*offset)
        self.led_tooling = self.create_led(status_frame, 'Tooling signal', offset, 12*offset)

    def create_led(self, parent, text, x, y):
        """ Create a LED indicator for an input. """
        c = Canvas(parent, width=30, height=30, bg=frame_bg_color, highlightthickness=0)
        c.place(x=x, y=y, anchor='w')
        l = c.create_oval(2,2,28,28,fill=fail_color, outline='gray')
        Label(parent, text=text, font=subtitle_font, bg=frame_bg_color,
                justify='left').place(x=x+35, y=y, anchor='w')
        return (c, l)

    def create_toggle_btn(self, parent, text, cmd, x, y):
        """ Create a Toggle button for an output. """
        btn = Button(parent, text=text, font=subtitle_font, height=2, bg=disable_color, fg=text_color, width=20,
                        activebackground=disable_color, activeforeground=text_color,
                        command= lambda: self.send_command(cmd))
        btn.place(x=x, y=y, anchor='n')
        return btn

    def update_manual(self, start, sensor, busy, ok, src_on, drv_on, tool_down):
        """ Update manual mode color indicators for inputs and outputs. """
        # --- Update inputs.
        self.led_start[0].itemconfig(self.led_start[1], fill=pass_color if int(start) else fail_color)
        self.led_sensor[0].itemconfig(self.led_sensor[1], fill=pass_color if int(sensor) else fail_color)
        self.led_tooling[0].itemconfig(self.led_tooling[1], fill=pass_color if int(tool_down) else fail_color)

        # --- Update outputs.
        self.btn_busy['bg'] = pass_color if int(busy) else disable_color
        self.btn_busy['activebackground'] = pass_color if int(busy) else disable_color
        self.btn_ok['bg'] = pass_color if int(ok) else disable_color
        self.btn_ok['activebackground'] = pass_color if int(ok) else disable_color
        self.btn_source['bg'] = pass_color if int(src_on) else disable_color
        self.btn_source['activebackground'] = pass_color if int(src_on) else disable_color
        self.btn_driver['bg'] = pass_color if int(drv_on) else disable_color
        self.btn_driver['activebackground'] = pass_color if int(drv_on) else disable_color

    def __force_fullscreen(self):
        """ Force fullscreen mode. """
        self.attributes('-fullscreen', True)
        self.update_idletasks()

    def close_manual_mode(self):
        """ Cancel manual mode. """
        self.send_command('cmd:manual_exit')
        self.destroy()


class GUI(Tk):
    def __init__(self):
        # --- Tkinter initialization.
        logger.info('Initializing Tkinter')
        super().__init__()

        # --- Protocol over-write.
        self.protocol('WM_DELETE_WINDOW', self.on_close)

        # --- Data and communications.
        self.model_manager = ModelManager()

        # --- Queues for thread communication.
        self.gui_queue = queue.Queue()
        self.model_queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.shutdown_timer_id = None
        self.gui_running = True

        # --- GUI variables.
        self.result_hold = False
        self.hold_timer = None

        # --- GUI creation.
        logger.info('Drawing GUI')
        self.__draw__()

        # --- Input threads.
        self.input_thread = threading.Thread(target=self.console_input, daemon=True)
        self.input_thread.start()

        # --- Start worker thread.
        self.start_worker()

        # --- Start polling loop.
        self.check_queue()

    def __force_fullscreen(self):
        """ Force fullscreen mode. """
        self.attributes('-fullscreen', True)
        self.update_idletasks()

    def __draw__(self):
        """ Draw the GUI. """
        # --- Variables setup.
        screen_width = 800
        screen_height = 480

        offset = 15
        header_width = screen_width - 2 * offset
        header_height = 40

        main_y = offset + header_height + offset
        main_height = screen_height - main_y - offset

        model_width = int((screen_width - 3 * offset) / 2)
        model_height = main_height - 150

        status_width = int((screen_width - 3 * offset) / 2)
        status_height = main_height

        inner_offset = 15
        state_offset = 4 * inner_offset
        state_width = status_width - state_offset
        state_height = state_offset

        command_height = status_height - offset - model_height

        # --- Main windows settings.
        self.title(f'{equipment_name}_{sw_version}_AutomaticTest')
        self['bg'] = root_bg_color

        if os.environ.get('SSH_CLIENT') or os.environ.get('SSH_TTY'):
            logger.info(f'Running from ssh session')
            self.attributes('-fullscreen', False)
            self['width'] = screen_width
            self['height'] = screen_height
        else:
            logger.info(f'Running from terminal')
            self['width'] = screen_width
            self['height'] = screen_height
            # self.after(500, self.__force_fullscreen)

        # --- Header drawing section.
        header_frame = Frame(self, width=header_width, height=header_height, bg=frame_bg_color)
        header_frame.place(x=offset, y=offset, anchor='nw')
        Label(header_frame, text="SM64 & SM66", font=title_font, bg=frame_bg_color,
                fg=text_color).place(x=int(header_width/2), y=3, anchor='n')

        # --- Model drawing section.
        model_frame = Frame(self, width=model_width, height=model_height, bg=frame_bg_color)
        model_frame.place(x=offset, y=main_y, anchor='nw')

        Label(model_frame, text="--- Modelos ---", font=subtitle_font, bg=frame_bg_color).place(x=int(model_width/2), y=5, anchor='n')

        Label(model_frame, text="Modelo Actual:", bg=frame_bg_color, justify='center',
                font=subtitle_font).place(x=int(model_width / 2), y=3 * inner_offset, anchor='n')

        self.lbl_current_model = Label(model_frame, text="* Sin Seleccionar *", bg=frame_bg_color, font=title_font,
                                        justify='center')
        self.lbl_current_model.place(x=int(model_width / 2), y=5 * inner_offset, anchor='n')

        Button (model_frame, text='SELECCION DE MODELO', bg=highlight_color, fg=fail_text_color, font=text_font,
                width=24, height=2, command=self.open_model_manager).place(x=int(model_width/2), y=8 * inner_offset, anchor='n')

        Button(model_frame, text='CALIBRAR', bg=pass_color, fg=fail_text_color, font=text_font,
                width=24, height=2, command=self.calibrate_model).place(x=int(model_width / 2), y=12 * inner_offset, anchor='n')

        # --- Status drawing section.
        status_frame = Frame(self, width=status_width, height=status_height, bg=frame_bg_color)
        status_frame.place(x=screen_width - offset, y=main_y, anchor='ne')

        # Label(status_frame, text="--- Estado ---", font=subtitle_font,
        #         bg=frame_bg_color).place(x=int(model_width / 2), y=5, anchor='n')

        self.state_frame = Frame(status_frame, width=state_width, height=state_height, bg=disable_color)
        self.state_frame.place(x=int(status_width / 2), y=main_height - 8 *  inner_offset, anchor='n')

        self.status_label = Label(self.state_frame, text="CARGANDO", font=title_font,
                                    bg=disable_color, fg=disable_text_color, height=1, justify='center')
        self.status_label.place(x = int(state_width / 2), y=inner_offset, anchor='n')

        self.info_label = Label(status_frame, text="Esperando modelo...", font=text_font, bg=frame_bg_color)
        self.info_label.place(x=int(status_width / 2), y=main_height - 2 * inner_offset, anchor='s')

        self.lbl_good_counter = Label(status_frame, text="Buenas: 0", font=text_font, bg=frame_bg_color)
        self.lbl_good_counter.place(x= 2 * inner_offset, y= main_height - 7, anchor='sw')

        self.lbl_bad_counter = Label(status_frame, text="Malas: 0", font=text_font, bg=frame_bg_color)
        self.lbl_bad_counter.place(x=status_width - 2 * inner_offset, y= main_height - 7, anchor='se')

        # --- Controls drawing section.
        control_frame = Frame(self, width=model_width, height=command_height,  bg=frame_bg_color)
        control_frame.place(x=offset, y=screen_height - offset, anchor='sw')

        Label(control_frame, text="--- Comandos ---", font=subtitle_font,
                bg=frame_bg_color).place(x=int(model_width / 2), y=5, anchor='n')

        self.btn_stop = Button(control_frame, text="CANCELAR",
                                font=subtitle_font, bg=fail_color, fg=fail_text_color,
                                height=2, width=11, justify='center')
        self.btn_stop.place(x=inner_offset, y=3 * inner_offset, anchor='nw')
        self.btn_stop.bind('<ButtonPress-1>', self.on_stop_btn_press)
        self.btn_stop.bind('<ButtonRelease-1>', self.on_stop_btn_release)

        Button(control_frame, text='MANUAL', bg=highlight_color, fg=fail_text_color,
                font=subtitle_font, width=11, height=2,
                command=self.open_manual_mode).place(x=model_width-inner_offset, y=3 * inner_offset, anchor='ne')

        # --- Camera drawing section.
        self.video_label = Label(status_frame, text="Loading camera...", bg=ready_text_color)
        self.video_label.place(x=2 * inner_offset, y=inner_offset, anchor='nw')
        vision_system.start_stream()
        self.update_video_feed()

    def update_video_feed(self):
        if vision_system.new_frame_available:
            frame_rgb = vision_system.get_frame_for_gui()

            if frame_rgb is not None:
                image = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image)

                self.video_label.config(image=photo)
                self.video_label.image = photo

        self.after(35, self.update_video_feed)

    # --- Logic methods.
    def open_manual_mode(self):
        """ Opens the TopLevel Manual Controller. """
        current_model_name = self.lbl_current_model['text']
        if current_model_name == '* Sin Seleccionar *':
            logger.warning('GUI: no model selected')
            return
        model_obj = self.model_manager.get_model(current_model_name)

        def send_to_worker(cmd):
            self.model_queue.put(cmd)

        # --- Starts manual controller in the GUI.
        self.manual_window = ManualController(self, send_to_worker, self.lbl_current_model['text'], model_obj.motor_type)

    def open_model_manager(self):
        """ Opens the TopLevel Model Selector. """
        ModelSelector(self, self.model_manager, self.load_model_by_name)

    def calibrate_model(self):
        """ Set FSM to calibrate the current model. """
        # self.model_queue.put('cmd:calibration_enter')
        success = vision_system.calibrate_gui_safe()

        # 2. Feedback visual (opcional)
        if success:
            print("GUI: Calibration complete.")
        else:
            print("GUI: Calibración failed or cancelled.")

    def load_model_by_name(self, name):
        """ Callback used by the ModelManager to load a model. """
        model = self.model_manager.get_model(name)
        if model:
            self.lbl_current_model['text'] = name
            logger.info(f'GUI: loading model "{name}"')
            self.model_manager.save_last_used(name)
            self.model_queue.put(model)
            self.gui_queue.put(f'waiting:model-{name}')

    def start_worker(self):
        """ Starts the persistent worker thread. """
        last_model_name = self.model_manager.get_last_used()
        init_model = None

        # --- Get last running model or create a default model.
        if last_model_name:
            init_model = self.model_manager.get_model(last_model_name)

        if not init_model:
            logger.info('GUI: no model selected, loading default model')
            init_model = MotorModel("None", "DC", 0, 0, 0, [])
        else:
            logger.info(f'GUI: model selected, loading "{init_model.name}"')
            if hasattr(self, 'lbl_current_model'):
                self.lbl_current_model['text'] = init_model.name

        # --- Start test FSM thread.
        self.worker_thread = threading.Thread(
            target=finite_state_machine,
            args=(self.gui_queue, init_model, self.model_queue, self.stop_flag),
            daemon=True
        )
        self.worker_thread.start()

    def console_input(self):
        """ Function used to interact directly with the GUI and FSM trough console input. """
        while self.gui_running:
            try:
                logger.info('Enter command >')
                # --- Wait for console input message.
                user_input = input()
                if user_input == 'exit':
                    self.on_close()
                else:
                    if user_input == 'cmd:calibrate':
                        self.calibrate_model()
                    # --- Write commands to FSM.
                    elif 'cmd' in user_input:
                        self.model_queue.put(user_input)
                    # --- Write command to GUI.
                    else:
                        self.gui_queue.put(user_input)
            except (EOFError, KeyboardInterrupt):
                break

    def check_queue(self):
        """ Polls the queue for messages from the worker. """
        if not self.gui_running:
            return
        try:
            while True:
                # --- Check if new message is in the queue and handle it.
                msg = self.gui_queue.get_nowait()
                self.update_gui_from_message(msg)
        except queue.Empty:
            pass
        finally:
            if self.gui_running:
                self.after(100, self.check_queue)

    def update_gui_from_message(self, msg: str):
        """ Parses messages and updates colors/text. """

        # --- Handle manual mode's messages.
        if msg.startswith('manual_status'):
            try:
                data = msg.split(':')[1]
                start, sensor, busy, ok, src, drv,tool_down = data.split(',')
                if hasattr(self, 'manual_window') and self.manual_window.winfo_exists():
                    self.manual_window.update_manual(start, sensor, busy, ok, src, drv, tool_down)
            except Exception as e:
                pass
            return

        # --- Handle results messages.
        if msg=='passed' or msg=='failed':
            # --- Set results for 2 seconds persistence over other messages.
            self.result_hold = True
            if self.hold_timer: self.after_cancel(self.hold_timer)
            self.hold_timer = self.after(2000, self.clear_result_hold)
            if msg == 'passed':
                self.add_goods()
                self.change_status('PASO', pass_color, fail_text_color)
                self.info_label['text'] = 'Motor paso'
            elif msg == 'failed':
                self.add_bads()
                self.change_status('FALLO', fail_color, fail_text_color)
                self.info_label['text'] = 'Motor fallo'
            return
        elif msg == 'waiting:testinit':
            if not self.result_hold:
                self.change_status('LISTO', disable_color, ready_text_color)
                self.info_label['text'] = 'Esperando inicio de prueba'
            return

        # --- Resets 2-second persistence of results if a new test started.
        if self.result_hold:
            self.result_hold = False
            if self.hold_timer:
                self.after_cancel(self.hold_timer)
                self.hold_timer = None

        # --- Handle in-test messages.
        if 'waiting:model' in msg:
            self.change_status('ESPERANDO', disable_color, disable_text_color)
            self.info_label['text'] = f'Esperando modelo: "{msg.split("-")[1]}"'
        elif 'model' in msg:
            self.change_status('CARGANDO', disable_color, disable_text_color)
            self.info_label['text'] = f'Cargando modelo: "{msg.split(":")[1]}"'
        elif msg == 'waiting:busyon':
            self.change_status('PROBANDO', process_color, ready_text_color)
            self.info_label['text'] = 'Prueba iniciada'
        elif msg == 'waiting:ramp':
            self.change_status('PROBANDO', process_color, ready_text_color)
            self.info_label['text'] = 'Realizando rampa de frequencia'
        elif 'record' in msg:
            self.change_status('PROBANDO', process_color, ready_text_color)
            self.info_label['text'] = f'Esperando flanco #{msg[7]}'
        elif msg == 'de-energizing':
            self.change_status('PROBANDO', process_color, ready_text_color)
            self.info_label['text'] = 'Desenergizando motor'
        elif msg == 'analyzing':
            self.change_status('PROBANDO', process_color, ready_text_color)
            self.info_label['text'] = 'Analizando resultados'
        elif msg == 'cancelled:by_user':
            self.change_status('CANCELADO', fail_color, fail_text_color)
            self.info_label['text'] = 'Cancelado por usuario'
        elif msg == 'cancelled:timeout':
            self.change_status('TIMEOUT', fail_color, fail_text_color)
            self.info_label['text'] = 'Cancelado por timeout'
        elif 'error' in msg:
            self.change_status('ERROR', fail_color, fail_text_color)
            self.info_label['text'] = f'{msg[6:]}'
        else:
            self.info_label.config(text=msg)

    def clear_result_hold(self):
        """ Clear the result 2-second persistence. """
        self.result_hold = False
        self.hold_timer = None
        self.change_status('LISTO', disable_color, ready_text_color)
        self.info_label['text'] = 'Esperando inicio de prueba'

    def change_status(self, status_msg, bg_clr, fg_clr):
        """ Update status label and frame. """
        self.state_frame['bg'] = bg_clr
        self.status_label['bg'] = bg_clr
        self.status_label['fg'] = fg_clr
        self.status_label['text'] = status_msg

    def add_goods(self):
        """ Add one piece to GUI's good counter. """
        text = self.lbl_good_counter['text']
        pieces = int(text.split(':')[1]) + 1
        text = f'{text.split(':')[0]}: {pieces}'
        self.lbl_good_counter['text'] = text

    def add_bads(self):
        """ Add one piece to GUI's bad counter. """
        text = self.lbl_bad_counter['text']
        pieces = int(text.split(':')[1]) + 1
        text = f'{text.split(':')[0]}: {pieces}'
        self.lbl_bad_counter['text'] = text

    def on_stop_btn_press(self, event):
        """ E-Stop button pressed actions. """
        self.stop_test()

        self.btn_stop['bg'] = darker_fail_color
        self.shutdown_timer_id = self.after(3000, self.perform_shutdown)

    def on_stop_btn_release(self, event):
        """ E-Stop button released actions. """
        # --- Cancel shutdown timer.
        if self.shutdown_timer_id is not None:
            self.after_cancel(self.shutdown_timer_id)
            self.shutdown_timer_id = None

        self.btn_stop['bg'] = fail_color

    def perform_shutdown(self):
        """ Starts shutdown procedure. """
        logger.warning(f'GUI: shutting down')
        self.shutdown_timer_id = None
        self.on_close()

    def stop_test(self):
        """ Sends stop signal to worker. """
        logger.warning("Stop Button Pressed")
        self.stop_flag.set()

    def on_close(self):
        """ Handles closing the GUI. """
        logger.warning('GUI: initializing application shutdown')

        # --- Stop camera stream.
        vision_system.stop_stream()

        # --- Inject venom pill to threads that trigger shutdown.
        self.gui_running = False
        self.model_queue.put(None)

        self.status_label.config(text="APAGANDO", bg=fail_color, fg=fail_text_color)
        self.state_frame.config(bg=fail_color)

        # --- Force redraw to see shutdown message.
        self.update()

        # --- Wait for console_input thread to stops.
        if self.input_thread.is_alive():
            self.input_thread.join(timeout=1)

        # --- Wait for FSM thread to stops.
        try:
            if self.worker_thread.is_alive():
                self.worker_thread.join(timeout=10.0)
        except Exception:
            pass
        self.destroy()


if __name__ == '__main__':
    logger.info('Initializing GUI')
    app = GUI()
    logger.info('Running GUI mainloop')
    app.mainloop()
    logger.info('Terminated GUi mainloop')
