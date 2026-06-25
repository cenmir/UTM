"""V6a (100% FDM) vs add:north E-PLA datasheet (ISO 527/178) — offset analysis.
Datasheet gives single typical values, so the offset is a single k = spec/measured
per property (vs the journal's ranges/windows). Strength and modulus share one
factor (~1.2) -> a coherent FFF knock-down; elongation is the brittle-FDM outlier.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

props = ["Tensile\nstrength", "Modulus E", "Elongation\nat break"]
meas = [47.82, 2.41, 2.98]     # V6a 100% FDM: MPa, GPa, %
spec = [58.0, 2.87, 8.0]       # add:north E-PLA: MPa, GPa, %
k = [s/m for s, m in zip(spec, meas)]
ret = [m/s*100 for m, s in zip(meas, spec)]
col = ["#2e7d32", "#2e7d32", "#e08214"]
print("k =", [round(v, 2) for v in k], " retention% =", [round(r) for r in ret])

fig, ax = plt.subplots(figsize=(8.8, 6.1))
x = list(range(3))
ax.bar(x, k, width=0.6, color=col, edgecolor="black", zorder=3)
ax.axhline(1.20, color="#1f5fa0", ls="--", lw=1.7, zorder=2)
ax.axhline(1.0, color="#888", ls=":", lw=1.4, zorder=2)
ax.text(2.46, 1.21, "k ≈ 1.20", ha="right", va="bottom", fontsize=10, color="#1f5fa0", fontweight="bold")
ax.text(2.46, 1.0, "parity", ha="right", va="bottom", fontsize=9.5, color="#777")
for xi, (kk, rr) in enumerate(zip(k, ret)):
    ax.text(xi, kk+0.07, f"k = {kk:.2f}", ha="center", fontsize=14, fontweight="bold")
    ax.text(xi, kk/2, f"{rr:.0f} %\nof spec", ha="center", va="center", color="white",
            fontsize=11.5, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(props, fontsize=12.5)
ax.set_ylabel("offset factor  k = E-PLA spec / measured", fontsize=12)
ax.set_ylim(0, 3.05)
ax.set_title("V6a (100 % FDM) vs add:north E-PLA datasheet (ISO 527)", fontweight="bold")
ax.grid(axis="y", alpha=0.3)
ax.text(0.0, 2.5, "strength & stiffness share\nONE factor (k≈1.2) →\ncoherent FFF knock-down",
        ha="center", fontsize=10, color="#1f5fa0",
        bbox=dict(facecolor="#eef4ec", edgecolor="none", boxstyle="round,pad=0.4"))
ax.text(2.0, 1.95, "elongation far higher\n(printed PLA is brittle)", ha="center", fontsize=10,
        color="#a0521a", bbox=dict(facecolor="#fdf1e6", edgecolor="none", boxstyle="round,pad=0.4"))
plt.tight_layout(); plt.savefig("V6a_epla_offset.png", dpi=150, bbox_inches="tight"); plt.close()
print("saved V6a_epla_offset.png")
