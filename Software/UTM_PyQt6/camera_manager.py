import math
import time
from collections import deque
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QThread
import numpy as np
import cv2
# pypylon is the ONLY hardware-specific dependency, and it needs the Basler Pylon runtime.
# A student laptop has neither and does not need them: the post-processing tab measures strain
# from recorded video with OpenCV, and the analysis modules are stdlib-only. Import it softly so
# the app still starts; connect_camera() is the single place that needs it and it says so clearly.
try:
    from pypylon import pylon
    PYLON_AVAILABLE = True
except ImportError:          # no pypylon, or no Pylon runtime behind it
    pylon = None
    PYLON_AVAILABLE = False


class CaptureThread(QThread):
    def __init__(self, camera_manager):
        super().__init__()
        self.cam = camera_manager
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            # Every access here can raise RuntimeError once Qt has deleted the underlying C++
            # CameraManager - which is exactly what happens if the app exits with the camera
            # running. Treat that as "stop", not as an error to report through a signal that
            # is itself already dead.
            try:
                if not (self.cam and self.cam.camera and self.cam.camera.IsGrabbing()):
                    break
                self.cam.capture_frame()
            except RuntimeError:
                break
            except Exception:
                break

    def stop(self):
        self.running = False
        # Bounded: a wait() with no timeout will hang the GUI thread on shutdown if the grab
        # is blocked waiting for a frame that is never coming.
        if not self.wait(2000):
            self.terminate()
            self.wait(500)


class CameraManager(QObject):

    # Carries the centroids ALONGSIDE the frame they came from. The GUI used to re-run detect_blobs
    # on the frame it received, which cost a second detection pass per frame, emitted a second
    # blobs_detected/error_occurred per frame (double-counting every dropout in the health HUD and
    # doubling the console spam), and could pair markers with the wrong frame once the GUI fell
    # behind. Shipping them together makes the pairing exact and the second pass unnecessary.
    frame_ready = pyqtSignal(np.ndarray, list)
    # candidates the filters threw out this frame: (x, y, radius, why). Drawn in red so
    # "0/2" becomes "seen, and here is the gate it failed".
    last_rejects = []

    # Operator-selected marker seeds, in FRAME coordinates (post-capture-rotation), or None.
    # When set, detection stops being a global search: a candidate only counts if it is near a
    # seed, and the seed follows the marker frame to frame. This is what makes the grips
    # unselectable by construction rather than by threshold luck - see cenmir/UTM#1.
    seed_points = None
    SEED_RADIUS = 90          # px; how far a marker may move between frames and still be "it"

    # last frame's accepted centroids and its shape, so the UI can map a click back into frame
    # coordinates and snap it to a real candidate rather than the pixel the cursor was over.
    last_centroids = []
    last_frame_shape = None
    seed_areas = None
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
            # 0.40 is the SETTLED default. It was introduced 2026-08-22 as a temporary loosening
            # for the PETG/TPU campaign and kept by decision on 2026-08-26 after that campaign
            # closed, rather than being put back to 0.50.
            #
            # What justifies keeping it: the sweep below found 0.40 mid-plateau, not on a cliff,
            # and NOTHING extra is admitted anywhere between 0.50 and 0.25 (3+ blobs stays at
            # 0.0 %). What 0.50 used to buy — keeping grips and fixture edges out — is now carried
            # by the pair-plausibility guards and a frozen Px₀ instead of by roundness alone.
            # If a run ever admits a grip edge as a marker, this is the first line to suspect.
            #
            # FINAL, not provisional. Confirmed again 2026-08-26: 0.40 stands even if marker
            # preparation improves and clean 0.76 dots come back. Better dots would clear 0.40
            # with more room, not create a reason to tighten it — so do not reopen this on the
            # strength of a good-looking specimen. Only evidence that 0.40 ADMITS something it
            # should not would justify revisiting, and the sweep says it does not.
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
            # The right long-term fix is still the SPECIMEN, and keeping 0.40 does not retire it:
            # mask around each dot so overspray cannot land touching it, and use matte paint. A
            # clean dot scores 0.76 and needs none of this. S37 (TPU, 2026-08-26) is the standing
            # evidence — its sprayed dots scored 0.18 and needed a one-off 0.16 profile to track
            # at all, which no gate value fixes and better preparation would have.
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
    MIN_CIRCULARITY = 0.40      # settled default, matches SPECIMEN_PRESETS["Black"] — note there

    def __init__(self):
        super().__init__()
        self.specimen_mode = "Black"
        self.material = "PLA"
        # Settings a PROFILE owns, which must survive set_specimen_mode. on_start_camera calls
        # that on every start, so without this the ROI and the roundness gate a profile had
        # just applied were silently reset by the very Stop/Start the operator was told to do
        # to make the ROI take effect. None = follow the preset.
        self._roi_override = None
        self._circ_override = None
        self._thr_override = None
        self._exp_override = None
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
        # Re-assert whatever the loaded profile asked for. The preset is the FALLBACK here, not
        # the authority: a profile is chosen deliberately and a mode change must not undo it.
        if self._roi_override:
            self.ROI = list(self._roi_override)
        if self._circ_override:
            self.MIN_CIRCULARITY = float(self._circ_override)
        if self._thr_override is not None:
            self.THRESHOLD = self._thr_override
        if self._exp_override is not None:
            self.EXPOSURE_TIME = self._exp_override
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

    # Radius of a clean marker, measured: a good dot runs ~11 140 px2, so ~60 px. Used only to
    # decide how close a centroid may get to the frame edge before the blob is clipped.
    MARKER_R_PX = 60.0

    def frame_headroom(self, target_strain):
        """Can the marker pair stay in frame all the way to `target_strain`?

        S35 (TPU, 2026-08-24) is why this exists. The pair was frozen 309 px from the edge it
        would travel toward, and the run lost tracking at 12.6 % strain with 305 px of frame
        sitting unused at the OTHER end. The frame was long enough; it was aimed wrong, and
        nothing said so until the specimen had been pulled.

        Returns None if there is nothing to judge yet, else a dict with the two edge gaps, the
        separation growth the target needs, and a verdict:
          "ok"    - both gaps hold the growth, so it is safe whichever end turns out to move
          "check" - the pair FITS but only one gap holds it, so the aim only works if the
                    marker at the tight end is the stationary one
          "fail"  - the pair cannot fit at this strain at any aim; the view must be zoomed out
        """
        c = getattr(self, "initial_centroids", None)
        f = getattr(self, "latest_frame", None)
        if not c or len(c) != 2 or f is None or not self.initial_distance:
            return None
        span = float(f.shape[0])                 # rotated: rows run along the specimen axis
        lo, hi = sorted(float(p[1]) for p in c)
        gap_lo = lo - self.MARKER_R_PX
        gap_hi = span - hi - self.MARKER_R_PX
        need = self.initial_distance * float(target_strain)
        # max(), NOT min(). Requiring BOTH ends to absorb the whole growth is unsatisfiable on
        # this rig and would nag forever: the pair nearly fills the frame, so at the BEST
        # possible aim one side has ~540 px and the other ~110 px. It does not need both -
        # only ONE marker travels (the crosshead end; the other creeps ~25 % as much), so the
        # test is whether the room is on the side that will use it. The message names which end
        # that has to be, because the frame cannot tell which grip is moving.
        wide, tight = max(gap_lo, gap_hi), min(gap_lo, gap_hi)
        # THREE states, because "one side can take it" is only conditionally safe: the room has
        # to be on the side the crosshead marker moves toward, and the frame cannot tell which
        # grip is moving. "safe" needs no such judgement and is what to aim for on a specimen
        # you cannot afford to waste.
        verdict = ("safe" if tight >= need else "ok" if wide >= need else "fail")
        return {"span": span, "gap_lo": gap_lo, "gap_hi": gap_hi, "need": need,
                "wide": wide, "tight": tight, "short_by": max(0.0, need - wide),
                "moving_end": "low" if gap_lo >= gap_hi else "high",
                "verdict": verdict, "px0": self.initial_distance,
                # Centred, both gaps are (span - px0)/2 - R and the growth is px0*eps, so the
                # largest Px0 that is safe either way solves (span-2R)/2 - px0/2 = px0*eps.
                "px0_for_safe": (span - 2 * self.MARKER_R_PX) / (1 + 2 * float(target_strain)),
                "centre_B": (span - self.initial_distance) / 2.0}

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
        roi = [int(v) for v in roi] if roi else None
        self._roi_override = roi
        if roi is None:                       # back to whatever the specimen preset asks for
            roi = list(self.SPECIMEN_PRESETS.get(self.specimen_mode, {}).get("roi", self.ROI))
        changed = roi != list(self.ROI)
        self.ROI = roi
        print(f"[Camera] ROI set to {roi} (OffsetX, OffsetY, Width, Height)")
        return changed and self.camera is not None and self.camera.IsOpen()

    def set_optics(self, threshold=None, exposure=None):
        """Pin the threshold and exposure, surviving set_specimen_mode.

        These decide whether the GRIPS are as bright as the markers, and the roundness gate is
        what stops a bright grip being read as one. Loosening that gate for a smudged dot is
        only safe alongside optics that keep the grips dark, so the two belong together in a
        profile rather than one being pinned and the other left to drift.

        S36 is the case: at the validated 50 ms / 165 the pair tracked 100 %; at 98 ms / 100
        with the same 0.25 gate a grip edge was frozen as Px0, 2118 px against a true ~1700.
        """
        if threshold is not None:
            self._thr_override = int(threshold)
            self.THRESHOLD = int(threshold)
        if exposure is not None:
            self._exp_override = int(exposure)
            self.EXPOSURE_TIME = int(exposure)
            if self.camera and self.camera.IsOpen():
                try:
                    self.camera.ExposureTime.Value = float(exposure)
                except Exception:
                    pass
        print(f"[Camera] Optics pinned: threshold {self.THRESHOLD}, "
              f"exposure {self.EXPOSURE_TIME / 1000:.0f} ms")

    def set_min_circularity(self, value):
        """Marker roundness gate. None restores the specimen preset's.

        Sticky for the same reason as the ROI: set_specimen_mode reloads it from the preset,
        and on_start_camera calls set_specimen_mode every time.
        """
        self._circ_override = float(value) if value else None
        self.MIN_CIRCULARITY = (self._circ_override if self._circ_override else
                                self.SPECIMEN_PRESETS.get(self.specimen_mode, {})
                                .get("min_circularity", self.MIN_CIRCULARITY))
        print(f"[Camera] Marker roundness gate: {self.MIN_CIRCULARITY:.2f}")

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
        if not PYLON_AVAILABLE:
            msg = ("pypylon is not installed - this build has no camera support. "
                   "Recorded video still works in the DIC Post-Processing tab.")
            print(f"[Camera] {msg}")
            self._safe_emit("error_occurred", msg)
            return False
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

            self._safe_emit("connection_changed", True)
            print("Camera connected successfully")
            return True

        except Exception as e:
            self._safe_emit("error_occurred", str(e))
            print(f"Camera connection failed: {e}")
            return False

    def disconnect_camera(self):
        try:
            if self.capture_thread:
                self.capture_thread.stop()
            if self.camera and self.camera.IsOpen():
                self.camera.Close()
            self._safe_emit("connection_changed", False)
            print("Camera disconnected")
        except Exception as e:
            self._safe_emit("error_occurred", str(e))

    def start_acquisition(self):
        try:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.capture_thread = CaptureThread(self)
            self.capture_thread.start()
            print("Acquisition started")
        except Exception as e:
            self._safe_emit("error_occurred", str(e))

    def stop_acquisition(self):
        try:
            if self.capture_thread:
                self.capture_thread.stop()
                self.capture_thread = None
            if self.camera and self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            print("Acquisition stopped")
        except Exception as e:
            self._safe_emit("error_occurred", str(e))

    # Warn when the loop falls below this. The camera runs at ~20 fps and the load cell at ~11 Hz,
    # so anything under ~12 Hz means load samples start going out without a strain reading.
    SLOW_LOOP_HZ = 12.0
    SLOW_WARN_EVERY_S = 10.0

    def capture_frame(self) -> np.ndarray:
        t = time.perf_counter
        try:
            _t0 = t()
            grab_result = self.camera.RetrieveResult(
                self.GRAB_TIMEOUT_MS, pylon.TimeoutHandling_ThrowException
            )
            _t1 = t()                                   # wait: idle if the loop is ahead of the camera
            if grab_result.GrabSucceeded():
                img = grab_result.Array
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                grab_result.Release()
                self.latest_frame = img  # add this
                self._grab_fail_streak = 0       # a good frame clears the give-up counter
                self._rate_grab.append(time.monotonic())
                _t2 = t()
                # Run blob detection on every frame
                sink = self.frame_sink
                if sink is not None:
                    try:
                        sink(img)          # ~47 us: a bounded-buffer append, never any encoding
                    except Exception as e:
                        self.frame_sink = None      # a broken sink must not kill the grab loop
                        self._safe_emit("error_occurred", f"Frame capture stopped: {e}")
                _t3 = t()
                centroids = self.detect_blobs(img)
                _t4 = t()
                if len(centroids) == 2:
                    self.calculate_dic_strain(centroids)
                _t5 = t()
                self._trace_blobs(centroids)
                self._safe_emit("frame_ready", img, centroids)
                _t6 = t()
                self._record_stages(_t0, _t1, _t2, _t3, _t4, _t5, _t6)
                return img
            grab_result.Release()
        except Exception as e:
            self._on_grab_failure(e)
        return None

    def _on_grab_failure(self, exc):
        """One place to handle a failed grab: coalesce the message, and stop if it persists.

        A timeout message from pylon is ~500 characters, and a sick link produces one per
        timeout indefinitely. Appending that to a QTextEdit on the GUI thread, forever, is what
        turned a camera problem into an unresponsive application.
        """
        now = time.monotonic()
        msg = str(exc).split("\n")[0][:160]

        self._grab_fail_streak += 1
        if self._grab_fail_streak >= self.MAX_CONSECUTIVE_GRAB_FAILURES:
            self._safe_emit(
                "error_occurred",
                "Camera stopped after %d consecutive failed grabs. The link is not delivering "
                "frames - check the USB cable and, if the camera is on a hub, try it directly "
                "on the PC. Last error: %s" % (self._grab_fail_streak, msg))
            try:
                self.stop_acquisition()
            except Exception:
                pass
            self._grab_fail_streak = 0
            return

        if msg == self._err_last_msg and (now - self._err_last_t) < 5.0:
            self._err_repeat += 1                 # same fault, still going: stay quiet
            return
        if self._err_repeat:
            msg = "%s   (repeated %d times)" % (msg, self._err_repeat + 1)
        self._err_last_msg, self._err_last_t, self._err_repeat = \
            str(exc).split("\n")[0][:160], now, 0
        self._safe_emit("error_occurred", msg)

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
        self._safe_emit("notice", f"DIC loop is running at {hz:.1f} Hz — below the {self.SLOW_LOOP_HZ:.0f} Hz "
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

    # OFF by default (2026-08-28). The health badge already shows "0/2 - track % - jitter"
    # continuously and without scrolling anything away, so this trace only ever duplicated it.
    TRACE_BLOBS = False

    # How often "Expected 2 blobs, found N" may reach the console. It describes a persistent
    # condition, so once every few seconds is as informative as once per frame and leaves the
    # console readable.
    BLOB_ERR_INTERVAL_S = 5.0

    # When True, the app measures nothing until the operator has selected markers, and stays
    # quiet until then. The global search still runs so that a click has something to snap to,
    # but it no longer reports its own failure to find markers nobody asked it to find.
    REQUIRE_SELECTION = True

    # A frame that has not arrived in this long is not coming. It was 5000 ms, which is five
    # seconds of a blocked capture thread per failed grab - long enough that the operator sees
    # the app stall, and long enough to hide a dying link behind what looks like a hang.
    # At 20 fps a healthy frame arrives in 50 ms; 1000 ms is 20x that.
    GRAB_TIMEOUT_MS = 1000

    # Consecutive failures before acquisition gives up. Spinning on timeouts forever is worse
    # than stopping and saying so: the feed is frozen either way, but only one of them tells
    # the operator what happened.
    MAX_CONSECUTIVE_GRAB_FAILURES = 8
    _grab_fail_streak = 0
    _err_last_msg = ""
    _err_last_t = 0.0
    _err_repeat = 0

    # Windowed-detection tuning. The area floor is far lower than the global MIN_AREA: inside a
    # box the operator pointed at, a small dot is a dot, not noise.
    SEED_MIN_AREA = 150
    SEED_CLOSE_K = 9          # morphological close, to bridge print-layer grooves. 0 disables.
    WEIGHT_DILATE = 4         # px of edge ramp to include in the intensity-weighted centre
    SEED_FRAG_AREA = 40       # smallest fragment counted as part of the marker
    # A marker cannot grow or teleport. Both guards exist because it did: merging every contour
    # near the seed also merged the DARK BACKGROUND (huge under THRESH_BINARY_INV), the centre
    # was dragged toward it, the seed followed, and it ratcheted off the specimen over ~5 frames.
    SEED_AREA_RATIO = 2.5     # reject a match this many times bigger than the marker we selected
    SEED_MAX_STEP_PX = 25     # and one that moved further than this in a single frame
    _blob_err_t = 0.0

    # Reject details cost a string format per rejected contour per frame - 30+ on a noisy
    # frame, 20 times a second - and they are ONLY read by the Select-blobs overlay. Off
    # unless the UI turns them on.
    collect_rejects = False

    def _trace_blobs(self, centroids):
        """Per-frame marker-count trace. Silent unless TRACE_BLOBS is turned on.

        The old throttle only applied when the count was UNCHANGED:

            if n == last_n and (now - last_t) < INTERVAL: return

        so a count flickering 0,1,0,1 - a marker sitting right on a filter gate - was a
        "change" every single frame and printed at the full 20 fps. The coalescing failed
        exactly when the rig was noisiest, which is when the console most needs to stay
        readable. The time floor is now unconditional.
        """
        if not self.TRACE_BLOBS:
            return
        now = time.monotonic()
        if (now - self._trace_last_t) < self.TRACE_MIN_INTERVAL_S:
            return                      # unconditional floor: a changing count cannot spam
        n = len(centroids)
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
            self._safe_emit("notice", f"{len(valid)} blobs qualified — kept the pair {why}; ignored {where}. "
                "A blob that keeps appearing near the frame edge is usually a grip or fixture: "
                "mask it (SPECIMEN_PRESETS mask_x) or move it out of the ROI.")
        return sorted(chosen, key=lambda b: b[1])

    def _safe_emit(self, name, *args):
        """Emit the named signal unless the C++ object is gone.

        Takes the signal NAME, not the bound signal. Once Qt has deleted the underlying C++
        object, merely LOOKING UP `self.error_occurred` raises RuntimeError - so a helper that
        takes the signal as an argument is evaluated at the call site, outside its own guard,
        and never catches anything. The getattr has to happen inside the try.

        On shutdown the capture thread can still be mid-frame when Qt deletes this object. The
        emit raises, and so does the emit in the except block reporting it, and the one in ITS
        handler: one race, three stacked tracebacks. Swallow it at the source.
        """
        try:
            getattr(self, name).emit(*args)
            return True
        except RuntimeError:
            return False

    def detect_in_window(self, frame, cx, cy, radius=None):
        """Best marker centroid within `radius` of (cx, cy), or None.

        Thresholds and contours ONLY that window. A 180 px box is ~32k pixels against 983k for
        the full frame, so this is ~30x less work per marker than the global search it replaces
        - and it cannot pick up a grip, because the grip is not in the box.

        The area gate is scaled to the window and circularity is NOT applied: the operator has
        already said "this is my marker", and a bled or hatched dot failing a roundness test is
        exactly the case this whole path exists to serve.
        """
        import cv2 as _cv
        r = int(radius or self.SEED_RADIUS)
        h, w = frame.shape[:2]
        x0, y0 = max(0, int(cx) - r), max(0, int(cy) - r)
        x1, y1 = min(w, int(cx) + r), min(h, int(cy) + r)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        patch = frame[y0:y1, x0:x1]

        _, binary = _cv.threshold(patch, self.THRESHOLD, 255, self.THRESHOLD_TYPE)
        # Close the grooves a wicked dot leaves along the print layer lines, so it reads as one
        # blob instead of a comb of fragments. Only inside the window, so it costs almost nothing.
        if self.SEED_CLOSE_K > 1:
            k = _cv.getStructuringElement(_cv.MORPH_ELLIPSE,
                                          (self.SEED_CLOSE_K, self.SEED_CLOSE_K))
            binary = _cv.morphologyEx(binary, _cv.MORPH_CLOSE, k)

        contours, _ = _cv.findContours(binary, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_SIMPLE)

        # MERGE every fragment near the seed instead of choosing one. A bled dot can still break
        # into several contours after the close, and picking "the nearest" made the centre hop
        # between fragments frame to frame - metres of apparent strain from a marker that never
        # moved. The fragments are all the same marker, so weigh them together.
        ph, pw = patch.shape[:2]
        near = []
        for cnt in contours:
            if _cv.contourArea(cnt) < self.SEED_FRAG_AREA:
                continue
            # DROP anything touching the window border. Under THRESH_BINARY_INV the dark
            # surround beyond the specimen edge is a blob like any other, and a window centred
            # near the edge swallows a strip of it - which is how the merged centre ended up
            # 40 px off the marker and how the seed then walked off the specimen entirely.
            # The marker is central by construction: the window is centred on it.
            bx_, by_, bw_, bh_ = _cv.boundingRect(cnt)
            if bx_ <= 0 or by_ <= 0 or bx_ + bw_ >= pw or by_ + bh_ >= ph:
                continue
            M = _cv.moments(cnt)
            if M["m00"] <= 0:
                continue
            bx = x0 + M["m10"] / M["m00"]
            by = y0 + M["m01"] / M["m00"]
            if ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5 <= r:
                near.append(cnt)
        if near:
            merged = np.zeros(patch.shape, np.uint8)
            _cv.drawContours(merged, near, -1, 255, -1)
            area = float(_cv.countNonZero(merged))
            if area >= self.SEED_MIN_AREA:
                wx, wy = self._weighted_centre_mask(patch, merged, x0, y0)
                if wx is not None:
                    return (wx, wy, area)

        best, best_score = None, None
        for cnt in contours:
            area = _cv.contourArea(cnt)
            if area < self.SEED_MIN_AREA:
                continue
            bx_, by_, bw_, bh_ = _cv.boundingRect(cnt)
            if bx_ <= 0 or by_ <= 0 or bx_ + bw_ >= pw or by_ + bh_ >= ph:
                continue                      # window border: background, not a marker
            M = _cv.moments(cnt)
            if M["m00"] <= 0:
                continue

            # INTENSITY-WEIGHTED centre, not the binary one. A binary mask only changes when a
            # pixel crosses the threshold, so as the marker slides sub-pixel the centroid sticks
            # and then jumps: measured, 25 sub-pixel steps produced only 13 distinct centroids,
            # ~0.1 px rms = ~70 ustrain at Px0 1416 - a visible staircase on the stress-strain
            # curve. The grey levels at the marker's edge vary CONTINUOUSLY with sub-pixel
            # position, and weighting by them recovers that. utm_postproc reached the same
            # conclusion offline: intensity-weighted 15-17 ustrain vs binary ~25.
            bx, by = self._weighted_centre(patch, cnt, x0, y0)
            if bx is None:
                bx = x0 + M["m10"] / M["m00"]
                by = y0 + M["m01"] / M["m00"]
            d = ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5
            if d > r:
                continue
            # nearest to where we expected it, tie-broken by size
            score = (d, -area)
            if best_score is None or score < best_score:
                best, best_score = (bx, by, area), score
        return best

    def _weighted_centre_mask(self, patch, mask, x0, y0):
        """Intensity-weighted centre over an arbitrary mask (one marker, however fragmented)."""
        import cv2 as _cv
        try:
            if self.WEIGHT_DILATE > 0:
                k = _cv.getStructuringElement(
                    _cv.MORPH_ELLIPSE, (self.WEIGHT_DILATE * 2 + 1,) * 2)
                mask = _cv.dilate(mask, k)
            sel = mask > 0
            if not sel.any():
                return None, None
            vals = patch[sel].astype(np.float32)
            if self.THRESHOLD_TYPE == _cv.THRESH_BINARY_INV:
                w = np.clip(self.THRESHOLD - vals, 0, None)
            else:
                w = np.clip(vals - self.THRESHOLD, 0, None)
            tot = float(w.sum())
            if tot <= 0:
                return None, None
            ys, xs = np.nonzero(sel)
            return (x0 + float((xs * w).sum() / tot),
                    y0 + float((ys * w).sum() / tot))
        except Exception:
            return None, None

    def _weighted_centre(self, patch, cnt, x0, y0):
        """Centre of the marker weighted by how far each pixel is past the threshold.

        Uses the anti-aliased edge the binary mask throws away, which is exactly the
        information that carries sub-pixel position.
        """
        import cv2 as _cv
        try:
            mask = np.zeros(patch.shape, np.uint8)
            _cv.drawContours(mask, [cnt], -1, 255, -1)
            # DILATE before weighting. The binary contour stops at the last pixel that crossed
            # the threshold, which throws away the anti-aliased ramp just outside it - and that
            # ramp is precisely where sub-pixel position lives. Weighting only inside the
            # contour recovered almost nothing (0.100 -> 0.088 px). Including the ramp is the
            # whole point. Pixels beyond it weigh 0 anyway, so the dilation cannot pull the
            # centre toward the background.
            if self.WEIGHT_DILATE > 0:
                k = _cv.getStructuringElement(
                    _cv.MORPH_ELLIPSE, (self.WEIGHT_DILATE * 2 + 1,) * 2)
                mask = _cv.dilate(mask, k)
            sel = mask > 0
            if not sel.any():
                return None, None
            vals = patch[sel].astype(np.float32)
            # weight = distance past the cut, in the direction that makes the MARKER heavy
            if self.THRESHOLD_TYPE == _cv.THRESH_BINARY_INV:
                w = np.clip(self.THRESHOLD - vals, 0, None)      # dark dots
            else:
                w = np.clip(vals - self.THRESHOLD, 0, None)      # light dots
            tot = float(w.sum())
            if tot <= 0:
                return None, None
            ys, xs = np.nonzero(sel)
            return (x0 + float((xs * w).sum() / tot),
                    y0 + float((ys * w).sum() / tot))
        except Exception:
            return None, None

    def track_seeds(self, frame):
        """Follow the selected markers. Local windows only - no global search."""
        out, moved, areas = [], [], []
        refs = self.seed_areas or [None] * len(self.seed_points or [])
        for i, (sx, sy) in enumerate(self.seed_points or []):
            ref = refs[i] if i < len(refs) else None
            hit = self.detect_in_window(frame, sx, sy)
            if hit is None:
                moved.append((sx, sy)); areas.append(ref)      # hold
                continue
            bx, by, a_ = hit

            # Too big to be the marker: almost certainly the dark surround merged in.
            if ref and a_ > ref * self.SEED_AREA_RATIO:
                moved.append((sx, sy)); areas.append(ref)
                continue
            # Moved further than a marker physically can between frames.
            if ((bx - sx) ** 2 + (by - sy) ** 2) ** 0.5 > self.SEED_MAX_STEP_PX:
                moved.append((sx, sy)); areas.append(ref)
                continue

            out.append((bx, by))
            moved.append((bx, by))
            areas.append(ref if ref else a_)                   # learn it on first good frame
        self.seed_areas = areas
        self.seed_points = moved
        out.sort(key=lambda p: p[1])
        return out

    def _apply_seeds(self, valid, rejects):
        """Keep only what is near an operator-selected seed, and move the seeds to follow.

        Two things happen here that a global search cannot do:

        * Anything far from both seeds is discarded no matter how well it scores. The grips
          cannot win, because they were never selected.
        * A candidate the GLOBAL gates rejected is admitted if it sits on a seed. The operator
          pointed at it; a circularity score is not entitled to overrule that. This is what
          makes a whiteboard dot that has bled along the layer lines usable.

        Seeds then step to wherever the marker was found, so they follow it through the pull.
        """
        pool = [(x, y, None) for (x, y) in valid]
        pool += [(x, y, why) for (x, y, _r, why) in rejects]

        chosen, used, new_seeds, still_rejected = [], set(), [], []
        for sx, sy in self.seed_points:
            best, best_d = None, None
            for i, (x, y, _why) in enumerate(pool):
                if i in used:
                    continue
                d = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
                if d <= self.SEED_RADIUS and (best_d is None or d < best_d):
                    best, best_d = i, d
            if best is None:
                new_seeds.append((sx, sy))          # hold position; the marker may come back
                continue
            used.add(best)
            bx, by, _ = pool[best]
            chosen.append((bx, by))
            new_seeds.append((bx, by))

        for i, (x, y, why) in enumerate(pool):
            if i not in used:
                # Only put words on it when the overlay will show them. `why or "..."` looked
                # harmless but re-introduced a string per rejected contour per frame - exactly
                # the cost the collect_rejects flag exists to avoid.
                label = (why or "not a selected marker") if self.collect_rejects else ""
                still_rejected.append((x, y, 12, label))

        self.seed_points = new_seeds
        chosen.sort(key=lambda b: b[1])             # keep the top-first axial order
        return chosen, still_rejected

    def _record_pair(self, valid):
        """Hand a tracked pair to the same strain path the global detector used."""
        try:
            self._safe_emit("blobs_detected", valid)
        except Exception:
            pass

    def set_seeds(self, points, areas=None):
        """Adopt operator-selected marker positions, or clear them with None/[].

        `areas` is the size of each marker when it was selected. It becomes the reference the
        area guard compares against, so the guard scales with whatever the operator picked
        instead of assuming a marker size.
        """
        self.seed_points = [(float(x), float(y)) for (x, y) in points] if points else None
        self.seed_areas = list(areas) if (points and areas) else None
        return self.seed_points

    def detect_blobs(self, frame) -> list:
        # Local-only path. With markers selected, look at their windows and nothing else. With
        # none selected, do NOTHING - no threshold, no contours, no 983k-pixel search for
        # markers nobody has asked to measure.
        if self.REQUIRE_SELECTION:
            self.last_frame_shape = frame.shape
            if not self.seed_points:
                self.last_centroids, self.last_rejects = [], []
                return []
            valid = self.track_seeds(frame)
            self.last_centroids, self.last_rejects = list(valid), []
            self._trace_blobs(valid)
            if len(valid) == 2:
                self._record_pair(valid)
            return valid

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

            valid, near, rejects = [], [], []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                perimeter = cv2.arcLength(cnt, True)
                circ = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
                M = cv2.moments(cnt)
                cy = (M["m01"] / M["m00"]) if M["m00"] > 0 else -1.0
                if self.MIN_AREA < area < self.MAX_AREA and circ > self.MIN_CIRCULARITY:
                    if M["m00"] > 0:
                        valid.append((M["m10"] / M["m00"], cy))
                elif (self.collect_rejects or self.seed_points) and area > 100:
                    # Needed in TWO cases, and conflating them was a bug:
                    #   * collect_rejects - the operator is looking at the Select-blobs overlay
                    #   * seed_points     - a SELECTED marker may well be one the global gates
                    #                       reject (that is the whole point), so seed matching
                    #                       has to search this list too. Gating it on the overlay
                    #                       alone made tracking work while the rings were shown
                    #                       and silently stop the moment they were hidden.
                    # A NEAR MISS: big enough to be a marker, rejected by a gate. Kept so the
                    # badge can say WHY instead of only "1/2". Losing a marker used to be
                    # silent, which is a bad way to spend a specimen.
                    # The formatted reason is only ever read by the overlay, and it costs a
                    # string format per rejected contour per frame. Position is cheap; words
                    # are not. Build words only when they will be shown.
                    if self.collect_rejects:
                        why = ("area %d < %d" % (area, self.MIN_AREA) if area <= self.MIN_AREA else
                               "area %d > %d" % (area, self.MAX_AREA) if area >= self.MAX_AREA else
                               "circularity %.2f < %.2f" % (circ, self.MIN_CIRCULARITY))
                    else:
                        why = ""
                    near.append((area, cy, why))
                    # centroid + an equivalent-circle radius, so the UI can ring it in red
                    if M["m00"] > 0:
                        rej_r = max(6, int((area / np.pi) ** 0.5))
                        rejects.append((M["m10"] / M["m00"], cy, rej_r, why))

            # Sort by Y so blob 1 is always top, blob 2 always bottom
            valid.sort(key=lambda b: b[1])

            # Say WHY a marker is missing. Throttled hard: this runs at ~20 Hz.
            if len(valid) < 2 and near:
                now = time.monotonic()
                if now - getattr(self, "_near_miss_t", 0.0) > 3.0:
                    self._near_miss_t = now
                    top = sorted(near, reverse=True)[:2]
                    self._safe_emit("notice", "Only %d marker%s passed the filters. Nearest miss%s: %s  "
                        "(threshold %d — try Settings ▸ DIC camera setup ▸ Auto-calibrate DIC)"
                        % (len(valid), "" if len(valid) == 1 else "s",
                           "" if len(top) == 1 else "es",
                           "; ".join("at y=%.0f %s" % (c, w) for _, c, w in top),
                           self.THRESHOLD))

            # Published for the live overlay. Set BEFORE the >2 pruning below so a marker
            # discarded by pair-plausibility can also be drawn, and reset every frame so a
            # stale reject can never outlive the frame it came from.
            self.last_rejects = rejects

            if self.seed_points:
                valid, rejects = self._apply_seeds(valid, rejects)
                self.last_rejects = rejects

            self.last_centroids = list(valid)
            self.last_frame_shape = frame.shape

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
                    self._safe_emit("error_occurred", f"Pair rejected — {sep:.0f} px vs Px₀ {self.initial_distance:.0f} px "
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
                        self._safe_emit("error_occurred", f"Pair rejected — separation moved {abs(sep - prev[1]):.0f} px in "
                            f"{dt*1000:.0f} ms (limit {allowed:.0f} px). A grip or mount edge has "
                            f"most likely been picked up instead of a marker."
                        )
                        return []                          # NOT recorded: a rejected pair must not
                        # become the baseline, or one bad frame would drag the guard onto itself
                self._last_sep = (now, sep)

            if len(valid) == 2:
                self._safe_emit("blobs_detected", valid)
            else:
                # Throttled: this is a STATE, not an event. It was firing every frame at
                # 20 fps for as long as a marker was missing, which is exactly the situation
                # in which the operator needs to read the console. The detailed near-miss
                # notice above already reports the same condition every 3 s, with the reason.
                # Before any marker is selected the app is not tracking anything, so a
                # global search coming up short is not a fault to report - it is the normal
                # state of an idle camera. Reporting it filled the console the moment the
                # camera started, before the operator had done anything at all.
                if not self.seed_points and self.REQUIRE_SELECTION:
                    return valid
                _now = time.monotonic()
                if _now - getattr(self, "_blob_err_t", 0.0) < self.BLOB_ERR_INTERVAL_S:
                    return valid
                self._blob_err_t = _now
                self._safe_emit("error_occurred", f"Expected 2 blobs, found {len(valid)}"
                )

            return valid

        except Exception as e:
            self._safe_emit("error_occurred", str(e))
            return []

    def link_is_healthy(self):
        """False while grabs are failing. Callers on the GUI THREAD must check this before
        touching camera nodes: a node read over a sick USB link can block for seconds, and the
        2 Hz health badge does exactly that read."""
        return self._grab_fail_streak == 0

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
            self._safe_emit("error_occurred", f"Exposure change failed: {e}")
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
            self._safe_emit("error_occurred", "Tare failed - no frame captured")
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
            self._safe_emit("error_occurred", "Tare failed - need exactly 2 blobs")

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
        # ONE conversion, shared with the offline video post-processor (utm_postproc). Strain is a
        # pixel ratio with no gauge, calibration or unit in it, so a live pull and the same pull
        # replayed from its recording must not be able to disagree — see utm_dic.dic_strain.
        from utm_dic import dic_strain as _dic_strain
        cauchy, true_strain = _dic_strain(current_distance, self.initial_distance)
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
        self._safe_emit("dic_strain_updated", cauchy, true_strain)
        return cauchy, true_strain
