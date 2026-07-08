"""Fracture-pattern montage for the 8.6.20 tensile campaign: fractured-specimen close-ups
grouped 50 % infill (V5 group) over 100 % infill (V6 quintet). Each tile is labelled with the
measured UTS and failure strain (load-collapse analyze, same as v6_compare). Saves one figure
(V6_fracture_patterns.png) for the comparison slide."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from statistics import mean, median

AREA = 80.0
ROOT = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure"

# (test, specimen, csv, image, tag)
SPECS_50 = [
    ("V5",  "S4", r"\Specimen_S4_V1_Spray\UTM_Test_20260612_172333_V5_TensionFailure.csv",  r"\Specimen_S4_V1_Spray\S4.jpg",       ""),
    ("V5b", "S3", r"\Specimen_S3_V1_Spray\UTM_Test_20260617_122450__V5b_TensionFailure.csv", r"\Specimen_S3_V1_Spray\S3(1).jpg",    ""),
    ("V5c", "S2", r"\Specimen_S2_V1_Spray\UTM_Test_20260617_130559_V5c_0_TensionFailure.csv", r"\Specimen_S2_V1_Spray\S2_2 (1).jpg", ""),
]
SPECS_100 = [
    ("V6a", "S7",  r"\Specimen_S7_V2_Spray\UTM_Test_20260617_165405_V6a_TensionFailure.csv",  r"\Specimen_S7_V2_Spray\S7(1).jpg",    "pilot"),
    ("V6b", "S8",  r"\Specimen_S8_V2_Spray\UTM_Test_20260625_144903_V6b_TensionFailure.csv",  r"\Specimen_S8_V2_Spray\S8 (1).jpg",   ""),
    ("V6c", "S10", r"\Specimen_S10_V2_Spray\UTM_Test_20260625_151046_V6c_TensionFailure.csv", r"\Specimen_S10_V2_Spray\S10 (1).jpg", "ductile"),
    ("V6d", "S11", r"\Specimen_S11_V2_Spray\UTM_Test_20260625_154219_V6d_TensionFailure.csv", r"\Specimen_S11_V2_Spray\S11 (1).jpg", ""),
    ("V6e", "S9",  r"\Specimen_S9_V2_Spray\UTM_Test_20260625_160032_V6e_TensionFailure.csv",  r"\Specimen_S9_V2_Spray\S9 (1).jpg",   "ductile"),
]


def analyze(path):
    rows = [l.strip() for l in open(ROOT + path, newline="") if not l.startswith("#") and l.strip()]
    idx = {h: i for i, h in enumerate(rows[0].split(","))}
    d = []
    for r in rows[1:]:
        p = r.split(",")
        try:
            d.append({"t": float(p[idx["Time_s"]]), "F": float(p[idx["Force_N"]]),
                      "pos": float(p[idx["Position_mm"]]), "ec": float(p[idx["DIC_Cauchy"]]),
                      "lpx": float(p[idx["L_px"]])})
        except (ValueError, IndexError):
            continue
    bp = sorted(x["pos"] for x in d[:30])[15]
    mv = next(i for i, x in enumerate(d) if x["pos"] > bp + 0.005)
    ec0 = median([x["ec"] for x in d[:mv] if x["lpx"] > 100] or [0.0])
    pk = max(range(mv, len(d)), key=lambda i: d[i]["F"])
    fr_load = next((i for i in range(pk, len(d)) if d[i]["F"] < 0.5 * d[pk]["F"]), len(d) - 1)
    # trim at the fracture frame: an unphysical one-step strain jump (> 3 %) = markers flying apart
    # (V5/S4 glitches to ec 0.19 while force is still up, so it beats load-collapse into the window).
    fr_glitch = next((i for i in range(mv + 1, len(d))
                      if d[i - 1]["lpx"] > 100 and d[i]["lpx"] > 100 and d[i]["ec"] - d[i - 1]["ec"] > 0.03), None)
    fr = min([fr_load] + ([fr_glitch] if fr_glitch is not None else []))
    post = [x for x in d[fr + 1:] if x["t"] > d[fr]["t"] + 2.0]
    anc = -mean(x["F"] for x in post)
    test = [x for x in d[mv:fr] if x["lpx"] > 100]
    uts = max((x["F"] + anc) / AREA for x in test)
    last = max(test, key=lambda x: x["t"])
    return uts, last["ec"] - ec0


def crop(path):
    im = Image.open(ROOT + path)
    w, h = im.size
    return im.crop((0, int(0.27 * h), w, int(0.99 * h)))   # drop grip tab, keep gauge + fracture faces


def tile(ax, spec, band):
    test, sp, csv, img, tag = spec
    uts, ef = analyze(csv)
    ax.imshow(crop(img)); ax.axis("off")
    ttl = f"{test} · {sp}"
    if tag:
        ttl += f"  ({tag})"
    ax.set_title(ttl, fontsize=10.5, fontweight="bold", color=band, pad=3)
    ax.text(0.5, -0.045, f"UTS {uts:.1f} MPa · ε_f {ef*100:.1f} %", transform=ax.transAxes,
            ha="center", va="top", fontsize=9.5, color="#222")


fig = plt.figure(figsize=(13.0, 6.7))
C50, C100 = "#1f5fa0", "#c00000"
cw = 0.176                       # cell width; bottom row = 5 columns
x0 = [0.055 + i * 0.186 for i in range(5)]
# top row (50 %): 3 tiles centred under bottom columns 2-4
for k, spec in enumerate(SPECS_50):
    ax = fig.add_axes([x0[k + 1], 0.545, cw, 0.345]); tile(ax, spec, C50)
# bottom row (100 %): 5 tiles
for k, spec in enumerate(SPECS_100):
    ax = fig.add_axes([x0[k], 0.075, cw, 0.345]); tile(ax, spec, C100)

fig.text(0.055, 0.945, "50 % INFILL — V5 group (LED off)", fontsize=13, fontweight="bold", color=C50)
fig.text(0.055, 0.475, "100 % INFILL — V6 quintet (LED on)", fontsize=13, fontweight="bold", color=C100)
fig.savefig("V6_fracture_patterns.png", dpi=150, bbox_inches="tight")
plt.close()
print("saved V6_fracture_patterns.png")
