"""Live-DIC helpers for the UTM: (1) a health summary for the live tracking badge, and
(2) multi-marker geometry -> lateral strain, Poisson's ratio, current area, true Cauchy stress.

Pure functions (no PyQt / OpenCV / hardware) so the app and the offline tools share ONE
implementation and it is unit-testable without a camera.

Marker layout for Poisson/Cauchy = a PLUS / DIAMOND of 4 dots: the existing 2 axial dots on
the centreline (top & bottom) PLUS 2 transverse dots at mid-height (left & right edge).
classify_markers() labels topmost/bottommost = axial, leftmost/rightmost = transverse.
The 2-marker (axial-only) case is unchanged — transverse is None and no Poisson/Cauchy is produced.
"""
from math import log
from statistics import pstdev

L_TRACK_PX = 100.0     # L_px above this = markers are being tracked (matches utm_analysis)


# ---------- (1) live tracking health ----------
def dic_health(history, blob_history=None, current_blobs=None, expected_markers=2, window=30):
    """Summarise recent DIC tracking for the live badge.
    history: sequence of (timestamp, cauchy, true, L_px, dx_px[, lateral]) (camera_manager.dic_history)
      -> pixel jitter / drift (only frames where markers were actually found land here).
    blob_history: recent per-frame blob COUNTS (ints) -> tracking%. Preferred, because it records
      dropped frames too; if None, tracking% falls back to L_px presence in `history`.
    current_blobs: latest detected blob count, or None if unknown.
    Returns {status, color, tracking_pct, jitter_px, drift_px, markers, expected, n}."""
    recent = list(history)[-window:]
    tracked = [r for r in recent if r[3] > L_TRACK_PX]
    lpx = [r[3] for r in tracked]
    dxs = [r[4] for r in tracked]
    # jitter = frame-to-frame wobble of L_px (differencing removes the slow strain ramp)
    diffs = [lpx[i] - lpx[i - 1] for i in range(1, len(lpx))]
    jitter_px = pstdev(diffs) / (2 ** 0.5) if len(diffs) > 1 else 0.0
    drift_px = (max(dxs) - min(dxs)) if dxs else 0.0
    if blob_history is not None:
        bh = list(blob_history)[-window:]
        n = len(bh)
        tracking_pct = 100.0 * sum(1 for b in bh if b == expected_markers) / n if n else 0.0
    else:
        n = len(recent)
        tracking_pct = 100.0 * len(tracked) / n if n else 0.0
    if n == 0:
        return {"status": "NO DATA", "color": "#8a8f98", "tracking_pct": 0.0,
                "jitter_px": 0.0, "drift_px": 0.0, "markers": current_blobs,
                "expected": expected_markers, "n": 0}
    markers_ok = (current_blobs is None) or (current_blobs == expected_markers)
    if not markers_ok or tracking_pct < 70:
        status, color = "BAD", "#e74c3c"
    elif tracking_pct < 95 or jitter_px > 1.5:
        status, color = "WARN", "#f39c12"
    else:
        status, color = "OK", "#2ecc71"
    return {"status": status, "color": color, "tracking_pct": tracking_pct,
            "jitter_px": jitter_px, "drift_px": drift_px, "markers": current_blobs,
            "expected": expected_markers, "n": n}


def health_text(h):
    """One-line badge label from a dic_health() dict."""
    m = "?" if h["markers"] is None else h["markers"]
    return (f"DIC {h['status']} · {m}/{h['expected']} · "
            f"track {h['tracking_pct']:.0f}% · jitter {h['jitter_px']:.1f}px")


# ---------- (2) multi-marker geometry: lateral strain / Poisson / Cauchy ----------
def classify_markers(centroids):
    """centroids: list of (cx, cy). Returns {'axial': (top, bottom), 'transverse': (left,right)|None}.
    Axial = topmost & bottommost (max vertical span); transverse = leftmost & rightmost (needs >=4)."""
    pts = [(float(x), float(y)) for x, y in centroids]
    if len(pts) < 2:
        return None
    by_y = sorted(pts, key=lambda p: p[1])
    out = {"axial": (by_y[0], by_y[-1]), "transverse": None}
    if len(pts) >= 4:
        by_x = sorted(pts, key=lambda p: p[0])
        out["transverse"] = (by_x[0], by_x[-1])
    return out


def dic_strain(l_px, l0_px):
    """THE pixel-to-strain conversion. Returns (cauchy, true).

    Every strain this project reports comes through here — the live rig via
    camera_manager.calculate_dic_strain(), and the offline video post-processor via
    utm_postproc. That is deliberate: strain is a PIXEL RATIO and contains no gauge length, no
    calibration and no physical unit, so there is nothing about it that should differ between a
    live pull and the same pull replayed from its recording. Two copies of three lines would be
    enough to drift, and this project has already lost curves to a duplicated analysis rule.

        cauchy = (L - L0) / L0        engineering / Cauchy, the CSV's DIC_Cauchy column
        true   = ln(L / L0)           log strain, the CSV's DIC_True column

    Returns (0.0, 0.0) rather than raising when the inputs cannot produce a strain, matching the
    live path: a dropout must read as "no reading", never as a confident zero-length marker pair.
    """
    if not l0_px or l0_px <= 0 or l_px is None or l_px <= 0:
        return 0.0, 0.0
    return (l_px - l0_px) / l0_px, log(l_px / l0_px)


def px_per_mm(l0_px, gauge_mm):
    """Scale factor, from the same pair that sets L0 — mirrors camera_manager.tare_dic()."""
    if not gauge_mm or gauge_mm <= 0 or not l0_px or l0_px <= 0:
        return None
    return l0_px / gauge_mm


def axial_distance_px(axial_pair):
    (_, y0), (_, y1) = axial_pair
    return abs(y1 - y0)


def transverse_distance_px(transverse_pair):
    (x0, _), (x1, _) = transverse_pair
    return abs(x1 - x0)


def lateral_strain(w_px, w0_px):
    """Transverse (width) strain — negative in tension as the specimen narrows."""
    return (w_px - w0_px) / w0_px if w0_px else 0.0


def poisson_ratio(eps_axial, eps_lateral):
    """nu = -eps_lateral / eps_axial. None when axial strain is ~0 (undefined)."""
    if eps_axial is None or abs(eps_axial) < 1e-6:
        return None
    return -eps_lateral / eps_axial


def current_area(area0, eps_lateral):
    """Current cross-section from measured lateral strain, assuming through-thickness strain
    equals the measured in-plane transverse strain (isotropic): A = A0 (1 + eps_lateral)^2."""
    return area0 * (1.0 + eps_lateral) ** 2


def cauchy_stress(force_N, area0_mm2, eps_lateral):
    """True (Cauchy) stress in MPa = F / current area, using the measured lateral contraction."""
    a = current_area(area0_mm2, eps_lateral)
    return force_N / a if a > 0 else 0.0


def poisson_cauchy(centroids, w0_px, force_N, area0_mm2, l0_px=None):
    """From >=4 markers -> lateral strain, Poisson (if l0_px given), current area and Cauchy stress.
    Returns None if fewer than 4 usable markers (so callers fall back to axial-only / nominal area)."""
    cls = classify_markers(centroids)
    if cls is None or cls["transverse"] is None:
        return None
    w = transverse_distance_px(cls["transverse"])
    eps_lat = lateral_strain(w, w0_px)
    eps_ax = ((axial_distance_px(cls["axial"]) - l0_px) / l0_px) if l0_px else None
    return {"eps_lateral": eps_lat, "eps_axial": eps_ax,
            "poisson": poisson_ratio(eps_ax, eps_lat),
            "area_mm2": current_area(area0_mm2, eps_lat),
            "cauchy_MPa": cauchy_stress(force_N, area0_mm2, eps_lat), "w_px": w}


def _selftest():
    # (1) health: clean vs dropped-out tracking
    ok = [(i, 0.001 * i, 0, 1665 + (0.3 if i % 2 else -0.3), 2.0) for i in range(30)]
    bad = [(i, 0.0, 0, (1665 if i % 3 else 0.0), 2.0) for i in range(30)]   # 1/3 dropout
    ho, hb = dic_health(ok, current_blobs=2), dic_health(bad, current_blobs=2)
    print("health OK :", health_text(ho))
    print("health BAD:", health_text(hb))
    assert ho["status"] == "OK" and hb["status"] == "BAD", "health status"
    assert dic_health([], current_blobs=0)["status"] == "NO DATA"
    assert dic_health(ok, current_blobs=1)["status"] == "BAD", "missing marker -> BAD"
    # blob_history path: half the frames drop to 1 marker -> ~50% tracking -> BAD
    bh = [2 if i % 2 else 1 for i in range(30)]
    hbh = dic_health(ok, blob_history=bh, current_blobs=2)
    assert hbh["tracking_pct"] < 60 and hbh["status"] == "BAD", "blob_history tracking"

    # (2) geometry: stretch 5% axial, contract with true nu=0.35 -> lateral -1.75%
    L0, w0, nu_true, eps_ax = 1665.0, 400.0, 0.35, 0.05
    Lp = L0 * (1 + eps_ax)
    w = w0 * (1 - nu_true * eps_ax)
    cx, y_top = 500.0, 200.0
    cents = [(cx, y_top), (cx, y_top + Lp),                    # axial (top, bottom)
             (cx - w / 2, y_top + Lp / 2), (cx + w / 2, y_top + Lp / 2)]   # transverse (L, R)
    pc = poisson_cauchy(cents, w0, force_N=1000.0, area0_mm2=80.0, l0_px=L0)
    eng = 1000.0 / 80.0
    print(f"geom: eps_lat={pc['eps_lateral']:.4f} (exp {-nu_true*eps_ax:.4f}), "
          f"nu={pc['poisson']:.3f} (exp {nu_true}), area={pc['area_mm2']:.3f} mm2 (<80), "
          f"cauchy={pc['cauchy_MPa']:.3f} MPa (> eng {eng:.3f})")
    assert abs(pc["poisson"] - nu_true) < 1e-6, "poisson"
    assert pc["area_mm2"] < 80.0 and pc["cauchy_MPa"] > eng, "area shrinks -> cauchy > eng"
    assert poisson_cauchy(cents[:2], w0, 1000, 80, L0) is None, "2 markers -> None"
    print("all utm_dic self-tests passed.")


if __name__ == "__main__":
    _selftest()
