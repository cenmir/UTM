"""8.6.3 staircase analysis — DIC linearity vs commanded displacement.

Reads a staircase CSV (multiple 0.1 mm steps with holds between), auto-detects
the hold phases, tabulates per-step statistics, fits ε_c vs Position and ε_c vs
Motor_Strain, and applies the 8.6.3 pass criteria:

  1. ε_c monotonic with Position on the ascending sweep
  2. Linear-fit R^2 > 0.99
  3. Fitted slope matches V2 transfer ratio 0.077 within +/- 10 %
  4. Reversibility: descending sweep within 5*10^-4 of ascending at same Position
  5. Smallest step (+0.1 mm, expected eps_c ~ 7.7*10^-5) distinguishable from noise

Usage:
  python staircase_analysis.py <path-to-csv>

If no path is given, uses a default filename pattern in the project root.
"""

import csv
import math
import os
import sys
from statistics import mean, stdev

V2_TRANSFER_RATIO = 0.077  # V2 steady-state DIC/Motor (post-shakedown)


def read_csv(path):
    rows = []
    with open(path, newline="") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            rows.append(line.strip())
    header = rows[0].split(",")
    idx = {h: i for i, h in enumerate(header)}
    out = []
    for row in rows[1:]:
        parts = row.split(",")
        try:
            out.append({
                "t":   float(parts[idx["Time_s"]]),
                "F":   float(parts[idx["Force_N"]]),
                "pos": float(parts[idx["Position_mm"]]),
                "sp":  float(parts[idx["Speed_mm_s"]]),
                "ms":  float(parts[idx["Motor_Strain"]]),
                "ec":  float(parts[idx["DIC_Cauchy"]]),
                "et":  float(parts[idx["DIC_True"]]),
                "lpx": float(parts[idx["L_px"]]),
            })
        except (ValueError, IndexError):
            continue
    return out


def detect_holds(data, min_hold_s=2.0, pos_tol=0.005, speed_tol=0.01):
    """Return list of (i0, i1, mean_pos) for each hold phase.
    A hold = contiguous run of >= min_hold_s where |Speed| < speed_tol and
    Position changes by < pos_tol over the window."""
    holds = []
    i = 0
    n = len(data)
    while i < n:
        if abs(data[i]["sp"]) >= speed_tol:
            i += 1
            continue
        j = i
        start_pos = data[i]["pos"]
        while j < n and abs(data[j]["sp"]) < speed_tol and abs(data[j]["pos"] - start_pos) < pos_tol:
            j += 1
        duration = data[j - 1]["t"] - data[i]["t"]
        if duration >= min_hold_s:
            mean_pos = sum(d["pos"] for d in data[i:j]) / (j - i)
            holds.append((i, j - 1, mean_pos))
        i = j
    return holds


def step_stats(data, i0, i1, skip_first_s=0.5):
    """Mean/std of channels within hold window, skipping initial settle."""
    t_start = data[i0]["t"]
    samples = [d for d in data[i0:i1 + 1]
               if d["t"] - t_start >= skip_first_s and abs(d["ec"]) > 1e-6]
    if len(samples) < 3:
        samples = data[i0:i1 + 1]
    return {
        "n": len(samples),
        "pos_mean": mean(d["pos"] for d in samples),
        "ms_mean":  mean(d["ms"] for d in samples),
        "ec_mean":  mean(d["ec"] for d in samples),
        "ec_std":   stdev(d["ec"] for d in samples) if len(samples) > 1 else 0.0,
        "et_mean":  mean(d["et"] for d in samples),
        "F_mean":   mean(d["F"] for d in samples),
        "dur":      data[i1]["t"] - data[i0]["t"],
    }


def linfit(xs, ys):
    n = len(xs)
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if denom == 0:
        return float("nan"), float("nan"), float("nan")
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    ymean = sy / n
    ss_tot = sum((y - ymean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")
    return slope, intercept, r2


def find_default_csv():
    candidates = [f for f in os.listdir(".") if "Staircase" in f and f.endswith(".csv")]
    if candidates:
        candidates.sort()
        return candidates[-1]
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else find_default_csv()
    if not path or not os.path.exists(path):
        print(f"No staircase CSV found. Pass one as: python staircase_analysis.py <file.csv>")
        sys.exit(1)
    print(f"Reading: {path}")
    data = read_csv(path)
    print(f"Rows: {len(data)}  duration: {data[-1]['t'] - data[0]['t']:.1f} s")

    holds = detect_holds(data, min_hold_s=2.0, pos_tol=0.005, speed_tol=0.01)
    print(f"\nDetected {len(holds)} hold phases:\n")

    stats = []
    for k, (i0, i1, p) in enumerate(holds):
        s = step_stats(data, i0, i1)
        stats.append(s)
        print(f"  step {k:2d}  t={data[i0]['t']:6.1f}->{data[i1]['t']:6.1f}s  "
              f"dur={s['dur']:5.1f}s  pos={s['pos_mean']:+7.4f} mm  "
              f"F={s['F_mean']:+8.2f} N  ms={s['ms_mean']:+8.5f}  "
              f"eps_c={s['ec_mean']:+10.6f}  std={s['ec_std']:.6f}  n={s['n']}")

    # Split into ascending vs descending sweeps (find the max-position step)
    max_idx = max(range(len(stats)), key=lambda i: abs(stats[i]["pos_mean"]))
    asc = stats[:max_idx + 1]
    desc = stats[max_idx:]

    print(f"\nAscending sweep: {len(asc)} steps (idx 0..{max_idx})")
    print(f"Descending sweep: {len(desc)} steps (idx {max_idx}..{len(stats)-1})")

    # ----- Criterion 1: monotonicity on ascending sweep -----
    print("\n[1] Monotonicity check (ascending):")
    monotonic = True
    for i in range(1, len(asc)):
        if asc[i]["ec_mean"] < asc[i-1]["ec_mean"] - 1e-5:  # tolerance for noise
            monotonic = False
            print(f"    REVERSAL at step {i}: {asc[i-1]['ec_mean']:+.6f} -> {asc[i]['ec_mean']:+.6f}")
    print(f"    {'PASS' if monotonic else 'FAIL'}")

    # ----- Criterion 2: linearity of ε_c vs Position -----
    xs = [s["pos_mean"] for s in asc]
    ys = [s["ec_mean"] for s in asc]
    slope, intercept, r2 = linfit(xs, ys)
    print(f"\n[2] Linear fit eps_c vs Position (ascending):")
    print(f"    slope = {slope:.6f}  intercept = {intercept:+.6f}  R^2 = {r2:.5f}")
    print(f"    {'PASS' if r2 > 0.99 else 'FAIL'} (criterion: R^2 > 0.99)")

    # ----- Criterion 3: slope match to V2 transfer ratio -----
    ms_xs = [s["ms_mean"] for s in asc]
    slope_ms, intercept_ms, r2_ms = linfit(ms_xs, ys)
    deviation_pct = abs(slope_ms - V2_TRANSFER_RATIO) / V2_TRANSFER_RATIO * 100
    print(f"\n[3] Linear fit eps_c vs Motor_Strain (ascending):")
    print(f"    slope = {slope_ms:.5f}  (V2 reference = {V2_TRANSFER_RATIO})  "
          f"deviation = {deviation_pct:.1f} %  R^2 = {r2_ms:.5f}")
    print(f"    {'PASS' if deviation_pct < 10 else 'FAIL'} (criterion: within 10 %)")

    # ----- Criterion 4: reversibility -----
    print("\n[4] Reversibility (asc vs desc at matched Position):")
    matched_diff = []
    for s_a in asc:
        # find closest descending step
        s_d = min(desc, key=lambda s: abs(s["pos_mean"] - s_a["pos_mean"]))
        if abs(s_d["pos_mean"] - s_a["pos_mean"]) > 0.05:
            continue
        diff = s_d["ec_mean"] - s_a["ec_mean"]
        matched_diff.append((s_a["pos_mean"], diff))
        print(f"    pos={s_a['pos_mean']:+7.4f}  asc={s_a['ec_mean']:+.6f}  "
              f"desc={s_d['ec_mean']:+.6f}  diff={diff:+.6f}")
    if matched_diff:
        max_abs_diff = max(abs(d) for _, d in matched_diff)
        print(f"    max |asc - desc| = {max_abs_diff:.6f}")
        print(f"    {'PASS' if max_abs_diff < 5e-4 else 'CHECK'} (criterion: < 5e-4)")

    # ----- Criterion 5: smallest step distinguishable from noise -----
    print("\n[5] DIC noise floor vs smallest step:")
    if len(stats) >= 2:
        step1_ec = stats[1]["ec_mean"] - stats[0]["ec_mean"]
        baseline_std = stats[0]["ec_std"]
        snr = abs(step1_ec) / baseline_std if baseline_std > 0 else float("inf")
        print(f"    First step delta eps_c = {step1_ec:+.6f}")
        print(f"    Baseline eps_c std       = {baseline_std:.6f}")
        print(f"    SNR                   = {snr:.1f}")
        print(f"    {'PASS' if snr > 3 else 'WEAK'} (criterion: SNR > 3)")

    print("\n=== Summary ===")
    print(f"Slope (eps_c vs Motor_Strain) = {slope_ms:.5f}  "
          f"(V2 ref {V2_TRANSFER_RATIO}, deviation {deviation_pct:.1f} %)")
    print(f"R^2 (eps_c vs Position)        = {r2:.5f}")
    print(f"Number of ascending steps      = {len(asc)}")
    print(f"Number of descending steps     = {len(desc)}")


if __name__ == "__main__":
    main()
