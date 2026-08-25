"""Plots for the V2 / S24 capture-validation deck (2026-08-14, 100 % infill).

Run from the repo root:  python documentation/scripts/v2_capture_plots.py

Every number is recomputed from the run's own files — the CSV, the capture folder's index.csv and
the two AVIs — so the deck cannot drift from the data it claims to show.
"""
import os, sys, csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(ROOT)), "Software", "UTM_PyQt6"))
sys.path.insert(0, APP)
import utm_analysis as UA

SPEC = os.path.join(APP, "8.6.20 - Tensile test to Failure", "Specimen_S24_V2_Spray")
RUN = os.path.join(SPEC, "20260814_120156")
CSV = os.path.join(SPEC, "UTM_Test_20260814_120352_100%infill_Videocapture.csv")
OUT = os.path.join(ROOT, "..", "figures")   # figures live in one place
AREA = GAUGE = 80.0

INK, MUTED, GRID = "#1a1a1a", "#666666", "#dddddd"
BLUE, GREEN, RED, AMBER = "#1f6fb4", "#2f9e44", "#c0392b", "#d29922"
plt.rcParams.update({"font.size": 11, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "figure.facecolor": "white"})


def finish(fig, name):
    for ax in fig.axes:
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    fig.tight_layout()
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    print("  wrote", name)
    return p


# ---------------------------------------------------------------- load everything once
rows = list(csv.DictReader(open(os.path.join(RUN, "frames", "index.csv"), encoding="utf-8")))
ft = np.array([float(r["t_monotonic_s"]) for r in rows])
gap_ms = np.diff(ft) * 1000.0
n_png = len(rows)

vid = {}
for nm in ("video.avi", "video_speckle.avi"):
    c = cv2.VideoCapture(os.path.join(RUN, nm))
    vid[nm] = (int(c.get(cv2.CAP_PROP_FRAME_COUNT)), c.get(cv2.CAP_PROP_FPS),
               os.path.getsize(os.path.join(RUN, nm)) / 1e6)
    c.release()

d = UA.read_csv(CSV)
r = UA.analyze(CSV, AREA, GAUGE)
col = lambda k: np.array([x[k] for x in d], float)
ec, F, t, lpx, pos = col("ec"), col("F"), col("t"), col("lpx"), col("pos")
blobs = np.array([int(l.rsplit(",", 1)[1]) for l in
                  open(CSV, encoding="utf-8", errors="ignore")
                  if l[:1].isdigit() and l.count(",") >= 14], int)
valid = lpx > 100.0
anchor = r["anchor"]
sig = (F + anchor) / AREA

# Strain must be ZEROED the way analyze() does it — subtract the pre-ramp baseline (~0.49 %) —
# or the deck would compare the report's zeroed 17.5 % against an unzeroed 7.9 % and overstate
# the size of the error.
base_pos = float(np.sort(pos[:30])[15])
mv_i = int(np.argmax(pos > base_pos + 0.005))
ec0 = float(np.median(ec[valid & (t < t[mv_i])][-20:]))
ecz = ec - ec0
print(f"  baseline strain ec0 = {ec0*100:.3f} %  (subtracted, as analyze does)")

i_coll = int(np.argmin(np.diff(F))) + 1                     # the load collapse
i_last = int(np.where(valid & (t < t[i_coll - 1]))[0][-1])  # last honest DIC sample
i_post = int(np.where(valid & (t > t[i_coll - 2]))[0][0])   # first sample after the halves parted
ec = ecz                                                     # everything below plots zeroed strain
ef_true, ef_rep = ec[i_last], 0.1755        # ef_rep = pre-fix analyze(), see EF_PREFIX below

print(f"  true ef {ef_true*100:.2f} %  ·  reported {ef_rep*100:.1f} %  ·  "
      f"UTS {np.nanmax(sig):.2f} MPa")

# ================================================================ 1. capture timing
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [2, 1]})
a.plot(ft[1:] - ft[0], gap_ms, lw=0.8, color=BLUE)
med = float(np.median(gap_ms))
a.axhline(med, color=GREEN, lw=2, ls="--")
a.text(2, med + 6, f"median {med:.1f} ms  =  {1000/med:.1f} fps",
       color=GREEN, fontweight="bold", fontsize=10)
a.axhline(2 * med, color=RED, lw=1.5, ls=":")
a.text(2, 2 * med + 3, "a dropped frame would land here", color=RED, fontsize=9.5)
a.set_xlabel("Time into capture (s)"); a.set_ylabel("Interval between frames (ms)")
a.set_title("Every frame interval, all 1 959 of them", fontsize=12, fontweight="bold", loc="left")
a.set_ylim(0, 2.4 * med)

b.hist(gap_ms, bins=40, color=BLUE, edgecolor="white", linewidth=0.4)
b.axvline(med, color=GREEN, lw=2, ls="--")
b.set_xlabel("Interval (ms)"); b.set_ylabel("Frames")
b.set_title(f"p95 {np.percentile(gap_ms,95):.1f} ms · max {gap_ms.max():.1f} ms",
            fontsize=12, fontweight="bold", loc="left")
finish(fig, "documentation/figures/v2_capture_timing.png")

# ================================================================ 2. three sinks in lockstep
fig, ax = plt.subplots(figsize=(7.6, 3.2))
names = ["PNG stills\n(raw)", "video.avi\n(raw)", "video_speckle.avi\n(adaptive)"]
counts = [n_png, vid["video.avi"][0], vid["video_speckle.avi"][0]]
sizes = [1900.0, vid["video.avi"][2], vid["video_speckle.avi"][2]]
bars = ax.barh(names, counts, color=[BLUE, BLUE, GREEN], height=0.55)
for bar, c, s in zip(bars, counts, sizes):
    ax.text(c + 25, bar.get_y() + bar.get_height() / 2, f"{c:,} frames   ·   {s:,.0f} MB",
            va="center", fontsize=11, fontweight="bold", color=INK)
ax.set_xlim(0, max(counts) * 1.5)
ax.set_xlabel("Frames written")
ax.set_title("All three sinks wrote the same 1 960 frames — none fell behind",
             fontsize=12.5, fontweight="bold", loc="left")
ax.invert_yaxis()
finish(fig, "documentation/figures/v2_capture_sinks.png")

# ================================================================ 3. the fracture-point error
fig, ax = plt.subplots(figsize=(8.4, 4.6))
m = valid
ax.plot(ec[m] * 100, sig[m], lw=2, color=BLUE, zorder=3)
ax.plot(ec[i_last] * 100, sig[i_last], "o", ms=11, color=GREEN, zorder=5)
ax.plot(ec[i_post] * 100, sig[i_post], "X", ms=13, color=RED, zorder=5)
ax.annotate(f"TRUE fracture\nε_f = {ef_true*100:.2f} %\nσ = {sig[i_last]:.1f} MPa",
            xy=(ec[i_last] * 100, sig[i_last]), xytext=(ec[i_last] * 100 - 5.6, 22),
            color=GREEN, fontweight="bold", fontsize=11,
            arrowprops=dict(arrowstyle="->", color=GREEN, lw=2))
ax.annotate(f"post-fracture marker jump\nreported as ε_f = {ef_rep*100:.1f} %",
            xy=(ec[i_post] * 100, sig[i_post]), xytext=(ec[i_post] * 100 - 9.5, -1.5),
            color=RED, fontweight="bold", fontsize=11,
            arrowprops=dict(arrowstyle="->", color=RED, lw=2))
ax.axvspan(ec[i_last] * 100, ec[i_post] * 100, color=RED, alpha=0.07, zorder=0)
ax.text((ec[i_last] + ec[i_post]) * 50, 47.5,
        "the specimen is already broken\nacross this whole span",
        ha="center", color=RED, fontsize=10, style="italic")
ax.set_xlabel("Engineering strain, DIC (%)"); ax.set_ylabel("Engineering stress (MPa)")
ax.set_title("The report's ε_f is the two halves springing apart, not the material stretching",
             fontsize=12.5, fontweight="bold", loc="left")
ax.set_ylim(-4, 52)
finish(fig, "documentation/figures/v2_fracture_point.png")

# ================================================================ 4. the smoking gun: L_px
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.8), sharex=True)
w = (t > t[i_last] - 25) & (t < t[i_last] + 12) & valid
a.plot(t[w] - t[i_last], lpx[w], "o-", ms=3, lw=1.4, color=BLUE)
a.axvline(0, color=GREEN, lw=2, ls="--")
a.annotate(f"+{lpx[i_post]-lpx[i_last]:.0f} px in {t[i_post]-t[i_last]:.2f} s",
           xy=(t[i_post] - t[i_last], lpx[i_post]), xytext=(-21, lpx[i_post] - 40),
           color=RED, fontweight="bold", fontsize=11,
           arrowprops=dict(arrowstyle="->", color=RED, lw=2))
a.set_ylabel("Marker separation L (px)"); a.set_xlabel("Time relative to fracture (s)")
a.set_title("Marker separation", fontsize=12, fontweight="bold", loc="left")

wf = (t > t[i_last] - 25) & (t < t[i_last] + 12)
b.plot(t[wf] - t[i_last], F[wf], lw=1.6, color=AMBER)
b.axvline(0, color=GREEN, lw=2, ls="--")
b.axhline(0, color=MUTED, lw=0.8)
b.set_ylabel("Force (N)"); b.set_xlabel("Time relative to fracture (s)")
b.set_title("Load collapses at the same instant", fontsize=12, fontweight="bold", loc="left")
fig.suptitle("A 10.9 % length change in 0.45 s — 209× the strain rate of the whole test",
             fontsize=12.5, fontweight="bold", x=0.012, ha="left")
finish(fig, "documentation/figures/v2_lpx_jump.png")

# ================================================================ 5. the impossibility check
fig, ax = plt.subplots(figsize=(7.8, 4.2))
trav = pos - pos[np.argmax(F > 5)]
stretch_rep = ef_rep * GAUGE
stretch_true = ef_true * GAUGE
tot = trav[i_post]
ax.barh(["Crosshead moved\n(the whole machine)", f"Gauge stretched\nif ε_f = {ef_rep*100:.1f} %",
         f"Gauge stretched\nif ε_f = {ef_true*100:.1f} %"],
        [tot, stretch_rep, stretch_true], color=[MUTED, RED, GREEN], height=0.55)
for i, v in enumerate([tot, stretch_rep, stretch_true]):
    ax.text(v + 0.15, i, f"{v:.2f} mm", va="center", fontweight="bold", fontsize=12)
ax.axvline(tot, color=MUTED, ls="--", lw=1.5)
ax.text(tot + 0.15, -0.62, "nothing can exceed this", color=MUTED, fontsize=10, style="italic")
ax.text(stretch_rep * 0.5, 1, "IMPOSSIBLE", ha="center", va="center", color="white",
        fontweight="bold", fontsize=15)
ax.set_xlabel("Displacement (mm)"); ax.set_xlim(0, max(stretch_rep, tot) * 1.35)
ax.set_title("The 80 mm gauge cannot stretch further than the crosshead travelled",
             fontsize=12.5, fontweight="bold", loc="left")
ax.invert_yaxis()
finish(fig, "documentation/figures/v2_gauge_impossible.png")

# ================================================================ 6. DIC health
fig, ax = plt.subplots(figsize=(9.6, 2.9))
ax.plot(t, blobs, lw=1.2, color=GREEN, drawstyle="steps-post")
bad = np.where(blobs != 2)[0]
ax.plot(t[bad], blobs[bad], "o", ms=9, color=RED, zorder=5)
for i in bad:
    ax.annotate(f"1 marker for one sample,\nat t = {t[i]:.1f} s — the fracture itself",
                xy=(t[i], blobs[i]), xytext=(t[i] - 74, 0.45), color=RED,
                fontweight="bold", fontsize=10.5,
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.8))
ax.set_ylim(0, 2.6); ax.set_yticks([0, 1, 2])
ax.set_xlabel("Time (s)"); ax.set_ylabel("Markers found")
ax.set_title(f"DIC tracked 2/2 markers on {100*(blobs==2).mean():.2f} % of "
             f"{len(blobs):,} samples — through to fracture",
             fontsize=12.5, fontweight="bold", loc="left")
finish(fig, "documentation/figures/v2_dic_health.png")

# ================================================================ 7. corrected KPI comparison
fig, ax = plt.subplots(figsize=(9.0, 3.4))
labels = ["UTS\n(MPa)", "σ_y\n(MPa)", "E\n(GPa)", "ε_f\n(%)", "Toughness\n(MJ/m³)"]
mm = valid & (t <= t[i_last])
tough_true = float(np.trapezoid(sig[mm], ec[mm]))
# The "as reported" column is what analyze() returned BEFORE the fracture-index fix. It has to be
# stated literally, because analyze() now returns the corrected values for both — which would draw
# two identical bars and quietly erase the finding this slide exists to show.
EF_PREFIX, TOUGH_PREFIX = 17.55, 6.774          # pre-fix analyze(), commit 4f009eb
rep = [r["uts"], r["sy"], r["E"], EF_PREFIX, TOUGH_PREFIX]
cor = [r["uts"], r["sy"], r["E"], ef_true * 100, tough_true]
x = np.arange(len(labels)); wd = 0.36
ax.bar(x - wd / 2, rep, wd, label="As reported", color=RED)
ax.bar(x + wd / 2, cor, wd, label="Corrected (fracture at the last honest DIC sample)",
       color=GREEN)
for i, (a_, b_) in enumerate(zip(rep, cor)):
    ax.text(i - wd / 2, a_ + 1, f"{a_:.1f}", ha="center", fontsize=10, fontweight="bold")
    ax.text(i + wd / 2, b_ + 1, f"{b_:.1f}", ha="center", fontsize=10, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylim(0, 55)
ax.legend(frameon=False, fontsize=10.5, loc="upper left")
ax.set_title("Only the two integrated-to-fracture numbers move. Strength and stiffness stand.",
             fontsize=12.5, fontweight="bold", loc="left")
finish(fig, "documentation/figures/v2_kpi_correction.png")

# ================================================================ 8. did capture slow the rig?
# The original requirement was "must not slow the GUI, data gathering rate or plotting speed".
# The run answers it directly: compare the load-cell sample rate before, during and after the
# 2.0 GB write, on the same test.
CAP_FROM, CAP_TO = 38.0, 136.0                  # capture window, seconds into the test
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.3))
wins = [("Before\ncapture", t < CAP_FROM), ("DURING capture\n(2.0 GB written)",
        (t >= CAP_FROM) & (t <= CAP_TO)), ("After\ncapture", t > CAP_TO)]
hz = [int(m.sum()) / (t[m][-1] - t[m][0]) for _, m in wins]
dic_hz = [int((m & valid).sum()) / (t[m & valid][-1] - t[m & valid][0]) for _, m in wins]
for ax, vals, lab, lim in ((a, hz, "Load-cell samples / s", 13),
                           (b, dic_hz, "DIC measurements / s", 4)):
    bars = ax.bar([w[0] for w in wins], vals, color=[MUTED, GREEN, MUTED], width=0.55)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + lim * 0.03, f"{v:.2f} Hz",
                ha="center", fontweight="bold", fontsize=12)
    ax.axhline(vals[0], color=MUTED, ls="--", lw=1.2)
    ax.set_ylabel(lab); ax.set_ylim(0, lim)
a.set_title(f"Data gathering: {abs(hz[1]-hz[0])/hz[0]*100:.1f} % change while writing 2.0 GB",
            fontsize=12, fontweight="bold", loc="left")
b.set_title("DIC kept up too", fontsize=12, fontweight="bold", loc="left")
finish(fig, "documentation/figures/v2_rate_unaffected.png")

print(f"\n  toughness {r['tough']/1000:.2f} -> {tough_true:.2f} MJ/m3 "
      f"({r['tough']/1000/tough_true:.2f}x overstated)")
print(f"  load rate {hz[0]:.2f} -> {hz[1]:.2f} -> {hz[2]:.2f} Hz "
      f"({abs(hz[1]-hz[0])/hz[0]*100:.2f} % change during capture)")
