import math
from collections import deque
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QThread
import numpy as np
import cv2
from pypylon import pylon


class CaptureThread(QThread):
    def __init__(self, camera_manager):
        super().__init__()
        self.cam = camera_manager
        self.running = False

    def run(self):
        self.running = True
        while self.running and self.cam.camera.IsGrabbing():
            self.cam.capture_frame()

    def stop(self):
        self.running = False
        self.wait()


class CameraManager(QObject):

    frame_ready = pyqtSignal(np.ndarray)
    blobs_detected = pyqtSignal(list)
    dic_strain_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)

    # Camera configuration
    ROI = [0, 1072, 1700, 256]      # [OffsetX, OffsetY, Width, Height]
    FRAME_RATE = 35
    EXPOSURE_TIME = 50000
    GAMMA = 0.5

    # Specimen mode presets: (threshold, threshold_type, exposure, min_area, max_area, min_circularity)
    SPECIMEN_PRESETS = {
        "White": {
            "threshold": 150,
            "threshold_type": cv2.THRESH_BINARY_INV,  # dark dots on light background
            "exposure": 50000,
            "roi": [0, 988, 2348, 419],  # set via roi_tool.py; verified 2 blobs, L0=1665 px, ~136px cross-margin
            "mask_x": None,  # no masking needed
            "min_area": 2000,
            "max_area": 200000,
            "min_circularity": 0.5,
        },
        "Black": {
            "threshold": 0,  # ignored — Otsu auto-selects
            "threshold_type": cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            "exposure": 50000,
            "roi": [0, 1072, 1700, 256],
            "mask_x": None,
            "min_area": 2000,
            "max_area": 200000,
            "min_circularity": 0.3,
        },
    }

    # Active blob detection configuration (defaults to Black specimen)
    THRESHOLD = 0
    THRESHOLD_TYPE = cv2.THRESH_BINARY + cv2.THRESH_OTSU
    MIN_AREA = 2000
    MAX_AREA = 200000
    MIN_CIRCULARITY = 0.3

    def __init__(self):
        super().__init__()
        self.specimen_mode = "Black"
        self.mask_x = None
        self.camera = None
        self.initial_distance = None
        # The two marker positions AT the moment Px₀ was frozen, in raw-frame pixels. Only the
        # SEPARATION enters the strain maths; these are kept so the live view can draw the frozen
        # reference beside the moving markers and make the travel visible rather than numeric.
        self.initial_centroids = None
        self.capture_thread = None
        self.latest_dic_strain = 0.0
        self.latest_dic_cauchy = 0.0
        self.latest_dic_true_strain = 0.0
        self.latest_frame = None
        self.gauge_length_mm = 0.0
        self.px_per_mm = 0.0
        self.latest_dic_timestamp = None
        # Queue of recent DIC readings: (pc_timestamp_datetime, cauchy, true_strain)
        # Keeps last ~500 frames for time-matching with load cell
        self.dic_history = deque(maxlen=500)

    def set_specimen_mode(self, mode: str):
        """Switch between 'White' and 'Black' specimen presets."""
        if mode not in self.SPECIMEN_PRESETS:
            return
        preset = self.SPECIMEN_PRESETS[mode]
        self.specimen_mode = mode
        self.THRESHOLD = preset["threshold"]
        self.THRESHOLD_TYPE = preset["threshold_type"]
        self.EXPOSURE_TIME = preset["exposure"]
        self.ROI = preset["roi"]
        self.mask_x = preset["mask_x"]
        self.MIN_AREA = preset["min_area"]
        self.MAX_AREA = preset["max_area"]
        self.MIN_CIRCULARITY = preset["min_circularity"]
        # Update exposure on live camera if connected
        if self.camera and self.camera.IsOpen():
            try:
                self.camera.ExposureTime.Value = self.EXPOSURE_TIME
            except Exception:
                pass
        print(f"[Camera] Specimen mode set to: {mode}")

    def connect_camera(self) -> bool:
        try:
            self.camera = pylon.InstantCamera(
                pylon.TlFactory.GetInstance().CreateFirstDevice()
            )
            self.camera.Open()

            # Reset to full sensor first
            self.camera.Width.Value = self.camera.Width.Max
            self.camera.Height.Value = self.camera.Height.Max
            self.camera.OffsetX.Value = 0
            self.camera.OffsetY.Value = 0

            # Apply ROI - size before offset
            self.camera.Width.Value = self.ROI[2]
            self.camera.Height.Value = self.ROI[3]
            self.camera.OffsetX.Value = self.ROI[0]
            self.camera.OffsetY.Value = self.ROI[1]

            # Apply settings
            self.camera.AcquisitionFrameRateEnable.Value = True
            self.camera.AcquisitionFrameRate.Value = self.FRAME_RATE
            self.camera.ExposureTime.Value = self.EXPOSURE_TIME
            self.camera.Gamma.Value = self.GAMMA
            self.camera.PixelFormat.Value = "Mono8"

            self.connection_changed.emit(True)
            print("Camera connected successfully")
            return True

        except Exception as e:
            self.error_occurred.emit(str(e))
            print(f"Camera connection failed: {e}")
            return False

    def disconnect_camera(self):
        try:
            if self.capture_thread:
                self.capture_thread.stop()
            if self.camera and self.camera.IsOpen():
                self.camera.Close()
            self.connection_changed.emit(False)
            print("Camera disconnected")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def start_acquisition(self):
        try:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.capture_thread = CaptureThread(self)
            self.capture_thread.start()
            print("Acquisition started")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop_acquisition(self):
        try:
            if self.capture_thread:
                self.capture_thread.stop()
                self.capture_thread = None
            if self.camera and self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            print("Acquisition stopped")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def capture_frame(self) -> np.ndarray:
        try:
            grab_result = self.camera.RetrieveResult(
                5000, pylon.TimeoutHandling_ThrowException
            )
            if grab_result.GrabSucceeded():
                img = grab_result.Array
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                grab_result.Release()
                self.latest_frame = img  # add this
                # Run blob detection on every frame
                centroids = self.detect_blobs(img)
                if len(centroids) == 2:
                    dy = abs(centroids[1][1] - centroids[0][1])
                    dx = abs(centroids[1][0] - centroids[0][0])
                    print(f"[DIC] found 2 blobs | L(cy)={dy:.1f}px dx={dx:.1f}px")
                    self.calculate_dic_strain(centroids)
                else:
                    print(f"[DIC] found {len(centroids)} blobs")
                self.frame_ready.emit(img)
                return img
            grab_result.Release()
        except Exception as e:
            self.error_occurred.emit(str(e))
        return None

    def detect_blobs(self, frame) -> list:
        try:
            # Apply mask for black specimen to exclude background wall
            if self.mask_x is not None:
                frame = frame.copy()
                frame[:, :self.mask_x[0]] = 0
                frame[:, self.mask_x[1]:] = 0

            _, binary = cv2.threshold(
                frame, self.THRESHOLD, 255, self.THRESHOLD_TYPE
            )
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            valid = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if self.MIN_AREA < area < self.MAX_AREA:
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter ** 2)
                        if circularity > self.MIN_CIRCULARITY:
                            M = cv2.moments(cnt)
                            if M["m00"] > 0:
                                cx = M["m10"] / M["m00"]
                                cy = M["m01"] / M["m00"]
                                valid.append((cx, cy))

            # Sort by Y so blob 1 is always top, blob 2 always bottom
            valid.sort(key=lambda b: b[1])

            if len(valid) == 2:
                self.blobs_detected.emit(valid)
            else:
                self.error_occurred.emit(
                    f"Expected 2 blobs, found {len(valid)}"
                )

            return valid

        except Exception as e:
            self.error_occurred.emit(str(e))
            return []

    def tare_dic(self):
        frame = self.latest_frame
        if frame is None:
            self.error_occurred.emit("Tare failed - no frame captured")
            return
        centroids = self.detect_blobs(frame)
        if len(centroids) == 2:
            self.initial_distance = abs(centroids[1][1] - centroids[0][1])
            # Sorted along the loading axis so the frozen pair and the live pair can be zipped
            # marker-for-marker later; detect_blobs makes no promise about ordering.
            self.initial_centroids = [(float(x), float(y))
                                      for x, y in sorted(centroids, key=lambda c: c[1])]
            # NEW: store calibration factor using gauge length passed in from UI
            if self.gauge_length_mm and self.gauge_length_mm > 0:
                self.px_per_mm = self.initial_distance / self.gauge_length_mm
            print(f"DIC tared — L0 = {self.initial_distance:.1f} px | {self.gauge_length_mm:.1f} mm | {self.px_per_mm:.2f} px/mm")
        else:
            self.error_occurred.emit("Tare failed - need exactly 2 blobs")

    import math

    # Updated signal
    dic_strain_updated = pyqtSignal(float, float)  # (cauchy, true)

    def calculate_dic_strain(self, centroids) -> tuple:
        if self.initial_distance is None or len(centroids) != 2:
            return 0.0, 0.0
        current_distance = abs(centroids[1][1] - centroids[0][1])
        dx_px = abs(centroids[1][0] - centroids[0][0])
        if current_distance == 0:
            return 0.0, 0.0
        cauchy = (current_distance - self.initial_distance) / self.initial_distance
        # True strain — guard against zero/negative distance
        if current_distance > 0 and self.initial_distance > 0:
             true_strain = math.log(current_distance / self.initial_distance)
        else:
             true_strain = 0.0
        now = datetime.now()
        self.latest_dic_timestamp = now
        self.latest_dic_cauchy = cauchy
        self.latest_dic_true_strain = true_strain
        self.latest_dic_L_px = current_distance
        self.latest_dic_dx_px = dx_px
        # Append to history queue for time-matching with load cell
        # Tuple layout: (timestamp, cauchy, true_strain, L_px, dx_px)
        self.dic_history.append((now, cauchy, true_strain, current_distance, dx_px))
        self.dic_strain_updated.emit(cauchy, true_strain)
        return cauchy, true_strain
