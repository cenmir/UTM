"""DIC auto-calibration — score a frame's trackability, and pick exposure / threshold from data.

    from utm_autocal import frame_score, best_threshold, pick_best

The rig's preset carries an exposure and a threshold chosen once, by hand, under one set of LEDs.
When the lighting drifts those numbers quietly stop being right: the markers wash out or sink into
the background, detection falls to 1/2 or 0/2, and the first sign is a ruined test. This module
turns "does it look OK" into a number, so the app can sweep the settings and choose.

WHAT MAKES A FRAME TRACKABLE — and why the score is shaped this way:

  * exactly TWO blobs. Not a preference, a gate: one marker means no gauge length and three means
    the detector is finding something that is not a marker. A frame that fails this scores 0
    however pretty it looks.
  * CONTRAST MARGIN — how far the markers sit from the background in grey levels, relative to the
    threshold. This is the one that predicts robustness. A frame can detect perfectly at this
    instant with the markers only 8 levels from the cut, and lose them on the next flicker.
  * HEADROOM — clipped pixels are unrecoverable. Blown highlights eat the specimen edge and
    crushed blacks merge the markers into the shadow band, so saturation is penalised even when
    detection currently succeeds.
  * AREA in the middle of the accepted band, not at its edge, so normal breathing of the blob does
    not push it outside min_area/max_area mid-test.
  * CIRCULARITY, which is what separates a marker from the grip bands and from a smear.

Pure NumPy/OpenCV on a supplied frame: no camera, no Qt, no app state, so the scoring can be tested
against synthetic and recorded frames. Anything that has to talk to the camera (actually changing
exposure and re-grabbing) lives in the caller.
"""
import numpy as np
import cv2

# A marker sitting this close to the threshold is one flicker from being lost, even if it is
# detected right now. Below this the contrast term goes to zero rather than degrading gracefully.
MIN_MARGIN = 12.0
GOOD_MARGIN = 45.0        # margin at which the contrast term is fully satisfied
MAX_CLIPPED_PCT = 2.0     # above this proportion of clipped pixels, headroom scores zero


def _blobs(binary, min_area, max_area, min_circ):
    """Contours passing the same gates camera_manager.detect_blobs applies."""
    cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if not (min_area < a < max_area):
            continue
        p = cv2.arcLength(c, True)
        if p <= 0:
            continue
        circ = 4 * np.pi * a / (p * p)
        if circ <= min_circ:
            continue
        M = cv2.moments(c)
        if M["m00"] > 0:
            out.append({"area": a, "circ": circ,
                        "cx": M["m10"] / M["m00"], "cy": M["m01"] / M["m00"]})
    return sorted(out, key=lambda b: b["cy"])


def frame_score(frame, threshold, thresh_type=cv2.THRESH_BINARY_INV,
                min_area=2000, max_area=200000, min_circ=0.5):
    """Score one frame 0..1 for how reliably its markers can be tracked.

    Returns a dict: score plus the individual terms, so the UI can say WHY a setting was chosen
    rather than presenting a bare number.
    """
    base = thresh_type & ~cv2.THRESH_OTSU
    used = threshold
    if thresh_type & cv2.THRESH_OTSU:
        used, binary = cv2.threshold(frame, 0, 255, base | cv2.THRESH_OTSU)
    else:
        _, binary = cv2.threshold(frame, threshold, 255, base)

    blobs = _blobs(binary, min_area, max_area, min_circ)
    n = len(blobs)
    clipped = float(((frame == 0) | (frame == 255)).mean() * 100.0)
    out = {"n_blobs": n, "threshold": float(used), "clipped_pct": clipped,
           "score": 0.0, "contrast": 0.0, "headroom": 0.0, "area_fit": 0.0,
           "circularity": 0.0, "sep_px": 0.0, "mean": float(frame.mean())}
    if n != 2:
        return out                       # hard gate — see module docstring

    # Contrast margin: how far marker and background grey levels sit from the cut. Sampled from the
    # mask itself rather than assumed, so it works for either polarity.
    mask = binary > 0
    fg = float(frame[mask].mean()) if mask.any() else used
    bg = float(frame[~mask].mean()) if (~mask).any() else used
    margin = min(abs(fg - used), abs(bg - used))
    out["contrast"] = float(np.clip((margin - MIN_MARGIN) / (GOOD_MARGIN - MIN_MARGIN), 0, 1))
    out["margin"] = margin
    out["fg_mean"], out["bg_mean"] = fg, bg

    out["headroom"] = float(np.clip(1.0 - clipped / MAX_CLIPPED_PCT, 0, 1))

    # Area comfort: 1.0 at the geometric middle of the accepted band, falling off toward either end.
    mid = np.sqrt(min_area * max_area)
    a = np.mean([b["area"] for b in blobs])
    out["area_fit"] = float(np.clip(1.0 - abs(np.log(a / mid)) / np.log(max_area / mid), 0, 1))
    out["area_px"] = float(a)

    out["circularity"] = float(np.clip((np.mean([b["circ"] for b in blobs]) - min_circ)
                                       / (1.0 - min_circ), 0, 1))
    out["sep_px"] = float(abs(blobs[1]["cy"] - blobs[0]["cy"]))

    # Contrast dominates: it is the term that predicts whether tracking SURVIVES, where the others
    # describe how comfortable it is right now.
    out["score"] = float(0.45 * out["contrast"] + 0.25 * out["headroom"]
                         + 0.15 * out["area_fit"] + 0.15 * out["circularity"])
    return out


def best_threshold(frame, thresh_type=cv2.THRESH_BINARY_INV, lo=40, hi=220, step=5, **kw):
    """Sweep the threshold on ONE frame and return (best_threshold, best_metrics, all_metrics).

    Needs no camera, so this half of calibration works on a recorded frame or a still image.
    """
    results = []
    for t in range(lo, hi + 1, step):
        m = frame_score(frame, t, thresh_type, **kw)
        m["threshold"] = float(t)
        results.append(m)
    ok = [m for m in results if m["n_blobs"] == 2]
    if not ok:
        return None, None, results
    best = max(ok, key=lambda m: m["score"])
    # Prefer the CENTRE of the widest run of working thresholds over the single best-scoring one:
    # a setting with room either side survives a lighting drift, a peak on a cliff does not.
    ts = sorted(m["threshold"] for m in ok)
    runs, cur = [], [ts[0]]
    for a, b in zip(ts, ts[1:]):
        (cur.append(b) if b - a <= step else (runs.append(cur), cur := [b]))
    runs.append(cur)
    widest = max(runs, key=len)
    if len(widest) >= 3:
        mid = widest[len(widest) // 2]
        best = min(ok, key=lambda m: abs(m["threshold"] - mid))
    return best["threshold"], best, results


def pick_best(samples):
    """Choose from [(setting, [frame, ...]), ...] — the best MEAN score across frames.

    Averaged over several frames on purpose: a single frame can look excellent on noise alone, and
    the setting that matters is the one that keeps working, not the one that peaked once.
    """
    scored = []
    for setting, metrics in samples:
        if not metrics:
            continue
        got2 = sum(1 for m in metrics if m["n_blobs"] == 2) / len(metrics)
        mean = float(np.mean([m["score"] for m in metrics]))
        scored.append({"setting": setting, "detect_rate": got2, "score": mean * got2,
                       "mean_score": mean,
                       "contrast": float(np.mean([m["contrast"] for m in metrics])),
                       "clipped_pct": float(np.mean([m["clipped_pct"] for m in metrics]))})
    if not scored:
        return None, []
    scored.sort(key=lambda s: s["score"], reverse=True)
    return (scored[0] if scored[0]["score"] > 0 else None), scored
