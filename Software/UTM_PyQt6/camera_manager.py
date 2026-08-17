import math
import time
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

    # Carries the centroids ALONGSIDE the frame they came from. The GUI used to re-run detect_blobs
    # on the frame it received, which cost a second detection pass per frame, emitted a second
    # blobs_detected/error_occurred per frame (double-counting every dropout in the health HUD and
    # doubling the console spam), and could pair markers with the wrong frame once the GUI fell
    # behind. Shipping them together makes the pairing exact and the second pass unnecessary.
    frame_ready = pyqtSignal(np.ndarray, list)
    blobs_detected = pyqtSignal(list)
    dic_strain_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    # Something worth telling the operator that is NOT a failure. error_occurred prints under
    # "[Camera Error]" and coalesces on identical text, so routing a resolved condition through it
    # both mislabels it and defeats the coalescing (these messages carry coordinates, so no two
    # match). Kept separate for that reason.
    notice = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)

    # Camera configuration. This ROI is the pre-preset fallback and must stay in step with the
    # SPECIMEN_PRESETS entry for the default mode below — it was left on the stale
    # [0, 1072, 1700, 256] crop, so a fresh launch (which starts in Black) sat on a ROI too small
    # to hold both markers until a mode was re-selected.
    ROI = [0, 988, 2348, 419]       # [OffsetX, OffsetY, Width, Height]
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
            "threshold_type": cv2.THRESH_BINARY + cv2.THRESH_OTSU,  # BRIGHT dots on dark PLA
            "exposure": 50000,
            # SAME ROI as White: the specimen sits in the same place in the fixtures whatever
            # colour it is, so the crop that frames it is a property of the RIG, not the material.
            # This preset kept the pre-recalibration [0, 1072, 1700, 256], which is not a tuning
            # difference — a pair 1665 px apart needs ~1815 px along the specimen, so 1700 cropped
            # one marker off the SENSOR before detection ever ran (live badge: "DIC BAD 1/2,
            # track 0 %"), and 256 px across left a 150 px marker only 53 px of lateral margin.
            "roi": [0, 988, 2348, 419],
            "mask_x": None,
            "min_area": 2000,
            "max_area": 200000,
            # 0.5, matching White. It was 0.3 to be forgiving on a narrow crop; on the full ROI more
            # background is in frame, so the looser test is now a liability rather than a help.
            "min_circularity": 0.5,
        },
    }

    # Active blob detection configuration (defaults to Black specimen — keep in step with
    # SPECIMEN_PRESETS["Black"], which set_specimen_mode() overwrites these from)
    THRESHOLD = 0
    THRESHOLD_TYPE = cv2.THRESH_BINARY + cv2.THRESH_OTSU
    MIN_AREA = 2000
    MAX_AREA = 200000
    MIN_CIRCULARITY = 0.5

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
        self._trace_last_n, self._trace_last_t = -1, 0.0    # see _trace_blobs
        # Optional callable(frame) fed EVERY grabbed frame — see utm_capture.CaptureManager.submit.
        # Deliberately hooked here on the camera thread rather than off frame_ready: the display
        # signal is throttled to 12 fps and rides the GUI event queue, so a recording driven from
        # there would drop two frames in three and stutter whenever the GUI was busy.
        self.frame_sink = None
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
        # Rolling timestamps for the MEASURED grab / DIC rates (see camera_params). ~4 s at 35 fps,
        # long enough to be steady and short enough to react when the pipeline stalls.
        self._rate_grab = deque(maxlen=140)
        self._rate_dic = deque(maxlen=140)

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
                self._rate_grab.append(time.monotonic())
                # Run blob detection on every frame
                sink = self.frame_sink
                if sink is not None:
                    try:
                        sink(img)          # ~47 us: a bounded-buffer append, never any encoding
                    except Exception as e:
                        self.frame_sink = None      # a broken sink must not kill the grab loop
                        self.error_occurred.emit(f"Frame capture stopped: {e}")
                centroids = self.detect_blobs(img)
                if len(centroids) == 2:
                    self.calculate_dic_strain(centroids)
                self._trace_blobs(centroids)
                self.frame_ready.emit(img, centroids)
                return img
            grab_result.Release()
        except Exception as e:
            self.error_occurred.emit(str(e))
        return None

    # stdout is not free, and this ran on EVERY grabbed frame — 35 lines/s of the same message.
    # Print on a CHANGE of marker count, then at most once a second while it stays there. A steady
    # 2/2 says nothing new every 29 ms; a 2 → 1 transition is the thing worth seeing in the log.
    TRACE_MIN_INTERVAL_S = 1.0

    def _trace_blobs(self, centroids):
        n = len(centroids)
        now = time.monotonic()
        if n == self._trace_last_n and (now - self._trace_last_t) < self.TRACE_MIN_INTERVAL_S:
            return
        self._trace_last_n, self._trace_last_t = n, now
        if n == 2:
            dy = abs(centroids[1][1] - centroids[0][1])
            dx = abs(centroids[1][0] - centroids[0][0])
            print(f"[DIC] found 2 blobs | L(cy)={dy:.1f}px dx={dx:.1f}px")
        else:
            print(f"[DIC] found {n} blobs")

    def _choose_marker_pair(self, valid, shape):
        """Pick the two real markers out of N qualifying blobs. Returns them sorted by Y.

        Two criteria, in order of how much they can be trusted:

        1. Once Px₀ is frozen the marker separation is KNOWN, so the pair whose separation is
           closest to it wins. Under load that separation grows, but only by a few percent — far
           less than the gap to any pairing that involves a grip — so it stays decisive all the way
           to fracture.
        2. Before Px₀ is set there is no separation to compare against, so fall back on geometry:
           the markers are sprayed on the specimen's centre-line, while the interlopers (grips,
           fixture edges, background) sit at the lateral extremes. Take the two blobs nearest the
           centre-line, breaking ties on area.

        Neither criterion is silent — the rejected blobs are reported, throttled, so a recurring
        interloper can be dealt with physically (or with `mask_x`) instead of merely tolerated.
        """
        import time as _time

        if self.initial_distance:
            best = None
            for i in range(len(valid)):
                for j in range(i + 1, len(valid)):
                    err = abs(abs(valid[j][1] - valid[i][1]) - self.initial_distance)
                    if best is None or err < best[0]:
                        best = (err, valid[i], valid[j])
            # If NO pairing is near Px₀, the markers themselves are missing and everything in frame
            # is an interloper. Returning the two most central of them would hand the strain maths a
            # confident, wrong number; hand back the raw list instead so the caller reports the
            # dropout. Caught by the check suite, which fed it a frame of grips and no markers and
            # got two grips back as if they were the pair.
            if best is None or best[0] > 0.25 * self.initial_distance:
                return valid
            chosen = [best[1], best[2]]
            why = f"separation closest to Px₀ (off by {best[0]:.0f} px)"
        else:
            # No Px₀ yet, so there is no separation to test against. Geometry instead: the markers
            # are sprayed on the specimen centre-line, the interlopers sit at the lateral extremes.
            mid_x = shape[1] / 2.0
            ranked = sorted(valid, key=lambda b: abs(b[0] - mid_x))
            chosen = ranked[:2]
            why = "nearest the specimen centre-line (Px₀ not set yet)"

        rejected = [b for b in valid if b not in chosen]
        now = _time.monotonic()
        if rejected and now - getattr(self, "_pair_last_t", 0.0) > 5.0:
            self._pair_last_t = now
            mid_x = shape[1] / 2.0
            where = ", ".join(
                f"({b[0]:.0f},{b[1]:.0f}) {abs(b[0] - mid_x) / mid_x * 100:.0f}% off-centre"
                for b in rejected)
            self.notice.emit(
                f"{len(valid)} blobs qualified — kept the pair {why}; ignored {where}. "
                "A blob that keeps appearing near the frame edge is usually a grip or fixture: "
                "mask it (SPECIMEN_PRESETS mask_x) or move it out of the ROI.")
        return sorted(chosen, key=lambda b: b[1])

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

            if len(valid) > 2:
                # More than 2 does NOT mean the markers were missed — it means something else in
                # frame passed the filters too. On the black specimen that is the white grips: the
                # recalibrated ROI is wide enough to include them, they are as bright as the spray
                # dots, and Otsu's threshold shifts a little frame to frame, so they drift in and
                # out of qualifying. Discarding those frames threw away good strain data and read
                # as a dropout in the health badge.
                valid = self._choose_marker_pair(valid, frame.shape)

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

    def set_exposure(self, microseconds):
        """Change exposure on a live camera. Returns the value the camera actually accepted.

        Basler clamps to the sensor's own limits and quantises to its increment, so the accepted
        value is read BACK rather than assumed — auto-calibration must score the exposure that was
        really used, not the one that was requested."""
        if self.camera is None:
            return None
        try:
            node = self.camera.ExposureTime
            lo, hi = node.Min, node.Max
            node.Value = float(max(lo, min(hi, microseconds)))
            self.EXPOSURE_TIME = float(node.Value)
            return self.EXPOSURE_TIME
        except Exception as e:
            self.error_occurred.emit(f"Exposure change failed: {e}")
            return None

    @staticmethod
    def _hz(stamps):
        """Rate from a rolling deque of timestamps (0.0 until there are two)."""
        if len(stamps) < 2:
            return 0.0
        span = stamps[-1] - stamps[0]
        return (len(stamps) - 1) / span if span > 0 else 0.0

    def camera_params(self):
        """Live parameter snapshot for the GUI readout (empty dict when not connected)."""
        if self.camera is None:
            return {}
        out = {"threshold": self.THRESHOLD, "mode": self.specimen_mode,
               "fps_set": self.FRAME_RATE}
        # MEASURED rates, not the camera's configured one.
        #
        # ResultingFrameRate is what the sensor is set up to deliver; it says nothing about how many
        # frames Python actually got, nor how many of those produced a strain reading. On S24
        # (2026-08-14) the configured rate read 35 fps, frames arrived at 19.9, and only 3.0 strain
        # readings per second reached the CSV -- a 6x loss nothing on screen would have shown. The
        # gap between these two numbers is the diagnostic.
        out["fps_grab"] = self._hz(self._rate_grab)
        out["hz_dic"] = self._hz(self._rate_dic)
        for name, key in (("ExposureTime", "exposure_us"), ("Gamma", "gamma"),
                          ("Gain", "gain"), ("ResultingFrameRate", "fps_actual")):
            try:
                out[key] = float(getattr(self.camera, name).Value)
            except Exception:
                pass
        f = self.latest_frame
        if f is not None:
            out["roi"] = f"{f.shape[1]}×{f.shape[0]}"
            out["mean"] = float(f.mean())
        return out

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
        self._rate_dic.append(time.monotonic())
        self.dic_strain_updated.emit(cauchy, true_strain)
        return cauchy, true_strain
