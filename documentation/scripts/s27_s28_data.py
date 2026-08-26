"""S27 / S28 — the 50 % infill video pair — and the infill knock-down factor.

Two questions, and they need different comparison sets:

  * S27 vs S28: repeatability of a 50 % specimen under the capture protocol.
  * 50 % vs 100 %: the KNOCK-DOWN FACTOR k = datasheet / measured. A 100 % specimen is close to
    solid material and should land near k ≈ 1; a 50 % one carries roughly half the load-bearing
    section and has needed k ≈ 2.4 to reach literature. Confirming that on a fresh pair, measured
    with the same capture protocol as the 100 % pair, is what closes the question — it separates
    "our numbers are low" from "our specimens are half air".

Canonical CSV per specimen is the one run.json points at. Both folders hold several saves of the
SAME run (the buffer kept growing while idle, so a later save is the same test with a longer tail);
analyze() trims to the test window and returns identical numbers from any of them, but the capture
link is only correct for one.
"""
import csv
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", "..", "Software", "UTM_PyQt6"))
sys.path.insert(0, _APP)

from utm_analysis import analyze, read_csv                          # noqa: E402
import utm_registry as _REG                                         # noqa: E402

BASE = os.path.join(_APP, "Test data", "8.6.20 - Tensile test to Failure")
AREA_MM2 = GAUGE_MM = 80.0

# add:north E-PLA technical datasheet — the canonical material reference (reference_addnorth_tds).
TDS = dict(UTS=58.0, E=2.87, ef=8.0)
TDS_NAME = "add:north E-PLA TDS"

RUNS = {
    "S27": dict(folder="Specimen_S27_V1_Spray_Video4", capture="20260817_155425",
                csv="UTM_Test_20260817_155639.csv", label="S27 · VC4",
                infill=50.0, colour="#2F9E44"),
    "S28": dict(folder="Specimen_S28_V1_Spray_Video5", capture="20260817_160817",
                csv="UTM_Test_20260817_161046.csv", label="S28 · VC5",
                infill=50.0, colour="#6A3D9A"),
    # The 100 % video pair, same protocol, for the infill comparison.
    "S25": dict(folder="Specimen_S25_V2_Spray_Video2", capture="20260817_103811",
                csv="UTM_Test_20260817_103930_100%infill_Videocapture_2.csv", label="S25 · VC2",
                infill=100.0, colour="#1F6FB4"),
    "S26": dict(folder="Specimen_S26_V2_Spray_Video3", capture="20260817_111525",
                csv="UTM_Test_20260817_111700_100%infill_Videocapture3.csv", label="S26 · VC3",
                infill=100.0, colour="#D95F02"),
}
PAIR_50 = ("S27", "S28")
PAIR_100 = ("S25", "S26")
ORDER = PAIR_50 + PAIR_100

_cache = {}


def csv_path(tag):
    return os.path.join(BASE, RUNS[tag]["folder"], RUNS[tag]["csv"])


def capture_dir(tag):
    return os.path.join(BASE, RUNS[tag]["folder"], RUNS[tag]["capture"])


def run(tag):
    if tag in _cache:
        return _cache[tag]
    p = csv_path(tag)
    rows = read_csv(p)
    col = lambda k: np.array([r[k] for r in rows], float)           # noqa: E731
    d = dict(RUNS[tag], tag=tag, path=p, n=len(rows),
             t=col("t"), F=col("F"), pos=col("pos"), ec=col("ec"), lpx=col("lpx"))
    d["valid"] = d["lpx"] > 100
    d["r"] = analyze(p, AREA_MM2, GAUGE_MM)
    d["moved"] = int(np.argmax(d["pos"] > d["pos"][:30].max() + 0.005))
    d["coverage"] = float(d["valid"].mean())
    _cache[tag] = d
    return d


def curve(tag):
    c = np.asarray(run(tag)["r"]["curve"], float)
    c = c[np.argsort(c[:, 0])]
    return c[:, 0], c[:, 1]


def summary(tag):
    d, r = run(tag), run(tag)["r"]
    return dict(tag=tag, label=d["label"], infill=d["infill"], colour=d["colour"],
                UTS=r["uts"], UTS_e=r["uts_ec"], sy=r["sy"], sy_e=r["sy_ec"],
                E=r["E"], E_R2=r["E_R2"], ef=r["ef"] * 100, sigf=r["sigf"],
                tough=r["tough"], anchor=r["anchor"], dur=r["dur"], rate=r["rate"] * 1000,
                n=d["n"], coverage=100 * d["coverage"])


def capture_facts(tag):
    import cv2
    cap = capture_dir(tag)
    with open(os.path.join(cap, "frames", "index.csv"), encoding="utf-8") as fh:
        t = np.array([float(r["t_monotonic_s"]) for r in csv.DictReader(fh)])
    gaps = np.diff(t) * 1000.0
    med = float(np.median(gaps))
    sinks = {}
    for nm in sorted(f for f in os.listdir(cap) if f.endswith(".avi")):
        c = cv2.VideoCapture(os.path.join(cap, nm))
        sinks[nm] = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        c.release()
    import json
    with open(os.path.join(cap, "run.json"), encoding="utf-8") as fh:
        rj = json.load(fh)
    return dict(stills=len(t), sinks=sinks, fps=1000.0 / med, med_ms=med,
                p95_ms=float(np.percentile(gaps, 95)),
                dropped=int(np.sum(np.round(gaps / med) - 1)),
                all_equal=len(set([len(t)] + list(sinks.values()))) == 1,
                run_json_matches=os.path.basename(rj["csv"]) == RUNS[tag]["csv"],
                captured_from=rj["captured_from"], captured_to=rj["captured_to"])


# ---------------------------------------------------------------- infill

def group_mean(tags, key):
    return float(np.mean([summary(t)[key] for t in tags]))


def group_spread(tags, key):
    a, b = (summary(t)[key] for t in tags)
    return 100.0 * abs(a - b) / np.mean([a, b])


def knockdown(tags, key="UTS"):
    """k = datasheet / measured. How far short of solid material this infill falls."""
    return TDS[key] / group_mean(tags, key)


def registry_infill(infill):
    """Every historical run at this infill, from the registry — context for the new pair.

    Read live rather than hard-coded so the table cannot drift from the registry. Rows whose
    infill_pct is wrong are excluded by force instead: the label defect writes 100 % after an app
    restart, and a 50 % specimen peaks near 1300 N where a 100 % one peaks near 3400 N, so the
    force settles it where the label cannot.
    """
    out = []
    seen = set()
    for r in _REG.load():
        if not r.get("specimen") or r.get("UTS_MPa") is None:
            continue
        uts = r["UTS_MPa"]
        actual = 100.0 if uts > 30 else 50.0        # the force, not the label
        if actual != infill:
            continue
        key = (r["specimen"], round(uts, 2))
        if key in seen:                              # duplicate rows from repeated saves
            continue
        seen.add(key)
        out.append(dict(specimen=r["specimen"], test=r.get("test") or "—", UTS=uts,
                        E=r.get("E_GPa"), ef=(r.get("ef") or 0) * 100,
                        anchor=r.get("anchor_N")))
    out.sort(key=lambda x: x["specimen"])
    return out


if __name__ == "__main__":
    print(f"{'':<6}{'infill':>7}{'UTS':>8}{'σ_y':>8}{'E':>8}{'ε_f':>8}{'tough':>7}{'anchor':>7}"
          f"{'cov':>6}")
    for t in ORDER:
        s = summary(t)
        print(f"{s['label']:<10}{s['infill']:>4.0f}%{s['UTS']:>8.2f}{s['sy']:>8.2f}{s['E']:>8.3f}"
              f"{s['ef']:>7.2f}%{s['tough']:>7.0f}{s['anchor']:>7.0f}{s['coverage']:>5.0f}%")
    print()
    for name, tags in (("50 %", PAIR_50), ("100 %", PAIR_100)):
        print(f"  {name:<6} mean UTS {group_mean(tags,'UTS'):6.2f}  E {group_mean(tags,'E'):5.3f}  "
              f"ef {group_mean(tags,'ef'):5.2f} %   |  pair differs by "
              f"UTS {group_spread(tags,'UTS'):4.1f} %  E {group_spread(tags,'E'):4.1f} %")
    print()
    print(f"  knock-down k vs {TDS_NAME} ({TDS['UTS']:.0f} MPa, {TDS['E']:.2f} GPa):")
    for name, tags in (("50 %", PAIR_50), ("100 %", PAIR_100)):
        print(f"    {name:<6} k_UTS {knockdown(tags,'UTS'):.2f}   k_E {knockdown(tags,'E'):.2f}")
    print(f"\n  ratio 100 %/50 %:  UTS {group_mean(PAIR_100,'UTS')/group_mean(PAIR_50,'UTS'):.2f}x   "
          f"E {group_mean(PAIR_100,'E')/group_mean(PAIR_50,'E'):.2f}x")
    for inf in (50.0, 100.0):
        rows = registry_infill(inf)
        print(f"\n  registry, {inf:.0f} % infill ({len(rows)} runs): "
              f"UTS {np.mean([r['UTS'] for r in rows]):.2f} ± "
              f"{np.std([r['UTS'] for r in rows], ddof=1):.2f}")
        for r in rows:
            _e = f"{r['E']:5.3f}" if r['E'] is not None else "  —  "
            print(f"     {r['specimen']:<5}{str(r['test'])[:24]:<26}{r['UTS']:6.2f}  {_e}")
