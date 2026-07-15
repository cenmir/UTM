"""8.6.20 V5 - comprehensive analysis (all aspects), V4-style plots.

Produces a 2x2 figure:
  P1  true stress vs DIC strain (E fit, 0.2% offset, sigma_y, UTS, fracture)
  P2  true stress vs crosshead Position
  P3  true force vs Position (incl. fracture drop + post-fracture anchor)
  P4  DIC strain & motor strain vs time + DIC/motor ratio (compliance evolution)

Also prints: phase timeline, multiple-window moduli, proportional limit,
resilience/toughness, strain rate, rig compliance, infill-corrected
material values (50% infill), and pass checks vs Chacon et al. (2017).
"""

from statistics import mean, stdev
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = r"Software\UTM_PyQt6\8.6.20\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv"
AREA = 80.0          # nominal mm^2 (10 x 8, CAD-verified)
GAUGE = 80.0         # mm
INFILL = 0.50        # slicer infill fraction (user-confirmed)

# Effective load-bearing area model: 2 perimeters (~0.9 mm wall) fully solid,
# core at infill density. With w = 0.9 mm walls on a 10 x 8 section:
WALL = 0.9
core_w, core_t = 10 - 2*WALL, 8 - 2*WALL
A_core = core_w * core_t
A_shell = AREA - A_core
A_eff = A_shell + INFILL * A_core      # geometric effective area


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
        p = row.split(",")
        try:
            out.append({
                "t": float(p[idx["Time_s"]]), "F": float(p[idx["Force_N"]]),
                "pos": float(p[idx["Position_mm"]]), "ms": float(p[idx["Motor_Strain"]]),
                "ec": float(p[idx["DIC_Cauchy"]]), "lpx": float(p[idx["L_px"]]),
            })
        except (ValueError, IndexError):
            continue
    return out


def linfit(xs, ys):
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x*x for x in xs)
    sxy = sum(x*y for x, y in zip(xs, ys))
    sl = (n*sxy - sx*sy) / (n*sxx - sx*sx)
    ic = (sy - sl*sx) / n
    ym = sy/n
    sst = sum((y-ym)**2 for y in ys)
    ssr = sum((y-(sl*x+ic))**2 for x, y in zip(xs, ys))
    return sl, ic, (1 - ssr/sst if sst else float("nan"))


data = read_csv(CSV)

# fracture = first L_px discontinuity
fr_i = next(i for i in range(1, len(data)) if abs(data[i]["lpx"] - data[i-1]["lpx"]) > 50)
t_fr = data[fr_i]["t"]
pre = data[:fr_i]
post = [d for d in data[fr_i+1:] if d["t"] > t_fr + 2.0]
anchor = -mean(d["F"] for d in post)

mv_i = next(i for i, d in enumerate(data) if d["pos"] > 0.005)
t0 = data[mv_i]["t"]

for d in data:
    d["sig"] = (d["F"] + anchor) / AREA          # true stress, nominal area
    d["Ftrue"] = d["F"] + anchor

test = pre[mv_i:]            # motion start -> last valid sample
uts = max(test, key=lambda d: d["sig"])
last = test[-1]

print("=" * 78)
print("8.6.20 V5 - FULL ANALYSIS  (specimen S4, 50% infill, spray markers)")
print("=" * 78)

# ---------- Phase timeline ----------
print("\n[1] Phase timeline")
print(f"    0.0 - {t0:.1f} s   baseline hold at preload (stress-relaxation visible)")
print(f"    {t0:.1f} s          motion start, 0.1 mm/s")
pl_dep = None
# proportional limit: departure >2% from elastic fit
win = [d for d in test if 0.0005 <= d["ec"] <= 0.004]
E1, c1, r1 = linfit([d["ec"] for d in win], [d["sig"] for d in win])
for d in test:
    if d["ec"] > 0.004:
        pred = E1*d["ec"] + c1
        if d["sig"] < pred * 0.98:
            pl_dep = d
            break
if pl_dep:
    print(f"    {pl_dep['t']:.1f} s         proportional limit: sigma = {pl_dep['sig']:.1f} MPa, eps = {pl_dep['ec']:.4f}")
# 0.2% offset
sy = None
for d in test:
    if E1*(d["ec"]-0.002)+c1 >= d["sig"]:
        sy = d
        break
if sy:
    print(f"    {sy['t']:.1f} s         0.2% offset yield: sigma_y = {sy['sig']:.2f} MPa, eps = {sy['ec']:.4f}")
print(f"    {uts['t']:.1f} s         UTS = {uts['sig']:.2f} MPa at eps = {uts['ec']:.4f}, pos = {uts['pos']:.2f} mm")
print(f"    {t_fr:.1f} s         FRACTURE (eps_f = {last['ec']:.4f}, sigma = {last['sig']:.2f} MPa, pos = {last['pos']:.2f} mm)")
print(f"    {t_fr:.1f}-{data[-1]['t']:.0f} s    post-fracture hold: display F = {-anchor:.1f} N -> preload anchor {anchor:.0f} N")

# ---------- Stiffness in multiple windows ----------
print("\n[2] Stiffness evolution (secant fits, nominal area)")
for lo, hi in [(0.0005, 0.002), (0.002, 0.004), (0.004, 0.008), (0.008, 0.012), (0.012, 0.018)]:
    w = [d for d in test if lo <= d["ec"] <= hi]
    if len(w) > 10:
        E, _, r2 = linfit([d["ec"] for d in w], [d["sig"] for d in w])
        print(f"    eps {lo:.4f}-{hi:.4f}:  E_tangent = {E/1000:5.2f} GPa  (n={len(w)}, R^2={r2:.4f})")

# ---------- Energy ----------
res = tough = 0.0
prev = None
for d in test:
    if prev is not None and d["ec"] > prev["ec"]:
        dA = 0.5*(d["sig"]+prev["sig"])*(d["ec"]-prev["ec"])
        tough += dA
        if sy and d["t"] <= sy["t"]:
            res += dA
    prev = d
print("\n[3] Energy (per nominal volume)")
print(f"    Resilience (to yield)   = {res*1000:.1f} kJ/m^3")
print(f"    Toughness  (to failure) = {tough*1000:.1f} kJ/m^3")

# ---------- Rates / compliance ----------
print("\n[4] Rates and rig compliance")
dur = last["t"] - t0
print(f"    Gauge strain rate (avg)   = {last['ec']/dur:.2e} /s;  crosshead rate 0.1 mm/s (constant)")
elong = last["ec"] * GAUGE
print(f"    Gauge elongation at break = {elong:.2f} mm of {last['pos']:.2f} mm travel -> DIC/motor = {last['ec']/last['ms']:.2f}")
print(f"    Rig take-up at 1.77 kN    = {last['pos']-elong:.2f} mm  (~{(last['Ftrue'])/(last['pos']-elong):.0f} N/mm rig stiffness)")
base = [d for d in data[:mv_i] if d["t"] > 5]
print(f"    Baseline noise: F std = {stdev(d['F'] for d in base):.2f} N, eps_c std = {stdev(d['ec'] for d in base):.6f}")
print(f"    Baseline relaxation: {base[0]['F']:.1f} -> {base[-1]['F']:.1f} N display over {base[-1]['t']-base[0]['t']:.0f} s")

# ---------- Infill correction ----------
f_geom = A_eff / AREA
print("\n[5] Infill-corrected material properties (50% infill)")
print(f"    Effective-area model: 2 perimeters ({WALL} mm) solid + 50% core")
print(f"    A_shell = {A_shell:.1f} mm^2, A_core = {A_core:.1f} mm^2 -> A_eff = {A_eff:.1f} mm^2 (f = {f_geom:.2f})")
corr = AREA / A_eff
print(f"    {'Quantity':<22}{'Nominal-area':>14}{'Corrected':>12}{'Chacon range':>16}{'Verdict':>9}")
rows = [
    ("E", E1/1000, (3.0, 5.5), "GPa"),
    ("sigma_y (0.2% offset)", sy["sig"] if sy else float('nan'), (30, 50), "MPa"),
    ("UTS", uts["sig"], (32, 60), "MPa"),
]
for name, val, (lo, hi), unit in rows:
    cv = val*corr
    verdict = "PASS" if lo <= cv <= hi else "CHECK"
    print(f"    {name:<22}{val:>10.2f} {unit:<4}{cv:>9.2f} {unit:<3}{f'{lo}-{hi} {unit}':>15}{verdict:>9}")

# ---------- 2x2 plot ----------
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# P1: stress vs strain
ax = axes[0, 0]
ax.plot([d["ec"] for d in test], [d["sig"] for d in test], "-", color="#1f77b4", lw=1.8,
        label="V5 (engineering stress, nominal area)")
xf = [0, 0.006]
ax.plot(xf, [E1*x + c1 for x in xf], "--", color="green", lw=1.5,
        label=f"Elastic fit E = {E1/1000:.2f} GPa (R^2={r1:.3f})")
xo = [0.002, 0.026]
ax.plot(xo, [E1*(x-0.002)+c1 for x in xo], ":", color="green", lw=1.2, label="0.2% offset line")
if sy:
    ax.plot(sy["ec"], sy["sig"], "o", color="orange", ms=11, label=f"sigma_y = {sy['sig']:.1f} MPa")
ax.plot(uts["ec"], uts["sig"], "v", color="#d62728", ms=13, label=f"UTS = {uts['sig']:.1f} MPa @ eps {uts['ec']:.3f}")
ax.plot(last["ec"], last["sig"], "x", color="black", ms=13, mew=3,
        label=f"Fracture eps_f = {last['ec']:.4f}")
ax.set_xlabel("DIC Cauchy strain"); ax.set_ylabel("Engineering stress (MPa)")
ax.set_title("Stress vs strain", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="lower right"); ax.set_ylim(bottom=0)

# P2: stress vs position
ax = axes[0, 1]
ax.plot([d["pos"] for d in test], [d["sig"] for d in test], "-", color="#1f77b4", lw=1.8)
ax.plot(uts["pos"], uts["sig"], "v", color="#d62728", ms=13, label=f"UTS at pos = {uts['pos']:.2f} mm")
ax.plot(last["pos"], last["sig"], "x", color="black", ms=13, mew=3,
        label=f"Fracture at pos = {last['pos']:.2f} mm")
ax.set_xlabel("Crosshead position (mm)"); ax.set_ylabel("Engineering stress (MPa)")
ax.set_title("Stress vs position", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="lower right"); ax.set_ylim(bottom=0)

# P3: true force vs position incl. fracture
ax = axes[1, 0]
seg = data[mv_i:fr_i+30]
ax.plot([d["pos"] for d in seg], [d["Ftrue"] for d in seg], "-", color="#1f77b4", lw=1.8,
        label="True force")
ax.axhline(anchor, color="gray", lw=1, ls="--", label=f"Preload anchor = {anchor:.0f} N")
ax.plot(uts["pos"], uts["Ftrue"], "v", color="#d62728", ms=13, label=f"Peak = {uts['Ftrue']:.0f} N")
ax.annotate("fracture\n(1.7 kN -> 0 in ~90 ms)", xy=(last["pos"], 200), fontsize=9,
            color="#d62728", ha="center")
ax.set_xlabel("Crosshead position (mm)"); ax.set_ylabel("True force (N)")
ax.set_title("Force vs position - rig view", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="center left"); ax.set_ylim(bottom=-100)

# P4: strains vs time + DIC/motor ratio
ax = axes[1, 1]
ax.plot([d["t"]-t0 for d in test], [d["ms"] for d in test], "-", color="#7f7f7f", lw=1.5,
        label="Motor strain (crosshead/80 mm)")
ax.plot([d["t"]-t0 for d in test], [d["ec"] for d in test], "-", color="#1f77b4", lw=1.8,
        label="DIC strain (gauge)")
ax2 = ax.twinx()
ratio_t = [d["t"]-t0 for d in test if d["ms"] > 0.004]
ratio = [d["ec"]/d["ms"] for d in test if d["ms"] > 0.004]
ax2.plot(ratio_t, ratio, ":", color="#d62728", lw=1.5)
ax2.set_ylabel("DIC / motor strain ratio", color="#d62728")
ax2.tick_params(axis="y", colors="#d62728")
ax2.set_ylim(0, 1)
ax.set_xlabel("Time since motion start (s)"); ax.set_ylabel("Strain")
ax.set_title("Strain partition vs time (rig compliance evolution)", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper left")

plt.suptitle("8.6.20 - V5 tensile failure, fresh PLA S4 (50% infill), preload anchor +463 N",
             fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig("V5_full_analysis.png", dpi=140, bbox_inches="tight")
print("\nSaved plot: V5_full_analysis.png")
