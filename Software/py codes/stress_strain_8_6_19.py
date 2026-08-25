"""8.6.19 — Stress-strain pairing & apparent modulus (elastic regime).

Re-uses V4b + V4c CSVs from 8.6.3. Computes engineering stress at each hold
(F / 80 mm²), pairs it with mean DIC ε_c, fits a linear regression on the
engaged subset of each cycle, and reports apparent E vs PLA literature.

Outputs:
  - tabulated stress / strain per step
  - linear fit on engaged subset for each cycle
  - apparent E (GPa)
  - R² and pass-fail against 8.6.19 criteria
  - σ–ε plot for presentation
"""

import os
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

V4B = r"Software\UTM_PyQt6\8.6.3\UTM_Test_20260605_152501_V4b_Staricase_Tension.csv"
V4C = r"Software\UTM_PyQt6\8.6.3\UTM_Test_20260605_164908_V4c_Staircase_Tension_350N.csv"

GAUGE_AREA_MM2 = 80.0
V4C_PRELOAD = 350.0  # N — tared out, must be added back for true stress

PLA_E_MIN_GPA = 3.0
PLA_E_MAX_GPA = 6.0
R2_PASS = 0.99


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
        if data[j - 1]["t"] - data[i]["t"] >= min_hold_s:
            holds.append((i, j - 1))
        i = j
    return holds


def step_stats(data, i0, i1, skip_first_s=2.0):
    t0 = data[i0]["t"]
    samples = [d for d in data[i0:i1 + 1]
               if d["t"] - t0 >= skip_first_s and abs(d["ec"]) > 1e-7]
    if len(samples) < 5:
        samples = data[i0:i1 + 1]
    return {
        "pos": mean(d["pos"] for d in samples),
        "F":   mean(d["F"] for d in samples),
        "ec":  mean(d["ec"] for d in samples),
        "ec_sd": stdev(d["ec"] for d in samples) if len(samples) > 1 else 0.0,
    }


def linfit(xs, ys):
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    ymean = sy / n
    ss_tot = sum((y - ymean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")
    return slope, intercept, r2


def asc_stats(path, skip_initial=False):
    data = read_csv(path)
    holds = detect_holds(data)
    stats = [step_stats(data, i0, i1) for i0, i1 in holds]
    if skip_initial and stats and stats[0]["pos"] > 0.4:
        stats = stats[1:]
    peak = max(range(len(stats)), key=lambda i: stats[i]["pos"])
    return stats[:peak + 1]


v4b = asc_stats(V4B)
v4c = asc_stats(V4C, skip_initial=True)

# Compute stress (MPa) at each step.  For V4c, add preload back for TRUE stress.
for s in v4b:
    s["sigma"] = s["F"] / GAUGE_AREA_MM2          # tared at 0 N, display = true
for s in v4c:
    s["sigma_disp"] = s["F"] / GAUGE_AREA_MM2
    s["sigma_true"] = (s["F"] + V4C_PRELOAD) / GAUGE_AREA_MM2


def report_table(label, stats, sigma_key):
    print(f"\n--- {label} ---")
    print(f"{'Pos':>8}{'F (N)':>10}{'sigma_MPa':>12}{'eps_c':>14}{'eps_c_std':>12}")
    for s in stats:
        print(f"{s['pos']:>+8.4f}{s['F']:>+10.2f}{s[sigma_key]:>+12.4f}{s['ec']:>+14.6f}{s['ec_sd']:>12.6f}")


print("=" * 80)
print("8.6.19 - Stress-strain pairing and apparent modulus")
print("=" * 80)
report_table("V4b ASC (display stress = true; F tared at 0 N)", v4b, "sigma")
report_table("V4c ASC (true stress = display + +350 N preload)", v4c, "sigma_true")

# Engaged subsets
v4b_eng = [s for s in v4b if s["pos"] >= 0.35]
v4c_clean = [s for s in v4c if abs(s["pos"] - 0.6) > 0.05]

# Linear fits  σ = E·ε + σ₀
sb, ib, rb = linfit([s["ec"] for s in v4b_eng], [s["sigma"] for s in v4b_eng])
sc, ic, rc = linfit([s["ec"] for s in v4c_clean], [s["sigma_true"] for s in v4c_clean])

E_b_GPa = sb / 1000.0
E_c_GPa = sc / 1000.0

print()
print("=" * 80)
print("Linear fit  sigma = E * eps_c + sigma_0 on engaged subset")
print("=" * 80)
print(f"V4b engaged (n={len(v4b_eng)}, Pos >= 0.4 mm):")
print(f"   E = {sb:>9.2f} MPa = {E_b_GPa:.3f} GPa,  sigma_0 = {ib:+.3f} MPa,  R^2 = {rb:.5f}")
print(f"V4c clean  (n={len(v4c_clean)}, true stress):")
print(f"   E = {sc:>9.2f} MPa = {E_c_GPa:.3f} GPa,  sigma_0 = {ic:+.3f} MPa,  R^2 = {rc:.5f}")

print()
print("=" * 80)
print("Pass criteria check (8.6.19)")
print("=" * 80)

def verdict(cond):
    return "PASS" if cond else "FAIL"

print(f"[1] R^2 > {R2_PASS} on engaged subset:")
print(f"    V4b R^2 = {rb:.5f}  {verdict(rb > R2_PASS)}")
print(f"    V4c R^2 = {rc:.5f}  {verdict(rc > R2_PASS)}")
print(f"[2] {PLA_E_MIN_GPA} GPa <= E <= {PLA_E_MAX_GPA} GPa (FDM-PLA literature):")
print(f"    V4b E  = {E_b_GPa:.3f} GPa  {verdict(PLA_E_MIN_GPA <= E_b_GPa <= PLA_E_MAX_GPA)}")
print(f"    V4c E  = {E_c_GPa:.3f} GPa  {verdict(PLA_E_MIN_GPA <= E_c_GPa <= PLA_E_MAX_GPA)}")
print(f"[3] Cross-check V4b vs V4c within 30 %:")
spread = abs(E_b_GPa - E_c_GPa) / max(E_b_GPa, E_c_GPa) * 100
print(f"    spread = {spread:.1f} %  {verdict(spread < 30)}")
peak_true_stress_v4c = max(s["sigma_true"] for s in v4c)
print(f"[4] Linear regime extends to: V4c peak true stress = {peak_true_stress_v4c:.2f} MPa")
print(f"    (above this, Pos 0.6 anomaly indicates yield-onset boundary at ~ 12 MPa)")

# ============ Plot ============
fig, ax = plt.subplots(1, 1, figsize=(11, 6.5))

# V4b
ax.plot([s["ec"] for s in v4b], [s["sigma"] for s in v4b], "o", color="#1f77b4",
        markersize=14, markeredgecolor="black", markeredgewidth=0.8,
        label="V4b ASC points (display = true σ)")
xs_b = [min(s["ec"] for s in v4b_eng), max(s["ec"] for s in v4b_eng)]
ax.plot(xs_b, [sb * x + ib for x in xs_b], "-", color="#1f77b4", linewidth=2.5,
        label=f"V4b engaged fit:  E = {E_b_GPa:.2f} GPa,  R² = {rb:.4f}")

# V4c
ax.plot([s["ec"] for s in v4c], [s["sigma_true"] for s in v4c], "s", color="#d62728",
        markersize=14, markeredgecolor="black", markeredgewidth=0.8,
        label="V4c ASC points (true σ = display + 350 N preload)")
xs_c = [min(s["ec"] for s in v4c_clean), max(s["ec"] for s in v4c_clean)]
ax.plot(xs_c, [sc * x + ic for x in xs_c], "-", color="#d62728", linewidth=2.5,
        label=f"V4c clean fit:   E = {E_c_GPa:.2f} GPa,  R² = {rc:.4f}")

# Y-value annotations
for s in v4b:
    ax.annotate(f"{s['sigma']:+.2f} MPa", xy=(s["ec"], s["sigma"]),
                xytext=(8, -3), textcoords="offset points",
                fontsize=7, color="#1f77b4", fontweight="bold")
for s in v4c:
    ax.annotate(f"{s['sigma_true']:+.2f} MPa", xy=(s["ec"], s["sigma_true"]),
                xytext=(8, 6), textcoords="offset points",
                fontsize=7, color="#d62728", fontweight="bold")

# PLA reference band (E = 3-6 GPa) — show as shaded slope envelope from origin
import numpy as np
eps_ref = np.linspace(-0.0008, 0.0016, 50)
ax.fill_between(eps_ref, PLA_E_MIN_GPA * 1000 * eps_ref, PLA_E_MAX_GPA * 1000 * eps_ref,
                color="green", alpha=0.08, label="FDM-PLA literature E = 3–6 GPa envelope")

# Yield-onset annotation (V4c)
ax.axhline(12.0, color="orange", linewidth=1, linestyle=":", alpha=0.6,
           label="Yield-onset boundary ≈ 12 MPa (V4c Pos 0.6 anomaly)")

ax.set_xlabel("DIC ε_c (Cauchy strain)", fontsize=13)
ax.set_ylabel("Engineering stress σ (MPa)", fontsize=13)
ax.set_title("8.6.19 — Stress vs strain on engaged regime\n"
             "V4b (+180 N preload) and V4c (+350 N preload), PLA specimen",
             fontsize=13, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=9, framealpha=0.95)
ax.axhline(0, color="gray", linewidth=0.5)
ax.axvline(0, color="gray", linewidth=0.5)

plt.tight_layout()
plt.savefig("images/V4/V4_8_6_19_stress_strain.png", dpi=160, bbox_inches="tight")
print(f"\nSaved plot: V4_8_6_19_stress_strain.png")
