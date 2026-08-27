"""DIC post-processing: measure strain from a RECORDED video, the same way the rig measures it live.

Point it at any video OpenCV can open, place two tracking boxes on the speckle (or on two sprayed
dots), and it reports separation in pixels and strain per frame — using utm_dic.dic_strain, the
same function the live camera path calls. Nothing about the strain maths is re-implemented here.

WHY THIS EXISTS
    Two uses. (1) Re-check our own recordings against what the rig reported live: same pull, same
    frames, an independent measurement path. (2) Measure specimens filmed on the MOT XT-205 video
    extensometer with OUR pixel-to-strain rule, so the two instruments can be compared on the same
    footing and the rig's offset factor can be quantified rather than assumed.

HOW THE TRACKING WORKS
    Each box is matched by normalised cross-correlation against its REFERENCE patch — not against
    the previous frame. Frame-to-frame tracking accumulates drift, and over a 1682-frame pull a
    drift of a fraction of a pixel per frame is a strain error larger than the strain being
    measured. Matching to the reference is drift-free by construction.

    The cost is that the patch must still resemble the reference late in the pull, which fails once
    the speckle around a marker deforms badly. So when peak correlation falls below `min_corr` the
    tracker re-seeds from the last good frame and FLAGS that frame. A flagged frame is reported,
    never silently blended in — the same principle as the live path's dropouts.

    Sub-pixel: a parabola through the correlation peak and its two neighbours, per axis. Without
    it, separation quantises to whole pixels and the strain trace looks like a staircase.

WHAT IS MEASURED
    The rig measures separation along the loading axis only — abs(dy) of the two centroids — and
    reports the perpendicular offset separately as dx_px. A recorded video may be rotated any way
    at all, so here the displacement is projected onto the axis of the REFERENCE pair. For an
    axis-aligned pair that is identical to the rig's abs(dy); for a rotated one it is the correct
    generalisation of it. The perpendicular component is reported as dx_px, as on the rig.

FRAME RATE IS AN INPUT, NOT AN ASSUMPTION
    A container's fps field is metadata, and it is often wrong. S26's video.avi declares 35 fps
    while the capture index proves it recorded 1682 frames in 84.4 s = 19.93 fps — a 1.75x error
    that would silently stretch the whole time axis. fps is therefore a parameter; the file's
    value is only the default, and `fps_warning()` says when it looks implausible.
"""
import os
from dataclasses import dataclass, field, replace

import numpy as np

try:
    import cv2
except ImportError:                                    # pragma: no cover - cv2 always present in the app
    cv2 = None

from utm_dic import dic_strain, px_per_mm


@dataclass
class Box:
    """A square tracking patch, by centre and half-size, in frame pixels."""
    cx: float
    cy: float
    half: int = 24

    def clamp(self, w, h):
        self.cx = float(min(max(self.cx, self.half + 1), w - self.half - 2))
        self.cy = float(min(max(self.cy, self.half + 1), h - self.half - 2))
        return self

    def patch(self, gray):
        x, y, r = int(round(self.cx)), int(round(self.cy)), self.half
        return gray[y - r:y + r + 1, x - r:x + r + 1]


@dataclass
class Settings:
    gauge_mm: float = 80.0        # physical distance between the two boxes, for px/mm only
    box_half: int = 24            # patch half-size
    search: int = 40              # how far a box may move between reference and current frame
    min_corr: float = 0.55        # below this the match is not trusted
    ref_frame: int = 0            # which frame defines L0
    fps: float = 0.0              # 0 = take the container's value
    step: int = 1                 # analyse every Nth frame
    # "auto"        correlate to find the patch, then refine on the marker centroid when the
    #               patch holds one. Best of both: correlation survives large motion, the
    #               centroid gives the rig's precision on a dot.
    # "correlation" correlation only — the honest choice for a speckle pattern, which has no
    #               marker to take a centroid of.
    refine: str = "auto"


@dataclass
class FrameResult:
    idx: int
    t: float
    a: tuple
    b: tuple
    l_px: float
    dx_px: float
    cauchy: float
    true: float
    corr: float
    ok: bool
    note: str = ""


@dataclass
class Summary:
    n: int = 0
    tracked: int = 0
    reseeds: int = 0
    centroid_frames: int = 0     # frames measured by marker centroid rather than correlation
    l0_px: float = 0.0
    px_mm: float = None
    fps: float = 0.0
    rows: list = field(default_factory=list)

    @property
    def coverage(self):
        return 100.0 * self.tracked / self.n if self.n else 0.0


def probe(path):
    """What the file says about itself. Never trusted for fps — see the module docstring."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError("cannot open video: %s" % path)
    info = {"frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0),
            "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "name": os.path.basename(path)}
    cap.release()
    info["duration_s"] = info["frames"] / info["fps"] if info["fps"] > 0 else 0.0
    return info


def true_fps_from_sidecar(video_path):
    """The MEASURED frame rate for one of our own captures, or None.

    A container's fps field is what the writer claimed, not what the camera did. Our capture
    folders record the truth beside the video: frames/index.csv timestamps every frame, and
    run.json brackets the recording with captured_from/captured_to. S26 declares 35 fps and
    actually ran at 19.93 — believing the container would stretch its whole time axis by 1.76x.

    Returns (fps, source, n_frames) so the UI can say WHERE the number came from, or None when
    the video has no sidecar (anything filmed on the extensometer, or any other camera).
    """
    d = os.path.dirname(os.path.abspath(video_path))
    idx = os.path.join(d, "frames", "index.csv")
    if os.path.isfile(idx):
        try:
            import csv as _csv
            import datetime as _dt
            with open(idx, encoding="utf-8") as fh:
                rows = list(_csv.DictReader(fh))
            if len(rows) > 1:
                t0 = _dt.datetime.fromisoformat(rows[0]["pc_time_iso"])
                t1 = _dt.datetime.fromisoformat(rows[-1]["pc_time_iso"])
                span = (t1 - t0).total_seconds()
                if span > 0:
                    return (len(rows) - 1) / span, "frames/index.csv timestamps", len(rows)
        except Exception:
            pass
    rj = os.path.join(d, "run.json")
    if os.path.isfile(rj):
        try:
            import json as _json
            import datetime as _dt
            with open(rj, encoding="utf-8") as fh:
                m = _json.load(fh)
            t0 = _dt.datetime.fromisoformat(m["captured_from"])
            t1 = _dt.datetime.fromisoformat(m["captured_to"])
            span = (t1 - t0).total_seconds()
            n = probe(video_path)["frames"]
            if span > 0 and n > 1:
                return (n - 1) / span, "run.json capture window", n
        except Exception:
            pass
    return None


def fps_warning(info, known_duration_s=None):
    """A sentence when the declared fps looks wrong, else ''."""
    fps = info.get("fps") or 0.0
    if fps <= 0:
        return "This file declares no frame rate — set it by hand, or the time axis is meaningless."
    if known_duration_s and known_duration_s > 0:
        real = info["frames"] / known_duration_s
        if abs(real - fps) / fps > 0.05:
            return ("The file declares %.2f fps, but %d frames over %.1f s is %.2f fps. "
                    "Using the declared value would scale the time axis by %.2fx."
                    % (fps, info["frames"], known_duration_s, real, fps / real))
    if fps > 120 or fps < 1:
        return "Declared %.2f fps is implausible for this rig — check it before trusting time." % fps
    return ""


def _grab(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError("cannot open video: %s" % path)
    return cap


def read_frame(path, idx):
    """One frame as greyscale — for the UI preview and for placing the boxes."""
    cap = _grab(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame


def find_markers(gray, min_area=300, max_area=200000, min_circ=0.45, dedupe_px=25.0):
    """Every round blob in the frame, at either polarity. [(cx, cy, radius, circ)], best first.

    Used for two things that must agree: Auto-detect, which wants exactly two, and click-to-snap,
    which wants the one nearest the cursor. One finder means a marker cannot be good enough to
    auto-detect but invisible to the snap, or the reverse.

    Both polarities are swept because the rig runs both — dark sprayed dots on white PLA, and
    bright dots on dark TPU — and a post-processed video carries no setting to say which. Several
    thresholds are tried because one fixed value does not survive a change of lighting; blobs
    found more than once are collapsed by proximity so a marker seen at four thresholds counts as
    one marker, ranked by its best circularity.
    """
    import cv2 as _cv
    found = []
    for mode in (_cv.THRESH_BINARY_INV, _cv.THRESH_BINARY):
        for thr in (90, 110, 130, 150, 170, 190, 210):
            _, b = _cv.threshold(gray, thr, 255, mode)
            contours, _ = _cv.findContours(b, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = _cv.contourArea(c)
                per = _cv.arcLength(c, True)
                if per <= 0 or not (min_area < area < max_area):
                    continue
                circ = 4 * np.pi * area / (per * per)
                if circ < min_circ:
                    continue
                M = _cv.moments(c)
                if M["m00"] <= 0:
                    continue
                found.append((M["m10"] / M["m00"], M["m01"] / M["m00"],
                              float(np.sqrt(area / np.pi)), float(circ)))
    found.sort(key=lambda m: -m[3])
    out = []
    for m in found:
        if all(np.hypot(m[0] - o[0], m[1] - o[1]) > dedupe_px for o in out):
            out.append(m)
    return out


def reference_threshold(patch, dark=True):
    """One grey level for a marker, chosen once from its reference patch.

    Otsu recomputed per frame is what makes a centroid noisy: the cut moves a little each frame,
    the contour's extent moves with it, and the centroid inherits that. Measured on S25, a
    per-frame Otsu centroid gives 151 microstrain against 25 for the same centroid on a threshold
    fixed once — a factor of six, for a one-line difference. The live rig uses a fixed level for
    exactly this reason.
    """
    thr, _ = cv2.threshold(patch, 0, 255,
                           (cv2.THRESH_BINARY_INV if dark else cv2.THRESH_BINARY) | cv2.THRESH_OTSU)
    return float(thr)


def centroid_refine(gray, cx, cy, half, dark=True, thr=None, min_frac=0.02, max_frac=0.9):
    """Re-locate a round marker by its intensity CENTROID, the way the live rig does.

    Correlation is what finds a patch that has moved; it is not the best way to pin down WHERE a
    large uniform dot is. Its peak on a flat disc is broad, so sub-pixel position comes from a
    poorly-conditioned parabola. Measured on S25: correlation alone gives 175-379 microstrain of
    noise depending on patch size, while the rig's blob centroid on the same specimen gives 28.
    The centroid averages every pixel of the disc instead of reading one peak.

    Threshold is Otsu WITHIN the patch, not a fixed global level: the patch is mostly dot and
    surround, which is exactly the bimodal case Otsu is for, and it follows lighting drift down
    the specimen for free.

    Returns (cx, cy, area) or None when the patch holds nothing that looks like a marker — in
    which case the caller keeps the correlation result rather than inventing a position.
    """
    h, w = gray.shape
    r = int(half)
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    x1, y1 = x0 + 2 * r + 1, y0 + 2 * r + 1
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    patch = gray[y0:y1, x0:x1]
    mode = cv2.THRESH_BINARY_INV if dark else cv2.THRESH_BINARY
    if thr is None:                       # no reference level available — Otsu, and noisier for it
        _, b = cv2.threshold(patch, 0, 255, mode | cv2.THRESH_OTSU)
    else:
        _, b = cv2.threshold(patch, thr, 255, mode)
    contours, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    n = patch.size
    best, best_d = None, None
    mid = float(r)
    for c in contours:
        a = cv2.contourArea(c)
        if not (min_frac * n < a < max_frac * n):
            continue
        M = cv2.moments(c)
        if M["m00"] <= 0:
            continue
        px, py = M["m10"] / M["m00"], M["m01"] / M["m00"]
        # The marker is the blob nearest the patch centre; anything else in view is not it.
        d = (px - mid) ** 2 + (py - mid) ** 2
        if best_d is None or d < best_d:
            best, best_d = (px, py, a), d
    if best is None or best_d > (0.6 * r) ** 2:
        return None
    return (x0 + best[0], y0 + best[1], best[2])


def snap_to_marker(markers, x, y, max_dist=None):
    """The marker centre nearest (x, y), or None if nothing is close enough.

    Clicking the exact centre of a dot by eye is guesswork, and the centre is what sets L0 — so a
    click near a marker should mean that marker's centroid, computed, not the pixel the cursor
    happened to be over. Falls back to None on a speckle pattern, which has no discrete markers
    and must stay free-placed.
    """
    if not markers:
        return None
    best = min(markers, key=lambda m: np.hypot(m[0] - x, m[1] - y))
    d = float(np.hypot(best[0] - x, best[1] - y))
    limit = max_dist if max_dist is not None else max(30.0, best[2] * 2.5)
    return (best[0], best[1], d, best) if d <= limit else None


def _subpixel(corr, mx, my):
    """Parabola through the correlation peak and its neighbours, per axis.

    Without this the peak is an integer pixel, separation quantises to 1 px, and on a 1600 px
    gauge that is a 625 microstrain staircase — coarser than the rig's own noise floor.
    """
    dx = dy = 0.0
    h, w = corr.shape
    if 0 < mx < w - 1:
        l, c, r = float(corr[my, mx - 1]), float(corr[my, mx]), float(corr[my, mx + 1])
        d = l - 2 * c + r
        if abs(d) > 1e-12:
            dx = 0.5 * (l - r) / d
    if 0 < my < h - 1:
        u, c, d_ = float(corr[my - 1, mx]), float(corr[my, mx]), float(corr[my + 1, mx])
        d = u - 2 * c + d_
        if abs(d) > 1e-12:
            dy = 0.5 * (u - d_) / d
    # A parabola fit only means anything within one sample of the peak.
    return (dx if abs(dx) <= 1 else 0.0), (dy if abs(dy) <= 1 else 0.0)


def _match(gray, tmpl, guess, search):
    """Locate `tmpl` near `guess`. Returns (cx, cy, peak_correlation) or None."""
    r = (tmpl.shape[0] - 1) // 2
    h, w = gray.shape
    x0 = int(round(guess[0])) - r - search
    y0 = int(round(guess[1])) - r - search
    x1 = int(round(guess[0])) + r + search + 1
    y1 = int(round(guess[1])) + r + search + 1
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    win = gray[y0:y1, x0:x1]
    if win.shape[0] < tmpl.shape[0] or win.shape[1] < tmpl.shape[1]:
        return None
    corr = cv2.matchTemplate(win, tmpl, cv2.TM_CCOEFF_NORMED)
    _, peak, _, loc = cv2.minMaxLoc(corr)
    mx, my = loc
    sx, sy = _subpixel(corr, mx, my)
    return (x0 + mx + sx + r, y0 + my + sy + r, float(peak))


def analyse(path, box_a, box_b, cfg=None, progress=None, should_stop=None, preview=None):
    """Track both boxes through the video and yield a FrameResult per analysed frame.

    progress(done, total) is called for the UI; should_stop() aborts cleanly between frames.
    preview(gray, a_xy, b_xy) hands the caller the decoded frame and where the boxes are NOW, so
    the pull can be shown while it is measured — the frame is already in memory here, and asking
    the UI to re-read it would fight the sequential decoder this loop depends on. The callback is
    handed the live array, not a copy: a caller that keeps it must copy it itself, because the
    decoder reuses the buffer.
    The generator's return value is a Summary (use `yield from` / .value via StopIteration).
    """
    cfg = cfg or Settings()
    info = probe(path)
    fps = cfg.fps if cfg.fps and cfg.fps > 0 else info["fps"]
    cap = _grab(path)

    # ---- reference frame: templates and L0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cfg.ref_frame))
    ok, frame = cap.read()
    if not ok:
        cap.release()
        raise IOError("cannot read reference frame %d" % cfg.ref_frame)
    gray0 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    h, w = gray0.shape
    for b in (box_a, box_b):
        b.half = int(cfg.box_half)
        b.clamp(w, h)
    tmpl_a, tmpl_b = box_a.patch(gray0), box_b.patch(gray0)
    if tmpl_a.size == 0 or tmpl_b.size == 0:
        cap.release()
        raise ValueError("a tracking box falls outside the frame")

    a0 = np.array([box_a.cx, box_a.cy], float)
    b0 = np.array([box_b.cx, box_b.cy], float)
    # L0 MUST be measured the same way every later frame is. If the frames are refined to the
    # marker centroid but L0 is taken from wherever the box was dropped, the difference becomes a
    # constant offset on every strain in the run — invisible, and wrong by however far the click
    # missed the centre.
    if cfg.refine == "auto":
        for pt, t in ((a0, tmpl_a), (b0, tmpl_b)):
            m_ = t.shape[0] // 2
            q_ = max(2, t.shape[0] // 6)
            mid_ = float(t[m_ - q_:m_ + q_ + 1, m_ - q_:m_ + q_ + 1].mean())
            bor_ = float(np.concatenate([t[0, :], t[-1, :], t[:, 0], t[:, -1]]).mean())
            got = centroid_refine(gray0, pt[0], pt[1], cfg.box_half, mid_ < bor_,
                                  reference_threshold(t, mid_ < bor_))
            if got:
                pt[0], pt[1] = got[0], got[1]
    axis = b0 - a0
    l0 = float(np.hypot(*axis))
    if l0 < 5:
        cap.release()
        raise ValueError("the two boxes are on top of each other — place them apart")
    axis = axis / l0                     # unit vector along the reference pair
    perp = np.array([-axis[1], axis[0]])

    # Is each marker dark-on-light or light-on-dark? Decided once, from the reference patch:
    # compare its middle against its border. A video carries no setting to say which, and the rig
    # runs both (dark spray on white PLA, bright on dark TPU).
    def _is_dark(t):
        m = t.shape[0] // 2
        q = max(2, t.shape[0] // 6)
        middle = float(t[m - q:m + q + 1, m - q:m + q + 1].mean())
        border = float(np.concatenate([t[0, :], t[-1, :], t[:, 0], t[:, -1]]).mean())
        return middle < border

    dark_a, dark_b = _is_dark(tmpl_a), _is_dark(tmpl_b)
    thr_a = reference_threshold(tmpl_a, dark_a)
    thr_b = reference_threshold(tmpl_b, dark_b)
    _ra = centroid_refine(gray0, a0[0], a0[1], cfg.box_half, dark_a, thr_a)
    _rb = centroid_refine(gray0, b0[0], b0[1], cfg.box_half, dark_b, thr_b)
    area_a = _ra[2] if _ra else 0.0
    area_b = _rb[2] if _rb else 0.0
    if not (_ra and _rb):
        # No discrete markers here — a speckle pattern. Correlation is the only honest option,
        # and the centroid path is disabled rather than left to latch onto texture.
        cfg = replace(cfg, refine="correlation")
    n_refined = 0

    summary = Summary(l0_px=l0, px_mm=px_per_mm(l0, cfg.gauge_mm), fps=fps)
    last_a, last_b = a0.copy(), b0.copy()
    live_a, live_b = tmpl_a, tmpl_b          # re-seeded templates, used only after a drop
    off_a = off_b = np.zeros(2)              # offset between a re-seeded template and the reference
    total = max(1, (info["frames"] - cfg.ref_frame) // max(1, cfg.step))

    # Read SEQUENTIALLY. Seeking with CAP_PROP_POS_FRAMES per frame forces the decoder to rewind
    # to the previous keyframe every time, which on a 1682-frame lossless AVI is minutes rather
    # than seconds. One seek to the reference frame, then straight reads, skipping for step>1.
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cfg.ref_frame))
    idx = cfg.ref_frame
    done = 0
    while True:
        if should_stop and should_stop():
            break
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

        note, reseeded = "", False

        # ---- CENTROID FIRST, when the markers are discrete dots.
        #
        # The centroid is chained from the marker's own previous position, NOT from a correlation
        # estimate. That matters: correlation jitters by ~0.3 px, and centring the measuring
        # window on a jittering estimate feeds that jitter straight into the result. Measured on
        # S25 — centroid off correlation 215 microstrain, centroid off its own last position 25,
        # against 175 for correlation alone and 28 for the live rig. Same maths, different anchor.
        #
        # Motion between frames is a fraction of the box, so a dot cannot escape its window in one
        # step; if it ever does, the centroid fails and correlation below recovers it.
        ra = rb = None
        corr = 0.0
        if cfg.refine == "auto":
            ca = centroid_refine(gray, last_a[0], last_a[1], cfg.box_half, dark_a, thr_a)
            cb = centroid_refine(gray, last_b[0], last_b[1], cfg.box_half, dark_b, thr_b)
            # A blob is only the marker if it is still about the size the marker was. Without this
            # the centroid will happily follow a dot that has merged with a shadow.
            if ca and cb and 0.5 * area_a < ca[2] < 2.0 * area_a \
                    and 0.5 * area_b < cb[2] < 2.0 * area_b:
                ra, rb = (ca[0], ca[1], 1.0), (cb[0], cb[1], 1.0)
                corr = 1.0
                n_refined += 1

        if ra is None or rb is None:
            ra = _match(gray, tmpl_a, last_a, cfg.search)
            rb = _match(gray, tmpl_b, last_b, cfg.search)
            corr = min(ra[2] if ra else 0.0, rb[2] if rb else 0.0)
        if corr < cfg.min_corr:
            # The reference patch no longer resembles the scene. Fall back to the last good
            # frame's patch and carry its offset, so the measurement stays anchored to L0.
            ra2 = _match(gray, live_a, last_a, cfg.search)
            rb2 = _match(gray, live_b, last_b, cfg.search)
            if ra2 and rb2 and min(ra2[2], rb2[2]) >= cfg.min_corr:
                ra = (ra2[0] + off_a[0], ra2[1] + off_a[1], ra2[2])
                rb = (rb2[0] + off_b[0], rb2[1] + off_b[1], rb2[2])
                corr = min(ra2[2], rb2[2])
                note, reseeded = "re-seeded (reference correlation %.2f)" % corr, True
                summary.reseeds += 1
            else:
                note = "LOST — best correlation %.2f" % corr

        if ra and rb and corr >= cfg.min_corr:
            pa = np.array(ra[:2], float)
            pb = np.array(rb[:2], float)
            d = pb - pa
            l_px = float(abs(np.dot(d, axis)))      # along the reference pair axis, as on the rig
            dx_px = float(abs(np.dot(d, perp)))     # perpendicular, reported like the rig's dx_px
            cauchy, true = dic_strain(l_px, l0)
            last_a, last_b = pa, pb
            if not reseeded:
                live_a, live_b = box_a.__class__(pa[0], pa[1], cfg.box_half).clamp(w, h).patch(gray), \
                                 box_b.__class__(pb[0], pb[1], cfg.box_half).clamp(w, h).patch(gray)
                off_a = off_b = np.zeros(2)
            summary.tracked += 1
            res = FrameResult(idx, (idx - cfg.ref_frame) / fps if fps > 0 else float(idx),
                              tuple(pa), tuple(pb), l_px, dx_px, cauchy, true, corr, True, note)
        else:
            res = FrameResult(idx, (idx - cfg.ref_frame) / fps if fps > 0 else float(idx),
                              tuple(last_a), tuple(last_b), float("nan"), float("nan"),
                              float("nan"), float("nan"), corr, False, note or "no match")

        summary.n += 1
        summary.rows.append(res)
        if preview is not None:
            # Where the boxes are NOW, so the drawn overlay follows the markers apart rather than
            # sitting where they started. On a lost frame these are the last good positions.
            preview(gray, tuple(last_a), tuple(last_b))
        yield res
        done += 1
        if progress:
            progress(done, total)
        idx += max(1, cfg.step)
        for _ in range(max(1, cfg.step) - 1):        # skip forward without decoding a seek
            if not cap.grab():
                break

    summary.centroid_frames = n_refined
    cap.release()
    return summary


def to_csv(summary, path, source_video="", cfg=None):
    """Write the run out in the same spirit as the rig's CSV: a header that says how, then rows."""
    cfg = cfg or Settings()
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("# UTM DIC Post-Processing\n#\n")
        f.write("# Source video: %s\n" % source_video)
        f.write("# Reference frame: %d\n" % cfg.ref_frame)
        f.write("# L0 (Px0): %.3f px\n" % summary.l0_px)
        f.write("# Gauge: %.2f mm  ->  px_per_mm: %s\n"
                % (cfg.gauge_mm, ("%.4f" % summary.px_mm) if summary.px_mm else "n/a"))
        f.write("# Frame rate used: %.4f fps\n" % summary.fps)
        f.write("# Box half-size: %d px   search: %d px   min correlation: %.2f\n"
                % (cfg.box_half, cfg.search, cfg.min_corr))
        f.write("# Frames analysed: %d   tracked: %d (%.1f %%)   re-seeds: %d\n"
                % (summary.n, summary.tracked, summary.coverage, summary.reseeds))
        f.write("# Strain is (L - L0)/L0 via utm_dic.dic_strain - the same function the live rig uses.\n#\n")
        f.write("Frame,Time_s,Ax,Ay,Bx,By,L_px,dx_px,DIC_Cauchy,DIC_True,Correlation,Tracked,Note\n")
        for r in summary.rows:
            f.write("%d,%.4f,%.3f,%.3f,%.3f,%.3f,%s,%s,%s,%s,%.4f,%d,%s\n"
                    % (r.idx, r.t, r.a[0], r.a[1], r.b[0], r.b[1],
                       "" if r.l_px != r.l_px else "%.4f" % r.l_px,
                       "" if r.dx_px != r.dx_px else "%.4f" % r.dx_px,
                       "" if r.cauchy != r.cauchy else "%.8f" % r.cauchy,
                       "" if r.true != r.true else "%.8f" % r.true,
                       r.corr, 1 if r.ok else 0, r.note.replace(",", ";")))
    return path
