"""Auto-preload speed schedule (from main.py PRELOAD_SPEED_KNOTS): crosshead speed vs load as a
fraction of target. Fast approach → ramp down → gentle crawl, stop at 1.03x target to offset PLA
stress relaxation. Saves preload_schedule.png for the deck."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

KNOTS = [(0.0, 0.20), (0.10, 0.20), (0.15, 0.10), (0.50, 0.10), (0.90, 0.02), (1.0, 0.02)]
STOP = 1.03
xs = [k[0] for k in KNOTS] + [STOP]
ys = [k[1] for k in KNOTS] + [0.02]

fig, ax = plt.subplots(figsize=(7.4, 4.7))
ax.axvspan(0.0, 0.15, color="#c8e6c9", alpha=0.35, zorder=0)
ax.axvspan(0.15, 0.90, color="#fff3cd", alpha=0.55, zorder=0)
ax.axvspan(0.90, STOP, color="#f8d7da", alpha=0.55, zorder=0)
ax.plot(xs, ys, "-", color="#1f77b4", lw=2.7, zorder=3)
ax.plot([k[0] for k in KNOTS], [k[1] for k in KNOTS], "o", color="#1f77b4",
        ms=7, mec="black", mew=0.6, zorder=4)
ax.axvline(STOP, color="#c00000", ls="--", lw=2.0, zorder=5)

ax.text(0.065, 0.213, "fast approach\n0.20 mm/s", ha="center", fontsize=10, color="#2e7d32", fontweight="bold")
ax.text(0.45, 0.118, "0.10 mm/s", ha="center", fontsize=10, color="#8a6d00", fontweight="bold")
ax.text(0.70, 0.068, "ramp down", ha="center", fontsize=9.5, color="#8a6d00", rotation=-20)
ax.text(0.945, 0.036, "gentle crawl\n0.02 mm/s", ha="center", fontsize=9.5, color="#a11")
ax.text(STOP - 0.01, 0.205, "STOP at 1.03× target\n(held load relaxes ~2 %\n→ settles ≥ target)",
        ha="right", va="top", color="#c00000", fontsize=9.5, fontweight="bold")

ax.set_xlabel("load as a fraction of target   (target e.g. 470 N)", fontsize=11)
ax.set_ylabel("crosshead speed (mm/s)", fontsize=11)
ax.set_title("Auto-preload speed schedule — load-scheduled, live SetSpeed", fontweight="bold")
ax.set_xlim(-0.02, 1.12); ax.set_ylim(0, 0.235)
ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig("preload_schedule.png", dpi=150, bbox_inches="tight"); plt.close()
print("saved preload_schedule.png")
