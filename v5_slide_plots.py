"""Slide-friendly single-panel plots for the 8.6.20 deck (revised).
Outputs:
  V5_slide_load_time.png       (with preload->UTS delta arrow)
  V5_slide_stress_strain.png   (yield-construction + fracture labelled)
  V5_slide_cauchy_true.png     (Cauchy vs True strain on one stress axis)  [NEW]
  V5_slide_stress_position.png (compliance split explained)
Also prints exact numbers used on the slides.
"""

from statistics import mean, stdev
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv"
AREA = 80.0
GAUGE = 80.0

BLUE = "#1f77b4"; RED = "#d62728"; GREEN = "#2e7d32"; ORANGE = "#ff9800"; GREY = "#666666"
PURPLE = "#7b1fa2"

plt.rcParams.update({"font.size": 14, "axes.titlesize": 17, "axes.labelsize": 15,
                     "legend.fontsize": 12, "xtick.labelsize": 13, "ytick.labelsize": 13})


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
                "ec": float(p[idx["DIC_Cauchy"]]), "et": float(p[idx["DIC_True"]]),
                "lpx": float(p[idx["L_px"]]),
            })
        except (ValueError, IndexError):
            continue
    return out


def linfit(xs, ys):
    n = len(xs); sx, sy = sum(xs), sum(ys)
    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
    sl = (n*sxy - sx*sy)/(n*sxx - sx*sx); ic = (sy - sl*sx)/n
    ym = sy/n
    r2 = 1 - sum((y-(sl*x+ic))**2 for x, y in zip(xs, ys))/sum((y-ym)**2 for y in ys)
    return sl, ic, r2


data = read_csv(CSV)
fr_i = next(i for i in range(1, len(data)) if abs(data[i]["lpx"] - data[i-1]["lpx"]) > 50)
t_fr = data[fr_i]["t"]
pre = data[:fr_i]
post = [d for d in data[fr_i+1:] if d["t"] > t_fr + 2.0]
anchor = -mean(d["F"] for d in post)
mv_i = next(i for i, d in enumerate(data) if d["pos"] > 0.005)
t0 = data[mv_i]["t"]
for d in data:
    d["sig"] = (d["F"] + anchor) / AREA
    d["Ftrue"] = d["F"] + anchor
test = pre[mv_i:]
uts = max(test, key=lambda d: d["sig"])
last = test[-1]
win = [d for d in test if 0.0005 <= d["ec"] <= 0.004]
E1, c1, r1 = linfit([d["ec"] for d in win], [d["sig"] for d in win])
sy = next(d for d in test if E1*(d["ec"]-0.002)+c1 >= d["sig"])
# proportional limit: first point (eps>0.004) departing >2% below the elastic fit
pl = next((d for d in test if d["ec"] > 0.004 and d["sig"] < 0.98*(E1*d["ec"]+c1)), None)
pl_e = pl["ec"] if pl else 0.0049

# ---- derived quantities for slides ----
delta_F = uts["Ftrue"] - anchor                       # net pull preload->UTS
gauge_elong = last["ec"] * GAUGE                      # mm via DIC
rig_takeup = last["pos"] - gauge_elong               # mm
rig_k = last["Ftrue"] / rig_takeup                   # N/mm
gauge_share = gauge_elong / last["pos"] * 100        # %
# DIC tracking
dic_track = (data[fr_i-1]["t"] - t0) / (t_fr - t0) * 100
print(f"anchor(preload) = {anchor:.1f} N   UTS Ftrue = {uts['Ftrue']:.0f} N   delta = {delta_F:.0f} N")
print(f"sigma_y(0.2% offset) = {sy['sig']:.2f} MPa at eps={sy['ec']:.4f}")
print(f"fracture(failure) stress = {last['sig']:.2f} MPa at eps_f={last['ec']:.4f}  (true strain {last['et']:.4f})")
print(f"UTS = {uts['sig']:.2f} MPa at eps={uts['ec']:.4f}")
print(f"gauge elong (DIC) = {gauge_elong:.2f} mm; rig take-up = {rig_takeup:.2f} mm; pos = {last['pos']:.2f} mm")
print(f"rig stiffness = {rig_k:.0f} N/mm; gauge share = {gauge_share:.1f} %")
print(f"DIC tracking = {dic_track:.1f} %  (last valid t={data[fr_i-1]['t']:.2f}s, motion {t0:.2f}s, fracture {t_fr:.2f}s)")
print("offset factors to reach Chacon lower bound:")
print(f"  E:    3.0/{E1/1000:.2f} = {3.0/(E1/1000):.2f}")
print(f"  sy:   30/{sy['sig']:.1f} = {30/sy['sig']:.2f}")
print(f"  UTS:  32/{uts['sig']:.1f} = {32/uts['sig']:.2f}")

# ============ PLOT 1: Load vs time (with delta arrow) ============
fig, ax = plt.subplots(figsize=(12.5, 6.2))
ax.plot([d["t"] for d in data], [d["Ftrue"] for d in data], "-", color=BLUE, lw=2)
ax.axvspan(0, t0, color="gray", alpha=0.08)
ax.text(t0/2, 1500, "baseline hold\n(preload +463 N)", ha="center", fontsize=12, color=GREY, style="italic")
ax.annotate("ramp start\n0.1 mm/s", xy=(t0, 463), xytext=(t0+6, 880),
            fontsize=12, color=BLUE, arrowprops=dict(arrowstyle="->", color=BLUE))
ax.annotate(f"UTS {uts['Ftrue']:.0f} N", xy=(uts["t"], uts["Ftrue"]), xytext=(uts["t"]-52, 1880),
            fontsize=13, fontweight="bold", color=RED, arrowprops=dict(arrowstyle="->", color=RED))
ax.annotate("FRACTURE  1.7 kN → 0\nin ~90 ms", xy=(t_fr, 500), xytext=(t_fr+30, 760),
            fontsize=12.5, fontweight="bold", color=RED, arrowprops=dict(arrowstyle="->", color=RED, lw=1.8))
# --- preload <-> UTS delta double arrow ---
xa = uts["t"] + 5
ax.annotate("", xy=(xa, uts["Ftrue"]), xytext=(xa, anchor),
            arrowprops=dict(arrowstyle="<->", color=PURPLE, lw=2.4))
ax.plot([uts["t"], xa], [uts["Ftrue"], uts["Ftrue"]], color=PURPLE, lw=0.8, ls=":")
ax.plot([t0, xa], [anchor, anchor], color=PURPLE, lw=0.8, ls=":")
ax.text(xa+4, 1500,
        f"Δ = {delta_F:.0f} N\nnet pull\n(UTS − preload\n= {uts['Ftrue']:.0f} − {anchor:.0f})",
        fontsize=12, color=PURPLE, fontweight="bold", va="center")
ax.axhline(0, color="gray", lw=0.8)
ax.text(205, 110, "post-fracture: specimen carries 0 N\n→ display −463 N anchors the preload",
        fontsize=11.5, color=GREEN, ha="center")
ax.set_xlabel("Time (s)"); ax.set_ylabel("True force (N)")
ax.set_title("8.6.20 V5 — Load vs time (full test)", fontweight="bold")
ax.set_xlim(-5, 285); ax.set_ylim(-90, 1980)
ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig("V5_slide_load_time.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 2: Stress vs strain — FOUR REGIONS marked ============
fig, ax = plt.subplots(figsize=(12.5, 6.2))
# region bands (behind everything)
bands = [
    (0.0, pl_e, "#c8e6c9", "I", "Linear elastic"),
    (pl_e, sy["ec"], "#fff3cd", "II", "Yield knee"),
    (sy["ec"], uts["ec"], "#ffe0b2", "III", "Plastic / strain-harden"),
    (uts["ec"], last["ec"], "#ffcdd2", "IV", "Soften → fracture"),
]
for x0, x1, col, rn, nm in bands:
    ax.axvspan(x0, x1, color=col, alpha=0.55, zorder=0)
    ax.text((x0+x1)/2, 25.4, rn, ha="center", fontsize=15, fontweight="bold", color="#222", zorder=4)
ax.plot([d["ec"] for d in test], [d["sig"] for d in test], "-", color=BLUE, lw=2.6, zorder=3,
        label="V5 (engineering stress)")
xf = [0, 0.006]
ax.plot(xf, [E1*x + c1 for x in xf], "--", color=GREEN, lw=2, zorder=3,
        label=f"elastic slope  E = {E1/1000:.2f} GPa  (R² = {r1:.3f})")
xo = [0.002, 0.0252]
ax.plot(xo, [E1*(x-0.002)+c1 for x in xo], ":", color=GREEN, lw=1.6, zorder=3,
        label="0.2 % offset line")
ax.plot(sy["ec"], sy["sig"], "o", color="#b8860b", ms=14, zorder=5, label=f"σ_y = {sy['sig']:.1f} MPa")
ax.plot(uts["ec"], uts["sig"], "v", color=RED, ms=15, zorder=5, label=f"UTS = {uts['sig']:.1f} MPa")
ax.plot(last["ec"], last["sig"], "x", color="black", ms=15, mew=3.2, zorder=5,
        label=f"fracture  σ_f = {last['sig']:.1f} MPa, ε_f = {last['ec']:.4f}")
# region name key (compact, upper-left where curve is low)
ax.text(0.0007, 24.4,
        "I  Linear elastic        II  Yield knee\nIII  Plastic / strain-harden    IV  Soften → fracture",
        fontsize=10, va="top", color="#333", zorder=6,
        bbox=dict(facecolor="white", edgecolor="#bbb", boxstyle="round,pad=0.3"))
ax.set_xlabel("DIC Cauchy strain ε_c"); ax.set_ylabel("Engineering stress (MPa)")
ax.set_title("8.6.20 V5 — Stress vs strain (four deformation regions)", fontweight="bold")
ax.grid(alpha=0.3, zorder=1); ax.legend(loc="lower right", fontsize=11)
ax.set_xlim(-0.0005, 0.027); ax.set_ylim(0, 26.5)
plt.tight_layout(); plt.savefig("V5_slide_stress_strain.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 3: Cauchy vs True strain (NEW) ============
fig, ax = plt.subplots(figsize=(12.5, 6.2))
ax.plot([d["ec"] for d in test], [d["sig"] for d in test], "-", color=BLUE, lw=2.5,
        label="Cauchy strain  ε_c = (L−L₀)/L₀")
ax.plot([d["et"] for d in test], [d["sig"] for d in test], "-", color=RED, lw=2.5,
        label="True strain  ε_t = ln(L/L₀)")
# divergence callout at fracture
ax.annotate(f"at fracture:\nε_c = {last['ec']:.4f}\nε_t = {last['et']:.4f}\n(Δ = {(last['ec']-last['et'])/last['ec']*100:.1f} %)",
            xy=(last["et"], last["sig"]), xytext=(0.0185, 11),
            fontsize=12, color="black",
            arrowprops=dict(arrowstyle="->", color="black"),
            bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.4"))
ax.text(0.004, 23.0,
        "Curves overlap at small strain (ε_t ≈ ε_c)\nand separate as strain grows:\nln(1+ε) < ε.  Here max gap ≈ 1.2 %.",
        fontsize=12, color=GREY, style="italic", va="top",
        bbox=dict(facecolor="white", edgecolor="#cccccc", boxstyle="round,pad=0.4"))
ax.set_xlabel("DIC strain"); ax.set_ylabel("Engineering stress (MPa)")
ax.set_title("8.6.20 V5 — Cauchy vs True strain", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right")
ax.set_xlim(-0.0005, 0.027); ax.set_ylim(0, 26)
plt.tight_layout(); plt.savefig("V5_slide_cauchy_true.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 4: Stress vs displacement — gauge vs rig split shown ============
fig, ax = plt.subplots(figsize=(12.5, 6.2))
# two curves: crosshead (motor) and gauge stretch (DIC strain x gauge length)
ax.plot([d["pos"] for d in test], [d["sig"] for d in test], "-", color=BLUE, lw=2.6,
        label="vs crosshead position (motor)")
ax.plot([d["ec"]*GAUGE for d in test], [d["sig"] for d in test], "--", color=ORANGE, lw=2.6,
        label="vs gauge stretch (DIC) — true specimen")
ax.plot(last["pos"], last["sig"], "x", color="black", ms=14, mew=3)
ax.plot(gauge_elong, last["sig"], "x", color="#b8860b", ms=14, mew=3)
# --- split bracket at top: 0 -> gauge_elong (gauge) and gauge_elong -> pos (rig) ---
yb = 24.2
ax.plot([0, last["pos"]], [yb, yb], color="#aaaaaa", lw=0.8)
ax.annotate("", xy=(gauge_elong, yb), xytext=(0, yb),
            arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=2.4))
ax.annotate("", xy=(last["pos"], yb), xytext=(gauge_elong, yb),
            arrowprops=dict(arrowstyle="<->", color=BLUE, lw=2.4))
ax.text(gauge_elong/2, yb+0.55, f"gauge stretch (DIC)\n{gauge_elong:.2f} mm  ({gauge_share:.0f} %)",
        ha="center", fontsize=11, color="#b8860b", fontweight="bold")
ax.text((gauge_elong+last["pos"])/2, yb+0.55, f"rig take-up\n{rig_takeup:.2f} mm  ({100-gauge_share:.0f} %)",
        ha="center", fontsize=11, color=BLUE, fontweight="bold")
# vertical droplines marking the two endpoints
ax.plot([gauge_elong, gauge_elong], [last["sig"], yb], color="#b8860b", lw=0.9, ls=":")
ax.plot([last["pos"], last["pos"]], [last["sig"], yb], color=BLUE, lw=0.9, ls=":")
# the horizontal gap between the two curves AT a given stress = rig take-up at that load
ax.annotate("", xy=(last["pos"], last["sig"]), xytext=(gauge_elong, last["sig"]),
            arrowprops=dict(arrowstyle="<->", color="#888", lw=1.6, ls=(0, (3, 2))))
ax.text((gauge_elong+last["pos"])/2, last["sig"]-1.6, "gap = rig take-up\n(grows with load)",
        ha="center", fontsize=10, color="#666", style="italic")
# rig stiffness box (empty lower-right-of-orange region)
ax.text(2.55, 11.5,
        f"rig stiffness\nk = F / δ_rig\n= {uts['Ftrue']:.0f} N ÷ {rig_takeup:.2f} mm\n≈ {rig_k:.0f} N/mm",
        fontsize=11.5, va="top",
        bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.45"))
ax.set_xlabel("Displacement (mm)"); ax.set_ylabel("Engineering stress (MPa)")
ax.set_title("8.6.20 V5 — Stress vs displacement: gauge stretch vs rig take-up", fontweight="bold")
ax.grid(alpha=0.3); ax.set_xlim(-0.1, 4.15); ax.set_ylim(0, 26.5)
ax.legend(loc="lower right", fontsize=11)
plt.tight_layout(); plt.savefig("V5_slide_stress_position.png", dpi=150, bbox_inches="tight"); plt.close()

# ============ PLOT 5: Cauchy strain vs crosshead displacement (V5 only) ============
fig, ax = plt.subplots(figsize=(12.5, 6.2))
ax.plot([d["pos"] for d in test], [d["ec"] for d in test], "-", color=BLUE, lw=2.6,
        label="V5 gauge strain ε_c (DIC)")
ax.plot([0, 4.1], [0, 4.1/GAUGE], ":", color="#555", lw=1.4,
        label="ideal: all travel → gauge (slope 1/80 mm)")
ax.plot(uts["pos"], uts["ec"], "v", color=RED, ms=15, label=f"UTS at {uts['pos']:.2f} mm")
ax.plot(last["pos"], last["ec"], "x", color="black", ms=15, mew=3.2,
        label=f"fracture: ε_f = {last['ec']:.4f} at {last['pos']:.2f} mm")
# gauge/rig split bar at the fracture-strain level
ax.annotate("", xy=(gauge_elong, last["ec"]), xytext=(0, last["ec"]),
            arrowprops=dict(arrowstyle="<->", color="#b8860b", lw=2.0))
ax.text(gauge_elong/2, last["ec"]+0.0011, f"gauge stretch {gauge_elong:.2f} mm",
        ha="center", fontsize=10.5, color="#b8860b", fontweight="bold")
ax.text(0.3, 0.0205,
        f"At fracture: {last['pos']:.2f} mm crosshead travel →\n"
        f"only {gauge_elong:.2f} mm ({gauge_share:.0f} %) stretches the gauge;\n"
        f"the rest ({rig_takeup:.2f} mm) is rig/grip take-up.\n"
        f"The curve sits below the dotted line for that reason.",
        fontsize=11.5, va="top",
        bbox=dict(facecolor="#E7F1F8", edgecolor="none", boxstyle="round,pad=0.5"))
ax.set_xlabel("Crosshead displacement / travel (mm)")
ax.set_ylabel("DIC Cauchy strain ε_c")
ax.set_title("8.6.20 V5 — gauge strain vs crosshead displacement", fontweight="bold")
ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=11)
ax.set_xlim(-0.05, 4.1); ax.set_ylim(-0.001, 0.027)
plt.tight_layout(); plt.savefig("V5_slide_strain_position.png", dpi=150, bbox_inches="tight"); plt.close()

print("\nSaved 5 slide plots.")
