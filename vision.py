import cv2
import numpy as np
import time
import json
import threading
import os
import logging
from config import PARAMS

# --- Log handler setup.
logger = logging.getLogger('SpinCheck')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VISION_FILE = os.path.join(BASE_DIR, 'vision_config.json')


class VisionSystem:
    def __init__(self):
        self.cap = None
        self.streaming = False
        self.thread = None
        self.lock = threading.Lock()

        self.latest_frame = None
        self.show_debug_points = True  # Poner en False para producción

        # Variables lógicas
        self.last_stable_state = "STOPPED"
        self.state_stable_start = 0
        self.direction_buffer = []
        self.reset_tracking_flag = False

        # Variables de Test
        self.test_active = False
        self.test_result = None
        self.test_start_time = 0

        # Variables de fps
        self.current_fps = 0.0

        # Configuración
        self.rot_roi = None
        self.runout_rois = []
        self.feature_params = dict(maxCorners=200, qualityLevel=0.3, minDistance=5, blockSize=7)
        self.lk_params = dict(winSize=(21, 21), maxLevel=3,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        self.load_config()

    def load_config(self):
        if os.path.exists(VISION_FILE):
            try:
                with open(VISION_FILE, 'r') as f:
                    data = json.load(f)
                    if data.get("rotation_roi"):
                        self.rot_roi = tuple(data.get("rotation_roi"))
                    self.runout_rois = [tuple(r) for r in data.get("runout_rois", [])]
            except Exception:
                pass

    def save_config(self, rot_roi, runout_rois):
        data = {"rotation_roi": rot_roi, "runout_rois": runout_rois}
        try:
            with open(VISION_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            self.rot_roi = rot_roi
            self.runout_rois = runout_rois
            return True
        except Exception:
            return False

    def start_stream(self):
        if self.cap is None:
            # --- CORRECCIÓN 1: Usar la misma configuración que la versión 1 (sin V4L2 forzado)
            # Si esto te da error de GStreamer, usa CAP_V4L2 pero RE-CALIBRA las ROIs.
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.streaming:
            self.streaming = True
            self.thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.thread.start()

    def stop_stream(self):
        self.streaming = False
        if self.thread: self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None

    def start_test(self):
        if not self.rot_roi: return False
        with self.lock:
            self.test_result = None
            self.test_start_time = time.time()
            self.last_stable_state = 'STOPPED'
            self.state_stable_start = 0
            self.direction_buffer = []
            self.reset_tracking_flag = True
            self.test_active = True
        return True

    def get_result(self):
        return self.test_result

    def get_frame_for_gui(self):
        with self.lock:
            if self.latest_frame is None: return None
            return self.latest_frame.copy()

    def _processing_loop(self):
        p0 = None
        old_gray = None
        prev_time = time.time()

        while self.streaming:
            if self.cap is None: break
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # --- FPS calculate.
            current_time = time.time()
            dt = current_time - prev_time
            prev_time = current_time

            if dt > 0:
                fps_instantaneo = 1.0 / dt
                # Suavizamos el valor: 90% del valor anterior + 10% del nuevo
                self.current_fps = (self.current_fps * 0.9) + (fps_instantaneo * 0.1)

            # --- DIBUJAR EN MEMORIA ---
            if self.rot_roi:
                vx, vy, vw, vh = self.rot_roi
                cv2.rectangle(frame, (int(vx), int(vy)), (int(vx + vw), int(vy + vh)), (0, 255, 0), 2)

                # Opcional: Dibujar el margen interno (zona segura) para depurar
                # margen_x = int(vw * 0.15)
                # margen_y = int(vh * 0.15)
                # cv2.rectangle(frame, (int(vx+margen_x), int(vy+margen_y)),
                #               (int(vx+vw-margen_x), int(vy+vh-margen_y)), (0, 100, 0), 1)

            for r in self.runout_rois:
                bx, by, bw, bh = r
                if bw > 0:
                    cv2.rectangle(frame, (int(bx), int(by)), (int(bx + bw), int(by + bh)), (0, 0, 255), 2)

            # --- LÓGICA DE DETECCIÓN ---
            if self.test_active and self.rot_roi:
                # --- CORRECCIÓN 2: Desempaquetar variables AQUÍ dentro para asegurar alcance ---
                vx, vy, vw, vh = self.rot_roi

                # Limpieza forzada
                if self.reset_tracking_flag:
                    p0 = None
                    old_gray = None
                    self.reset_tracking_flag = False

                # Timeout
                if (time.time() - self.test_start_time) > PARAMS.VISION_TIMEOUT_SEC:
                    self.test_result = "TIMEOUT"
                    self.test_active = False

                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Inicializar puntos
                if p0 is None:
                    mask = np.zeros_like(frame_gray)
                    # Asegurar enteros para la máscara
                    mask[int(vy):int(vy + vh), int(vx):int(vx + vw)] = 255

                    # Restar runout
                    for r in self.runout_rois:
                        bx, by, bw, bh = r
                        if bw > 0: mask[int(by):int(by + bh), int(bx):int(bx + bw)] = 0

                    p0 = cv2.goodFeaturesToTrack(frame_gray, mask=mask, **self.feature_params)
                    old_gray = frame_gray.copy()

                # 4. Lucas-Kanade
                if p0 is not None and len(p0) > 0:
                    p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **self.lk_params)

                    if p1 is not None:
                        good_new = p1[st == 1]
                        good_old = p0[st == 1]
                        dx_list = []
                        valid_points = []
                        runout_detected = False

                        # --- MEJORA 1: MÁRGENES DINÁMICOS ---
                        # Definimos un margen del 15% del ancho/alto.
                        # Si el punto llega a ese 15% del borde, lo matamos.
                        margin_x = int(vw * 0.15)
                        margin_y = int(vh * 0.15)

                        for new, old in zip(good_new, good_old):
                            a, b = new.ravel() # Posición actual
                            c, d = old.ravel() # Posición anterior

                            # Check Runout
                            for r in self.runout_rois:
                                bx, by, bw, bh = r
                                if bw > 0 and (bx < a < bx + bw) and (by < b < by + bh):
                                    runout_detected = True
                                    cv2.circle(frame, (int(a), int(b)), 8, (0, 0, 255), -1)
                                    break
                            if runout_detected: break

                            # --- MEJORA 1 (Aplicación): FILTRO ESTRICTO DE BORDES ---
                            # Solo aceptamos el punto si está bien adentro de la caja
                            in_safe_zone = (vx + margin_x < a < vx + vw - margin_x) and \
                                           (vy + margin_y < b < vy + vh - margin_y)

                            if in_safe_zone:
                                dx_list.append(a - c)
                                valid_points.append(new)
                                if self.show_debug_points:
                                    cv2.circle(frame, (int(a), int(b)), 2, (0, 255, 0), -1)
                            # Si no está en zona segura, simplemente NO lo agregamos a valid_points
                            # y desaparecerá en el siguiente ciclo.

                        if runout_detected:
                            self.test_result = "FAIL_RUNOUT"
                            self.test_active = False
                            cv2.putText(frame, "FAIL: RUNOUT", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                        else:
                            if dx_list:
                                self.direction_buffer.append(np.mean(dx_list))
                                if len(self.direction_buffer) > 10: self.direction_buffer.pop(0)

                            smoothed_dx = np.mean(self.direction_buffer) if self.direction_buffer else 0

                            # --- MEJORA 2: REPOBLADO PROACTIVO ---
                            # Actualizamos la lista p0 solo con los puntos que sobrevivieron al margen
                            p0 = np.array(valid_points).reshape(-1, 1, 2)

                            # Si tenemos menos de 150 puntos (el max es 200), agregamos más.
                            # Antes esperabas a tener < 50, eso es muy poco.
                            if len(valid_points) < 150:
                                mask = np.zeros_like(frame_gray)
                                # Misma mascara de siempre
                                mask[int(vy):int(vy + vh), int(vx):int(vx + vw)] = 255
                                for r in self.runout_rois:
                                    bx, by, bw, bh = r
                                    if bw > 0: mask[int(by):int(by + bh), int(bx):int(bx + bw)] = 0

                                # Pedimos nuevos puntos
                                p_new = cv2.goodFeaturesToTrack(frame_gray, mask=mask, **self.feature_params)
                                if p_new is not None:
                                    p0 = np.vstack((p0, p_new)) if len(p0) > 0 else p_new

                            old_gray = frame_gray.copy()

                            current_state = "STOPPED"
                            if smoothed_dx > 0.3:
                                current_state = "RIGHT"
                            elif smoothed_dx < -0.3:
                                current_state = "LEFT"

                            cv2.putText(frame, f"Giro: {current_state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                            if current_state == self.last_stable_state and current_state != "STOPPED":
                                if (time.time() - self.state_stable_start) >= PARAMS.VISION_STABLE_TIME_SEC:
                                    self.test_result = current_state
                                    self.test_active = False
                            else:
                                if current_state != self.last_stable_state:
                                    self.last_stable_state = current_state
                                    self.state_stable_start = time.time()
            else:
                if p0 is not None:
                    p0 = None
                    old_gray = None

            # --- Draw FPS.
            alto_imagen = frame.shape[0]
            cv2.putText(frame, f"FPS: {int(self.current_fps)}", (10, alto_imagen - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # --- Save frame for gui.
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with self.lock:
                self.latest_frame = frame_rgb

    def calibrate_gui_safe(self):
        """
        Abre ventanas de OpenCV para seleccionar ROIs.
        DEBE ser llamada desde el Hilo Principal (donde corre Tkinter).
        Bloquea la ejecución momentáneamente hasta que el usuario termina.
        """
        # 1. Obtener una "foto" estática del momento actual
        frame_bgr = None
        with self.lock:
            if self.latest_frame is None:
                logger.error("VISION: No hay imagen de cámara disponible para calibrar.")
                return False
            # IMPORTANTE: La GUI tiene la imagen en RGB, OpenCV necesita BGR
            frame_bgr = cv2.cvtColor(self.latest_frame, cv2.COLOR_RGB2BGR)

        window_name = "Calibracion - SpinCheck"
        logger.info("--- INICIO CALIBRACION ---")

        try:
            # --- PASO 1: ZONA VERDE (GIRO) ---
            logger.info(">> Paso 1: Selecciona el SINFÍN (Verde) y presiona ESPACIO o ENTER.")
            # selectROI bloquea hasta que el usuario confirma
            r_rot = cv2.selectROI(window_name, frame_bgr, showCrosshair=True, fromCenter=False)

            # Validar si el usuario canceló (width o height es 0)
            if r_rot[2] == 0 or r_rot[3] == 0:
                logger.warning("VISION: Calibración cancelada por el usuario.")
                cv2.destroyWindow(window_name)
                cv2.waitKey(1)
                return False

            # Dibujar referencia verde en una imagen temporal
            # Esto ayuda al usuario a ver dónde poner las rojas respecto a la verde
            temp_img = frame_bgr.copy()
            cv2.rectangle(temp_img, (int(r_rot[0]), int(r_rot[1])),
                          (int(r_rot[0] + r_rot[2]), int(r_rot[1] + r_rot[3])), (0, 255, 0), 2)

            # --- PASO 2: ZONA ROJA 1 (RUNOUT ARRIBA) ---
            logger.info(">> Paso 2: Selecciona RUNOUT SUPERIOR (Rojo 1) y presiona ESPACIO o ENTER.")
            # Si el usuario quiere omitir, puede presionar 'c' o Enter sin seleccionar nada
            r_run1 = cv2.selectROI(window_name, temp_img, showCrosshair=True, fromCenter=False)

            # Dibujar referencia roja 1
            if r_run1[2] > 0 and r_run1[3] > 0:
                cv2.rectangle(temp_img, (int(r_run1[0]), int(r_run1[1])),
                              (int(r_run1[0] + r_run1[2]), int(r_run1[1] + r_run1[3])), (0, 0, 255), 2)

            # --- PASO 3: ZONA ROJA 2 (RUNOUT ABAJO) ---
            logger.info(">> Paso 3: Selecciona RUNOUT INFERIOR (Rojo 2) y presiona ESPACIO o ENTER.")
            r_run2 = cv2.selectROI(window_name, temp_img, showCrosshair=True, fromCenter=False)

            # --- CIERRE Y GUARDADO ---
            cv2.destroyWindow(window_name)
            cv2.waitKey(1)  # Vital en Linux para procesar el cierre de la ventana

            # Armar la lista de runouts validos
            runout_list = []
            if r_run1[2] > 0: runout_list.append(r_run1)
            if r_run2[2] > 0: runout_list.append(r_run2)

            # Guardar usando tu función existente
            success = self.save_config(r_rot, runout_list)

            if success:
                logger.info(f"VISION: Calibración exitosa. {len(runout_list)} zonas de runout guardadas.")
                # Actualizar variables internas inmediatamente
                self.rot_roi = r_rot
                self.runout_rois = runout_list

            return success

        except Exception as e:
            logger.error(f"VISION ERROR CRÍTICO durante calibración: {e}")
            try:
                cv2.destroyWindow(window_name)
                cv2.waitKey(1)
            except:
                pass
            return False


vision_system = VisionSystem()

if __name__ == "__main__":
    logger.error(f'{__name__} module is not tended to be imported')