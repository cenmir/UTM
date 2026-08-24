"""Shared tensile-test analysis for the UTM DIC rig — the SINGLE source of truth for
fracture detection, force-anchor self-calibration, and engineering properties
(E, sigma_y, UTS, failure strain, toughness).

Used offline by the analysis/deck scripts and (later) live by the app, so the fracture
detector and property maths exist in exactly ONE place. Extracted from v6_compare.py,
folding in the V5-S4 unphysical-strain-jump guard from v6_fracture_montage.py.

No app / matplotlib / hardware dependencies — pure functions on a list of sample dicts.
"""
from statistics import mean, median

DEFAULT_AREA = 80.0      # mm^2  (nominal cross-section)
DEFAULT_GAUGE = 80.0     # mm    (DIC gauge length)


def read_csv(path):
    """Read a UTM test CSV (skips '#' comment/metadata lines, name-indexes columns).
    Returns a list of dict rows with float t, F, pos, ec, et, lpx. Rows that fail to
    parse are skipped; missing DIC_True / L_px default to 0.0."""
    rows = [l.strip() for l in open(path, newline="") if not l.startswith("#") and l.strip()]
    idx = {h: i for i, h in enumerate(rows[0].split(","))}
    out = []
    for row in rows[1:]:
        p = row.split(",")
        try:
            out.append({
                "t": float(p[idx["Time_s"]]),
                "F": float(p[idx["Force_N"]]),
                "pos": float(p[idx["Position_mm"]]),
                "ec": float(p[idx["DIC_Cauchy"]]),
                "et": float(p[idx["DIC_True"]]) if "DIC_True" in idx else 0.0,
                "lpx": float(p[idx["L_px"]]) if "L_px" in idx else 0.0,
                # commanded crosshead speed — the reliable way to spot an intentional HOLD
                # (see find_dwells); older CSVs may not have it, hence the NaN default.
                "spd": float(p[idx["Speed_mm_s"]]) if "Speed_mm_s" in idx else float("nan"),
            })
        except (ValueError, IndexError, KeyError):
            continue
    return out


def read_meta(path):
    """Recover test metadata from the CSV '#' header (area, gauge, comment, calibration,
    date, duration, px_per_mm). Dependency-free — shared by the report and the registry."""
    meta = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("#"):
                break
            s = line[1:].strip()
            low = s.lower()
            try:
                if low.startswith("test date:"):
                    meta["date"] = s.split(":", 1)[1].strip()
                elif low.startswith("duration:"):
                    meta["duration"] = s.split(":", 1)[1].strip()
                elif low.startswith("comment:"):
                    meta["comment"] = s.split(":", 1)[1].strip()
                elif low.startswith("capture:"):
                    # SF11: folder holding this run's DIC frames / video. A Windows path carries a
                    # drive-letter colon, so split on the FIRST colon only and keep the rest.
                    meta["capture"] = s.split(":", 1)[1].strip()
                elif "area:" in low:
                    meta["area"] = float(s.split("Area:", 1)[1].split("mm")[0].strip())
                    if "gauge length:" in low:
                        meta["gauge"] = float(s.split("Gauge Length:", 1)[1].split("mm")[0].strip())
                    if "material:" in low:                     # PLA / PETG / TPU — label + DIC window
                        meta["material"] = s.split("Material:", 1)[1].split(",")[0].strip()
                    if "infill:" in low:                       # recorded label only (not used in any calc)
                        meta["infill"] = s.split("Infill:", 1)[1].split("%")[0].strip()
                elif low.startswith("calibration"):
                    meta["scale"] = s.split("Scale:", 1)[1].split(",")[0].strip()
                    meta["offset"] = s.split("Offset:", 1)[1].strip()
                elif "px_per_mm:" in low:
                    meta["px_per_mm"] = s.split(":", 1)[1].strip()
            except (ValueError, IndexError):
                continue
    return meta


def linfit(xs, ys):
    """Least-squares line fit. Returns (slope, intercept, r2)."""
    n = len(xs); sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    sl = (n * sxy - sx * sy) / (n * sxx - sx * sx); ic = (sy - sl * sx) / n
    ym = sy / n
    ss_tot = sum((y - ym) ** 2 for y in ys)
    r2 = 1 - sum((y - (sl * x + ic)) ** 2 for x, y in zip(xs, ys)) / ss_tot if ss_tot else 0.0
    return sl, ic, r2


def find_fracture(data, mv_i):
    """Fracture index = the EARLIEST of two signatures, so it is robust across brittle
    AND ductile pulls:

      (a) LOAD COLLAPSE — force drops below half the post-motion peak. The primary,
          reliable signature for the energetic 100 % fractures.
      (b) DIC STRAIN-JUMP GUARD — an unphysical one-frame Cauchy-strain jump (> 3 %)
          while both markers are still tracked = the markers flying apart. This catches
          the V5-S4 case where the raw force does NOT drop below half-peak at fracture
          (so load-collapse lands late, on a post-fracture DIC glitch of ec ~ 0.19).

    NOTE: the old marker-separation test (L_px > 1.06*L0) is deliberately NOT used — it
    misfires on ductile specimens whose gauge strain crosses ~6 % during normal drawing.

    THE GUARD COMPARES CONSECUTIVE *TRACKED* SAMPLES, NOT ADJACENT ROWS. A CSV row only
    carries a DIC reading when one was within DIC_STALE_THRESHOLD_MS of that load sample;
    every other row is written with ec = 0.0 and lpx = 0.0. The original test required
    data[i-1] and data[i] to BOTH be tracked, which silently made it a function of how
    densely DIC happened to land in the CSV:

        V5  (2026-06-12)  3057/3057 rows tracked -> 100.0 % adjacent pairs, guard alive
        S24 (2026-08-14)   571/2135 rows tracked ->   7.3 % adjacent pairs, guard DEAD

    On S24 a dropout row sat between the last intact sample and the post-fracture jump, so
    the guard could not see a 10.1-percentage-point strain step. Detection fell through to
    load-collapse, which fires one sample late, and epsilon_f was read from a sample taken
    AFTER the specimen had broken: 17.5 % instead of 7.4 %, and toughness 2.26x too high.

    dt_max keeps this a JUMP test rather than a drift test: 3 % of strain accumulated
    slowly is a ductile specimen drawing, which is exactly what the removed L_px test used
    to misfire on.
    """
    pk = max(range(mv_i, len(data)), key=lambda i: data[i]["F"])
    fr_load = next((i for i in range(pk, len(data)) if data[i]["F"] < 0.5 * data[pk]["F"]),
                   len(data) - 1)

    fr_glitch, prev, dt_max = None, None, 1.0
    for i in range(mv_i + 1, len(data)):
        if data[i]["lpx"] <= 100:               # no DIC on this row - skip, do not reset
            continue
        if prev is not None and data[i]["t"] - data[prev]["t"] <= dt_max \
                and data[i]["ec"] - data[prev]["ec"] > 0.03:
            fr_glitch = i
            break
        prev = i
    return min([fr_load] + ([fr_glitch] if fr_glitch is not None else []))


def _fit_window(test, lo, hi):
    """(strains, stresses) for the samples inside a strain window — the argument pair linfit wants."""
    win = [d for d in test if lo <= d["ecz"] <= hi]
    return [d["ecz"] for d in win], [d["sig"] for d in win]


# The search that defines E. Bounds chosen so it cannot wander somewhere that is not the modulus:
E_SEARCH_MAX = 0.02          # never look above 2 % strain — past that is plastic on this material
E_SEARCH_MIN_SPAN = 0.0025   # a window narrower than 0.25 % strain fits noise, not a slope
E_SEARCH_R2 = 0.999          # "straight" has to mean straight before "steepest" is allowed to pick
E_SEARCH_MIN_PTS = 25
# ...but an ABSOLUTE floor alone splits the dataset in two. The older 50 % runs are noisier and no
# window on them reaches 0.999, so they would fall back to the fixed window while the clean runs
# got the new rule — two rules over one dataset, which is worse than either rule applied
# consistently. The floor is therefore relative as well: accept anything within this margin of the
# straightest window the record can actually offer, so "as straight as this record allows" means
# the same thing on a clean run and a noisy one.
E_SEARCH_R2_MARGIN = 0.0005


def _steepest_straight_run(test):
    """The steepest genuinely-straight stretch below E_SEARCH_MAX. (slope, intercept, R2, lo, hi).

    Every candidate window is fitted in O(1) from prefix sums rather than by re-summing its points.
    That matters: this runs behind the app's Generate-report button, and the naive version took
    about 5 s per test — long enough to feel like a hang. Same arithmetic, ~50x faster.

    Returns None only when the record is too short to search at all, which the caller handles by
    falling back to the fixed window rather than inventing a modulus.
    """
    pts = [d for d in test if d["ecz"] <= E_SEARCH_MAX]
    n = len(pts)
    if n < E_SEARCH_MIN_PTS * 2:
        return None
    xs = [d["ecz"] for d in pts]
    ys = [d["sig"] for d in pts]
    cx = [0.0] * (n + 1); cy = [0.0] * (n + 1)
    cxx = [0.0] * (n + 1); cxy = [0.0] * (n + 1); cyy = [0.0] * (n + 1)
    for i, (xi, yi) in enumerate(zip(xs, ys)):
        cx[i + 1] = cx[i] + xi
        cy[i + 1] = cy[i] + yi
        cxx[i + 1] = cxx[i] + xi * xi
        cxy[i + 1] = cxy[i] + xi * yi
        cyy[i + 1] = cyy[i] + yi * yi

    def _fit(i, j):
        """OLS over pts[i:j] from the prefix sums. (slope, intercept, R2) or None."""
        m = j - i
        sx = cx[j] - cx[i]; sy = cy[j] - cy[i]
        sxx = cxx[j] - cxx[i]; sxy = cxy[j] - cxy[i]; syy = cyy[j] - cyy[i]
        den = m * sxx - sx * sx
        if den <= 0:
            return None
        slope = (m * sxy - sx * sy) / den
        ic = (sy - slope * sx) / m
        ss_tot = syy - sy * sy / m
        if ss_tot <= 0:
            return None
        ss_res = syy - ic * sy - slope * sxy        # the OLS identity, no second pass needed
        return slope, ic, 1.0 - ss_res / ss_tot

    def _scan(accept):
        best = None
        for i in range(n - E_SEARCH_MIN_PTS):
            if xs[i] > E_SEARCH_MAX - E_SEARCH_MIN_SPAN:
                break
            for j in range(i + E_SEARCH_MIN_PTS, n + 1):
                if xs[j - 1] - xs[i] < E_SEARCH_MIN_SPAN:
                    continue
                f = _fit(i, j)
                if f is None:
                    continue
                cand = accept(f, i, j, best)
                if cand is not None:
                    best = cand
        return best

    # Pass 1: how straight can this record get at all?
    top = _scan(lambda f, i, j, b: (f[2],) if (b is None or f[2] > b[0]) else None)
    if top is None:
        return None
    floor = min(E_SEARCH_R2, top[0] - E_SEARCH_R2_MARGIN)
    # Pass 2: among windows that straight, the steepest one.
    best = _scan(lambda f, i, j, b:
                 (f[0], f[1], f[2], xs[i], xs[j - 1]) if (f[2] >= floor and (b is None or f[0] > b[0]))
                 else None)
    return best


def analyze(source, area=DEFAULT_AREA, gauge=DEFAULT_GAUGE):
    """Full tensile analysis of one test. `source` is a CSV path OR an already-read list
    of sample dicts. Returns a dict of engineering properties:

        anchor    N     force-anchor self-calibration (= -mean post-fracture force)
        E         GPa   elastic modulus (linfit over ec in [0.0005, 0.004])
        E_R2      -     R^2 of the elastic fit
        sy        MPa   0.2 %-offset yield stress
        uts       MPa   ultimate tensile strength (engineering stress = (F+anchor)/nominal area)
        uts_F     N     true force at UTS
        ef        -     failure strain (last tracked DIC Cauchy, baseline-rezeroed)
        sigf      MPa   fracture stress
        soft      %     post-UTS softening = (UTS - sigf)/UTS
        tough     kJ/m3 toughness = integral sigma d(epsilon)
        travel    mm    crosshead travel at fracture
        gauge_share %   DIC gauge stretch / crosshead travel
        dur       s     pull duration
        rate      mm/s  mean crosshead rate during the pull
        fr_i,mv_i -     fracture / motion-start sample indices
    """
    data = read_csv(source) if isinstance(source, str) else source
    base_pos = sorted(d["pos"] for d in data[:30])[15]
    mv_i = next(i for i, d in enumerate(data) if d["pos"] > base_pos + 0.005)
    t0 = data[mv_i]["t"]
    ec0_list = [d["ec"] for d in data[:mv_i] if d["lpx"] > 100]
    ec0 = median(ec0_list) if ec0_list else 0.0

    fr_i = find_fracture(data, mv_i)
    t_fr = data[fr_i]["t"]
    pre = data[:fr_i]
    post = [d for d in data[fr_i + 1:] if d["t"] > t_fr + 2.0 and d["lpx"] > 100]
    if not post:                                   # DIC dropped out post-fracture -> force only
        post = [d for d in data[fr_i + 1:] if d["t"] > t_fr + 2.0]
    anchor = -mean(d["F"] for d in post) if post else 0.0

    for d in data:
        d["sig"] = (d["F"] + anchor) / area
        d["Ftrue"] = d["F"] + anchor
        d["ecz"] = d["ec"] - ec0
        d["etz"] = d["et"] - ec0
        d["travel"] = d["pos"] - base_pos

    test = [d for d in pre[mv_i:] if d["lpx"] > 100]
    uts = max(test, key=lambda d: d["sig"])

    # PHYSICAL BACKSTOP on the fracture sample, independent of how it was chosen.
    #
    # Strain is a ratio; multiply it back into millimetres and it must fit inside what the
    # machine actually did. The 80 mm gauge cannot stretch further than the crosshead
    # travelled, because the crosshead moved the grips, the load train, the frame AND the
    # specimen. Any sample claiming otherwise is measuring two separated halves, not
    # material — so walk back to the last tracked sample that is physically possible.
    #
    # On S24 this alone would have caught it: 17.5 % of 80 mm is 14.04 mm of gauge stretch
    # against 9.35 mm of total travel. analyze() was already REPORTING that as
    # gauge_share = 150 %; nothing was acting on it.
    test.sort(key=lambda d: d["t"])
    dropped = 0
    while len(test) > 1 and test[-1]["travel"] > 0 \
            and (test[-1]["ec"] - ec0) * gauge > test[-1]["travel"]:
        test.pop()
        dropped += 1
    last = test[-1]
    # ---- Young's modulus -------------------------------------------------------------------
    # The fixed 0.05-0.40 % window is kept and reported, but it is no longer what E means.
    #
    # It assumes every specimen's curve is straight in the same place, and ours are not: the local
    # slope rises through the first half-percent before yielding takes it down, and how far it has
    # risen by 0.40 % differs specimen to specimen. Measured over every 100 % infill run on record
    # (n = 11, documentation/e_fit_data.py) the fixed window scatters 13.2 % and sits 7 % under the
    # material datasheet, while the STEEPEST GENUINELY-STRAIGHT stretch scatters 8.5 % and lands
    # +5 %. Winning on repeatability and on datasheet agreement at the same time is what rules out
    # noise-chasing — a rule chasing noise would raise scatter, not lower it.
    #
    # Steepest, not straightest: maximising R2 alone also rewards the compliant toe and the early
    # yield knee, both of which are smooth and neither of which is the modulus. Require the fit to
    # be straight FIRST, then take the steepest survivor.
    E_fixed, c1_fixed, r1_fixed = linfit(*_fit_window(test, 0.0005, 0.004))
    steep = _steepest_straight_run(test)
    if steep is None:                      # too few points to search — fall back, and say so
        E, c1, r1, e_lo, e_hi = E_fixed, c1_fixed, r1_fixed, 0.0005, 0.004
        E_method = "fixed 0.05-0.40 % (fallback: no straight run found)"
    else:
        E, c1, r1, e_lo, e_hi = steep
        E_method = f"steepest straight run {e_lo*100:.2f}-{e_hi*100:.2f} %"
    sy = next(d for d in test if E * (d["ecz"] - 0.002) + c1 >= d["sig"])
    gauge_stretch = last["ecz"] * gauge
    tough = 0.0; prev = None
    for d in test:
        if prev and d["ecz"] > prev["ecz"]:
            tough += 0.5 * (d["sig"] + prev["sig"]) * (d["ecz"] - prev["ecz"])
        prev = d
    curve = [(d["ecz"] * 100, d["sig"]) for d in test if d["ecz"] > -0.002]   # (strain %, stress) for plots

    return {
        "anchor": anchor, "E": E / 1000, "E_R2": r1, "sy": sy["sig"],
        # The fixed-window value is kept so every historical number stays recoverable from the
        # same call, and so a run can be re-stated on the old basis without re-deriving it.
        "E_fixed": E_fixed / 1000, "E_fixed_R2": r1_fixed,
        "E_lo": e_lo * 100, "E_hi": e_hi * 100, "E_method": E_method,
        "uts": uts["sig"], "uts_F": uts["Ftrue"], "ef": last["ecz"],
        "sigf": last["sig"], "soft": (uts["sig"] - last["sig"]) / uts["sig"] * 100,
        "tough": tough * 1000, "travel": last["travel"],
        "gauge_share": gauge_stretch / last["travel"] * 100 if last["travel"] else 0.0,
        "dur": last["t"] - t0,
        "rate": (data[fr_i]["pos"] - data[mv_i]["pos"]) / (t_fr - t0) if (t_fr - t0) else 0.0,
        "uts_ec": uts["ecz"] * 100, "sy_ec": sy["ecz"] * 100, "c1": c1,
        "curve": curve, "fr_i": fr_i, "mv_i": mv_i, "ef_backstepped": dropped,
    }


class LiveFractureDetector:
    """Incremental, sample-by-sample version of find_fracture() for LIVE use in the app
    (Phase A auto-halt). Feed each load sample as it arrives; returns True once fracture
    is detected. Not wired into the app yet — provided so live and offline share one
    detector.

        det = LiveFractureDetector()
        if det.update(force, ec=dic_cauchy, lpx=dic_L_px):
            # fracture -> halt motor, start post-fracture anchor hold

    - Arms only after the load has built past `arm_frac` of the running peak (so the
      toe / grip-seating region cannot trigger it).
    - Fires on load collapse below `collapse_frac` of the running peak, OR on an
      unphysical one-frame DIC strain jump (> `ec_jump`) while both markers track AND
      the load has already fallen below `jump_load_frac` of the peak — a broken
      specimen cannot still be carrying its peak force.
    """

    def __init__(self, collapse_frac=0.5, arm_frac=0.3, ec_jump=0.03, jump_load_frac=0.9):
        self.collapse_frac = collapse_frac
        self.arm_frac = arm_frac
        self.ec_jump = ec_jump
        self.jump_load_frac = jump_load_frac
        self.peak = 0.0
        self.armed = False
        self.fired = False
        self._prev_ec = None
        self._prev_lpx = None

    def update(self, force, ec=None, lpx=None):
        if self.fired:
            return True
        if force > self.peak:
            self.peak = force
        if self.peak > 0 and force >= self.arm_frac * self.peak:
            self.armed = True
        # A DIC jump only counts as fracture if the LOAD agrees. A specimen that has broken cannot
        # still be at its peak force, so a strain jump while the load is holding up is a tracking
        # fault, not a fracture.
        #
        # S29 (PETG, 2026-08-19) is why this qualifier exists. The detector momentarily picked up a
        # mount edge instead of a speckle dot; L_px moved 1722 -> 1858 px in one frame and ec went
        # 0.029 -> 0.109, a jump of 0.081 against the 0.03 threshold. It fired at 2931 N — the peak
        # — and auto-stopped a test on an INTACT specimen, which then sat relaxing 2909 -> 2726 N
        # for 19 s with the crosshead frozen. The run was lost at 36.6 MPa, well short of failure.
        #
        # `armed` is deliberately still not required: a genuine brittle fracture can arrive before
        # the load has built to arm_frac of a peak it never reached. The load qualifier is the
        # narrower and better-founded gate.
        if (ec is not None and lpx is not None and self._prev_ec is not None
                and self._prev_lpx is not None and lpx > 100 and self._prev_lpx > 100
                and ec - self._prev_ec > self.ec_jump
                and self.peak > 0 and force < self.jump_load_frac * self.peak):
            self.fired = True
        if self.armed and self.peak > 0 and force < self.collapse_frac * self.peak:
            self.fired = True
        self._prev_ec, self._prev_lpx = ec, lpx
        return self.fired


def find_dwells(data, min_s=5.0, min_load=50.0, upto_peak=True):
    """Locate the intentional HOLDs in a staircase / staircase-to-fracture run and measure the
    stress relaxation at each.

    Detect on the COMMANDED speed (`spd == 0`), not on a position-gradient threshold. A tapered
    approach crawls at 0.02 mm/s, which a gradient cut-off cannot separate from a true hold: on
    rig run T7.2 a `|d(pos)/dt| < 0.004` rule silently missed 3 of the 8 levels — and those were
    the levels that carried the yield signal. Falls back to the gradient rule only for older CSVs
    with no Speed_mm_s column.

    Returns a list of dicts: level (1-based), t_start, dwell_s, arrive (N), end (N),
    drop (N), drop_pct — the drop as a % of the arrival load.

    Reading it: drop_pct FALLS through the elastic region, reaches a minimum, then CLIMBS once a
    level passes yield. That turning point is the yield onset (T7.2: min 1.60 % at 694 N tared,
    rising to 3.23 % by 1165 N)."""
    if not data:
        return []
    peak_i = max(range(len(data)), key=lambda i: data[i]["F"]) if upto_peak else len(data) - 1
    have_spd = any(d.get("spd") == d.get("spd") for d in data)      # any non-NaN
    if have_spd:
        held = [i for i in range(peak_i + 1)
                if data[i].get("spd") == 0.0 and data[i]["F"] > min_load]
    else:
        held = []
        for i in range(1, peak_i + 1):
            dt = data[i]["t"] - data[i - 1]["t"]
            if dt > 0 and abs(data[i]["pos"] - data[i - 1]["pos"]) / dt < 0.004 \
                    and data[i]["F"] > min_load:
                held.append(i)
    out, run = [], []
    for i in held + [None]:
        if run and (i is None or i != run[-1] + 1):
            a, b = run[0], run[-1]
            dur = data[b]["t"] - data[a]["t"]
            if dur >= min_s:
                arrive, end = data[a]["F"], data[b]["F"]
                out.append({"level": len(out) + 1, "t_start": data[a]["t"], "dwell_s": dur,
                            "arrive": arrive, "end": end, "drop": arrive - end,
                            "drop_pct": (100.0 * (arrive - end) / arrive) if arrive else 0.0})
            run = []
        if i is not None:
            run.append(i)
    return out


def yield_onset(dwells):
    """The level at which drop_pct stops falling and starts climbing = yield onset.
    Returns that dwell dict, or None if there are too few levels / it never turns."""
    if len(dwells) < 3:
        return None
    pcts = [d["drop_pct"] for d in dwells]
    lo = min(range(len(pcts)), key=lambda i: pcts[i])
    if lo == 0 or lo == len(pcts) - 1:
        return None                     # monotonic -> no resolvable knee in this range
    return dwells[lo]
