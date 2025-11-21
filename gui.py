import queue
from tkinter import *
from tkinter import ttk, messagebox
import time
import threading
import logging
from models import MotorModel, ModelManager
from test import finite_state_machine

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
fail_text_color = '#ffffff'
process_color = '#ffcc00'
disable_color = '#f3f3f3'
disable_text_color = '#888888'
ready_text_color = '#000000'
root_bg_color = '#A3D0FF'
frame_bg_color = '#ffffff'
text_color = '#333333'

class ModelManagement(Toplevel):
    def __init__(self, parent, manager, callback):
        # --- Top level initialization
        super().__init__(parent)

        # --- Setup
        self.title(f'{equipment_name}_{sw_version}->ModelManagement')
        self.geometry('300x400')
        self.manager = manager
        self.callback = callback

        # --- Form fields
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

        Label(self, text="Frequency (Hz) [AC Only]:").pack(pady=5)
        self.entry_freq = Entry(self)
        self.entry_freq.insert(0, "0.0")
        self.entry_freq.pack()

        Button(self, text="Save Profile", command=self.save, bg=pass_color).pack(pady=20)

    def save(self):
        try:
            name = self.entry_name.get()
            m_type = self.combo_type.get()
            volt = float(self.entry_volt.get())
            curr = float(self.entry_curr.get())
            freq = float(self.entry_freq.get())

            if not name: raise ValueError("Name is required")

            # Create new model (Master table starts empty, requires calibration)
            new_model = MotorModel(name, m_type, volt, curr, freq, calibration_table=[])
            self.manager.add_model(new_model)

            messagebox.showinfo("Success", f"Profile '{name}' saved!")
            self.callback()  # Refresh main list
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid Input: {e}")


class GUI(Tk):
    def __init__(self):
        # --- Tkinter initialization
        logger.info('Initializing Tkinter')
        super().__init__()

        # --- Protocol over-write
        self.protocol('WM_DELETE_WINDOW', self.on_close)

        # --- Data and communications
        self.model_manager = ModelManager()

        # --- Queues for thread communication
        self.gui_queue = queue.Queue()
        self.model_queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.gui_running = True

        # --- GUI creation
        logger.info('Drawing GUI')
        self.__draw__()

        # --- Input threads
        self.input_thread = threading.Thread(target=self.console_input, daemon=True)
        self.input_thread.start()

        # --- Start worker thread
        self.start_worker()

        # --- Start polling loop
        self.check_queue()


    def __draw__(self):
        # --- Variables
        screen_width = 800
        screen_height = 400

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
        state_width = status_width - 2 * state_offset
        state_height = 200

        command_height = status_height - offset - model_height


        title_font = ("Arial", 22, "bold")
        subtitle_font = ("Arial", 16)
        text_font = ("Arial", 12)

        # --- Main windows settings
        self.title(f'{equipment_name}_{sw_version}->AutomaticTest')
        self['bg'] = root_bg_color
        self['width'] = screen_width
        self['height'] = screen_height

        # --- Header section
        header_frame = Frame(self, width=header_width, height=header_height, bg=frame_bg_color)
        header_frame.place(x=offset, y=offset, anchor='nw')
        Label(header_frame, text="SM64 & SM66 Motor Tester", font=title_font, bg=frame_bg_color,
                fg=text_color).place(x=int(header_width/2), y=3, anchor='n')

        # --- Model section
        model_frame = Frame(self, width=model_width, height=model_height, bg=frame_bg_color)
        model_frame.place(x=offset, y=main_y, anchor='nw')

        Label(model_frame, text="--- Modelos ---", font=subtitle_font, bg=frame_bg_color).place(x=int(model_width/2), y=5, anchor='n')

        Label(model_frame, text="Seleccion de modelo:", bg=frame_bg_color,
                font=text_font).place(x=inner_offset, y=3 * inner_offset, anchor='nw')

        self.model_combo = ttk.Combobox(model_frame, state="readonly", width=25, font=subtitle_font, justify='center')
        self.model_combo.place(x=inner_offset, y=5 * inner_offset, anchor='nw')
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_selected)

        Button(model_frame, text="Nuevo modelo", command=self.new_model, font=text_font,
                bg=pass_color).place(x= inner_offset, y=8 * inner_offset, anchor='nw')
        Button(model_frame, text="Borrar modelo", command=self.delete_model, bg=fail_color, font=text_font,
                fg=fail_text_color).place(x=model_width - inner_offset, y=8 * inner_offset, anchor='ne')

        self.refresh_models()

        # --- Status section
        status_frame = Frame(self, width=status_width, height=status_height, bg=frame_bg_color)
        status_frame.place(x=screen_width - offset, y=main_y, anchor='ne')

        Label(status_frame, text="--- Estado ---", font=subtitle_font,
                bg=frame_bg_color).place(x=int(model_width / 2), y=5, anchor='n')

        self.state_frame = Frame(status_frame, width=state_width, height=state_height, bg=disable_color)
        self.state_frame.place(x=state_offset, y=4 * inner_offset, anchor='nw')

        self.status_label = Label(self.state_frame, text="CARGANDO", font=title_font,
                                    bg=disable_color, fg=disable_text_color, height=3, justify='center')
        self.status_label.place(x = int(state_width / 2), y = 3 * inner_offset, anchor='n')

        self.info_label = Label(status_frame, text="Esperando modelo...", font=text_font, bg=frame_bg_color)
        self.info_label.place(x=int(status_width / 2), y=main_height - inner_offset, anchor='s')

        # --- CONTROLS ---
        control_frame = Frame(self, width=model_width, height=command_height,  bg=frame_bg_color)
        control_frame.place(x=offset, y=screen_height - offset, anchor='sw')

        Label(control_frame, text="--- Comandos ---", font=subtitle_font,
                bg=frame_bg_color).place(x=int(model_width / 2), y=5, anchor='n')

        self.btn_stop = Button(control_frame, text="CANCELAR",
                                font=subtitle_font, bg=fail_color, fg=fail_text_color,
                                command=self.stop_test, height=2, width=24, justify='center')
        self.btn_stop.place(x=int(model_width / 2), y=3 * inner_offset, anchor='n')

    # --- LOGIC METHODS ---
    def start_worker(self):
        """Starts the persistent worker thread."""
        # Get default model or create a dummy one if empty
        initial_names = self.model_manager.get_all_names()
        if initial_names:
            init_model = self.model_manager.get_model(initial_names[0])
        else:
            # Fallback if no models exist yet
            init_model = MotorModel("Default", "DC", 0, 0, 0, [])

        self.worker_thread = threading.Thread(
            target=finite_state_machine,
            args=(self.gui_queue, init_model, self.model_queue, self.stop_flag),
            daemon=True
        )
        self.worker_thread.start()

    def console_input(self):
        while self.gui_running:
            try:
                logger.info('Enter command >')
                user_input = input()
                if user_input == 'exit':
                    self.on_close()
                else:
                    self.gui_queue.put(user_input)
            except (EOFError, KeyboardInterrupt):
                break

    def check_queue(self):
        """Polls the queue for messages from the worker."""

        if not self.gui_running:
            return

        try:
            while True:
                msg = self.gui_queue.get_nowait()
                self.update_gui_from_message(msg)
        except queue.Empty:
            pass
        finally:
            if self.gui_running:
                self.after(100, self.check_queue)

    def update_gui_from_message(self, msg: str):
        """Parses messages and updates colors/text."""
        if 'waiting:model' in msg:
            self.state_frame['bg'] = disable_color
            self.status_label['bg'] = disable_color
            self.status_label['fg'] = disable_text_color
            self.status_label['text'] = 'ESPERANDO'
            self.info_label['text'] = f'Esperando modelo: "{msg.split("-")[1]}"'
        elif 'model' in msg:
            self.state_frame['bg'] = disable_color
            self.status_label['bg'] = disable_color
            self.status_label['fg'] = disable_text_color
            self.status_label['text'] = 'CARGANDO'
            self.info_label['text'] = f'Cargando modelo: "{msg.split(":")[1]}"'
        elif msg == 'waiting:testinit':
            self.state_frame['bg'] = disable_color
            self.status_label['bg'] = disable_color
            self.status_label['fg'] = ready_text_color
            self.status_label['text'] = 'LISTO'
            self.info_label['text'] = 'Esperando inicio de prueba'
        elif msg == 'waiting:busyon':
            self.state_frame['bg'] = process_color
            self.status_label['bg'] = process_color
            self.status_label['fg'] = ready_text_color
            self.status_label['text'] = 'PROBANDO'
            self.info_label['text'] = 'Prueba iniciada'
        elif 'record' in msg:
            self.state_frame['bg'] = process_color
            self.status_label['bg'] = process_color
            self.status_label['fg'] = ready_text_color
            self.status_label['text'] = 'PROBANDO'
            self.info_label['text'] = f'Esperando flanco #{msg[7]}'
        elif msg == 'de-energizing':
            self.state_frame['bg'] = process_color
            self.status_label['bg'] = process_color
            self.status_label['fg'] = ready_text_color
            self.status_label['text'] = 'PROBANDO'
            self.info_label['text'] = 'Desenergizando motor'
        elif msg == 'analyzing':
            self.state_frame['bg'] = process_color
            self.status_label['bg'] = process_color
            self.status_label['fg'] = ready_text_color
            self.status_label['text'] = 'PROBANDO'
            self.info_label['text'] = 'Analizando resultados'
        elif msg == 'passed':
            self.state_frame['bg'] = pass_color
            self.status_label['bg'] = pass_color
            self.status_label['fg'] = fail_text_color
            self.status_label['text'] = 'PASO'
            self.info_label['text'] = 'Motor paso'
        elif msg == 'failed':
            self.state_frame['bg'] = fail_color
            self.status_label['bg'] = fail_color
            self.status_label['fg'] = fail_text_color
            self.status_label['text'] = 'FALLO'
            self.info_label['text'] = 'Motor fallo'
        elif 'cancelled' in msg:
            self.state_frame['bg'] = fail_color
            self.status_label['bg'] = fail_color
            self.status_label['fg'] = fail_text_color
            self.status_label['text'] = 'CANCELADO'
            reason = msg.split(':')[1]
            logger.warning(f'GUI: cancelled reason {reason}')
            if reason == 'by_user':
                self.info_label['text'] = 'Prueba cancelada por usuario'
            elif reason == 'timeout':
                self.info_label['text'] = 'Prueba cancelada, motor fallo'
        elif 'error' in msg:
            self.state_frame['bg'] = fail_color
            self.status_label['bg'] = fail_color
            self.status_label['fg'] = fail_text_color
            self.status_label['text'] = 'ERROR'
            self.info_label['text'] = f'{msg[6:]}'
        else:
            self.info_label.config(text=msg)


    def refresh_models(self):
        """Reloads model list from manager."""
        names = self.model_manager.get_all_names()
        self.model_combo['values'] = names
        if names:
            self.model_combo.current(0)
            # Don't auto load here to avoid accidental triggers on startup,
            # but we could if we wanted.

    def on_model_selected(self, event):
        """Sends the selected model to the worker."""
        name = self.model_combo.get()
        model = self.model_manager.get_model(name)
        if model:
            logger.info(f"Loading model: {name}")
            self.model_queue.put(model)  # Send to worker
            self.gui_queue.put(f'waiting:model-{name}')

    def new_model(self):
        """Opens dialog to add model."""
        ModelManagement(self, self.model_manager, self.refresh_models)

    def delete_model(self):
        name = self.model_combo.get()
        if not name: return
        if messagebox.askyesno("Confirmar", f"Borrar modelo: '{name}'?"):
            self.model_manager.delete_model(name)
            self.refresh_models()
            self.model_combo.set('')

    def stop_test(self):
        """Sends stop signal to worker."""
        logger.warning("Stop Button Pressed")
        self.stop_flag.set()

    def on_close(self):
        logger.warning('GUI: initializing application shutdown')

        self.gui_running = False
        self.model_queue.put(None)

        self.status_label.config(text="APAGANDO", bg=fail_color, fg=fail_text_color)
        self.state_frame.config(bg=fail_color)
        self.update()  # Force redraw so user sees the message

        if self.input_thread.is_alive():
            self.input_thread.join(timeout=1)

        try:
            if self.worker_thread.is_alive():
                self.worker_thread.join()
        except Exception:
            pass
        self.destroy()



if __name__ == '__main__':
    logger.info('Initializing GUI')
    app = GUI()
    logger.info('Running GUI mainloop')
    app.mainloop()
    logger.info('Terminated GUi mainloop')
