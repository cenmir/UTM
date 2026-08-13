"""Frame capture for the DIC camera — PNG stills and/or an AVI video, written off the hot path.

    from utm_capture import CaptureManager
    cap = CaptureManager(root="captures")
    cap.start_png(label="V7a", size=(419, 2348))
    cap.submit(frame, t_mono)          # called from the CAMERA thread, ~40 us
    cap.stop_all()

WHY IT IS SHAPED LIKE THIS
--------------------------
The rig grabs at 35 fps and the load cell streams at ~11 Hz through the same process. Encoding a
frame is 9-10 ms of work; doing that inline on the camera thread would halve the DIC sample rate,
and doing it on the GUI thread would freeze the interface. So every frame is handed to a worker
thread and the caller returns immediately.

Three measurements set the design (all at the rig's real 419x2348 ROI):

  * cv2 RELEASES THE GIL while encoding. A writer thread running flat out added +0.09 ms to main-
    thread latency, so this can live in-process; no subprocess or shared memory is needed.
  * PNG compression 0 costs 9.2 ms/frame; level 1 costs 27.1 ms and saves only 31 % of the bytes.
    At 35 fps level 1 needs ~95 % of a core and cannot keep up. Level 0 is the default here, and
    the cost is disk: ~1.9 GB per minute.
  * MJPG at isColor=False costs 9.7 ms/frame and 0.62 GB/min. XVID is 20x smaller but LOSSY in a
    way that eats speckle detail, and these frames exist to be re-analysed. MJPG is intra-frame
    (every frame independently decodable) which is what extensometer software expects.

BACKPRESSURE: the buffer is bounded and drops the OLDEST frame when full, counting the loss. A test
must never stall or run out of memory because a disk got slow — a gap in the frames is recoverable,
a stalled control loop is not. `dropped` is surfaced in the UI so a lossy run is never silent.

Each PNG run also writes index.csv (frame, file, iso time, monotonic seconds). Without it the
stills cannot be aligned to the force data afterwards, which is the entire point of capturing them.

ODD FRAME WIDTHS: JPEG works in macroblocks, so MJPG drops the last column of an odd-width frame —
the rig's 419 px ROI comes back 418. Measured: this is a CROP, not a rescale. Marker separation
round-trips at 0.0000 px error, so strain read off the video is unaffected; only the outermost
column of background is missing. The PNGs are untouched at full width either way.
"""
import csv
import os
import threading
import time
from collections import deque
from datetime import datetime

import cv2

PNG_COMPRESSION = 0          # see module docstring: 0 is the only level that keeps up at 35 fps
VIDEO_FOURCC = "MJPG"
DEFAULT_BUFFER = 90          # ~2.6 s of slack at 35 fps before the oldest frame is dropped


class Style:
    """How a frame is processed before it is written. Applied in the WORKER thread.

    The transforms are all sub-millisecond (binary 0.41 ms, CLAHE 0.71 ms at the rig's ROI), so a
    processed view costs 1-3 % of a core rather than anything the camera or GUI would notice.

    `png_compression` is per-style on purpose. Level 1 costs 3x level 0 on a photographic frame and
    saves only 31 %, so RAW uses 0. On a two-tone binary frame level 1 is the SAME speed as level 0
    and 23x smaller (42 KB vs 965 KB — 0.08 GB/min instead of 1.9), so SPECKLE uses 1. Picking one
    level for both would either throw away that 23x or halve the achievable frame rate.
    """

    # Rough bytes-per-frame, MEASURED at the rig's 419x2348 ROI on a representative speckle frame
    # and rounded UP. They exist so the UI can warn about disk before a run rather than after, so
    # erring high is the safe direction. Real size moves with speckle density and sensor noise.
    def __init__(self, key, label, transform=None, png_compression=PNG_COMPRESSION, note="",
                 png_kb=970, avi_kb=320):
        self.key = key
        self.label = label
        self.transform = transform
        self.png_compression = png_compression
        self.note = note
        self.png_kb = png_kb
        self.avi_kb = avi_kb

    def apply(self, frame):
        return frame if self.transform is None else self.transform(frame)

    def gb_per_min(self, fps=35, png=False):
        return (self.png_kb if png else self.avi_kb) * fps * 60 / 1024 / 1024


def style_raw():
    return Style("raw", "Raw (as the sensor sees it)", None, 0,
                 "everything is kept; the only view you can re-derive the others from",
                 png_kb=970, avi_kb=320)


def style_speckle(threshold=150, thresh_type=None, adaptive=True, ema=0.15):
    """Markers only — a hard two-tone view, the 'X-ray' of the speckle pattern.

    ADAPTIVE (default): the cut level is recomputed from each frame's own histogram by Otsu's
    method, so it follows the lighting instead of being a number chosen on one good day. A fixed
    threshold silently fails the moment the LEDs are dimmed, warm up, or the specimen is changed —
    it goes all-black or all-white and the recording is worthless.

    The Otsu value is then EMA-smoothed (`ema`, ~1 s at 35 fps). Raw per-frame Otsu jitters by a
    few levels on sensor noise, which makes the marker edges shimmer; smoothing tracks a real
    lighting change within about a second while ignoring frame-to-frame noise. The very first
    frame adopts its Otsu value outright so the run does not open mid-fade from the seed.

    `threshold` is the fallback used when adaptive is off — the same number the blob detector runs
    on, so what is recorded is what the DIC is actually tracking.
    """
    import cv2 as _cv2
    tt = _cv2.THRESH_BINARY_INV if thresh_type is None else thresh_type
    # THRESH_OTSU cannot be OR-ed with a type that already carries OTSU (the Black preset does).
    base = tt & ~_cv2.THRESH_OTSU
    state = {"t": None}

    def _fixed(f):
        return _cv2.threshold(f, threshold, 255, base)[1]

    def _adaptive(f):
        # Otsu picks the level; we then re-threshold at the SMOOTHED level, so the mask that gets
        # written is never the raw jittery one.
        chosen, _ = _cv2.threshold(f, 0, 255, base | _cv2.THRESH_OTSU)
        prev = state["t"]
        state["t"] = chosen if prev is None else (1 - ema) * prev + ema * chosen
        return _cv2.threshold(f, state["t"], 255, base)[1]

    return Style("speckle", "Speckle only — adaptive (markers on black)",
                 _adaptive if adaptive else _fixed, 1,
                 "markers only, cut level follows the lighting; ~20x smaller on disk, "
                 "but grey detail is gone for good",
                 png_kb=45, avi_kb=105)


def style_boost(clip=2.5, tile=8):
    """Local contrast equalisation — pulls markers out of a dim or unevenly lit frame."""
    import cv2 as _cv2
    _c = _cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
    return Style("boost", "Boosted contrast (CLAHE)", lambda f: _c.apply(f), 0,
                 "helps when the LEDs are uneven; keeps greys, so still re-analysable",
                 png_kb=970, avi_kb=380)


STYLES = ("raw", "speckle", "boost")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class _Sink:
    """One worker thread draining one bounded buffer. Subclasses do the actual writing."""

    def __init__(self, buffer=DEFAULT_BUFFER):
        self._buf = deque(maxlen=buffer)     # maxlen gives drop-oldest for free
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread = None
        self._running = False
        self.written = 0
        self.dropped = 0
        self.path = None
        self.error = None

    # -- called from the CAMERA thread; must stay in the microseconds ---------------------------
    def submit(self, item):
        if not self._running:
            return
        with self._lock:
            if len(self._buf) == self._buf.maxlen:
                self.dropped += 1            # deque is about to discard the oldest itself
            self._buf.append(item)
        self._wake.set()

    def _start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, name=type(self).__name__, daemon=True)
        self._thread.start()

    def stop(self, flush_timeout=8.0):
        """Stop accepting frames, then let the worker drain what is already buffered.

        The drain matters: without it the last ~2 s of a fracture — the part everybody wants to
        look at — is dropped on the floor when the test ends."""
        if not self._running:
            return
        self._running = False
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=flush_timeout)
        self._close()

    def _run(self):
        while True:
            with self._lock:
                item = self._buf.popleft() if self._buf else None
            if item is None:
                if not self._running:
                    return                    # stopped AND drained
                self._wake.wait(0.05)
                self._wake.clear()
                continue
            try:
                self._write(item)
                self.written += 1
            except Exception as e:            # a bad frame must not kill the run
                self.error = str(e)

    def _write(self, item):
        raise NotImplementedError

    def _close(self):
        pass


class PngSink(_Sink):
    """Every frame as a lossless PNG, plus an index that ties each file to a timestamp."""

    def __init__(self, directory, buffer=DEFAULT_BUFFER, style=None):
        super().__init__(buffer)
        self.path = directory
        self.style = style or style_raw()
        os.makedirs(directory, exist_ok=True)
        self._n = 0
        self._index = open(os.path.join(directory, "index.csv"), "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._index)
        self._csv.writerow(["frame", "file", "pc_time_iso", "t_monotonic_s"])
        self._start()

    def _write(self, item):
        frame, t_mono, iso = item
        name = f"f{self._n:06d}.png"
        cv2.imwrite(os.path.join(self.path, name), self.style.apply(frame),
                    [cv2.IMWRITE_PNG_COMPRESSION, self.style.png_compression])
        self._csv.writerow([self._n, name, iso, f"{t_mono:.4f}"])
        self._n += 1

    def _close(self):
        try:
            self._index.flush()
            self._index.close()
        except Exception:
            pass


class VideoSink(_Sink):
    """The whole run as one AVI. Grayscale in, isColor=False — no needless BGR expansion."""

    def __init__(self, path, size, fps, buffer=DEFAULT_BUFFER, style=None):
        super().__init__(buffer)
        self.path = path
        self.style = style or style_raw()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*VIDEO_FOURCC), fps, size, False)
        if not self._vw.isOpened():
            self.error = f"could not open {VIDEO_FOURCC} writer for {path}"
            self._vw = None
            return
        self._start()

    def _write(self, item):
        if self._vw is not None:
            self._vw.write(self.style.apply(item[0]))

    def _close(self):
        if self._vw is not None:
            self._vw.release()
            self._vw = None


class CaptureManager:
    """Owns the two sinks and the run folder. All methods are safe to call from the GUI thread.

    `submit` is the exception — it is called from the camera thread, and is the only method that
    has to be fast."""

    def __init__(self, root="captures", fps=35):
        self.root = root
        self.fps = fps
        # BOTH are lists. Raw and speckle answer different questions and an operator generally
        # wants both: raw is the archival record, speckle shows the marker motion at a glance.
        # Each style gets its own independent worker and its own file/folder, so two views cost
        # two worker threads rather than two passes over the camera thread.
        self.pngs = []
        self.videos = []
        self._run_dir = None
        self.png_styles = [style_raw()]
        self.video_styles = [style_raw()]

    # ---- state the UI polls -------------------------------------------------------------------
    @property
    def capturing(self):
        return any(p._running for p in self.pngs)

    @property
    def recording(self):
        return any(v._running for v in self.videos)

    @property
    def active(self):
        return self.capturing or self.recording

    def stats(self):
        errs = [s.error for s in self.pngs + self.videos if s and s.error]
        return {
            # Per-sink counts are equal by construction, so report ONE sink's worth. A summed
            # figure for a two-view capture reads as double-counting.
            "png_written": max((p.written for p in self.pngs), default=0),
            "png_dropped": max((p.dropped for p in self.pngs), default=0),
            "png_files": len([p for p in self.pngs if p.written or p._running]),
            # Per-file counts are equal by construction (same frames, same buffer size), so the
            # headline number is one file's worth, not the sum — a "2x frames" figure for a
            # two-view recording would read as a bug.
            "vid_written": max((v.written for v in self.videos), default=0),
            "vid_dropped": max((v.dropped for v in self.videos), default=0),
            "vid_files": len([v for v in self.videos if v.written or v._running]),
            "dir": self._run_dir,
            "error": errs[0] if errs else None,
        }

    def run_dir(self, label=None):
        """One folder per run, shared by the stills and the video so they stay together."""
        if self._run_dir is None:
            name = _stamp() + (f"_{label}" if label else "")
            self._run_dir = os.path.join(self.root, name)
            os.makedirs(self._run_dir, exist_ok=True)
        return self._run_dir

    # ---- start / stop -------------------------------------------------------------------------
    def start_png(self, label=None):
        if self.capturing:
            return self.png.path
        d = self.run_dir(label)
        self.pngs = []
        for st in (self.png_styles or [style_raw()]):
            sub = "frames" if st.key == "raw" else f"frames_{st.key}"
            self.pngs.append(PngSink(os.path.join(d, sub), style=st))
        return [p.path for p in self.pngs]

    def start_video(self, size, label=None):
        """One AVI per selected style, all fed from the same frames. `size` is (width, height)."""
        if self.recording:
            return [v.path for v in self.videos]
        d = self.run_dir(label)
        self.videos = []
        for st in (self.video_styles or [style_raw()]):
            name = "video.avi" if st.key == "raw" else f"video_{st.key}.avi"
            self.videos.append(VideoSink(os.path.join(d, name), size, self.fps, style=st))
        return [v.path for v in self.videos]

    def stop_png(self):
        for p in self.pngs:
            p.stop()
        self._maybe_clear_run()

    def stop_video(self):
        for v in self.videos:
            v.stop()
        self._maybe_clear_run()

    def stop_all(self):
        self.stop_png()
        self.stop_video()

    def _maybe_clear_run(self):
        if not self.active:
            self._run_dir = None            # next start opens a fresh, timestamped folder

    # ---- the hot path -------------------------------------------------------------------------
    def submit(self, frame):
        """Hand one frame to whichever sinks are running. Called from the camera thread.

        No copy: capture_frame's cv2.rotate already returns a fresh array per frame, so the
        buffered reference cannot be overwritten under us. Copying here would add 0.16 ms to every
        grab for nothing.
        """
        if self.pngs:
            stamp = (frame, time.monotonic(), datetime.now().isoformat(timespec="milliseconds"))
            for p in self.pngs:
                if p._running:
                    p.submit(stamp)          # one timestamp, so the views stay frame-aligned
        for v in self.videos:
            if v._running:
                v.submit((frame,))
