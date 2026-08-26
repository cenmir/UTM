"""Side-by-side comparison of V4b (0 N preload) and V4c (+350 N preload).

Reads both CSVs, extracts the staircase hold-phase statistics, and produces:
  - tabulated per-step values
  - per-step Delta eps_c
  - linear fits (full + engaged)
  - 2x2 plot grid: eps_c vs Position, eps_c vs Motor_Strain, force vs Position, residuals
"""

import os
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

V4B = r"Software\UTM_PyQt6\Test data\Smart Features - Advanced Test Modes\8.6.3\UTM_Test_20260605_152501_V4b_Staricase_Tension.csv"
V4C = r"Software\UTM_PyQt6\Test data\Smart Features - Advanced Test Modes\8.6.3\UTM_Test_20260605_164908_V4c_Staircase_Tension_350N.csv"
OUT_PNG = "images/V4/V4b_vs_V4c_comparison.png"


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
            })
        except (ValueError, IndexError):
            continue
    return out


def detect_holds(data, min_hold_s=2.0, pos_tol=0.005, speed_tol=0.01):
    holds = []
    i, n = 0, len(data)
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
            holds.append((i, j - 1))
        i = j
    return holds


def step_stats(data, i0, i1, skip_first_s=2.0):
    """Mean over hold window, skipping first 2 s for viscoelastic settle."""
    t0 = data[i0]["t"]
    samples = [d for d in data[i0:i1 + 1]
               if d["t"] - t0 >= skip_first_s and abs(d["ec"]) > 1e-7]
    if len(samples) < 5:
        samples = data[i0:i1 + 1]
    return {
        "pos":   mean(d["pos"] for d in samples),
        "ms":    mean(d["ms"] for d in samples),
        "ec":    mean(d["ec"] for d in samples),
        "ec_sd": stdev(d["ec"] for d in samples) if len(samples) > 1 else 0.0,
        "F":     mean(d["F"] for d in samples),
        "dur":   data[i1]["t"] - data[i0]["t"],
    }


def linfit(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
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


def extract_staircase(path, label, skip_initial=False):
    """Return list of ascending step stats only (skip pre-staircase baseline if needed)."""
    data = read_csv(path)
    holds = detect_holds(data)
    stats = [step_stats(data, i0, i1) for i0, i1 in holds]
    # For V4c, skip the first hold (pre-test baseline at Pos 0.6 before reset)
    if skip_initial and stats and stats[0]["pos"] > 0.4:
        stats = stats[1:]
    # Find peak position; everything up to peak is ascending
    if not stats:
        return [], []
    peak_idx = max(range(len(stats)), key=lambda i: stats[i]["pos"])
    asc = stats[:peak_idx + 1]
    desc = stats[peak_idx:]
    return asc, desc


# ---- Extract ----
v4b_asc, v4b_desc = extract_staircase(V4B, "V4b")
v4c_asc, v4c_desc = extract_staircase(V4C, "V4c", skip_initial=True)

# ---- Tabulate ----
print("=" * 90)
print("V4b (0 N preload, 0.2 mm steps)")
print("=" * 90)
print(f"{'Sweep':<6}{'Pos':>9}{'F (N)':>10}{'ms':>12}{'eps_c':>13}{'std':>10}")
for s in v4b_asc:
    print(f"{'ASC':<6}{s['pos']:>+9.4f}{s['F']:>+10.2f}{s['ms']:>+12.5f}{s['ec']:>+13.6f}{s['ec_sd']:>10.6f}")
for s in v4b_desc[1:]:
    print(f"{'DESC':<6}{s['pos']:>+9.4f}{s['F']:>+10.2f}{s['ms']:>+12.5f}{s['ec']:>+13.6f}{s['ec_sd']:>10.6f}")

print()
print("=" * 90)
print("V4c (+350 N preload, 0.2 mm steps)")
print("=" * 90)
print(f"{'Sweep':<6}{'Pos':>9}{'F (N)':>10}{'F_true':>10}{'ms':>12}{'eps_c':>13}{'std':>10}")
for s in v4c_asc:
    f_true = s["F"] + 350
    print(f"{'ASC':<6}{s['pos']:>+9.4f}{s['F']:>+10.2f}{f_true:>+10.2f}{s['ms']:>+12.5f}{s['ec']:>+13.6f}{s['ec_sd']:>10.6f}")
for s in v4c_desc[1:]:
    f_true = s["F"] + 350
    print(f"{'DESC':<6}{s['pos']:>+9.4f}{s['F']:>+10.2f}{f_true:>+10.2f}{s['ms']:>+12.5f}{s['ec']:>+13.6f}{s['ec_sd']:>10.6f}")

# ---- Per-step deltas ----
def deltas(stats):
    return [(stats[i]["pos"], stats[i]["ec"] - stats[i-1]["ec"], stats[i]["F"] - stats[i-1]["F"])
            for i in range(1, len(stats))]

print()
print("=" * 90)
print("Per-step Delta eps_c (ascending)")
print("=" * 90)
print(f"{'Step':<7}{'V4b Pos':>10}{'V4b dF':>10}{'V4b deps_c':>14}{'  ||  ':<8}{'V4c Pos':>10}{'V4c dF':>10}{'V4c deps_c':>14}")
v4b_d = deltas(v4b_asc)
v4c_d = deltas(v4c_asc)
nmax = max(len(v4b_d), len(v4c_d))
for k in range(nmax):
    b = v4b_d[k] if k < len(v4b_d) else (None, None, None)
    c = v4c_d[k] if k < len(v4c_d) else (None, None, None)
    bp = f"{b[0]:+.3f}" if b[0] is not None else "    --"
    bf = f"{b[2]:+.0f}" if b[2] is not None else "  --"
    be = f"{b[1]:+.6f}" if b[1] is not None else "      --"
    cp = f"{c[0]:+.3f}" if c[0] is not None else "    --"
    cf = f"{c[2]:+.0f}" if c[2] is not None else "  --"
    ce = f"{c[1]:+.6f}" if c[1] is not None else "      --"
    print(f"{k+1:<7}{bp:>10}{bf:>10}{be:>14}{'  ||  ':<8}{cp:>10}{cf:>10}{ce:>14}")

# ---- Linear fits ----
def fit_section(stats, mask=None):
    pts = [s for s in stats if (mask is None or mask(s))]
    xs = [s["pos"] for s in pts]
    ys = [s["ec"] for s in pts]
    ms = [s["ms"] for s in pts]
    sp, ip, rp = linfit(xs, ys)
    sm, im, rm = linfit(ms, ys)
    return pts, sp, ip, rp, sm, im, rm

print()
print("=" * 90)
print("Linear fits (ascending)")
print("=" * 90)
# V4b full + engaged
b_full = fit_section(v4b_asc)
b_eng  = fit_section(v4b_asc, lambda s: s["pos"] >= 0.35)
print(f"V4b  full (n={len(b_full[0])}):     slope_pos={b_full[1]:+.6f}/mm  R^2={b_full[3]:.4f}  | slope_ms={b_full[4]:.4f}")
print(f"V4b  engaged (n={len(b_eng[0])}):   slope_pos={b_eng[1]:+.6f}/mm  R^2={b_eng[3]:.4f}  | slope_ms={b_eng[4]:.4f}")
# V4c full + excluding pos 0.6
c_full = fit_section(v4c_asc)
c_minus_06 = fit_section(v4c_asc, lambda s: abs(s["pos"] - 0.6) > 0.05)
print(f"V4c  full (n={len(c_full[0])}):     slope_pos={c_full[1]:+.6f}/mm  R^2={c_full[3]:.4f}  | slope_ms={c_full[4]:.4f}")
print(f"V4c  no-Pos0.6 (n={len(c_minus_06[0])}): slope_pos={c_minus_06[1]:+.6f}/mm  R^2={c_minus_06[3]:.4f}  | slope_ms={c_minus_06[4]:.4f}")

# ---- Plot ----
fig, axes = plt.subplots(2, 2, figsize=(15, 11))

# Panel 1: eps_c vs Position
ax = axes[0, 0]
ax.plot([s["pos"] for s in v4b_asc], [s["ec"] for s in v4b_asc], "o-", color="#1f77b4",
        markersize=10, label="V4b ascending (0 N preload)")
ax.plot([s["pos"] for s in v4b_desc[1:]], [s["ec"] for s in v4b_desc[1:]], "o--", color="#1f77b4",
        markersize=8, alpha=0.5, label="V4b descending")
ax.plot([s["pos"] for s in v4c_asc], [s["ec"] for s in v4c_asc], "s-", color="#d62728",
        markersize=10, label="V4c ascending (+350 N preload)")
ax.plot([s["pos"] for s in v4c_desc[1:]], [s["ec"] for s in v4c_desc[1:]], "s--", color="#d62728",
        markersize=8, alpha=0.5, label="V4c descending")
# Fit overlays
xs_b, ys_b = [s["pos"] for s in b_eng[0]], [b_eng[1] * s["pos"] + b_eng[2] for s in b_eng[0]]
ax.plot(xs_b, ys_b, ":", color="#1f77b4", linewidth=2, label=f"V4b engaged fit, R²={b_eng[3]:.3f}")
xs_c, ys_c = [s["pos"] for s in c_minus_06[0]], [c_minus_06[1] * s["pos"] + c_minus_06[2] for s in c_minus_06[0]]
ax.plot(xs_c, ys_c, ":", color="#d62728", linewidth=2, label=f"V4c (no Pos0.6) fit, R²={c_minus_06[3]:.3f}")
ax.axvspan(0, 0.35, color="gray", alpha=0.08, label="V4b slack zone (excluded)")
ax.set_xlabel("Position (mm)", fontsize=11)
ax.set_ylabel("DIC ε_c (Cauchy strain)", fontsize=11)
ax.set_title("ε_c vs Position — both cycles", fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=8)
ax.axhline(0, color="gray", linewidth=0.5)

# Panel 2: eps_c vs Motor_Strain
ax = axes[0, 1]
ax.plot([s["ms"] for s in v4b_asc], [s["ec"] for s in v4b_asc], "o-", color="#1f77b4",
        markersize=10, label="V4b ascending")
ax.plot([s["ms"] for s in v4c_asc], [s["ec"] for s in v4c_asc], "s-", color="#d62728",
        markersize=10, label="V4c ascending")
# V2 reference line
ms_max = max(max(s["ms"] for s in v4b_asc), max(s["ms"] for s in v4c_asc))
ax.plot([0, ms_max], [0, 0.077 * ms_max], "--", color="green", linewidth=1.5, label="V2 whole-ramp slope = 0.077")
ax.plot([0, ms_max], [0, b_eng[4] * ms_max], ":", color="#1f77b4", linewidth=1.5, label=f"V4b engaged slope = {b_eng[4]:.3f}")
ax.plot([0, ms_max], [0, c_minus_06[4] * ms_max], ":", color="#d62728", linewidth=1.5, label=f"V4c (no Pos0.6) slope = {c_minus_06[4]:.3f}")
ax.set_xlabel("Motor_Strain", fontsize=11)
ax.set_ylabel("DIC ε_c", fontsize=11)
ax.set_title("ε_c vs Motor_Strain — slope comparison", fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=8)
ax.axhline(0, color="gray", linewidth=0.5)

# Panel 3: Force vs Position
ax = axes[1, 0]
ax.plot([s["pos"] for s in v4b_asc], [s["F"] for s in v4b_asc], "o-", color="#1f77b4",
        markersize=10, label="V4b ASC (display)")
ax.plot([s["pos"] for s in v4c_asc], [s["F"] for s in v4c_asc], "s-", color="#d62728",
        markersize=10, label="V4c ASC (display)")
ax.plot([s["pos"] for s in v4c_asc], [s["F"] + 350 for s in v4c_asc], "s:", color="#d62728",
        markersize=8, alpha=0.6, label="V4c ASC (true, +350 N preload)")
ax.set_xlabel("Position (mm)", fontsize=11)
ax.set_ylabel("Force (N)", fontsize=11)
ax.set_title("Force vs Position — rig stiffness", fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=9)
ax.axhline(0, color="gray", linewidth=0.5)

# Panel 4: Per-step Delta eps_c
ax = axes[1, 1]
v4b_steps = list(range(1, len(v4b_d) + 1))
v4c_steps = list(range(1, len(v4c_d) + 1))
ax.bar([x - 0.18 for x in v4b_steps], [d[1] for d in v4b_d], width=0.36, color="#1f77b4",
       alpha=0.8, label="V4b per-step Δε_c")
ax.bar([x + 0.18 for x in v4c_steps], [d[1] for d in v4c_d], width=0.36, color="#d62728",
       alpha=0.8, label="V4c per-step Δε_c")
ax.axhline(0.0002, color="gray", linewidth=1, linestyle="--", label="Expected ~+0.0002 (ideal)")
ax.set_xlabel("Step number", fontsize=11)
ax.set_ylabel("Δε_c per step", fontsize=11)
ax.set_title("Per-step Δε_c — consistency check", fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3, axis="y")
ax.legend(loc="upper left", fontsize=9)
ax.axhline(0, color="gray", linewidth=0.5)

plt.suptitle("V4b (no preload) vs V4c (+350 N preload) — DIC linearity comparison",
             fontsize=14, fontweight="bold", y=1.00)
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=140, bbox_inches="tight")
print(f"\nPlot saved: {OUT_PNG}")
