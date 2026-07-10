"""Fracture-pattern montage for the 8.6.20 tensile campaign: fractured-specimen close-ups
grouped 50 % infill (V5 group) over 100 % infill (V6 quintet). Each tile is labelled with the
measured UTS and failure strain (load-collapse analyze, same as v6_compare). Saves one figure
(V6_fracture_patterns.png) for the comparison slide."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Software", "UTM_PyQt6"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from utm_analysis import analyze

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


# analyze() now comes from utm_analysis (shared library) — same load-collapse + strain-jump detector.


def crop(path):
    im = Image.open(ROOT + path)
    w, h = im.size
    return im.crop((0, int(0.27 * h), w, int(0.99 * h)))   # drop grip tab, keep gauge + fracture faces


def tile(ax, spec, band):
    test, sp, csv, img, tag = spec
    r = analyze(ROOT + csv)
    uts, ef = r["uts"], r["ef"]
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
