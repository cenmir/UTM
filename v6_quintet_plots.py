"""Figures for the V6 100% quintet (n=5) validation slides: overlay stress-strain,
strength repeatability vs references, ductility range, and offset-k vs datasheet.
Reuses the v6_compare analyze() (load-collapse fracture, anchor, DIC baseline re-zero)."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Software", "UTM_PyQt6"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statistics import mean, stdev
from utm_analysis import analyze

ROOT = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure"
FILES = {
    "V6a (S7)":  ROOT + r"\Specimen_S7_V2_Spray\UTM_Test_20260617_165405_V6a_TensionFailure.csv",
    "V6b (S8)":  ROOT + r"\Specimen_S8_V2_Spray\UTM_Test_20260625_144903_V6b_TensionFailure.csv",
    "V6c (S10)": ROOT + r"\Specimen_S10_V2_Spray\UTM_Test_20260625_151046_V6c_TensionFailure.csv",
    "V6d (S11)": ROOT + r"\Specimen_S11_V2_Spray\UTM_Test_20260625_154219_V6d_TensionFailure.csv",
    "V6e (S9)":  ROOT + r"\Specimen_S9_V2_Spray\UTM_Test_20260625_160032_V6e_TensionFailure.csv",
}
COL = {"V6a (S7)": "#1f77b4", "V6b (S8)": "#d62728", "V6c (S10)": "#2ca02c",
       "V6d (S11)": "#9467bd", "V6e (S9)": "#e08214"}
EPLA = {"E": 2.87, "uts": 58.0, "ef": 8.0}
CHA = {"uts": (32, 60), "sy": (30, 50), "E": (3.0, 5.5)}


# read_csv / linfit / analyze now come from utm_analysis (shared library).
# analyze() returns a superset dict incl. E, sy, uts, ef, tough, uts_ec, curve — used below.


R = {k: analyze(v) for k, v in FILES.items()}
names = list(FILES)
uts = [R[n]["uts"] for n in names]; sy = [R[n]["sy"] for n in names]
E = [R[n]["E"] for n in names]; ef = [R[n]["ef"]*100 for n in names]
print("UTS mean %.2f CV %.1f%%" % (mean(uts), stdev(uts)/mean(uts)*100))

# ---- 1. overlay stress-strain (batch V6b–e; pilot V6a omitted for clarity) ----
fig, ax = plt.subplots(figsize=(7.6, 5.6))
batch = [n for n in names if not n.startswith("V6a")]
for n in batch:
    xs, ys = zip(*R[n]["curve"])
    lab = f"{n}: UTS {R[n]['uts']:.1f} MPa, ε_f {R[n]['ef']*100:.1f}%"
    ax.plot(xs, ys, color=COL[n], lw=1.8, label=lab)
    ax.plot(R[n]["uts_ec"], R[n]["uts"], "o", color=COL[n], ms=5)
ax.set_xlabel("Cauchy strain  ε_c  (%)", fontsize=12)
ax.set_ylabel("Engineering stress  (MPa)", fontsize=12)
ax.set_title("V6 — 100 % infill, batch V6b–e (LED on, 0.1 mm/s)", fontweight="bold")
ax.set_xlim(0, 8); ax.set_ylim(0, 52); ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="lower right")
ax.text(0.15, 49.6, "Pilot V6a omitted for clarity (batch edge; kept in the n = 5 stats)",
        fontsize=8.5, color="#777", style="italic")
plt.tight_layout(); plt.savefig("images/V6/V6_quintet_curves.png", dpi=150, bbox_inches="tight"); plt.close()

# ---- 2. strength repeatability vs references ----
fig, ax = plt.subplots(figsize=(7.8, 5.4))
x = range(5)
m, sd = mean(uts), stdev(uts)
ax.axhspan(CHA["uts"][0], CHA["uts"][1], color="#c8e6c9", alpha=0.45, zorder=0, label="Chacón UTS range 32–60")
ax.axhline(EPLA["uts"], color="#1f5fa0", ls="--", lw=1.7, zorder=2, label="add:north E-PLA 58 MPa")
ax.axhspan(m-sd, m+sd, color="#999", alpha=0.18, zorder=1)
ax.axhline(m, color="#333", lw=1.4, zorder=2)
bars = ax.bar(x, uts, width=0.6, color=[COL[n] for n in names], edgecolor="black", zorder=3)
bars[0].set_hatch("////"); bars[0].set_edgecolor("#c00000"); bars[0].set_linewidth(1.8)
for xi, v in zip(x, uts):
    ax.text(xi, v+0.6, f"{v:.1f}", ha="center", fontsize=10, fontweight="bold")
ax.annotate("V6a — pilot\n(str/mod edge)", xy=(-0.2, uts[0]+0.3), xytext=(0, 52),
            fontsize=8.0, ha="center", va="bottom", fontweight="bold", color="#c00000",
            arrowprops=dict(arrowstyle="->", color="#c00000", lw=1.2))
ax.text(4.55, 53, f"mean {m:.1f} ± {sd:.1f} MPa  (CV {sd/m*100:.1f} %)", ha="right", va="bottom", fontsize=10.5, color="#333")
ax.set_xticks(x); ax.set_xticklabels([n.split()[0] for n in names], fontsize=11)
ax.set_ylabel("UTS  (MPa)", fontsize=12); ax.set_ylim(0, 64)
ax.set_title("Strength repeatability vs references (n = 5)", fontweight="bold")
ax.legend(fontsize=9, loc="lower center", ncol=1); ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig("images/V6/V6_strength_repeat.png", dpi=150, bbox_inches="tight"); plt.close()

# ---- 3. ductility range (bimodal) ----
fig, ax = plt.subplots(figsize=(7.8, 5.4))
cl0 = "#8c564b"; cl1 = "#17becf"
bar_c = [cl1 if v >= 6 else cl0 for v in ef]
ax.axhspan(min(ef), max(ef), color="#ffe0b2", alpha=0.5, zorder=0, label=f"measured range {min(ef):.1f}–{max(ef):.1f} %")
ax.axhline(EPLA["ef"], color="#1f5fa0", ls="--", lw=1.7, zorder=2, label="add:north E-PLA 8 %")
bars = ax.bar(x, ef, width=0.6, color=bar_c, edgecolor="black", zorder=3)
bars[0].set_hatch("////"); bars[0].set_edgecolor("#c00000"); bars[0].set_linewidth(1.8)
for xi, v in zip(x, ef):
    ax.text(xi, v+0.12, f"{v:.1f}", ha="center", fontsize=10, fontweight="bold")
ax.annotate("V6a — pilot\n(most brittle)", xy=(-0.2, ef[0]+0.15), xytext=(0, 5.4),
            fontsize=8.0, ha="center", va="bottom", fontweight="bold", color="#c00000",
            arrowprops=dict(arrowstyle="->", color="#c00000", lw=1.2))
ax.set_xticks(x); ax.set_xticklabels([n.split()[0] for n in names], fontsize=11)
ax.set_ylabel("Failure strain  ε_f  (%)", fontsize=12); ax.set_ylim(0, 9)
ax.set_title("Ductility — NOT repeatable (CV 33 %), bimodal", fontweight="bold")
ax.text(0.5, 8.4, "tough-skin cluster (A/B/D)", color=clo if (clo:=cl0) else clo, fontsize=9.5, ha="center")
ax.text(3.5, 8.4, "ductile cluster (C/E)", color=cl1, fontsize=9.5, ha="center")
ax.legend(fontsize=9, loc="upper center"); ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig("images/V6/V6_ductility.png", dpi=150, bbox_inches="tight"); plt.close()

# ---- 4. offset k vs add:north datasheet ----
fig, ax = plt.subplots(figsize=(6.4, 5.4))
props = ["UTS", "Modulus E", "Elong. ε_f"]
kk = [[EPLA["uts"]/v for v in uts], [EPLA["E"]/v for v in E], [EPLA["ef"]/v for v in ef]]
km = [mean(k) for k in kk]; ke = [(max(k)-min(k))/2 for k in kk]
colb = ["#2e7d32", "#2e7d32", "#e08214"]
ax.bar(range(3), km, yerr=ke, width=0.55, color=colb, edgecolor="black", capsize=6, zorder=3)
ax.axhline(1.20, color="#1f5fa0", ls="--", lw=1.7, zorder=2); ax.text(2.4, 1.22, "k ≈ 1.2", ha="right", color="#1f5fa0", fontweight="bold", fontsize=10)
ax.axhline(1.0, color="#888", ls=":", lw=1.3, zorder=2); ax.text(2.4, 1.0, "parity", ha="right", va="bottom", color="#777", fontsize=9)
for xi, (kv, ret) in enumerate(zip(km, [mean(uts)/EPLA["uts"]*100, mean(E)/EPLA["E"]*100, mean(ef)/EPLA["ef"]*100])):
    ax.text(xi, kv+ke[xi]+0.08, f"k={kv:.2f}\n{ret:.0f}%", ha="center", fontsize=10, fontweight="bold")
ax.set_xticks(range(3)); ax.set_xticklabels(props, fontsize=11)
ax.set_ylabel("offset k = E-PLA spec / measured (n=5)", fontsize=11); ax.set_ylim(0, 3.0)
ax.set_title("Knock-down vs add:north E-PLA datasheet", fontweight="bold")
ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig("images/V6/V6_offset_k.png", dpi=150, bbox_inches="tight"); plt.close()
print("saved 4 figs: V6_quintet_curves / V6_strength_repeat / V6_ductility / V6_offset_k")
