"""8.6.20 - Tensile-to-failure analysis (V5, fresh PLA specimen).

Reconstructs true stress using the post-fracture force anchor (after fracture
the specimen carries zero load, so the display reading equals minus the
effective preload at tare). Extracts:
  - E_apparent (linear regression on early elastic window)
  - sigma_y (0.2 % offset)
  - UTS (true stress) and strain at UTS
  - failure strain eps_f (last valid DIC sample before fracture)
  - curve shape + plot

Pass criteria are checked against Chacon et al. (2017): E = 3.0-5.5 GPa,
sigma_y = 30-50 MPa, plus geometry-validity checks.
"""

from statistics import mean
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = r"Software\UTM_PyQt6\8.6.20\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv"
AREA = 80.0  # mm^2 nominal (10 x 8 mm, CAD-verified)


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
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    ym = sy / n
    sst = sum((y - ym) ** 2 for y in ys)
    ssr = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    return slope, intercept, (1 - ssr / sst if sst else float("nan"))


data = read_csv(CSV)
print(f"Rows: {len(data)}  duration {data[-1]['t']:.1f} s")

# ---- Find fracture: first DIC geometry discontinuity (L_px jump) ----
fr_i = next(i for i in range(1, len(data)) if abs(data[i]["lpx"] - data[i-1]["lpx"]) > 50)
t_fr = data[fr_i]["t"]
drop_i = max(range(1, len(data)), key=lambda i: data[i-1]["F"] - data[i]["F"])
print(f"Fracture at t = {t_fr:.2f} s (L_px jump {data[fr_i-1]['lpx']:.0f} -> {data[fr_i]['lpx']:.0f} px; "
      f"force drop {data[drop_i-1]['F'] - data[drop_i]['F']:.0f} N at t={data[drop_i]['t']:.2f}s)")

pre = data[:fr_i]          # up to last sample before fracture
post = [d for d in data[fr_i+1:] if d["t"] > t_fr + 2.0]

# ---- Preload anchor: post-fracture the specimen carries 0 N ----
anchor = -mean(d["F"] for d in post)
print(f"Post-fracture display force = {-anchor:.1f} N  ->  effective preload at tare = {anchor:.1f} N")
print(f"True force = display + {anchor:.1f} N")

# ---- Motion start ----
mv_i = next(i for i, d in enumerate(data) if d["pos"] > 0.005)
print(f"Motion start t = {data[mv_i]['t']:.2f} s; fracture after {t_fr - data[mv_i]['t']:.1f} s of pull")
print(f"Position at fracture = {pre[-1]['pos']:.3f} mm")

# ---- Key quantities (true stress, nominal area) ----
for d in pre:
    d["sig"] = (d["F"] + anchor) / AREA

uts_i = max(range(len(pre)), key=lambda i: pre[i]["sig"])
uts = pre[uts_i]
last = pre[-1]
print()
print(f"UTS (true, nominal area)   = {uts['sig']:.2f} MPa  at eps_c = {uts['ec']:.4f}  (t={uts['t']:.1f}s, pos={uts['pos']:.2f} mm)")
print(f"Stress at fracture          = {last['sig']:.2f} MPa  ({(uts['sig']-last['sig'])/uts['sig']*100:.1f} % softening after UTS)")
print(f"Failure strain eps_f (DIC)  = {last['ec']:.4f}")
print(f"Motor strain at fracture    = {last['ms']:.4f}  (DIC/motor = {last['ec']/last['ms']:.2f})")
print(f"Peak true force             = {(uts['sig']*AREA):.0f} N")

# ---- Elastic modulus: regression on early window ----
# window: motion started, strain between 0.0005 and 0.004 (well below yield)
win = [d for d in pre if 0.0005 <= d["ec"] <= 0.004 and d["pos"] > 0.005]
E_MPa, c0, r2 = linfit([d["ec"] for d in win], [d["sig"] for d in win])
print()
print(f"E_apparent = {E_MPa/1000:.2f} GPa  (window eps 0.0005-0.004, n={len(win)}, R^2={r2:.4f})")

# ---- 0.2 % offset yield ----
sig_y = None
for d in pre[mv_i:]:
    line = E_MPa * (d["ec"] - 0.002) + c0
    if line >= d["sig"]:
        sig_y = d["sig"]; eps_y = d["ec"]
        break
if sig_y:
    print(f"sigma_y (0.2% offset)       = {sig_y:.2f} MPa at eps = {eps_y:.4f}")
else:
    print("sigma_y (0.2% offset)       = not reached before fracture")

# ---- monotonicity before UTS ----
maxdrop = 0
for i in range(mv_i+1, uts_i):
    d = pre[i-1]["F"] - pre[i]["F"]
    maxdrop = max(maxdrop, d)
print(f"Largest pre-UTS force drop  = {maxdrop:.1f} N  ({maxdrop/(uts['sig']*AREA)*100:.2f} % of peak)")

# ---- DIC tracking integrity ----
t_total = t_fr - data[mv_i]["t"]
print(f"DIC valid through fracture: last pre-fracture eps_c = {last['ec']:.4f} at t = {last['t']:.2f}s "
      f"({(last['t']-data[mv_i]['t'])/t_total*100:.1f} % of test)")

# ---- Plot ----
fig, ax = plt.subplots(figsize=(11, 7))
xs = [d["ec"] for d in pre[mv_i:]]
ys = [d["sig"] for d in pre[mv_i:]]
ax.plot(xs, ys, "-", color="#1f77b4", linewidth=1.8, label="V5 fresh PLA (engineering stress, nominal 80 mm2)")

# elastic fit line
xfit = [0, 0.006]
ax.plot(xfit, [E_MPa*x + c0 for x in xfit], "--", color="green", linewidth=1.5,
        label=f"Elastic fit: E = {E_MPa/1000:.2f} GPa (R2={r2:.3f})")
# offset line
xoff = [0.002, 0.026]
ax.plot(xoff, [E_MPa*(x-0.002) + c0 for x in xoff], ":", color="green", linewidth=1.3,
        label="0.2 % offset line")

ax.plot(uts["ec"], uts["sig"], "v", color="#d62728", markersize=14,
        label=f"UTS = {uts['sig']:.1f} MPa at eps = {uts['ec']:.3f}")
ax.plot(last["ec"], last["sig"], "x", color="black", markersize=14, markeredgewidth=3,
        label=f"Fracture: eps_f = {last['ec']:.4f}, sigma = {last['sig']:.1f} MPa")
if sig_y:
    ax.plot(eps_y, sig_y, "o", color="orange", markersize=11,
            label=f"sigma_y (0.2% offset) = {sig_y:.1f} MPa")

ax.set_xlabel("DIC Cauchy strain (from preloaded reference)", fontsize=12)
ax.set_ylabel("Engineering stress (MPa, nominal area)", fontsize=12)
ax.set_title("8.6.20 - V5 tensile test to failure, fresh PLA\n"
             f"preload anchor +{anchor:.0f} N from post-fracture zero", fontsize=13, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=10)
ax.set_xlim(left=-0.0005)
ax.set_ylim(bottom=0)
plt.tight_layout()
plt.savefig("V5_tensile_failure_curve.png", dpi=150, bbox_inches="tight")
print("\nSaved plot: V5_tensile_failure_curve.png")
