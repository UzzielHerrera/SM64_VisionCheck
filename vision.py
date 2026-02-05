import cv2
import numpy as np


def detectar_giro_sinfin():
    cap = cv2.VideoCapture(0)

    # Aumenté un poco maxCorners para tener más densidad en el tornillo
    feature_params = dict(maxCorners=200,
                          qualityLevel=0.2,
                          minDistance=5,
                          blockSize=7)

    lk_params = dict(winSize=(21, 21),  # Ventana un poco más grande para 10 RPM
                     maxLevel=3,
                     criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

    ret, old_frame = cap.read()
    if not ret: return

    print("Selecciona el área del sinfín y presiona ENTER")
    r = cv2.selectROI("Selector", old_frame, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow("Selector")

    roi_x, roi_y, roi_w, roi_h = int(r[0]), int(r[1]), int(r[2]), int(r[3])
    old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)

    mask = np.zeros_like(old_gray)
    mask[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w] = 255

    p0 = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)

    direction_buffer = []
    BUFFER_SIZE = 10

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Si por alguna razón perdimos todos los puntos, re-inicializar
        if p0 is None or len(p0) == 0:
            p0 = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)
            old_gray = frame_gray.copy()
            continue

        p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

        if p1 is not None:
            good_new = p1[st == 1]
            good_old = p0[st == 1]

            dx_list = []

            # --- LISTA PARA FILTRAR PUNTOS ---
            puntos_validos_proximo_ciclo = []

            # Margen de seguridad (píxeles) antes de llegar al borde del ROI
            MARGEN_BORDE = 10

            for i, (new, old) in enumerate(zip(good_new, good_old)):
                a, b = new.ravel()
                c, d = old.ravel()

                # Calcular movimiento
                dx = a - c
                dx_list.append(dx)

                # --- LÓGICA DE LIMPIEZA (NUEVO) ---
                # Verificar si el punto sigue dentro del ROI con un margen seguro.
                # Si el punto toca el borde derecho o izquierdo, NO lo agregamos a la lista nueva.
                # Esto hace que el punto se "olvide".

                condicion_borde_izq = a > (roi_x + MARGEN_BORDE)
                condicion_borde_der = a < (roi_x + roi_w - MARGEN_BORDE)
                condicion_borde_arr = b > (roi_y + MARGEN_BORDE)
                condicion_borde_aba = b < (roi_y + roi_h - MARGEN_BORDE)

                if condicion_borde_izq and condicion_borde_der and condicion_borde_arr and condicion_borde_aba:
                    puntos_validos_proximo_ciclo.append(new)

                    # Solo dibujamos los puntos que sobreviven
                    frame = cv2.line(frame, (int(a), int(b)), (int(c), int(d)), (0, 255, 0), 2)
                    frame = cv2.circle(frame, (int(a), int(b)), 3, (0, 0, 255), -1)

            # Calcular promedio
            if dx_list:
                avg_dx = np.mean(dx_list)
                direction_buffer.append(avg_dx)
                if len(direction_buffer) > BUFFER_SIZE:
                    direction_buffer.pop(0)

            smoothed_dx = np.mean(direction_buffer) if direction_buffer else 0

            # Visualización
            UMBRAL = 0.2
            status_text = "DETENIDO"
            color_text = (0, 255, 255)

            if smoothed_dx > UMBRAL:
                status_text = ">>> DERECHA >>>"
                color_text = (0, 255, 0)
            elif smoothed_dx < -UMBRAL:
                status_text = "<<< IZQUIERDA <<<"
                color_text = (0, 0, 255)

            cv2.rectangle(frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (255, 0, 0), 2)
            cv2.putText(frame, f"Flow: {smoothed_dx:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_text, 2)
            cv2.putText(frame, status_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, color_text, 3)
            # Mostrar cuántos puntos estamos rastreando activamente
            cv2.putText(frame, f"Puntos: {len(puntos_validos_proximo_ciclo)}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (200, 200, 200), 1)

            old_gray = frame_gray.copy()

            # --- REPOBLACIÓN (NUEVO) ---
            # Convertimos la lista filtrada a numpy array para que OpenCV la entienda
            p0 = np.array(puntos_validos_proximo_ciclo).reshape(-1, 1, 2)

            # Si después de borrar los del borde nos quedan pocos puntos (ej. menos de 30),
            # buscamos nuevos puntos en toda el área para encontrar los que acaban de entrar.
            if len(puntos_validos_proximo_ciclo) < 50:
                p_nuevos = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)
                if p_nuevos is not None:
                    # Fusionar los puntos viejos que sobrevivieron con los nuevos encontrados
                    p0 = np.vstack((p0, p_nuevos))

        else:
            p0 = cv2.goodFeaturesToTrack(old_gray, mask=mask, **feature_params)

        cv2.imshow('Deteccion Giro Sinfin', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    detectar_giro_sinfin()