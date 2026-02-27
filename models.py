import json
import os
import logging

# --- Log handler setup/
logger = logging.getLogger('SpinCheck')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_FILE = os.path.join(BASE_DIR, 'models.json')
LAST_RUN = os.path.join(BASE_DIR, 'last_run.json')

class MotorModel:
    """ MotorModel class """
    def __init__(self, name, motor_type, voltage, max_current=0.0, start_freq=0.0, end_freq=0.0, delta_t = 0.0, direction='CW'):
        self.name = name
        self.motor_type = motor_type
        self.voltage = voltage
        self.max_current = max_current
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.delta_t = delta_t
        self.direction = direction

    def __repr__(self):
        # --- Overwrite string representation
        return (f"<MotorModel name='{self.name}' type='{self.motor_type}' "
                f"V={self.voltage} A={self.max_current} Start_Hz={self.start_freq} End_Hz={self.end_freq} dT={self.delta_t}"
                f"Direction={self.direction}>")

class ModelManager:
    """ ModelManager class """
    def __init__(self, models_filename=MODELS_FILE, last_run_filename=LAST_RUN):
        self.models_filename = models_filename
        self.last_run_filename = last_run_filename
        self.models = self.load_all()

    def load_all(self):
        """ Loads all models from `models_filename`. """
        if not os.path.exists(self.models_filename):
            return {}
        try:
            with open(self.models_filename) as f:
                data = json.load(f)
                models_dict = {}
                # --- Create models from file.
                for name, p_data in data.items():
                    models_dict[name] = MotorModel(**p_data)
                return models_dict
        except Exception as e:
            logger.error(e)
            return {}

    def save_all(self):
        """ Saves all models to `models_filename`. """
        data_to_save = {name: motor_model.__dict__ for name, motor_model in self.models.items()}
        with open(self.models_filename, 'w') as f:
            json.dump(data_to_save, f, indent=4)

    def get_model(self, name):
        """ Returns a `MotorModel` object for the given `name`. """
        return self.models.get(name)

    def add_model(self, new_model: MotorModel):
        """ Adds a new `MotorModel` object to the model's list. """
        self.models[new_model.name] = new_model
        self.save_all()

    def get_all_names(self):
        """ Returns a list of all `MotorModel` names. """
        return list(self.models.keys())

    def delete_model(self, name):
        """ Deletes a `MotorModel` object from the model's list. """
        if name in self.models:
            del self.models[name]
            logger.info(f'ModelManager: {name} deleted successfully')
            self.save_all()
            return True
        else:
            logger.warning(f'ModelManager: {name} not found in models')
            return False

    def save_last_used(self, name):
        """ Saves the last used `MotorModel` object for the given `name`. """
        try:
            with open(self.last_run_filename, 'w') as f:
                json.dump({'last_model': name}, f)
        except Exception as e:
            logger.error(f'ModelManager: {e}')

    def get_last_used(self):
        """ Returns the last used `MotorModel` object for the given `name`. """
        if not os.path.exists(self.last_run_filename):
            return None
        try:
            with open(self.last_run_filename, 'r') as f:
                data = json.load(f)
                return data.get('last_model')
        except Exception as e:
            logger.error(f'ModelManager: {e}')
            return None

if __name__ == '__main__':
    m = ModelManager(MODELS_FILE)

    # --- Add a dummy model to demonstrate deletion
    if 'model_to_delete' not in m.get_all_names():
        new_model = MotorModel('model_to_delete', 'ac', 10.0, 1.5, 60.0, 120.0, 1.0, [])
        m.add_model(new_model)
        print(f"Added 'model_to_delete'. Current models: {m.get_all_names()}")

    # --- Demonstrate Deletion
    print("\n--- Deleting 'model_to_delete' ---")
    m.delete_model('model_to_delete')
    print(f"Models after deletion: {m.get_all_names()}")

    # --- Attempt to delete a non-existent model
    print("\n--- Deleting 'nonexistent_model' ---")
    m.delete_model('nonexistent_model')

    # --- If you have an existing model, this prints it
    model = m.get_model('ac_dummy')
    if model:
        print(model)