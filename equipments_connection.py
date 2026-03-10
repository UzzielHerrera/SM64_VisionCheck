import os
import csv
import sys
import time
import json
import queue
import sqlite3
import logging
import threading
import mysql.connector
from datetime import datetime
from mysql.connector import Error

# --- Logger setup.
logger = logging.getLogger('SpinCheck')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- File paths.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
LOG_FILE = os.path.join(BASE_DIR, 'db_log.csv')
LOCAL_BUFFER_DB_FILE = os.path.join(BASE_DIR, 'local_buffer.db')


class EquipmentsConnection:
    def __init__(self):
        self.credentials = None
        self._load_credentials()
        self.queue: queue.Queue = queue.Queue()
        self._init_local_db()

        self.worker_thread = threading.Thread(target=self._database_worker_thread, daemon=True)
        self.worker_thread.start()

    def _init_local_db(self):
        """Create a local SQL database."""
        conn = sqlite3.connect(LOCAL_BUFFER_DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS pending_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, equipment TEXT, payload TEXT)''')
        conn.commit()
        conn.close()

    def _load_credentials(self):
        if not os.path.exists(CREDENTIALS_FILE):
            logger.error('DB: Credentials file not found.')
            return {}
        try:
            with open(CREDENTIALS_FILE, 'r') as file:
                self.credentials = json.load(file)
                logger.info('DB: Credentials loaded.')
        except Exception as e:
            logger.error(f'DB: Error loading credentials: {e}')

    def _get_connection(self):
        """ Create and return a MYSQL connection. """
        if not self.credentials:
            logger.error('DB: Credentials not loaded.')

        try:
            return mysql.connector.connect(**self.credentials)
        except Error as e:
            logger.error(f'DB: Failed connecting to MySQL database: {e}')
            return None
        except Exception as e:
            logger.error(f'DB: Fatal error trying to MySQL database: {e}')

    def test_connection(self):
        """ Test if connection is working. """
        db = self._get_connection()
        if db and db.is_connected():
            db.close()
            return True
        return False

    def _execute_query(self, query, params=None, fetch_one=False, fetch_all=False, commit=False):
        """ Execute query and return results. """
        db = self._get_connection()
        if not db:
            return False

        result = None
        try:
            cursor = db.cursor()
            cursor.execute(query, params or ())

            if commit:
                db.commit()
                result = cursor.lastrowid or cursor.rowcount
            if fetch_one:
                result = cursor.fetchone()
            if fetch_all:
                result = cursor.fetchall()

            cursor.close()
        except Error as e:
            logger.error(f'DB: Failed executing query: {e}, Query: {query}, Params: {params}')
            if commit:
                db.rollback()
        finally:
            db.close()

        return result

    def _get_current_date_hour(self):
        """ Get current date and hour. """
        now = datetime.now()
        date_format = '%#m/%#d/%Y' if 'win' in sys.platform else '%-m/%-d/%Y'
        hour_format = '%#I:%M %p' if 'win' in sys.platform else '%-I:%M %p'
        return now.strftime(date_format), now.strftime(hour_format)

    def _check_serial_number_exists(self, equipment_number, serial_number):
        query = f"SELECT RESULT_REGISTER, DEFECT_DESCRIPTION_REGISTER, TEST_D_REGISTER, TEST_H_REGISTER, ATTEMPTS, NEST FROM {equipment_number} WHERE SERIAL_NUM=%s"
        row = self._execute_query(query, (serial_number,), fetch_one=True)
        return (True, row) if row else (False, ())

    def _check_serial_with_parameters(self, equipment_number, parameters):
        query = f"SELECT RESULT_REGISTER, DEFECT_DESCRIPTION_REGISTER, TEST_D_REGISTER, TEST_H_REGISTER, ATTEMPTS, NEST, SERIAL_NUM FROM {equipment_number} WHERE PARAMETERS=%s"
        row = self._execute_query(query, (parameters,), fetch_one=True)
        return (True, row) if row else (False, ())

    def _get_sku_number_from_model(self, model):
        query = "SELECT SKU_NUMBER, SKU_LAST_PRINTED FROM SKU_LABEL WHERE MODEL=%s"
        row = self._execute_query(query, (model,), fetch_one=True)

        if not row:
            return '', 0

        sku_number, sku_last_printed = str(row[0]), int(row[1])

        update_query = "UPDATE SKU_LABEL SET SKU_LAST_PRINTED=%s WHERE MODEL=%s"
        self._execute_query(update_query, (sku_last_printed + 1, model), commit=True)

        return sku_number, sku_last_printed

    def _base36encode(self, number, zeros=2, alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        if not isinstance(number, int):
            raise TypeError('number must be an integer')

        base36 = ''
        sign = '-' if number < 0 else ''
        number = abs(number)

        if number == 0:
            base36 = alphabet[0]

        while number != 0:
            number, i = divmod(number, len(alphabet))
            base36 = alphabet[i] + base36

        return sign + base36.zfill(zeros)

    def _get_encoded_date(self):
        year_array = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        year_index = int(datetime.today().strftime('%Y')) - 2006
        while year_index >= 26:
            year_index -= 26
        day = self._base36encode(datetime.now().timetuple().tm_yday, zeros=2)
        return year_array[year_index] + day

    def get_new_serial_number(self, model):
        sku_number, sku_last_printed = self._get_sku_number_from_model(model)
        if not sku_number:
            return None
        return sku_number + self._get_encoded_date() + self._base36encode(sku_last_printed, zeros=3)

    def _create_register(self, equipment_number, entry):
        query = f"""
                    INSERT INTO {equipment_number} 
                    (SERIAL_NUM, RESULT, DEFECT_DESCRIPTION, TEST_D, TEST_H, ATTEMPTS, USERNAME, 
                    PARAMETERS, SW, NEST, MODEL, WORK_ORDER, RESULT_REGISTER, 
                    DEFECT_DESCRIPTION_REGISTER, TEST_D_REGISTER, TEST_H_REGISTER) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
        params = (
            entry['serial_num'], entry['results'], entry['defect_description'], entry['test_d'], entry['test_h'],
            entry['attempts'], entry['username'], entry['parameters'], entry['sw'], entry['nest'], entry['model'],
            entry['work_order'], entry['result_register'], entry['defect_description_register'],
            entry['test_d_register'], entry['test_h_register']
        )
        try:
            self._execute_query(query, params, commit=True)
            logger.info(f'DB: Successfully created register at {equipment_number}')
            return True
        except Exception as e:
            logger.error(f"DB: error writing register: {e}")
            return False

    def _update_register(self, equipment_number, entry, prev_data):
        new_attempts = int(prev_data[4]) + 1

        query = f"""
                    UPDATE {equipment_number} SET 
                    RESULT_REGISTER=%s, DEFECT_DESCRIPTION=%s, TEST_D=%s, TEST_H=%s, 
                    ATTEMPTS=%s, NEST=%s, RESULT=%s, DEFECT_DESCRIPTION_REGISTER=%s, 
                    TEST_D_REGISTER=%s, TEST_H_REGISTER=%s 
                    WHERE SERIAL_NUM=%s
                """
        params = (
            f"{prev_data[0]};{entry['results']}",               # RESULT_REGISTER
            entry['defect_description'],                        # DEFECT_DESCRIPTION
            entry['test_d'],                                    # TEST_D
            entry['test_h'],                                    # TEST_H
            new_attempts,                                       # ATTEMPTS
            f"{prev_data[5]};{entry['nest']}",                  # NEST
            entry['results'],                                   # RESULT
            f"{prev_data[1]};{entry['defect_description']}",    # DEFECT_DESCRIPTION_REGISTER
            f"{prev_data[2]};{entry['test_d']}",                # TEST_D_REGISTER
            f"{prev_data[3]};{entry['test_h']}",                # TEST_H_REGISTER
            entry['serial_num']                                 # WHERE SERIAL_NUM
        )
        try:
            self._execute_query(query, params, commit=True)
            logger.info(f"DB: Successfully updated register: {entry['serial_num']} at {equipment_number}")
            return True
        except Exception as e:
            logger.error(f"DB: Error updating register {entry['serial_num']}: {e}")
            return False

    def _upload_register(self, equipment_numner, entry):
        """Chose to create or update a register."""
        invalid_serials = ("-", "/", "NA", "")
        serial = entry.get('serial_num', 'NA')

        if serial not in invalid_serials:
            is_exist, prev_data = self._check_serial_number_exists(equipment_numner, serial)

            if is_exist:
                return self._update_register(equipment_numner, entry, prev_data)

        success = self._create_register(equipment_numner, entry)
        return success

    def _database_worker_thread(self):
        logger.info(f"DB: Worker thread started")
        while True:
            # --- Store entry to local database.
            try:
                item = self.queue.get()
                if item is None:
                    break

                equipment_number, entry = item

                conn = sqlite3.connect(LOCAL_BUFFER_DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO pending_records (equipment, payload) VALUES (?, ?)",
                            (equipment_number, json.dumps(entry)))
                conn.commit()
                conn.close()

                self.queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"DB: Fatal error sending log to local db: {e}")

            # --- Store entry to external database.
            try:
                conn = sqlite3.connect(LOCAL_BUFFER_DB_FILE)
                c = conn.cursor()
                c.execute("SELECT id, equipment, payload FROM pending_records ORDER BY id ASC")
                pending_items = c.fetchall()

                if pending_items:
                    if self.test_connection():
                        for row_id, equipment_num, payload_str in pending_items:
                            entry = json.loads(payload_str)

                            success = self._upload_register(equipment_num, entry)

                            if success:
                                c.execute("DELETE FROM pending_records WHERE id=?", (row_id,))
                                conn.commit()
                            else:
                                logger.warning("DB: Failed to upload to external database")
                                break
                conn.close()
            except Exception as e:
                logger.error(f"DB: Fatal error sending log external db: {e}")
                time.sleep(2.0)
        logger.info('DB: Worker thread finished')

    def write_log(self, equipment_number, serial_num:str = 'NA', results:str = 'Pass', defect_description:str = '-', parameters:str = 'NA', model: str = 'NA'):
        current_date, current_hour = self._get_current_date_hour()
        entry = {
            'serial_num': serial_num,
            'results': results,
            'defect_description': defect_description,
            'test_d': current_date,
            'test_h': current_hour,
            'attempts': '1',
            'username': 'NA',
            'parameters': parameters,
            'sw': 'NA',
            'nest': '1',
            'model': model,
            'work_order': 'NA',
            'result_register': results,
            'defect_description_register': defect_description,
            'test_d_register': current_date,
            'test_h_register': current_hour,
        }
        self.queue.put((equipment_number, entry))

    def change_model(self, equipment_number, new_model):

        if not self.test_connection():
            return False

        update_query = "UPDATE EQUIPMENTS_INFORMATION SET RUNNING_MODEL=%s WHERE EQUIPMENT_DB=%s"
        self._execute_query(update_query, (new_model, equipment_number), commit=True)

        check_query = "SELECT RUNNING_MODEL FROM EQUIPMENTS_INFORMATION WHERE EQUIPMENT_DB=%s"
        row = self._execute_query(check_query, (equipment_number,), fetch_one=True)

        if row and row[0] == new_model:
            logger.info(f"DB: Equipment {equipment_number} model changed to {new_model}")
            return True

        logger.warning(f"DB: Equipment {equipment_number} model not changed successfully")
        return False

    def check_attempts(self, equipment_number, serial_number):
        query = f'SELECT ATTEMPTS FROM {equipment_number} WHERE SERIAL_NUM=%s'
        row = self._execute_query(query, (serial_number,), fetch_one=True)

        attempts = int(row[0]) if row else 0
        return attempts < 3

db = EquipmentsConnection()

if __name__ == "__main__":
    # --- Test connection to server.
    if db.test_connection():
        logger.info("DB: Connected successfully.")
    else:
        logger.error("DB: Cannot connect.")