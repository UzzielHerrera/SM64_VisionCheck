import json
import os
import logging
import logging.handlers

# Log handler
logger = logging.getLogger('SpinCheck')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class MotorModel:
    def __init__(self, name, motor_type, voltage, frequency=0):
        self.name = name
        self.motor_type = motor_type
        self.voltage = voltage
        self.frequency = frequency

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

    def add_model(self, name, motor_type, voltage, frequency):
        self.models[name] = MotorModel(name, motor_type, voltage, frequency)
        self.save_all()

    def get_all_names(self):
        return list(self.models.keys())

if __name__ == '__main__':
    m = ModelManager('models.json')
    # m.add_model('dc_dummy', 'dc', 1.25, 62.5)
    print(m.get_all_names())