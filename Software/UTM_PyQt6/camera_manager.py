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
            # FIXED, not Otsu. Measured over two full runs of saved frames (dic_replay.py):
            #
            #                     Otsu      fixed 149
            #   S29  PETG        48.5 %       99.5 %      <- the run that had to be abandoned
            #   S13  black PLA   99.8 %       99.8 %
            #
            # Otsu recomputes the cut per frame from the whole picture, so it follows the SCENE
            # rather than the markers. On black PLA it happened to land at 131, inside that
            # specimen's 140-180 working window. On PETG — glossier, more translucent, brighter
            # body — it lands at 127, and that specimen's window is 130-160. Otsu sat three grey
            # levels BELOW the range where both markers survive, so one marker fell under the cut
            # on half the frames. Nothing was wrong with the markers, the ROI or the lighting: the
            # threshold rule was choosing a value just outside the band that works.
            #
            # 149 is the joint optimum — the value whose WORSE material still scores 97.3 % raw
            # (S29 99.4, S13 97.3). Not the peak for either alone (PETG peaks flat at 151-157,
            # PLA at 148 and again at 166-169) but the one with both materials inside it.
            #
            # This is a lighting-dependent constant, so it is a starting point and not a law. When
            # the LEDs or the material change, run Camera > Auto-calibrate DIC: it sweeps fixed
            # thresholds AND Otsu, scores them on contrast margin, and applies the winner.
            "threshold": 149,
            "threshold_type": cv2.THRESH_BINARY,  # BRIGHT dots on a dark specimen
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
            # ⚠ TEMPORARY 0.40 FOR THE PETG/TPU CAMPAIGN — put back to 0.50 when it ends.
            # Roadmap item 10 carries the revert.
            #
            # The PETG specimens sprayed on 2026-08-22 have a crescent of overspray fused to the rim
            # of each dot. The dot itself is round; the dot-plus-crescent is not. Measured on the
            # capture at 20260822_174204: marker 2 is 17 131 px² against a clean dot's 11 140, and
            # scores circularity 0.49-0.51 across the run — straddling a 0.50 gate, so sensor noise
            # flipped it either side frame by frame and 18 % of frames lost it.
            #
            # Threshold cannot fix this: NO fixed threshold yields exactly two blobs on those
            # frames, because the failure is shape and not brightness. Swept on the real capture,
            # 2-blob rate against min_circularity:
            #     0.50 -> 81.8 %   0.45 -> 100 %   0.40 -> 100 %   0.25 -> 100 %
            # and NOTHING extra is admitted anywhere in that range (3+ blobs stays at 0.0 %), so
            # 0.40 sits mid-plateau rather than on a cliff.
            #
            # This is a REAL loosening and the right long-term fix is the specimen: mask around each
            # dot so overspray cannot land touching it, and use matte paint. A clean dot scores 0.76.
            "min_circularity": 0.40,
        },
    }

    # Active blob detection configuration (defaults to Black specimen — keep in step with
    # SPECIMEN_PRESETS["Black"], which set_specimen_mode() overwrites these from)
    THRESHOLD = 149
    THRESHOLD_TYPE = cv2.THRESH_BINARY

    # How far a marker pair may sit from Px₀ before it is treated as a lost marker rather than as
    # strain — applied when there are exactly two candidates and nothing to choose between.
    #
    # ASYMMETRIC, because tension only pulls the markers APART. A separation far ABOVE Px₀ is what
    # a stretching specimen looks like; a separation far BELOW it is not something a tensile test
    # can produce, so the two directions deserve different limits and the old symmetric ±25 % gave
    # them the same one.
    #
    # Measured over every frame of S13 and S26 before changing this: the LOWER bound fired once (a
    # post-fracture frame at 0.063 × Px₀ — the markers had gone) and the UPPER bound fired NEVER.
    # S29's mount-holder swap, the incident these guards were added for, sat at 1.11 × Px₀ — well
    # inside the old window, and was caught by the RATE guard below, not by this one.
    #
    # So the upper bound has never demonstrably caught anything, and raising it costs nothing;
    # the lower bound is where the value is, and 0.85 is TIGHTER than the 0.75 the symmetric
    # version implied. This change is stricter where the guard works and looser where it does not.
    PAIR_MIN_FRAC = 0.85     # 15 % compressive strain — far beyond the ~1 % the rig's V3 series did
    # Upper bound as a MULTIPLE of Px₀, i.e. 1 + the largest strain worth believing.
    # 1.25 is the default and stays tight. An elastomer needs more, and gets it from the MATERIAL
    # setting rather than from an edit here or from the specimen-mode dropdown — how far a pair may
    # legitimately travel is a property of the polymer, and a TPU specimen can be black or white.
    # See MATERIALS in main.py; set_material() writes it here.
    PAIR_MAX_FRAC = 1.25

    # How fast the separation may CHANGE. This is the guard that catches a grip or mount edge being
    # picked up in place of a marker, which the ±25 % window cannot: on S29 the swap moved L_px by
    # 135 px in a single frame — only +8 % of Px₀, comfortably inside the window, and it still cost
    # the whole test (a bogus one-sample strain jump tripped the auto-stop at peak load, 2931 N,
    # with the specimen intact).
    #
    # The rate argument is what makes it safe. At 0.10 mm/s over an 80 mm gauge at 20.9 px/mm, real
    # strain moves the pair by about 0.1 px per frame, i.e. ~2 px/s — and that is the case where ALL
    # crosshead motion reaches the gauge, where measured DIC is ~0.38 of it. 30 px/s is a 15x margin
    # on the physical limit and still ~500x tighter than the swap it has to reject.
    #
    # Rate, not a flat step, because dropouts create gaps: after 10 s with no reading the specimen
    # really has moved, and a flat limit would reject the recovery frame and never re-acquire.
    # Unlike the PAIR_MIN/MAX_FRAC window this needs no change for TPU — an elastomer strains enormously but not
    # instantaneously, and at 0.10 mm/s it moves the markers no faster than PLA does.
    PAIR_MAX_STEP_PX_PER_S = 30.0
    PAIR_STEP_FLOOR_PX = 30.0        # always allow this much, so noise alone can never lock it out
    MIN_AREA = 2000
    MAX_AREA = 200000
    MIN_CIRCULARITY = 0.40      # ⚠ temporary, matches SPECIMEN_PRESETS["Black"] — see the note there

    def __init__(self):
        super().__init__()
        self.specimen_mode = "Black"
        self.material = "PLA"
        self.mask_x = None
        self.camera = None
        self.initial_distance = None
        # (monotonic, separation) of the last ACCEPTED pair — the baseline the rate guard measures
        # against. None means "no baseline yet", which lets the next pair through unchallenged.
        self._last_sep = None
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
        # Per-stage cost of the grab loop, in ms, over the last ~140 frames.
        #
        # This exists because two runs (S24 27 %, S13 47 %) came back with half their load samples
        # carrying no strain, and the cause could not be found offline: the camera grabbed at
        # 19.9 fps with zero dropped frames, the detector found both markers on 99.9 % of frames,
        # and detection benchmarks at 1.4 ms. The loop has no sleep and StartGrabbing uses
        # LatestImageOnly, so the driver DISCARDS whatever the loop cannot keep up with — which
        # means the loop's own speed IS the DIC delivery rate, and the only way to find the slow
        # stage is to time each one on the rig. Five perf_counter calls per frame, ~50 ns each.
        self._stage_ms = {k: deque(maxlen=140) for k in
                          ("wait", "rotate", "sink", "detect", "strain", "emit", "total")}
        self._slow_last_t = 0.0
        # Rolling timestamps for the MEASURED grab / DIC rates (see camera_params). ~4 s at 35 fps,
        # long enough to be steady and short enough to react when the pipeline stalls.
        self._rate_grab = deque(maxlen=140)
        self._rate_dic = deque(maxlen=140)

    def set_specimen_mode(self, mode: str):
        """Switch specimen preset. Applies optics AND the strain window that preset tolerates."""
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
        # The pair window is deliberately NOT touched here. How far a marker pair may legitimately
        # travel is a property of the MATERIAL; White/Black is a property of the OPTICS. Resetting
        # it here would silently re-tighten an elastomer's window the moment the operator switched
        # polarity mid-setup. set_material() owns it.
        # Update exposure on live camera if connected
        if self.camera and self.camera.IsOpen():
            try:
                self.camera.ExposureTime.Value = self.EXPOSURE_TIME
            except Exception:
                pass
        print(f"[Camera] Specimen mode set to: {mode}")

    def set_roi(self, roi):
        """Override the sensor crop for this specimen.

        Separate from the specimen preset because the ROI a MATERIAL needs is not the ROI a
        colour needs. The shipped 2348 px crop lets the marker pair separate to 33 % strain
        before a marker reaches the edge; the rig's own 30 mm travel backstop is 37.5 % on an
        80 mm gauge, so on an elastomer the markers leave the frame BEFORE anything stops the
        test, and the strain trace simply ends mid-pull. The full 2448 px sensor width moves
        that limit to 39 %, past the backstop.

        Takes effect on the next connect: Basler ROI is applied in connect_camera, and Width /
        OffsetX cannot be changed on a streaming camera.
        """
        roi = [int(v) for v in roi]
        changed = roi != list(self.ROI)
        self.ROI = roi
        print(f"[Camera] ROI set to {roi} (OffsetX, OffsetY, Width, Height)")
        return changed and self.camera is not None and self.camera.IsOpen()

    def set_material(self, name, max_frac):
        """How far a marker pair may travel before it is called a lost marker.

        Separate from set_specimen_mode on purpose. That one picks OPTICS — dark dots on a light
        specimen or the reverse — and a TPU specimen can be either colour. This one picks the
        strain the DIC is willing to believe, which is a property of the polymer.
        """
        self.material = name
        self.PAIR_MAX_FRAC = float(max_frac)
        print(f"[Camera] Material set to: {name} (pair window "
              f"{self.PAIR_MIN_FRAC:.2f}-{self.PAIR_MAX_FRAC:.2f} x Px0)")

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

    # Warn when the loop falls below this. The camera runs at ~20 fps and the load cell at ~11 Hz,
    # so anything under ~12 Hz means load samples start going out without a strain reading.
    SLOW_LOOP_HZ = 12.0
    SLOW_WARN_EVERY_S = 10.0

    def capture_frame(self) -> np.ndarray:
        t = time.perf_counter
        try:
            _t0 = t()
            grab_result = self.camera.RetrieveResult(
                5000, pylon.TimeoutHandling_ThrowException
            )
            _t1 = t()                                   # wait: idle if the loop is ahead of the camera
            if grab_result.GrabSucceeded():
                img = grab_result.Array
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                grab_result.Release()
                self.latest_frame = img  # add this
                self._rate_grab.append(time.monotonic())
                _t2 = t()
                # Run blob detection on every frame
                sink = self.frame_sink
                if sink is not None:
                    try:
                        sink(img)          # ~47 us: a bounded-buffer append, never any encoding
                    except Exception as e:
                        self.frame_sink = None      # a broken sink must not kill the grab loop
                        self.error_occurred.emit(f"Frame capture stopped: {e}")
                _t3 = t()
                centroids = self.detect_blobs(img)
                _t4 = t()
                if len(centroids) == 2:
                    self.calculate_dic_strain(centroids)
                _t5 = t()
                self._trace_blobs(centroids)
                self.frame_ready.emit(img, centroids)
                _t6 = t()
                self._record_stages(_t0, _t1, _t2, _t3, _t4, _t5, _t6)
                return img
            grab_result.Release()
        except Exception as e:
            self.error_occurred.emit(str(e))
        return None

    def _record_stages(self, t0, t1, t2, t3, t4, t5, t6):
        """Bank the per-stage cost, and say something if the loop has gone slow.

        `wait` is time blocked in RetrieveResult. A HEALTHY loop spends most of its time there —
        it means the loop is faster than the camera and is idling. A loop that is starving the DIC
        shows the opposite: near-zero wait and the time piled into one of the other stages, which
        is exactly the fingerprint needed to tell a slow detector from a slow sink from a GUI
        queue that has backed up behind frame_ready.
        """
        s = self._stage_ms
        s["wait"].append((t1 - t0) * 1e3)
        s["rotate"].append((t2 - t1) * 1e3)
        s["sink"].append((t3 - t2) * 1e3)
        s["detect"].append((t4 - t3) * 1e3)
        s["strain"].append((t5 - t4) * 1e3)
        s["emit"].append((t6 - t5) * 1e3)
        s["total"].append((t6 - t0) * 1e3)
        if len(s["total"]) < s["total"].maxlen:
            return
        med = sorted(s["total"])[len(s["total"]) // 2]
        hz = 1000.0 / med if med > 0 else 0.0
        now = time.monotonic()
        if hz >= self.SLOW_LOOP_HZ or now - self._slow_last_t < self.SLOW_WARN_EVERY_S:
            return
        self._slow_last_t = now
        self.notice.emit(f"DIC loop is running at {hz:.1f} Hz — below the {self.SLOW_LOOP_HZ:.0f} Hz "
                         f"needed to give every load sample a strain reading. {self.loop_breakdown()}")

    def loop_breakdown(self):
        """One line naming where the grab loop's time goes — median ms per stage."""
        s = self._stage_ms
        if not s["total"]:
            return "no frames yet"
        med = lambda k: sorted(s[k])[len(s[k]) // 2] if s[k] else 0.0   # noqa: E731
        parts = " · ".join(f"{k} {med(k):.1f}" for k in
                           ("wait", "rotate", "sink", "detect", "strain", "emit"))
        return f"per frame (ms): {parts} · TOTAL {med('total'):.1f}"

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

            # A pair has to be PLAUSIBLE, not merely a pair. Until now the separation was only
            # checked when there were more than two candidates to choose between; exactly two
            # qualifying blobs went straight to the strain maths however far apart they were. On
            # S13 that let one frame through with the markers 112 px apart against a 1668 px Px₀ —
            # frame 1458 of 1539, i.e. after fracture, when one marker had gone. One row is all it
            # takes: a single bogus L_px is exactly the post-fracture marker jump that has produced
            # a wrong published number before. Cheap to catch, and a dropout is always better than
            # a confident wrong strain.
            if len(valid) == 2 and self.initial_distance:
                sep = abs(valid[1][1] - valid[0][1])
                lo = self.PAIR_MIN_FRAC * self.initial_distance
                hi = self.PAIR_MAX_FRAC * self.initial_distance
                if not (lo <= sep <= hi):
                    why = ("collapsed — a marker has been lost" if sep < lo else
                           "beyond any strain worth believing")
                    self.error_occurred.emit(
                        f"Pair rejected — {sep:.0f} px vs Px₀ {self.initial_distance:.0f} px "
                        f"(outside {self.PAIR_MIN_FRAC:.2f}–{self.PAIR_MAX_FRAC:.2f} × Px₀; {why})"
                    )
                    return []
                # ...and it has to have got there at a physical SPEED. A mount edge picked up in
                # place of a marker lands well inside the window above but arrives instantly; real
                # strain cannot move the pair more than ~2 px/s at test speed.
                now = time.monotonic()
                prev = self._last_sep                      # (monotonic, separation) or None
                if prev is not None:
                    dt = max(1e-3, now - prev[0])
                    allowed = self.PAIR_STEP_FLOOR_PX + self.PAIR_MAX_STEP_PX_PER_S * dt
                    if abs(sep - prev[1]) > allowed:
                        self.error_occurred.emit(
                            f"Pair rejected — separation moved {abs(sep - prev[1]):.0f} px in "
                            f"{dt*1000:.0f} ms (limit {allowed:.0f} px). A grip or mount edge has "
                            f"most likely been picked up instead of a marker."
                        )
                        return []                          # NOT recorded: a rejected pair must not
                        # become the baseline, or one bad frame would drag the guard onto itself
                self._last_sep = (now, sep)

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
        # Clear the rate baseline BEFORE detecting: a tare is the one moment a large, instantaneous
        # change in separation is legitimate (new specimen, re-mount), and a stale baseline from the
        # previous specimen would reject the very frame the tare needs.
        self._last_sep = None
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
