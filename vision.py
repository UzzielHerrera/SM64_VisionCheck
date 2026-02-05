import os
import cv2
import time
import json
import numpy as np


CONFIG_FILE = "vision_config.json"

def save_rois(rotation_roi, runout_roi):
    """
    Guarda las coordenadas de las ROI en un JSON.
    Format: [x, y, w, h]
    """
    data = {
        "rotation_roi": rotation_roi,  # Tupla o lista (x, y, w, h)
        "runout_roi": runout_roi  # Tupla o lista (x, y, w, h)
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Configuración guardada en {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        return False


def load_rois():
    """
    Carga las coordenadas desde el JSON.
    Retorna: (rotation_roi, runout_roi) o (None, None) si falla.
    """
    if not os.path.exists(CONFIG_FILE):
        print("No se encontró archivo de calibración.")
        return None, None

    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        return data["rotation_roi"], data["runout_roi"]
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return None, None


def calibrate_vision_system():
    cap = cv2.VideoCapture(0)

    # Esperar un poco a que la cámara ajuste la exposición
    time.sleep(1.0)

    ret, frame = cap.read()
    if not ret:
        print("Error: No se pudo acceder a la cámara")
        return False

    print("--- CALIBRACIÓN ---")

    # 1. Seleccionar Zona de Giro (Verde)
    print("Paso 1: Dibuja la zona de GIRO (Verde) y pulsa ENTER")
    r_rot = cv2.selectROI("Calibracion - Rotation Zone", frame, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow("Calibracion - Rotation Zone")

    # Validación simple
    if r_rot[2] == 0 or r_rot[3] == 0:
        print("Selección inválida. Cancelando.")
        return False

    # 2. Seleccionar Zona de Runout (Roja)
    print("Paso 2: Dibuja la zona de RUNOUT (Roja) y pulsa ENTER")
    # Dibujamos la verde para referencia
    temp_frame = frame.copy()
    cv2.rectangle(temp_frame, (int(r_rot[0]), int(r_rot[1])),
                  (int(r_rot[0] + r_rot[2]), int(r_rot[1] + r_rot[3])), (0, 255, 0), 2)

    r_run = cv2.selectROI("Calibracion - Runout Zone", temp_frame, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow("Calibracion - Runout Zone")

    # Guardar en JSON
    # r_rot y r_run son tuplas (x, y, w, h)
    success = save_rois(r_rot, r_run)

    cap.release()
    return success


def run_vision_test():
    # 1. Cargar Configuración
    rot_roi, run_roi = load_rois()
    if rot_roi is None:
        return "ERROR_NO_CALIBRATION"

    # Desempaquetar coordenadas (Valid=Green, Bad=Red)
    vx, vy, vw, vh = rot_roi
    bx, by, bw, bh = run_roi

    cap = cv2.VideoCapture(0)

    # Parámetros Lucas-Kanade
    feature_params = dict(maxCorners=200, qualityLevel=0.3, minDistance=5, blockSize=7)
    lk_params = dict(winSize=(21, 21), maxLevel=3,
                     criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

    ret, old_frame = cap.read()
    if not ret: return "CAMERA_ERROR"

    old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)

    # --- MÁSCARA AUTOMÁTICA ---
    mask = np.zeros_like(old_gray)
    mask[int(vy):int(vy + vh), int(vx):int(vx + vw)] = 255

    # Restar zona de runout de la máscara de búsqueda inicial
    if bw > 0 and bh > 0:
        mask[int(by):int(by + bh), int(bx):int(bx + bw)] = 0

    p0 = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)

    # Variables de lógica
    direction_buffer = []
    BUFFER_SIZE = 10
    last_stable_state = "STOPPED"
    state_start_time = time.time()
    REQUIRED_DURATION = 3.0
    final_result = "TIMEOUT"

    MAX_TEST_DURATION = 10.0
    global_start_time = time.time()

    while (time.time() - global_start_time) < MAX_TEST_DURATION:
        ret, frame = cap.read()
        if not ret: break

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if p0 is None or len(p0) == 0:
            p0 = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)
            old_gray = frame_gray.copy()
            continue

        p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

        smoothed_dx = 0

        if p1 is not None:
            good_new = p1[st == 1]
            good_old = p0[st == 1]
            dx_list = []
            puntos_validos = []
            MARGEN = 5

            runout_detected = False

            for new, old in zip(good_new, good_old):
                a, b = new.ravel()
                c, d = old.ravel()

                # --- CHECK RUNOUT ---
                if bw > 0 and bh > 0:
                    if (a > bx) and (a < bx + bw) and (b > by) and (b < by + bh):
                        runout_detected = True
                        # Dibujar en ROJO GRUESO el punto que causó la falla para evidencia
                        cv2.circle(frame, (int(a), int(b)), 8, (0, 0, 255), -1)
                        break

                        # --- CHECK SALIDA DE ZONA VERDE ---
                in_valid_box = (a > vx + MARGEN) and (a < vx + vw - MARGEN) and \
                               (b > vy + MARGEN) and (b < vy + vh - MARGEN)

                if in_valid_box:
                    dx_list.append(a - c)
                    puntos_validos.append(new)

                    # --- OPCIONAL: Puntos de Rastreo ---
                    # Descomenta la siguiente linea si quieres ver los puntos verdes moviendose
                    cv2.circle(frame, (int(a), int(b)), 2, (0, 255, 0), -1)

            if runout_detected:
                print("FAIL: Runout Detected")
                cv2.putText(frame, "FAIL: RUNOUT", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

                # Dibujamos las cajas una ultima vez antes de congelar
                cv2.rectangle(frame, (int(vx), int(vy)), (int(vx + vw), int(vy + vh)), (0, 255, 0), 2)
                if bw > 0 and bh > 0:
                    cv2.rectangle(frame, (int(bx), int(by)), (int(bx + bw), int(by + bh)), (0, 0, 255), 2)

                cv2.imshow("Vision Test Running", frame)
                cv2.waitKey(2000)  # Mostrar error por 2 segundos
                cap.release()
                return "FAIL_RUNOUT"

            if dx_list:
                direction_buffer.append(np.mean(dx_list))
                if len(direction_buffer) > BUFFER_SIZE: direction_buffer.pop(0)

            smoothed_dx = np.mean(direction_buffer) if direction_buffer else 0

            # Repoblar
            p0 = np.array(puntos_validos).reshape(-1, 1, 2)
            if len(puntos_validos) < 50:
                p_nuevos = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)
                if p_nuevos is not None:
                    p0 = np.vstack((p0, p_nuevos)) if len(p0) > 0 else p_nuevos

            old_gray = frame_gray.copy()

        # --- DIBUJAR INTERFAZ ESTÁTICA (Siempre visible) ---
        # 1. Caja Verde (Zona OK)
        cv2.rectangle(frame, (int(vx), int(vy)), (int(vx + vw), int(vy + vh)), (0, 255, 0), 2)

        # 2. Caja Roja (Zona Runout) - Si existe
        if bw > 0 and bh > 0:
            cv2.rectangle(frame, (int(bx), int(by)), (int(bx + bw), int(by + bh)), (0, 0, 255), 2)

        # --- Lógica de Estado ---
        UMBRAL = 0.3
        current_state = "STOPPED"
        if smoothed_dx > UMBRAL:
            current_state = "RIGHT"
        elif smoothed_dx < -UMBRAL:
            current_state = "LEFT"

        # Mostrar Estado en texto (sin barra de progreso)
        cv2.putText(frame, f"Giro: {current_state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        if current_state == last_stable_state and current_state != "STOPPED":
            elapsed_time = time.time() - state_start_time

            # Ya no dibujamos barra, solo chequeamos el tiempo
            if elapsed_time >= REQUIRED_DURATION:
                final_result = current_state
                break
        else:
            if current_state != last_stable_state:
                last_stable_state = current_state
                state_start_time = time.time()

        # --- DISPLAY ---
        cv2.imshow("Vision Test Running", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            final_result = "CANCELLED"
            break

    cap.release()
    cv2.destroyAllWindows()
    return final_result

if __name__ == "__main__":
    # calibrate_vision_system()
    print(run_vision_test())