"""Replay recorded frames through the REAL detector and say why tracking failed.

    python dic_replay.py "<folder with frames/ or the frames/ folder itself>" [--mode Black]

The live badge tells you tracking is bad. It cannot tell you WHICH of the four ways it is bad, and
by the time you are reading it the specimen is already in the grips. This runs the app's own
`detect_blobs` over saved frames, with the same preset, and reports the four things the badge
cannot:

  1. BLOB-COUNT HISTOGRAM. `1` means a marker is being lost -- a contrast/threshold problem.
     `3+` means something else in frame qualifies -- grips, glare, a fixture edge.
  2. THRESHOLD WOBBLE. Otsu recomputes the cut on every frame from the whole picture. If a bright
     region drifts in and out, the cut moves with it and markers qualify on one frame and not the
     next. A wobble of more than a few grey levels IS the failure, not a symptom of it.
  3. THE WORKING PLATEAU -- the span of FIXED thresholds that find exactly 2 blobs. A wide plateau
     means the frame is comfortable and a fixed cut will hold; a narrow or empty one means no
     threshold works and the fix is physical (lighting, exposure, marker paint), not numerical.
  4. NEAR MISSES. For every contour that was rejected, which single filter rejected it. A marker
     failing circularity by 0.02 is a different problem from one failing area by 10x.

Reads the saved PNGs, which are stored ALREADY ROTATED (2348x419) exactly as `detect_blobs`
receives them live, so the replay is faithful -- no re-rotation here on purpose.
"""
# Run from the APP directory (Software/UTM_PyQt6), which is also where this script's data and
# output paths are resolved from:  python tools/dic_replay.py
# The app modules live one level up, so put that on the path before importing them.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def presets():
    """The real preset table, without starting Qt or a camera."""
    from camera_manager import CameraManager
    return CameraManager.SPECIMEN_PRESETS


def live_detector(mode, px0=None):
    """The REAL CameraManager.detect_blobs, preset applied, no camera and no window.

    Worth the Qt import: `detect_blobs` does not stop at the filters. When more than two contours
    qualify it calls `_choose_marker_pair`, which rescues the frame by picking the pairing closest
    to Px0. A replay that stopped at the filters would report a frame with 3 blobs as a dropout when
    the live app tracks it perfectly -- and would send the operator chasing a fault that is not
    there. `px0` therefore matters: pass the Px0 the run actually used, or the rescue path is being
    tested in the wrong mode.
    """
    from PyQt6.QtCore import QCoreApplication
    from camera_manager import CameraManager
    if QCoreApplication.instance() is None:
        live_detector._app = QCoreApplication([])      # keep it alive for the process
    cm = CameraManager()
    cm.set_specimen_mode(mode)
    cm.initial_distance = px0
    cm.error_occurred.connect(lambda _m: None)         # swallow the per-frame dropout chatter
    return cm


def px0_from_run(root):
    """Px0 = px_per_mm x gauge, read from the run's CSV header. None if no CSV is beside it.

    The header does not store Px0 directly, but it stores both factors it was derived from, and
    `tare_dic` sets px_per_mm = initial_distance / gauge_length_mm -- so the product recovers it
    exactly rather than approximately.
    """
    import re
    cands = glob.glob(os.path.join(root, "*.csv")) + \
        glob.glob(os.path.join(root, "..", "*.csv")) + \
        glob.glob(os.path.join(root, "..", "..", "*.csv"))
    for c in cands:
        try:
            with open(c, encoding="utf-8", errors="replace") as fh:
                head = "".join(next(fh) for _ in range(25))
        except Exception:
            continue
        ppm = re.search(r"px_per_mm:\s*([\d.]+)", head)
        gl = re.search(r"Gauge Length:\s*([\d.]+)", head)
        if ppm and gl:
            return float(ppm.group(1)) * float(gl.group(1))
    return None


def contours_of(frame, thr, ttype):
    used, binary = cv2.threshold(frame, thr, 255, ttype)
    cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return used, cnts


def classify(cnts, min_area, max_area, min_circ):
    """(accepted, rejected) where each rejected carries the ONE filter that killed it."""
    acc, rej = [], []
    for c in cnts:
        area = cv2.contourArea(c)
        per = cv2.arcLength(c, True)
        circ = (4 * np.pi * area / (per ** 2)) if per > 0 else 0.0
        M = cv2.moments(c)
        cx = M["m10"] / M["m00"] if M["m00"] else 0.0
        cy = M["m01"] / M["m00"] if M["m00"] else 0.0
        d = {"area": area, "circ": circ, "cx": cx, "cy": cy}
        if area <= min_area:
            d["why"] = "too small"
        elif area >= max_area:
            d["why"] = "too big"
        elif circ <= min_circ:
            d["why"] = "not round"
        else:
            acc.append(d)
            continue
        rej.append(d)
    return acc, rej


def plateau(frame, ttype, min_area, max_area, min_circ, lo=40, hi=220, step=5):
    """Widest run of FIXED thresholds giving exactly 2 blobs -> (width_levels, lo, hi)."""
    base = ttype & ~cv2.THRESH_OTSU
    good = []
    for t in range(lo, hi + 1, step):
        _u, cnts = contours_of(frame, t, base)
        acc, _r = classify(cnts, min_area, max_area, min_circ)
        if len(acc) == 2:
            good.append(t)
    if not good:
        return 0, None, None
    runs, cur = [], [good[0]]
    for a, b in zip(good, good[1:]):
        if b - a <= step:
            cur.append(b)
        else:
            runs.append(cur); cur = [b]
    runs.append(cur)
    w = max(runs, key=len)
    return (w[-1] - w[0]), w[0], w[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="capture folder, or its frames/ subfolder")
    ap.add_argument("--mode", default="Black", choices=("Black", "White"))
    ap.add_argument("--max", type=int, default=400, help="frames to read (0 = all)")
    ap.add_argument("--px0", type=float, default=None,
                    help="Px0 in px; read from the run's CSV header when not given")
    args = ap.parse_args()

    root = args.path

    def _stills(*parts):
        """Frames are TIFF since 2026-08-21 and PNG before it; a replay must read both."""
        out = []
        for ext in ("*.tif", "*.tiff", "*.png"):
            out += glob.glob(os.path.join(*(parts + (ext,))))
        return sorted(out)

    files = _stills(root)
    if not files:
        files = _stills(root, "frames")
    if not files:
        for sub in sorted(glob.glob(os.path.join(root, "*"))):
            files = _stills(sub, "frames")
            if files:
                break
    if not files:
        print(f"No PNG frames under {root}"); return 2
    if args.max:
        step = max(1, len(files) // args.max)
        files = files[::step]

    p = presets()[args.mode]
    ttype, thr = p["threshold_type"], p["threshold"]
    mn, mx, mc = p["min_area"], p["max_area"], p["min_circularity"]
    is_otsu = bool(ttype & cv2.THRESH_OTSU)
    print(f"{len(files)} frames | mode {args.mode} | "
          f"threshold {'AUTO (Otsu)' if is_otsu else thr} | area {mn}-{mx} | circ > {mc}\n")

    # Px0 from the run's own header if we can find it -- the rescue path needs the real one.
    px0 = args.px0 or px0_from_run(root)
    cm = live_detector(args.mode, px0)
    print(f"Px0 for the pair-rescue path: "
          f"{('%.1f px' % px0) if px0 else 'NOT SET -- rescue falls back to centre-line geometry'}\n")

    counts, raw_counts, thrs, seps, why = {}, {}, [], [], {}
    near = []
    for i, fp in enumerate(files):
        f = cv2.imread(fp, cv2.IMREAD_GRAYSCALE)
        if f is None:
            continue
        used, cnts = contours_of(f, thr, ttype)
        acc, rej = classify(cnts, mn, mx, mc)
        raw_counts[len(acc)] = raw_counts.get(len(acc), 0) + 1
        thrs.append(used)
        # what the LIVE app actually gets, rescue path and all
        got = cm.detect_blobs(f)
        counts[len(got)] = counts.get(len(got), 0) + 1
        if len(got) == 2:
            a = sorted(got, key=lambda b: b[1])
            seps.append(abs(a[1][1] - a[0][1]))
        for r in rej:
            why[r["why"]] = why.get(r["why"], 0) + 1
        # a rejected contour big enough to BE a marker is the interesting kind
        for r in rej:
            if r["area"] > mn * 0.4 and r["why"] == "not round":
                near.append(r["circ"])

    n = sum(counts.values())
    print("BLOB COUNT PER FRAME  (what the live app gets, after the pair-rescue path)")
    for k in sorted(counts):
        bar = "#" * int(40 * counts[k] / n)
        tag = {0: "nothing found", 1: "A MARKER IS BEING LOST", 2: "good"}.get(k, "EXTRA OBJECTS QUALIFY")
        print(f"  {k} blobs  {counts[k]:5d}  {100*counts[k]/n:5.1f} %  {bar:<40} {tag}")
    ok = 100.0 * counts.get(2, 0) / n
    print(f"\n  tracking = {ok:.1f} %   (the live badge shows this number)")

    raw2 = 100.0 * raw_counts.get(2, 0) / max(1, sum(raw_counts.values()))
    extra = 100.0 * sum(v for k, v in raw_counts.items() if k > 2) / max(1, sum(raw_counts.values()))
    print(f"  before the rescue: {raw2:.1f} % gave exactly 2, {extra:.1f} % gave MORE than 2")
    if extra > 5:
        print(f"  -> the rescue is carrying {ok - raw2:+.1f} points of tracking. Whatever those extra")
        print("    objects are, they are in frame on a large share of frames -- worth removing")
        print("    physically (mask, matte the grips, tighten the ROI) rather than relying on it.")

    if is_otsu:
        t = np.array(thrs, float)
        print(f"\nOTSU THRESHOLD ACROSS FRAMES")
        print(f"  min {t.min():.0f}   median {np.median(t):.0f}   max {t.max():.0f}   "
              f"spread {t.max()-t.min():.0f} levels   sd {t.std():.1f}")
        if t.max() - t.min() > 10:
            print("  ^ THE CUT IS MOVING. Otsu recomputes it per frame from the whole picture, so a")
            print("    bright region drifting in and out drags it. This alone can produce exactly")
            print("    the intermittent 1/2 the badge reports. A FIXED threshold cannot wobble.")
        else:
            print("  ^ stable -- Otsu is not the problem here.")

    mid = files[len(files) // 2]
    f = cv2.imread(mid, cv2.IMREAD_GRAYSCALE)
    w, lo, hi = plateau(f, ttype, mn, mx, mc)
    print(f"\nWORKING PLATEAU (fixed thresholds finding exactly 2 blobs, mid-run frame)")
    if w:
        print(f"  {lo}..{hi}   width {w} grey levels")
        print("  " + ("wide -- a fixed threshold will hold comfortably" if w >= 40 else
                      "NARROW -- little room before a marker drops out; consider lighting/exposure "
                      "or better marker contrast as well as a fixed cut"))
    else:
        print("  NONE -- no fixed threshold finds exactly 2 blobs on this frame.")
        print("  This cannot be fixed by tuning a number. The markers are not separable from the")
        print("  background at any cut: change exposure, lighting, or the markers themselves.")

    if why:
        print("\nWHY CONTOURS WERE REJECTED (all frames)")
        for k, v in sorted(why.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<12} {v}")
    if near:
        a = np.array(near)
        print(f"\n  {len(a)} marker-sized contours failed ROUNDNESS "
              f"(circ {a.min():.2f}..{a.max():.2f} vs the {mc} gate)")
        if a.max() > mc - 0.15:
            print("  ^ some were CLOSE. A marker merging with a grip or a glare halo looks like this.")

    if seps:
        s = np.array(seps)
        print(f"\nPAIR SEPARATION on the frames that did track")
        print(f"  {s.min():.0f}..{s.max():.0f} px   sd {s.std():.1f} px")
        if s.std() > 20:
            print("  ^ WRONG-OBJECT LOCK. A real specimen strains a few percent; swings of hundreds")
            print("    of px mean the pair sometimes includes something that is not a marker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
