import cv2
import numpy as np
import time
import json
import threading
import os
import logging
import glob
from config import PARAMS
from collections import deque
import datetime

# --- Log handler setup.
logger = logging.getLogger('SpinCheck')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VISION_FILE = os.path.join(BASE_DIR, 'vision_config.json')
VIDEO_DIR = os.path.join(BASE_DIR, 'video_logs')


class VisionSystem:
    def __init__(self):
        self.cap = None
        self.streaming = False
        self.thread = None
        self.lock = threading.Lock()

        self.latest_frame = None
        self.new_frame_available = False
        self.show_debug_points = True
        self.debug_mask = False

        # --- Video variables.
        self.video_buffer = deque(maxlen=int(PARAMS.VISION_TIMEOUT_SEC * PARAMS.VISION_TARGET_FPS))
        self.saving_video = False

        # --- Logic variables.
        self.last_stable_state = 'STOPPED'
        self.state_stable_start = 0
        self.direction_buffer = []
        self.reset_tracking_flag = False

        # --- Test variables.
        self.test_active = False
        self.test_result = None
        self.test_start_time = 0

        # --- FPS variables.
        self.current_fps = 0.0

        # --- Configuration.
        self.spin_roi = None
        self.runout_rois = []
        self.feature_params = dict(maxCorners=200, qualityLevel=0.3, minDistance=5, blockSize=7)
        self.lk_params = dict(winSize=(21, 21), maxLevel=3,
                                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        self.load_config()

    def load_config(self):
        """Load rois from JSON file."""
        if os.path.exists(VISION_FILE):
            try:
                with open(VISION_FILE, 'r') as f:
                    data = json.load(f)
                    if data.get('rotation_roi'):
                        self.spin_roi = tuple(data.get('rotation_roi'))
                    self.runout_rois = [tuple(r) for r in data.get('runout_rois', [])]
            except Exception:
                pass

    def save_config(self, spin_roi, runout_rois):
        """Save rois to JSON file."""
        data = {'rotation_roi': spin_roi, 'runout_rois': runout_rois}
        try:
            with open(VISION_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            self.spin_roi = spin_roi
            self.runout_rois = runout_rois
            return True
        except Exception:
            return False

    def start_stream(self):
        """Start streaming thread and grab camera control."""
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.streaming:
            self.streaming = True
            self.thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.thread.start()

    def stop_stream(self):
        """Stop streaming thread and release camera control."""
        self.streaming = False
        if self.thread: self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None

    def start_test(self):
        """Start test in processing loop."""
        if not self.spin_roi: return False
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
        """Get results from test in processing loop."""
        return self.test_result

    def get_frame_for_gui(self):
        """Get a copy from last frame in processing loop."""
        with self.lock:
            self.new_frame_available = False
            if self.latest_frame is None: return None
            return self.latest_frame.copy()


    def _processing_loop(self):
        """Processing loop that detects spin direction and runout."""
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

            # --- Threshold.
            optimal_threshold = 0
            mean_brightness = 0
            strict_threshold = 0
            color_mask = None

            if dt > 0:
                fps_instantaneo = 1.0 / dt
                self.current_fps = (self.current_fps * 0.9) + (fps_instantaneo * 0.1)

            # --- Set frame from BGR to GRAY for analysis.
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # --- Spin detection roi drawing.
            if self.spin_roi:
                vx, vy, vw, vh = self.spin_roi
                cv2.rectangle(frame, (int(vx), int(vy)), (int(vx + vw), int(vy + vh)), (0, 255, 0), 2)

                # --- Get roi gray frame
                threshold_frame = frame_gray[int(vy):int(vy + vh), int(vx):int(vx + vw)]

                # --- Get mean brightness.
                mean_brightness = cv2.mean(threshold_frame)[0]

                # --- Threshold value.
                optimal_threshold, _ = cv2.threshold(threshold_frame, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                strict_threshold = optimal_threshold * 1.10
                strict_threshold = min(230, strict_threshold)
                _, color_mask = cv2.threshold(frame_gray, strict_threshold, 255, cv2.THRESH_BINARY)

            # --- Runout detection roi drawing.
            for r in self.runout_rois:
                bx, by, bw, bh = r
                if bw > 0:
                    cv2.rectangle(frame, (int(bx), int(by)), (int(bx + bw), int(by + bh)), (0, 0, 255), 2)

            # --- Full logic.
            if self.test_active and self.spin_roi:
                # --- Get roi as x, y, width and height.
                vx, vy, vw, vh = self.spin_roi

                # --- Force clean.
                if self.reset_tracking_flag:
                    p0 = None
                    old_gray = None
                    self.reset_tracking_flag = False

                # --- Timeout detection.
                if (time.time() - self.test_start_time) > PARAMS.VISION_TIMEOUT_SEC:
                    self.test_result = 'TIMEOUT'
                    self.test_active = False

                # --- First tracking points calculate.
                if p0 is None:
                    # --- Check endless missing.
                    if mean_brightness < PARAMS.VISION_ENDLESS_DETECTION:
                        self.test_result = 'FAIL_ENDLESS_MISSING'
                        self.test_active = False
                        continue

                    # --- Create an array of 'Black' for mask as frame form.
                    mask = np.zeros_like(frame_gray)
                    # --- Draw a 'White' rectangle on mask where spin roi is.
                    mask[int(vy):int(vy + vh), int(vx):int(vx + vw)] = 255

                    for r in self.runout_rois:
                        # --- Get runout roi as x, y, width and height.
                        bx, by, bw, bh = r
                        # --- Reset to 'Black' on mask where a runout roi intersects with spin roi.
                        if bw > 0: mask[int(by):int(by + bh), int(bx):int(bx + bw)] = 0

                    # --- Create final mask.
                    final_mask = cv2.bitwise_and(mask, color_mask)

                    # --- Return a list of [x, y] tracking points in current frame.
                    p0 = cv2.goodFeaturesToTrack(frame_gray, mask=final_mask, **self.feature_params)

                    # --- Save frame for next loop.
                    old_gray = frame_gray.copy()

                # --- Optical flow calculate.
                if p0 is not None and len(p0) > 0:
                    # --- Get new tracking point list, status and error from optical flow calculation.
                    p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **self.lk_params)

                    if p1 is not None:
                        # --- Save only the points that opencv still tracking.
                        good_new = p1[st == 1]
                        good_old = p0[st == 1]
                        dx_list = []
                        valid_points = []
                        runout_detected = False

                        # --- Safe margins for tracking points.
                        margin_x = int(vw * 0.15)
                        margin_y = int(vh * 0.15)

                        for new, old in zip(good_new, good_old):
                            a, b = new.ravel() # Current position.
                            c, d = old.ravel() # Previous position.

                            # --- Check runout.
                            for r in self.runout_rois:
                                # --- Get runout as x, y, width and height.
                                bx, by, bw, bh = r
                                # --- Check if tracking point coordinates are in runout zone.
                                if bw > 0 and (bx < a < bx + bw) and (by < b < by + bh):
                                    # --- Trigger runout fail.
                                    runout_detected = True
                                    cv2.circle(frame, (int(a), int(b)), 8, (0, 0, 255), -1)
                                    break
                            if runout_detected: break

                            # Check if current position of tracking point are in safe zone.
                            in_safe_zone = (vx + margin_x < a < vx + vw - margin_x) and (vy + margin_y < b < vy + vh - margin_y)
                            if in_safe_zone:
                                # --- Append horizontal movement of point to dx_list.
                                dx_list.append(a - c)
                                valid_points.append(new)
                                # --- Draw where point is on frame.
                                if self.show_debug_points:
                                    cv2.circle(frame, (int(a), int(b)), 2, (0, 255, 0), -1)

                        # --- Runout fail.
                        if runout_detected:
                            self.test_result = 'FAIL_RUNOUT'
                            self.test_active = False
                            cv2.putText(frame, 'FAIL: RUNOUT', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                        else:

                            if dx_list:
                                # --- Append mean of all horizontal movement of points to direction buffer.
                                self.direction_buffer.append(np.mean(dx_list))
                                # --- Save last 10 point.
                                if len(self.direction_buffer) > 10: self.direction_buffer.pop(0)

                            # --- Get mean of directional buffer. This actuates as a damper.
                            smoothed_dx = np.mean(self.direction_buffer) if self.direction_buffer else 0

                            # --- Check if there is less than 150 valid points.
                            p0 = np.array(valid_points).reshape(-1, 1, 2)
                            if len(valid_points) < 150:
                                mask = np.zeros_like(frame_gray)
                                # --- Mask recalculate.
                                mask[int(vy):int(vy + vh), int(vx):int(vx + vw)] = 255
                                for r in self.runout_rois:
                                    bx, by, bw, bh = r
                                    if bw > 0: mask[int(by):int(by + bh), int(bx):int(bx + bw)] = 0
                                final_mask = cv2.bitwise_and(mask, color_mask)

                                # --- Get new points.
                                p_new = cv2.goodFeaturesToTrack(frame_gray, mask=final_mask, **self.feature_params)
                                if p_new is not None:
                                    p0 = np.vstack((p0, p_new)) if len(p0) > 0 else p_new

                            # --- Save frame for next loop.
                            old_gray = frame_gray.copy()

                            # --- Check smooth movement logic.
                            current_state = 'STOPPED'
                            if smoothed_dx > 0.3:
                                current_state = 'RIGHT'
                            elif smoothed_dx < -0.3:
                                current_state = 'LEFT'

                            # --- Draw current state on frame.
                            cv2.putText(frame, f'DIR: {current_state}, DX: {smoothed_dx:0.2f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (51, 255, 204), 2)

                            # --- Check if current state is same as previous.
                            if current_state == self.last_stable_state and current_state != 'STOPPED':
                                # --- Check if current state maintains for PARAMS.VISION_STABLE_TIME_SEC.
                                if (time.time() - self.state_stable_start) >= PARAMS.VISION_STABLE_TIME_SEC:
                                    self.test_result = current_state
                                    self.test_active = False
                            else:
                                # --- Reset timer if state changed.
                                if current_state != self.last_stable_state:
                                    self.last_stable_state = current_state
                                    self.state_stable_start = time.time()
            else:
                # --- Reset previous tracking points to None if no test or all points where lost.
                if p0 is not None:
                    p0 = None
                    old_gray = None

            # --- Draw FPS.
            alto_imagen = frame.shape[0]
            cv2.putText(frame, f'FPS: {int(self.current_fps)}, OTSU: {int(strict_threshold)}, BRIGHTNESS: {int(mean_brightness)}', (10, alto_imagen - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (51, 255, 204), 2)

            # --- Save frame to video buffer.
            with self.lock:
                self.video_buffer.append(frame.copy())

            # --- Save frame for gui.
            if self.debug_mask and self.spin_roi and color_mask is not None:
                mask_bgr = cv2.cvtColor(color_mask, cv2.COLOR_GRAY2BGR)
                vx, vy, vw, vh = self.spin_roi
                cv2.rectangle(mask_bgr, (int(vx), int(vy)), (int(vx + vw), int(vy + vh)), (0, 255, 0), 2)
                cv2.putText(mask_bgr, f'Otsu Threshold: {int(strict_threshold)}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                frame_rgb = cv2.cvtColor(mask_bgr, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # --- frame resize.
            frame_gui = cv2.resize(frame_rgb, (320, 240))

            with self.lock:
                self.latest_frame = frame_gui
                self.new_frame_available = True

    def calibrate_gui_safe(self):
        """
        Opens opencv window to select roi's.
        Blocks camera execution until calibration ended.
        """
        # --- Load last frame to calibration window.
        frame_bgr = None
        with self.lock:
            if self.latest_frame is None:
                logger.error('VISION: No image to calibrate')
                return False
            frame_bgr = cv2.cvtColor(self.latest_frame, cv2.COLOR_RGB2BGR)

        window_name = 'Calibration'
        logger.info('VISION: Starts calibration')

        try:
            logger.info('VISION: Select spin zone (Green) then press ENTER.')
            r_rot = cv2.selectROI(window_name, frame_bgr, showCrosshair=True, fromCenter=False)

            # --- Validate height or width.
            if r_rot[2] == 0 or r_rot[3] == 0:
                logger.warning('VISION: wrong height or width.')
                cv2.destroyWindow(window_name)
                cv2.waitKey(1)
                return False

            # --- Draw safe zone roi to frame.
            temp_img = frame_bgr.copy()
            cv2.rectangle(temp_img, (int(r_rot[0]), int(r_rot[1])),
                            (int(r_rot[0] + r_rot[2]), int(r_rot[1] + r_rot[3])), (0, 255, 0), 2)

            logger.info('VISION: Select upper runout zone (Red 1) then press ENTER.')
            r_run1 = cv2.selectROI(window_name, temp_img, showCrosshair=True, fromCenter=False)

            # --- Draw upper runout zone to frame.
            if r_run1[2] > 0 and r_run1[3] > 0:
                cv2.rectangle(temp_img, (int(r_run1[0]), int(r_run1[1])),
                                (int(r_run1[0] + r_run1[2]), int(r_run1[1] + r_run1[3])), (0, 0, 255), 2)

            logger.info('VISION: Select lower runout zone (Red 2) then press ENTER.')
            r_run2 = cv2.selectROI(window_name, temp_img, showCrosshair=True, fromCenter=False)

            # --- Destroy window.
            cv2.destroyWindow(window_name)
            cv2.waitKey(1)  # Vital en Linux para procesar el cierre de la ventana

            # --- Create runout list.
            runout_list = []
            if r_run1[2] > 0: runout_list.append(r_run1)
            if r_run2[2] > 0: runout_list.append(r_run2)

            # --- Save roid to JSON file.
            success = self.save_config(r_rot, runout_list)

            if success:
                logger.info(f"VISION: Calibration success.")
                # --- Update memory roi's.
                self.spin_roi = r_rot
                self.runout_rois = runout_list

            return success

        except Exception as e:
            logger.error(f"VISION: {e}")
            try:
                cv2.destroyWindow(window_name)
                cv2.waitKey(1)
            except:
                pass
            return False

    def save_video(self, name='video'):
        """Trigger a save of last frame buffer as video file."""
        if self.saving_video:
            return

        with self.lock:
            buffer_copy = list(self.video_buffer)

        if len(buffer_copy) == 0:
            logger.warning('VISION: No image to save.')
            return

        self.saving_video = True
        # --- Start video saving on thread.
        threading.Thread(target=self._write_video_thread, args=(buffer_copy, name), daemon=True).start()

    def _write_video_thread(self, frames_to_save, name):
        """Write frames to video file and handle automatic old file deletion."""
        try:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            if not os.path.exists(VIDEO_DIR):
                os.makedirs(VIDEO_DIR)

            filename = os.path.join(VIDEO_DIR, f'{timestamp}_{name}.mp4')

            height, width, layers = frames_to_save[0].shape
            size = (width, height)

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(filename, fourcc, 30, size)

            # --- Save frame to frame.
            for frame in frames_to_save:
                out.write(frame)

            out.release()
            logger.info(f'VISION: Save video to {filename}')

            # --- Look up for all videos in dir.
            search_pattern = os.path.join(VIDEO_DIR, '*.mp4')
            video_files = glob.glob(search_pattern)

            # --- Delete oldest videos.
            if len(video_files) > PARAMS.VISION_MAX_VIDEO_LOGS:
                video_files.sort(key=os.path.getmtime)

                videos_to_delete = len(video_files) - PARAMS.VISION_MAX_VIDEO_LOGS

                for i in range(videos_to_delete):
                    old_videos = video_files[i]
                    try:
                        os.remove(old_videos)
                        logger.info(f'VISION: Deleted old video {os.path.basename(old_videos)}')
                    except Exception as e:
                        logger.error(f'VISION: {e}')

        except Exception as e:
            logger.error(f'VISION: {e}')
        finally:
            self.saving_video = False


vision_system = VisionSystem()

if __name__ == "__main__":
    logger.error(f'{__name__} module is not tended to be imported')