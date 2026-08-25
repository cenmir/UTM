"""Frame capture for the DIC camera — lossless stills and/or an AVI video, written off the hot path.

⚠ THE STILLS ARE THE MEASUREMENT; THE VIDEO IS FOR LOOKING AT. The stills (TIFF by default, PNG on
request) are bit-exact. The AVI is MJPG, which is LOSSY — measured against the matching still on a
real S26 frame, only 54 % of pixels come back identical, worst case 12 grey levels out, RMS 1.34 —
and MJPG also drops the last column of an odd-width frame, so a 419 px ROI returns 418. Re-analyse
the STILLS. If a lossless video is ever needed, FFV1 was measured at 100.0 % identical, 228 kB per
frame and 9.7 ms on this machine (pad the width to even first, or the column goes missing anyway).

    from utm_capture import CaptureManager
    cap = CaptureManager(root=os.path.join("output", "captures"))
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

# ---- still-image formats -----------------------------------------------------------------------
# ALL THREE ARE LOSSLESS. PNG always was — `PNG_COMPRESSION = 0` merely turns off deflate, it does
# not make PNG "raw", and no level of PNG has ever discarded a pixel. So this choice is about BYTES
# and CPU, never about image quality.
#
# Measured on a real 419x2348 mono frame from S26 (raw frame = 983 812 B):
#
#     format              size      of raw   encode
#     PNG level 0        987 813 B   100 %   7.3 ms   <- what the rig wrote until 2026-08-21
#     TIFF uncompressed  984 702 B   100 %   1.5 ms   <- default now: same disk, 5x less CPU
#     TIFF LZW           362 002 B    37 %   7.6 ms   <- same pixels, a third of the disk
#     PNG level 9        297 871 B    30 %  84.9 ms   <- cannot keep up; here for contrast only
#
# TIFF-uncompressed is the default because it is what an uncompressed still actually is, it costs
# a fifth of the CPU we were spending, and every analysis tool in this workflow reads it. TIFF-LZW
# is offered for long runs where 2.5 GB per 125 s is the problem.
#
# `params` is passed straight to cv2.imwrite. For PNG the level comes from the STYLE instead (a
# binary speckle frame compresses 23x where a photographic one does not), so it is filled in at
# write time.
STILL_FORMATS = {
    "tiff":     {"ext": ".tif", "params": [cv2.IMWRITE_TIFF_COMPRESSION, 1],   # 1 = COMPRESSION_NONE
                 "label": "TIFF, uncompressed", "kb": 962, "ms": 1.5,
                 "why": "No compression at all, so the file IS the sensor bytes. Cheapest to "
                        "write by a wide margin — a fifth of PNG’s cost — for the same size on "
                        "disk. The default, and the right choice unless disk space is the "
                        "problem."},
    "tiff_lzw": {"ext": ".tif", "params": [cv2.IMWRITE_TIFF_COMPRESSION, 5],   # 5 = LZW, lossless
                 "label": "TIFF, LZW (lossless, ~1/3 the size)", "kb": 355, "ms": 7.6,
                 "why": "Identical pixels in about a third of the space. Costs the same as PNG "
                        "to write. Pick this for long runs, or when a session has to fit on a "
                        "stick."},
    "png":      {"ext": ".png", "params": None,                                # per-style level
                 "label": "PNG (lossless)", "kb": 970, "ms": 7.3,
                 "why": "What the rig wrote until 2026-08-21. Also lossless — PNG never "
                        "discarded a pixel — but five times the CPU of TIFF for the same file "
                        "size. Kept for tools that will not read TIFF."},
}
STILL_FORMAT = "tiff"

# ---- video codecs ------------------------------------------------------------------------------
# Measured on this machine over 30 real S26 frames, width padded to even so nothing is cropped.
# "identical" is the share of pixels that survive a write/read round trip unchanged:
#
#     codec   identical   kB/frame   encode    per 125 s run
#     FFV1      100.0 %       228     9.7 ms       0.6 GB     <- default: lossless
#     Y800      100.0 %       964     0.8 ms       2.4 GB     <- lossless, raw, cheapest CPU
#     MJPG       51.8 %        38     2.6 ms       0.1 GB     <- lossy; small, for review only
#
# Everything else that claims lossless FAILED here and is deliberately not offered: HuffYUV,
# FFVHuff and both Ut Video variants all returned 72.4 % (they round-trip through YUV and lose
# greyscale precision in this build), lossless JPEG silently fell back to MJPG, and Lagarith and
# raw DIB would not open at all. A codec that says lossless and is not is worse than an honest
# lossy one, so only the two verified at 100.0 % are listed as lossless.
#
# FFV1 goes in MKV rather than AVI: same bytes and the same 100.0 %, but AVI has no standard way
# to carry FFV1 and some players refuse it.
VIDEO_CODECS = {
    "ffv1": {"fourcc": "FFV1", "ext": ".mkv", "lossless": True,  "kb": 228, "ms": 9.7,
             "identical": 100.0, "label": "FFV1 (lossless)",
             "why": "Every pixel survives, at a quarter the size of raw. The only codec here "
                    "that is both lossless and small, so it is the default and the one to use "
                    "if the video will be re-analysed. Writes .mkv, because AVI has no standard "
                    "way to carry FFV1."},
    "y800": {"fourcc": "Y800", "ext": ".avi", "lossless": True,  "kb": 964, "ms": 0.8,
             "identical": 100.0, "label": "Raw Y800 (lossless, no encoding)",
             "why": "No encoding at all — the frames go straight to disk. Also pixel-perfect, "
                    "and by far the cheapest on CPU, but four times the size of FFV1. Choose it "
                    "only if the machine cannot keep up."},
    "mjpg": {"fourcc": "MJPG", "ext": ".avi", "lossless": False, "kb": 38, "ms": 2.6,
             "identical": 51.8, "label": "MJPG (lossy — for review only)",
             "why": "Tiny, and every frame seeks independently, which is what review software "
                    "expects. But only about half the pixels survive it and hard edges ring, so "
                    "never measure from an MJPG file. What the rig wrote until 2026-08-21."},
}
VIDEO_CODEC = "ffv1"


class Style:
    """How a frame is processed before it is written. Applied in the WORKER thread.

    The transforms are all sub-millisecond (binary 0.41 ms, CLAHE 0.71 ms at the rig's ROI), so a
    processed view costs 1-3 % of a core rather than anything the camera or GUI would notice.

    `png_compression` is per-style on purpose. Level 1 costs 3x level 0 on a photographic frame and
    saves only 31 %, so RAW uses 0. On a two-tone binary frame level 1 is the SAME speed as level 0
    and 23x smaller (42 KB vs 965 KB — 0.08 GB/min instead of 1.9), so SPECKLE uses 1. Picking one
    level for both would either throw away that 23x or halve the achievable frame rate.
    """

    # Bytes per frame at the rig's 419x2348 ROI. `avi_kb` is the MJPG size, which is also the
    # baseline the codec estimates scale from, so it has to be REAL: the earlier values (raw 320,
    # speckle 105, boost 380) were guesses rounded up and came out ~9x high, which made the
    # dialog quote 3.85 GB/min for an FFV1 stream that actually costs 0.47. Re-measured 2026-08-22
    # from the S26 run on disk: raw 36.1, speckle 35.0, boost 83.5 kB/frame over 1 682 frames.
    # Rounded up a little, because erring high is the safe direction for a disk warning.
    def __init__(self, key, label, transform=None, png_compression=PNG_COMPRESSION, note="",
                 png_kb=970, avi_kb=38):
        self.key = key
        self.label = label
        self.transform = transform
        self.png_compression = png_compression
        self.note = note
        self.png_kb = png_kb
        self.avi_kb = avi_kb

    @property
    def compressible(self):
        """Does this VIEW compress hugely — as a two-tone speckle frame does and a photograph does not?

        Historically this fact lived in `png_compression`: the speckle style asked for level 1
        because on a binary frame it is 23x smaller AND the same speed, where on a photographic
        frame level 1 costs 3x and saves 31 %. But that is a fact about the IMAGE, not about PNG.
        Writing a binary frame as uncompressed TIFF throws away exactly the same 23x, so the flag
        now steers the TIFF choice too and the speckle view stays small in either format.
        """
        return self.png_compression > 0

    def apply(self, frame):
        return frame if self.transform is None else self.transform(frame)

    def gb_per_min(self, fps=35, png=False):
        return (self.png_kb if png else self.avi_kb) * fps * 60 / 1024 / 1024


def style_raw():
    return Style("raw", "Raw (as the sensor sees it)", None, 0,
                 "everything is kept; the only view you can re-derive the others from",
                 png_kb=970, avi_kb=38)


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
                 png_kb=45, avi_kb=36)


def style_boost(clip=2.5, tile=8):
    """Local contrast equalisation — pulls markers out of a dim or unevenly lit frame."""
    import cv2 as _cv2
    _c = _cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
    return Style("boost", "Boosted contrast (CLAHE)", lambda f: _c.apply(f), 0,
                 "helps when the LEDs are uneven; keeps greys, so still re-analysable",
                 png_kb=970, avi_kb=85)


STYLES = ("raw", "speckle", "boost")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_manifest(run_dir, info):
    """Drop run.json into a capture folder so the frames can be traced back to their test.

    A capture folder and its CSV are written minutes apart by different parts of the app, and
    without this the only thing joining a multi-gigabyte pile of frames to the force data is the
    operator remembering which is which. Both halves of the link are written: this file points at
    the CSV, and the CSV header points back here.
    """
    import json
    path = os.path.join(run_dir, "run.json")
    try:
        existing = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        existing.update({k: v for k, v in info.items() if v is not None})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        return path
    except Exception:
        return None


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


class StillSink(_Sink):
    """Every frame as a LOSSLESS still — TIFF or PNG — plus an index tying each file to a timestamp.

    Was `PngSink` until 2026-08-21, when TIFF became the default and the name stopped being true.
    The alias below keeps older callers working.
    """

    def __init__(self, directory, buffer=DEFAULT_BUFFER, style=None, fmt=None):
        super().__init__(buffer)
        self.path = directory
        self.style = style or style_raw()
        self.fmt = fmt if fmt in STILL_FORMATS else STILL_FORMAT
        os.makedirs(directory, exist_ok=True)
        self._n = 0
        self._index = open(os.path.join(directory, "index.csv"), "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._index)
        self._csv.writerow(["frame", "file", "pc_time_iso", "t_monotonic_s"])
        self._start()

    def _write(self, item):
        frame, t_mono, iso = item
        spec = STILL_FORMATS[self.fmt]
        # A two-tone speckle frame compresses ~23x where a photographic one does not, so a
        # COMPRESSIBLE view is written compressed whichever format was chosen. Uncompressed TIFF on
        # a binary frame would waste the same 23x that PNG level 1 was introduced to capture.
        if self.fmt == "tiff" and self.style.compressible:
            spec = STILL_FORMATS["tiff_lzw"]
        # PNG still takes its exact level from the style.
        params = spec["params"] or [cv2.IMWRITE_PNG_COMPRESSION, self.style.png_compression]
        name = f"f{self._n:06d}{spec['ext']}"
        cv2.imwrite(os.path.join(self.path, name), self.style.apply(frame), params)
        self._csv.writerow([self._n, name, iso, f"{t_mono:.4f}"])
        self._n += 1

    def _close(self):
        try:
            self._index.flush()
            self._index.close()
        except Exception:
            pass


PngSink = StillSink          # historical name; it no longer only writes PNG


class VideoSink(_Sink):
    """The whole run as one video. Grayscale in, isColor=False — no needless BGR expansion.

    ODD WIDTHS ARE PADDED, NOT CROPPED. Every codec here works in even-width blocks, so a 419 px
    ROI came back 418 and the outermost column was silently gone. Padding to 420 with a copy of the
    last column keeps the frame whole; `true_width` records what to crop back to, and the manager
    writes it into run.json so a reader can recover the exact frame without guessing.
    """

    def __init__(self, path, size, fps, buffer=DEFAULT_BUFFER, style=None, codec=None):
        super().__init__(buffer)
        self.path = path
        self.style = style or style_raw()
        self.codec = codec if codec in VIDEO_CODECS else VIDEO_CODEC
        spec = VIDEO_CODECS[self.codec]
        w, h = size
        self.true_width = w
        self._pad = w % 2                       # 0 or 1 extra column
        base, ext = os.path.splitext(path)
        self.path = base + spec["ext"]
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._vw = cv2.VideoWriter(self.path, cv2.VideoWriter_fourcc(*spec["fourcc"]),
                                   fps, (w + self._pad, h), False)
        if not self._vw.isOpened():
            self.error = (f"could not open a {spec['label']} writer for {self.path} — "
                          f"this OpenCV build may lack the codec")
            self._vw = None
            return
        self._start()

    def _write(self, item):
        if self._vw is None:
            return
        f = self.style.apply(item[0])
        if self._pad:
            f = cv2.copyMakeBorder(f, 0, 0, 0, self._pad, cv2.BORDER_REPLICATE)
        self._vw.write(f)

    def _close(self):
        if self._vw is not None:
            self._vw.release()
            self._vw = None


class CaptureManager:
    """Owns the two sinks and the run folder. All methods are safe to call from the GUI thread.

    `submit` is the exception — it is called from the camera thread, and is the only method that
    has to be fast."""

    def __init__(self, root=os.path.join("output", "captures"), fps=35):
        self.root = root
        self.fps = fps
        # BOTH are lists. Raw and speckle answer different questions and an operator generally
        # wants both: raw is the archival record, speckle shows the marker motion at a glance.
        # Each style gets its own independent worker and its own file/folder, so two views cost
        # two worker threads rather than two passes over the camera thread.
        self.pngs = []
        self.videos = []
        # Which lossless still format the next run writes. All choices are lossless; see
        # STILL_FORMATS for the measured size/CPU trade-off. Set from the capture-settings dialog.
        self.still_format = STILL_FORMAT
        # Which video codec. FFV1 by default so the video is a MEASUREMENT and not just a preview;
        # MJPG remains available for a small review copy. See VIDEO_CODECS.
        self.video_codec = VIDEO_CODEC
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
            self.pngs.append(StillSink(os.path.join(d, sub), style=st,
                                       fmt=self.still_format))
        write_manifest(d, {"still_format": self.still_format, "still_lossless": True})
        return [p.path for p in self.pngs]

    def start_video(self, size, label=None):
        """One AVI per selected style, all fed from the same frames. `size` is (width, height)."""
        if self.recording:
            return [v.path for v in self.videos]
        d = self.run_dir(label)
        self.videos = []
        for st in (self.video_styles or [style_raw()]):
            name = "video" if st.key == "raw" else f"video_{st.key}"
            v = VideoSink(os.path.join(d, name), size, self.fps, style=st,
                          codec=self.video_codec)
            # A missing codec must not silently cost the operator the recording. Fall back to
            # MJPG, which every build has, and leave the error on the sink so the UI can say the
            # video is LOSSY — a lossy recording the operator knows about is recoverable, one
            # they believe is lossless is not.
            if v.error and self.video_codec != "mjpg":
                msg = v.error
                v = VideoSink(os.path.join(d, name), size, self.fps, style=st, codec="mjpg")
                v.error = f"{msg}; fell back to MJPG, which is LOSSY"
            self.videos.append(v)
        # Make the folder self-describing. `true_width` is the one a reader cannot guess: the file
        # is an even number of pixels wide and the last column is padding, so without this someone
        # re-analysing the video months from now would measure a column that was never real.
        used = {v.codec for v in self.videos}
        write_manifest(d, {
            "video_codec": sorted(used),
            "video_lossless": all(VIDEO_CODECS[c]["lossless"] for c in used),
            "video_true_width": self.videos[0].true_width if self.videos else None,
            "video_padded_width": (self.videos[0].true_width + self.videos[0]._pad)
                                  if self.videos else None,
        })
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
