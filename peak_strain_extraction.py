"""Compute peak eps_c using three defensible methods for each V2 / V3 cycle.

Method (a)  instantaneous max |eps_c| during the hold phase
Method (b)  mean of eps_c over first 2 s of hold (recommended for report)
Method (c)  mean of eps_c over entire hold phase

The hold phase = window where |Position − Position_peak| < 0.001 mm AND |Speed| < 0.01 mm/s.

Outputs a comparison table printed to stdout.
"""

import csv
import math
import os

V2_FILES = [
    ("V2 T0", "Software/UTM_PyQt6/UTM_Test_20260604_110050_V2_Tension_T0.csv"),
    ("V2 T3", "Software/UTM_PyQt6/UTM_Test_20260604_110728_V2_Tension_T3.csv"),
    ("V2 T4", "Software/UTM_PyQt6/UTM_Test_20260604_111009_V2_Tension_T4.csv"),
    ("V2 T5", "Software/UTM_PyQt6/UTM_Test_20260604_111217_V2_Tension_T5.csv"),
    ("V2 T6", "Software/UTM_PyQt6/UTM_Test_20260604_112311_V2_Tension_T6.csv"),
    ("V2 T7", "Software/UTM_PyQt6/UTM_Test_20260604_112744._V2_Tension_T7.csv"),
]
V3_FILES = [
    ("V3 T0", "Software/UTM_PyQt6/UTM_Test_20260604_115945_V3_Compression_T0.csv"),
    ("V3 T3", "Software/UTM_PyQt6/UTM_Test_20260604_120155_V3_Compression_T3.csv"),
    ("V3 T4", "Software/UTM_PyQt6/UTM_Test_20260604_120955_V3_Compression_T4.csv"),
    ("V3 T5", "Software/UTM_PyQt6/UTM_Test_20260604_121202_V3_Compression_T5.csv"),
    ("V3 T6", "Software/UTM_PyQt6/UTM_Test_20260604_121411_V3_Compression_T6.csv"),
]


def read_csv(path):
    rows = []
    with open(path, newline="") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            rows.append(line.strip())
    header = rows[0].split(",")
    idx = {h: i for i, h in enumerate(header)}
    data = []
    for row in rows[1:]:
        parts = row.split(",")
        try:
            data.append({
                "t":   float(parts[idx["Time_s"]]),
                "F":   float(parts[idx["Force_N"]]),
                "pos": float(parts[idx["Position_mm"]]),
                "sp":  float(parts[idx["Speed_mm_s"]]),
                "ec":  float(parts[idx["DIC_Cauchy"]]),
                "et":  float(parts[idx["DIC_True"]]),
                "lpx": float(parts[idx["L_px"]]),
            })
        except (ValueError, IndexError):
            continue
    return data


def find_hold(data):
    """Return (hold_start_idx, hold_end_idx) where Position is at peak and Speed ≈ 0."""
    peak_pos = min((d["pos"] for d in data), key=abs) if False else None
    # peak Position = the |Position| value that is most extreme from baseline (~−7)
    positions = [d["pos"] for d in data]
    baseline = positions[0]
    peak_pos = max(positions, key=lambda p: abs(p - baseline))
    tol = 0.0015
    in_hold = [
        i for i, d in enumerate(data)
        if abs(d["pos"] - peak_pos) < tol and abs(d["sp"]) < 0.01 and abs(d["ec"]) > 1e-5
    ]
    if not in_hold:
        return None, None, None
    return in_hold[0], in_hold[-1], peak_pos


def method_a_max(data, i0, i1):
    """Most extreme |eps_c| in hold window."""
    return max((data[i]["ec"] for i in range(i0, i1 + 1)), key=abs)


def method_b_first2s(data, i0, i1):
    """Mean eps_c over first 2 s of hold."""
    t0 = data[i0]["t"]
    samples = [data[i]["ec"] for i in range(i0, i1 + 1) if data[i]["t"] - t0 <= 2.0 and abs(data[i]["ec"]) > 1e-5]
    return sum(samples) / len(samples) if samples else float("nan")


def method_c_full(data, i0, i1):
    """Mean eps_c over entire hold."""
    samples = [data[i]["ec"] for i in range(i0, i1 + 1) if abs(data[i]["ec"]) > 1e-5]
    return sum(samples) / len(samples) if samples else float("nan")


def summarise(label, path):
    if not os.path.exists(path):
        print(f"{label}: FILE NOT FOUND {path}")
        return None
    data = read_csv(path)
    i0, i1, peak_pos = find_hold(data)
    if i0 is None:
        print(f"{label}: no hold phase detected")
        return None
    a = method_a_max(data, i0, i1)
    b = method_b_first2s(data, i0, i1)
    c = method_c_full(data, i0, i1)
    n_hold = i1 - i0 + 1
    print(f"{label}  peakPos={peak_pos:+.4f}  hold={n_hold} pts  "
          f"(a)max={a:+.6f}  (b)first2s={b:+.6f}  (c)full={c:+.6f}")
    return {"label": label, "a": a, "b": b, "c": c}


def deviation_pct(x, y):
    return abs(x - y) / max(abs(x), abs(y)) * 100 if max(abs(x), abs(y)) > 0 else 0


def report(series_label, results, dev_pair):
    print(f"\n=== {series_label} ===")
    print(f"{'Cycle':<7}{'(a) max eps_c':>16}{'(b) first-2s eps_c':>20}{'(c) full-hold eps_c':>20}")
    for r in results:
        print(f"{r['label']:<7}{r['a']:>16.6f}{r['b']:>20.6f}{r['c']:>20.6f}")
    # deviation between dev_pair
    p1, p2 = dev_pair
    r1 = next(r for r in results if r["label"] == p1)
    r2 = next(r for r in results if r["label"] == p2)
    print(f"\n|{p1} vs {p2}| deviation:")
    print(f"  Method (a) max:       {deviation_pct(r1['a'], r2['a']):.2f} %")
    print(f"  Method (b) first-2s:  {deviation_pct(r1['b'], r2['b']):.2f} %")
    print(f"  Method (c) full-hold: {deviation_pct(r1['c'], r2['c']):.2f} %")


print("Processing V2 (tension) files...")
v2 = [summarise(label, path) for label, path in V2_FILES]
v2 = [r for r in v2 if r]
report("V2 Tension — peak eps_c by method", v2, ("V2 T6", "V2 T7"))

print("\nProcessing V3 (compression) files...")
v3 = [summarise(label, path) for label, path in V3_FILES]
v3 = [r for r in v3 if r]
report("V3 Compression — peak eps_c by method", v3, ("V3 T5", "V3 T6"))
