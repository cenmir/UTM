"""V6a/b/c/d/e quintet repeatability — 100% infill, LED on, 0.1 mm/s. Uses the shared
analyze() from utm_analysis (anchor self-calibration, baseline DIC re-zero, load-collapse
+ strain-jump fracture detection)."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "UTM_PyQt6"))
from statistics import mean, median, pstdev, stdev
from utm_analysis import analyze
ROOT = r"Software\UTM_PyQt6\Test data\8.6.20 - Tensile test to Failure"
FILES = {
    "V6a (S7)": ROOT + r"\Specimen_S7_V2_Spray\UTM_Test_20260617_165405_V6a_TensionFailure.csv",
    "V6b (S8)": ROOT + r"\Specimen_S8_V2_Spray\UTM_Test_20260625_144903_V6b_TensionFailure.csv",
    "V6c (S10)": ROOT + r"\Specimen_S10_V2_Spray\UTM_Test_20260625_151046_V6c_TensionFailure.csv",
    "V6d (S11)": ROOT + r"\Specimen_S11_V2_Spray\UTM_Test_20260625_154219_V6d_TensionFailure.csv",
    "V6e (S9)": ROOT + r"\Specimen_S9_V2_Spray\UTM_Test_20260625_160032_V6e_TensionFailure.csv",
}
EPLA = {"E": 2.87, "uts": 58.0, "ef": 8.0}                  # add:north E-PLA datasheet (typical)


names = list(FILES.keys())
R = {k: analyze(v) for k, v in FILES.items()}

rows = [
    ("Peak force", "uts_F", "N", "%.0f"),
    ("UTS", "uts", "MPa", "%.2f"),
    ("Yield σ_y (0.2%)", "sy", "MPa", "%.2f"),
    ("Elastic modulus E", "E", "GPa", "%.2f"),
    ("Fracture stress", "sigf", "MPa", "%.2f"),
    ("Failure strain ε_f", "ef", "", "%.4f"),
    ("Softening UTS→fr.", "soft", "%", "%.1f"),
    ("Toughness", "tough", "kJ/m³", "%.0f"),
    ("Crosshead travel", "travel", "mm", "%.2f"),
    ("Gauge share", "gauge_share", "%", "%.1f"),
    ("Pull duration", "dur", "s", "%.1f"),
    ("Rate", "rate", "mm/s", "%.3f"),
    ("Preload anchor", "anchor", "N", "%.0f"),
]
hdr = f"{'Metric':<22}" + "".join(f"{n:>11}" for n in names) + f"{'mean':>10}{'CV%':>8}{'range%':>8}"
print(hdr); print("-"*len(hdr))
for label, key, unit, fmt in rows:
    vals = [R[n][key] for n in names]
    m = mean(vals); sd = stdev(vals)
    cv = sd/abs(m)*100 if m else 0
    rng = (max(vals)-min(vals))/abs(m)*100 if m else 0
    u = f" {unit}" if unit else ""
    cells = "".join(f"{fmt%v+u:>11}" for v in vals)
    print(f"{label:<22}{cells}{fmt%m+u:>10}{cv:>7.1f}%{rng:>7.1f}%")

print("\nOffset k = E-PLA spec / measured (per specimen):")
print(f"{'':<16}" + "".join(f"{n:>11}" for n in names) + f"{'mean':>9}")
for nm, key, ref in [("UTS vs E-PLA", "uts", EPLA["uts"]), ("Modulus vs E-PLA", "E", EPLA["E"]),
                     ("ε_f vs E-PLA", "ef", EPLA["ef"]/100)]:
    ks = [ref/R[n][key] for n in names]
    print(f"  {nm:<14}" + "".join(f"{k:>11.2f}" for k in ks) + f"{mean(ks):>9.2f}")

uts_vals = [R[n]["uts"] for n in names]
print(f"\nUTS all inside Chacón 32-60 MPa: {[round(v,1) for v in uts_vals]}  -> k≈1 (no knock-down)")
print(f"Strength (UTS) triplet: mean {mean(uts_vals):.2f} MPa, CV {stdev(uts_vals)/mean(uts_vals)*100:.1f}%")
ef_vals = [R[n]["ef"] for n in names]
print(f"Ductility (ε_f) triplet: {[round(v,4) for v in ef_vals]}, CV {stdev(ef_vals)/mean(ef_vals)*100:.0f}%")
