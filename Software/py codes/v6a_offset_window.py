"""V6 single-common-offset-factor analysis (n = 5 mean; same interval-intersection method as V5).
For each property the feasible k window = [lit_lo/measured, lit_hi/measured]; a single
uniform k must lie in the intersection. Shows that at 100 % infill the ALL-property
window is EMPTY (E pulls up, in-range strength caps it) while the strength-only
window contains k = 1 → use k = 1 (no knock-down) for strength.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

M = {"E": 2.60, "σ_y": 45.0, "UTS": 46.2}            # V6 n=5 mean (GPa / MPa)
LIT = {"E": (3.0, 5.5), "σ_y": (30, 50), "UTS": (32, 60)}   # Chacón (2017)
order = ["E", "σ_y", "UTS"]
col = {"E": "#6a1b9a", "σ_y": "#2e7d32", "UTS": "#d62728"}
win = {p: (LIT[p][0]/M[p], LIT[p][1]/M[p]) for p in order}

all_lo = max(win[p][0] for p in order); all_hi = min(win[p][1] for p in order)
s_lo = max(win["σ_y"][0], win["UTS"][0]); s_hi = min(win["σ_y"][1], win["UTS"][1])
print("per-property k windows:", {p: (round(a, 2), round(b, 2)) for p, (a, b) in win.items()})
print(f"all-property intersection: [{all_lo:.2f}, {all_hi:.2f}]  -> "
      f"{'EMPTY' if all_lo > all_hi else 'valid'}")
print(f"strength-only (σ_y,UTS):  [{s_lo:.2f}, {s_hi:.2f}]  (contains k=1: {s_lo <= 1 <= s_hi})")

fig, ax = plt.subplots(figsize=(12, 5.5))
for i, p in enumerate(order):
    lo, hi = win[p]; y = len(order)-i
    ax.barh(y, hi-lo, left=lo, height=0.42, color=col[p], alpha=0.85, edgecolor="black", zorder=3)
    ax.text(lo-0.025, y, f"{lo:.2f}", ha="right", va="center", fontsize=11)
    ax.text(hi+0.025, y, f"{hi:.2f}", ha="left", va="center", fontsize=11)
    ax.text(0.40, y, p, ha="right", va="center", fontsize=14, fontweight="bold", color=col[p])
ax.axvspan(s_lo, s_hi, color="#c8e6c9", alpha=0.55, zorder=0,
           label=f"strength common k ∈ [{s_lo:.2f}, {s_hi:.2f}]  (k=1 OK)")
ax.axvline(1.0, color="black", ls="--", lw=1.7, zorder=4, label="k = 1 (no knock-down)")
# conflict: E floor just above the strength ceiling
ax.annotate(f"E window opens at {win['E'][0]:.2f} — just above the\nstrength ceiling ({s_hi:.2f}) ⇒ no single all-property k\n(gap only {win['E'][0]-s_hi:.2f}; E ~13 % low, not far off)",
            xy=(win["E"][0], 3), xytext=(1.42, 3.55),
            ha="left", va="center", color="#b00020", fontsize=10.5, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#b00020", lw=1.6))
ax.set_yticks([]); ax.set_xlabel("offset factor  k = literature / measured")
ax.set_xlim(0.45, 2.45); ax.set_ylim(0.4, 3.95)
ax.set_title("V6 (n = 5, 100 % infill) — feasible offset-factor window per property", fontweight="bold")
ax.legend(loc="lower right", fontsize=11); ax.grid(axis="x", alpha=0.3)
plt.tight_layout(); plt.savefig("images/V6a/V6a_offset_window.png", dpi=150, bbox_inches="tight"); plt.close()
print("saved V6a_offset_window.png")
