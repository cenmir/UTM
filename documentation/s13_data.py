"""S13 — the first BLACK specimen taken to fracture — against the white 100 % infill pair.

The question this run answers is whether the DIC works on a black specimen with white spray dots,
which is the opposite polarity to every specimen tested before it. That is a property of the
MEASUREMENT CHAIN, so the comparison has to hold the material fixed: S13 is 100 % infill, and the
only valid white comparators are S25 and S26, which are the same. (S28 is 50 % infill — a different
material — so it is deliberately excluded here.)

Three things get measured, and they answer different questions:
  * MECHANICS — does the marker colour change the numbers? It must not.
  * NOISE, on the stationary pre-ramp hold, over a COMMON window. The floor is window-dependent
    on this rig, so unequal holds cannot be compared.
  * COVERAGE — what fraction of load samples got a strain reading at all. S13 came back at 47 %,
    and separating that from the colour question is most of the work.
"""
import csv
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", "Software", "UTM_PyQt6"))
sys.path.insert(0, _APP)

from utm_analysis import analyze, read_csv                          # noqa: E402

BASE = os.path.join(_APP, "8.6.20 - Tensile test to Failure")
AREA_MM2 = GAUGE_MM = 80.0
STALE_MS = 100          # main.py DIC_STALE_THRESHOLD_MS — the matching window
NOISE_WINDOW_S = 10     # shortest hold available across the three runs

RUNS = {
    "S13": dict(folder="Specimen_S13_V2_Spray_Video7", capture="20260818_111143",
                csv="UTM_Test_20260818_111324.csv", label="S13 · VC7",
                marker="BLACK", colour="#1A1A1A", infill=100.0),
    "S25": dict(folder="Specimen_S25_V2_Spray_Video2", capture="20260817_103811",
                csv="UTM_Test_20260817_103930_100%infill_Videocapture_2.csv", label="S25 · VC2",
                marker="white", colour="#1F6FB4", infill=100.0),
    "S26": dict(folder="Specimen_S26_V2_Spray_Video3", capture="20260817_111525",
                csv="UTM_Test_20260817_111700_100%infill_Videocapture3.csv", label="S26 · VC3",
                marker="white", colour="#D95F02", infill=100.0),
}
ORDER = ("S13", "S25", "S26")
WHITE = ("S25", "S26")

_cache = {}


def csv_path(tag):
    return os.path.join(BASE, RUNS[tag]["folder"], RUNS[tag]["csv"])


def capture_dir(tag):
    return os.path.join(BASE, RUNS[tag]["folder"], RUNS[tag]["capture"])


def run(tag):
    """Everything derived from one CSV, computed once."""
    if tag in _cache:
        return _cache[tag]
    p = csv_path(tag)
    rows = read_csv(p)
    col = lambda k: np.array([r[k] for r in rows], float)           # noqa: E731

    # DIC_Time_s and DIC_Blobs are not in utm_analysis's row dict, so read them straight off.
    with open(p, encoding="utf-8", errors="ignore") as fh:
        body = [ln for ln in fh if not ln.startswith("#")]
    dic_t, blobs = [], []
    for r in csv.DictReader(body):
        try:
            dic_t.append(float(r.get("DIC_Time_s") or 0.0))
            blobs.append(float(r.get("DIC_Blobs") or 0.0))
        except ValueError:
            dic_t.append(0.0)
            blobs.append(0.0)

    d = dict(RUNS[tag], tag=tag, path=p, n=len(rows),
             t=col("t"), F=col("F"), pos=col("pos"), ec=col("ec"), lpx=col("lpx"),
             dic_t=np.array(dic_t), blobs=np.array(blobs))
    d["valid"] = d["lpx"] > 100                    # a real reading; 0.0 means no match this row
    d["r"] = analyze(p, AREA_MM2, GAUGE_MM)
    d["moved"] = int(np.argmax(d["pos"] > d["pos"][:30].max() + 0.005))
    d["dur"] = d["t"][-1] - d["t"][0]
    d["coverage"] = float(d["valid"].mean())
    d["two_blob"] = float((d["blobs"] == 2).mean())
    # Gaps between DISTINCT readings. This is what the 100 ms matching window is judged against.
    uniq = np.unique(d["dic_t"][d["dic_t"] > 0])
    d["gaps_ms"] = np.diff(uniq) * 1000.0
    d["gap_median_ms"] = float(np.median(d["gaps_ms"]))
    d["gap_over_stale"] = float((d["gaps_ms"] > STALE_MS).mean())
    _cache[tag] = d
    return d


def curve(tag):
    c = np.asarray(run(tag)["r"]["curve"], float)
    c = c[np.argsort(c[:, 0])]
    return c[:, 0], c[:, 1]


def hold(tag):
    """(t, microstrain) over the stationary pre-ramp hold — every reading here is noise."""
    d = run(tag)
    m = (np.arange(len(d["t"])) < d["moved"]) & d["valid"]
    return d["t"][m], d["ec"][m] * 1e6


def noise(tag, window_s=NOISE_WINDOW_S):
    """RMS / peak-peak / drift over the LAST `window_s` of the hold.

    Windowed on purpose: the floor grows with observation time on this rig (±12 µε at 40 s against
    ±26 µε at 900 s), so comparing a 10 s hold against a 33 s one would credit the short one.
    """
    t, e = hold(tag)
    keep = t >= t[-1] - window_s
    e, t = e[keep], t[keep]
    return dict(n=len(e), rms=float(e.std(ddof=1)), pp=float(e.max() - e.min()),
                drift=float(np.polyfit(t, e, 1)[0]), span=float(t[-1] - t[0]))


def noise_sweep(tag, windows=(3, 5, 8, 10, 15, 20, 30)):
    t, e = hold(tag)
    out = []
    for w in windows:
        k = t >= t[-1] - w
        out.append(float(e[k].std(ddof=1)) if k.sum() > 8 else np.nan)
    return np.array(windows, float), np.array(out)


def capture_facts(tag):
    """Frame counts and rate from the capture index — did the camera keep up?"""
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
    return dict(stills=len(t), sinks=sinks, fps=1000.0 / med, med_ms=med,
                p95_ms=float(np.percentile(gaps, 95)),
                dropped=int(np.sum(np.round(gaps / med) - 1)),
                all_equal=len(set([len(t)] + list(sinks.values()))) == 1)


def summary(tag):
    d, r = run(tag), run(tag)["r"]
    nz = noise(tag)
    return dict(tag=tag, label=d["label"], marker=d["marker"], colour=d["colour"],
                UTS=r["uts"], UTS_e=r["uts_ec"], sy=r["sy"], sy_e=r["sy_ec"],
                E=r["E"], E_R2=r["E_R2"], ef=r["ef"] * 100, sigf=r["sigf"],
                tough=r["tough"], anchor=r["anchor"], dur=r["dur"], rate=r["rate"] * 1000,
                n=d["n"], coverage=100 * d["coverage"], two_blob=100 * d["two_blob"],
                gap_median=d["gap_median_ms"], rms=nz["rms"], pp=nz["pp"], drift=nz["drift"])


def white_mean(key):
    return float(np.mean([summary(t)[key] for t in WHITE]))


def white_spread(key):
    """How much the two WHITE runs disagree with each other — the yardstick any black-vs-white
    difference has to be judged against."""
    a, b = (summary(t)[key] for t in WHITE)
    return 100.0 * abs(a - b) / np.mean([a, b])


def e_window_points(tag, lo=0.05, hi=0.40):
    """How many strain readings land inside the fixed E fit window — the coverage that matters."""
    d, r = run(tag), run(tag)["r"]
    idx = np.arange(len(d["t"]))
    loaded = (idx >= r["mv_i"]) & (idx <= r["fr_i"]) & d["valid"]
    base = d["ec"][r["mv_i"]:r["mv_i"] + 20][d["valid"][r["mv_i"]:r["mv_i"] + 20]]
    base = base[0] if len(base) else 0.0
    rel = (d["ec"] - base) * 100
    gaps = np.diff(d["t"][loaded]) * 1000
    return dict(loaded=int(loaded.sum()), in_window=int((loaded & (rel >= lo) & (rel < hi)).sum()),
                gap_median=float(np.median(gaps)), gap_max=float(gaps.max()))


if __name__ == "__main__":
    for t in ORDER:
        s = summary(t)
        print(f"{s['label']:<10}{s['marker']:<7}UTS {s['UTS']:6.2f}  E {s['E']:5.3f}  "
              f"ef {s['ef']:5.2f}%  cov {s['coverage']:5.1f}%  2blob {s['two_blob']:5.1f}%  "
              f"noise {s['rms']:5.1f} µε  gap {s['gap_median']:5.0f} ms")
    print(f"\nwhite pair disagree with each other: UTS {white_spread('UTS'):.1f} %  "
          f"E {white_spread('E'):.1f} %  ef {white_spread('ef'):.1f} %")
    b = summary("S13")
    for k in ("UTS", "E", "ef"):
        print(f"  black vs white mean, {k:>3}: {100*(b[k]/white_mean(k)-1):+.1f} %")
    for t in ORDER:
        print(t, e_window_points(t))
