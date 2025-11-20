import json
import os
import logging
import logging.handlers

# --- Log handler setup
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class MotorModel:
    def __init__(self, name, motor_type, voltage, max_current=0.0, frequency=0.0, calibration_table = []):
        self.name = name
        self.motor_type = motor_type
        self.voltage = voltage
        self.max_current = max_current
        self.frequency = frequency
        self.calibration_table = calibration_table if calibration_table is not None else []

    def __repr__(self):
        # Updated string representation
        return (f"<MotorModel name='{self.name}' type='{self.motor_type}' "
                f"V={self.voltage} A={self.max_current} Hz={self.frequency} "
                f"Table_Steps={len(self.calibration_table)}>")

class ModelManager:
    def __init__(self, filename='models.json'):
        self.filename = filename
        self.models = self.load_all()

    def load_all(self):
        if not os.path.exists(self.filename):
            return {}
        try:
            with open(self.filename) as f:
                data = json.load(f)
                models_dict = {}
                for name, p_data in data.items():
                    models_dict[name] = MotorModel(**p_data)
                return models_dict
        except Exception as e:
            logger.error(e)
            return {}

    def save_all(self):
        data_to_save = {name: model.__dict__ for name, model in self.models.items()}
        with open(self.filename, 'w') as f:
            json.dump(data_to_save, f, indent=4)

    def get_model(self, name):
        return self.models.get(name)

    def add_model(self, new_model: MotorModel):
        self.models[new_model.name] = new_model
        self.save_all()

    def get_all_names(self):
        return list(self.models.keys())

    def delete_model(self, name):
        if name in self.models:
            del self.models[name]
            logger.info(f'Model {name} deleted successfully')
            self.save_all()
            return True
        else:
            logger.warning(f'Model {name} not found in models')
            return False

if __name__ == '__main__':
    m = ModelManager('models.json')

    # 1. Add a dummy model to demonstrate deletion
    if 'model_to_delete' not in m.get_all_names():
        new_model = MotorModel('model_to_delete', 'ac', 10.0, 1.5, 60.0, [])
        m.add_model(new_model)
        print(f"Added 'model_to_delete'. Current models: {m.get_all_names()}")

    # 2. Demonstrate Deletion
    print("\n--- Deleting 'model_to_delete' ---")
    m.delete_model('model_to_delete')
    print(f"Models after deletion: {m.get_all_names()}")

    # 3. Attempt to delete a non-existent model
    print("\n--- Deleting 'nonexistent_model' ---")
    m.delete_model('nonexistent_model')

    # If you have an existing model, this prints it
    model = m.get_model('ac_dummy')
    if model:
        print(model)