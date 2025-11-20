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
process_color = '#ffcc00'
disable_color = '#f3f3f3'
root_bg_color = '#f0f0f0'
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
        self.title(f'{equipment_name}_{sw_version}->AutomaticTest')
        self['bg'] = root_bg_color
        self['width'] = 800
        self['height'] = 400

        # Main Container
        main_frame = Frame(self, bg=root_bg_color)
        main_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)

        # --- HEADER ---
        header_frame = Frame(main_frame, bg=root_bg_color)
        header_frame.pack(fill=X, pady=(0, 20))
        Label(header_frame, text="Motor Test Rig Control", font=("Arial", 24, "bold"),
              bg=root_bg_color, fg=text_color).pack(side=LEFT)

        # --- PROFILE SECTION ---
        model_frame = LabelFrame(main_frame, text="Profile Management", bg=frame_bg_color, font=("Arial", 12, "bold"))
        model_frame.pack(fill=X, pady=10, ipady=5)

        pf_inner = Frame(model_frame, bg=frame_bg_color)
        pf_inner.pack(fill=X, padx=10, pady=10)

        Label(pf_inner, text="Select Profile:", bg=frame_bg_color).pack(side=LEFT, padx=5)

        # Profile ComboBox
        self.model_combo = ttk.Combobox(pf_inner, state="readonly", width=30)
        self.model_combo.pack(side=LEFT, padx=5)
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_selected)

        # Buttons
        Button(pf_inner, text="Delete", command=self.delete_model, bg=fail_color, fg="white").pack(side=RIGHT, padx=5)
        Button(pf_inner, text="New Profile", command=self.new_model, bg=process_color).pack(side=RIGHT, padx=5)

        # Populate list
        self.refresh_models()

        # --- STATUS DISPLAY ---
        status_frame = LabelFrame(main_frame, text="Test Status", bg=frame_bg_color, font=("Arial", 12, "bold"))
        status_frame.pack(fill=BOTH, expand=True, pady=10)

        self.status_label = Label(status_frame, text="READY", font=("Arial", 40, "bold"),
                                    bg=disable_color, fg="#888888", height=3)
        self.status_label.pack(fill=BOTH, expand=True, padx=20, pady=20)

        self.info_label = Label(status_frame, text="Waiting for model...", font=("Arial", 14), bg=frame_bg_color)
        self.info_label.pack(pady=10)

        # --- CONTROLS ---
        control_frame = Frame(main_frame, bg=root_bg_color)
        control_frame.pack(fill=X, pady=20)

        self.btn_stop = Button(control_frame, text="EMERGENCY STOP / CANCEL",
                                font=("Arial", 14, "bold"), bg=fail_color, fg="white",
                                command=self.stop_test, height=2)
        self.btn_stop.pack(fill=X)

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
        self.info_label.config(text=msg)

        if "APROBADO" in msg:
            self.status_label.config(text="PASS", bg=pass_color, fg="white")
        elif "RECHAZADO" in msg or "Error" in msg:
            self.status_label.config(text="FAIL", bg=fail_color, fg="white")
        elif "Iniciando" in msg or "Prueba" in msg or "Configurando" in msg:
            self.status_label.config(text="TESTING", bg=process_color, fg="black")
        elif "CANCELADA" in msg:
            self.status_label.config(text="CANCELED", bg=fail_color, fg="white")
        elif "Listo" in msg:
            self.status_label.config(text="READY", bg=disable_color, fg="#888888")
        elif "Cargando" in msg:
            self.status_label.config(text="LOADING", bg=disable_color, fg="black")

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
            self.status_label.config(text="LOADING...", bg=disable_color)

    def new_model(self):
        """Opens dialog to add model."""
        ModelManagement(self, self.model_manager, self.refresh_models)

    def delete_model(self):
        name = self.model_combo.get()
        if not name: return
        if messagebox.askyesno("Confirm", f"Delete model '{name}'?"):
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

        self.status_label.config(text="SHUTTING DOWN...", bg=disable_color)
        self.update()  # Force redraw so user sees the message

        if self.input_thread.is_alive():
            self.input_thread.join(timeout=1)


        if self.worker_thread.is_alive():
            self.worker_thread.join()

        self.destroy()



if __name__ == '__main__':
    logger.info('Initializing GUI')
    app = GUI()
    logger.info('Running GUI mainloop')
    app.mainloop()
    logger.info('Terminated GUi mainloop')
