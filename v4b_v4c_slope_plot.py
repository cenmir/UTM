"""Single-panel linearity plot for the 8.6.3 presentation slide.
Shows eps_c vs Position for V4b and V4c with engaged-regime linear fits.
"""

from statistics import mean, stdev
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

V4B = r"Software\UTM_PyQt6\8.6.3\UTM_Test_20260605_152501_V4b_Staricase_Tension.csv"
V4C = r"Software\UTM_PyQt6\8.6.3\UTM_Test_20260605_164908_V4c_Staircase_Tension_350N.csv"


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
                "t": float(parts[idx["Time_s"]]), "F": float(parts[idx["Force_N"]]),
                "pos": float(parts[idx["Position_mm"]]), "sp": float(parts[idx["Speed_mm_s"]]),
                "ms": float(parts[idx["Motor_Strain"]]), "ec": float(parts[idx["DIC_Cauchy"]]),
            })
        except (ValueError, IndexError):
            continue
    return out


def detect_holds(data):
    holds, i, n = [], 0, len(data)
    while i < n:
        if abs(data[i]["sp"]) >= 0.01:
            i += 1; continue
        j, start_pos = i, data[i]["pos"]
        while j < n and abs(data[j]["sp"]) < 0.01 and abs(data[j]["pos"] - start_pos) < 0.005:
            j += 1
        if data[j-1]["t"] - data[i]["t"] >= 2.0:
            holds.append((i, j-1))
        i = j
    return holds


def step_stats(data, i0, i1):
    t0 = data[i0]["t"]
    s = [d for d in data[i0:i1+1] if d["t"]-t0 >= 2.0 and abs(d["ec"]) > 1e-7]
    if len(s) < 5: s = data[i0:i1+1]
    return {"pos": mean(d["pos"] for d in s), "ec": mean(d["ec"] for d in s),
            "ms": mean(d["ms"] for d in s)}


def linfit(xs, ys):
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
    slope = (n*sxy - sx*sy) / (n*sxx - sx*sx)
    intercept = (sy - slope*sx) / n
    ymean = sy / n
    r2 = 1 - sum((y - (slope*x + intercept))**2 for x, y in zip(xs, ys)) / sum((y - ymean)**2 for y in ys)
    return slope, intercept, r2


def asc_stats(path, skip_initial=False):
    data = read_csv(path)
    holds = detect_holds(data)
    stats = [step_stats(data, i0, i1) for i0, i1 in holds]
    if skip_initial and stats and stats[0]["pos"] > 0.4:
        stats = stats[1:]
    peak = max(range(len(stats)), key=lambda i: stats[i]["pos"])
    return stats[:peak+1]


v4b = asc_stats(V4B)
v4c = asc_stats(V4C, skip_initial=True)

# Fits
v4b_eng = [s for s in v4b if s["pos"] >= 0.35]
v4c_clean = [s for s in v4c if abs(s["pos"] - 0.6) > 0.05]
sb, ib, rb = linfit([s["pos"] for s in v4b_eng], [s["ec"] for s in v4b_eng])
sc, ic, rc = linfit([s["pos"] for s in v4c_clean], [s["ec"] for s in v4c_clean])

# Plot
fig, ax = plt.subplots(1, 1, figsize=(11, 6.5))

# V4b
ax.plot([s["pos"] for s in v4b], [s["ec"] for s in v4b], "o", color="#1f77b4",
        markersize=14, label="V4b ASC points (+180 N preload, insufficient)",
        markeredgecolor="black", markeredgewidth=0.8)
xs_b = [0.35, 1.0]
ax.plot(xs_b, [sb*x + ib for x in xs_b], "-", color="#1f77b4", linewidth=2.5,
        label=f"V4b engaged fit (Pos ≥ 0.4 mm):  slope = {sb*1000:.2f} ×10⁻³/mm,  R² = {rb:.4f}")

# V4c
ax.plot([s["pos"] for s in v4c], [s["ec"] for s in v4c], "s", color="#d62728",
        markersize=14, label="V4c ASC points (+350 N preload)",
        markeredgecolor="black", markeredgewidth=0.8)
xs_c = [0, 0.8]
ax.plot(xs_c, [sc*x + ic for x in xs_c], "-", color="#d62728", linewidth=2.5,
        label=f"V4c clean fit (Pos ≠ 0.6 mm):  slope = {sc*1000:.2f} ×10⁻³/mm,  R² = {rc:.4f}")

# Y-value annotations next to each point (small font)
for s in v4b:
    ax.annotate(f"{s['ec']:+.5f}", xy=(s["pos"], s["ec"]),
                xytext=(8, -3), textcoords="offset points",
                fontsize=7, color="#1f77b4", fontweight="bold")
for s in v4c:
    ax.annotate(f"{s['ec']:+.5f}", xy=(s["pos"], s["ec"]),
                xytext=(8, 5), textcoords="offset points",
                fontsize=7, color="#d62728", fontweight="bold")

# Slack zone shading
ax.axvspan(0, 0.35, color="gray", alpha=0.10)
ax.text(0.175, -0.0005, "V4b slack zone\n(grip take-up)", ha="center", va="center", fontsize=9,
        color="#555555", style="italic")

# Pos 0.6 anomaly marker on V4c
pos06 = next(s for s in v4c if abs(s["pos"] - 0.6) < 0.05)
ax.annotate("Pos 0.6 anomaly\n(viscoelastic / yield onset)",
            xy=(pos06["pos"], pos06["ec"]), xytext=(0.62, 0.0003),
            fontsize=9, color="#A52A2A", style="italic",
            arrowprops=dict(arrowstyle="->", color="#A52A2A", lw=1.2))

ax.set_xlabel("Position (mm)", fontsize=13)
ax.set_ylabel("DIC ε_c  (Cauchy strain)", fontsize=13)
ax.set_title("Phase 8.6.3 — DIC linearity vs commanded crosshead position\n"
             "V4b (+180 N preload, insufficient) vs V4c (+350 N preload), PLA specimen",
             fontsize=13, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=10, framealpha=0.95)
ax.axhline(0, color="gray", linewidth=0.5)
ax.set_xlim(-0.05, 1.05)
ax.set_ylim(-0.0009, 0.0017)

plt.tight_layout()
plt.savefig("V4b_V4c_linearity_slide.png", dpi=160, bbox_inches="tight")
print("Saved: V4b_V4c_linearity_slide.png")
print(f"V4b engaged: slope = {sb:.6f}/mm, R² = {rb:.4f}")
print(f"V4c clean:   slope = {sc:.6f}/mm, R² = {rc:.4f}")
