"""S25 vs S26 — the two frame-capture fracture runs, as data.

Both specimens are 100 % infill PLA with spray markers, pulled to fracture with the frame-capture
feature armed (PNG stills + raw/boost/speckle AVI). They exist to give the extensometer software a
video whose every frame has a matching load and DIC sample, so this module's job is to publish the
stress-strain curves in a form that can be lined up against extensometer output row by row.

Raw, the two curves are 768 + 903 samples and they never sample the SAME strain, so a side-by-side
raw dump cannot be read across. `grid_rows()` therefore resamples both onto one strain axis; the
exact yield / UTS / fracture samples are then INSERTED at their true strain so the highlighted rows
carry measured numbers, not interpolated ones. `full_rows()` keeps every raw sample for the
reference PDF, where there is room for it.

Nothing here is typed in by hand — every number comes back through utm_analysis.analyze(), the same
function the app's own report button calls.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", "..", "Software", "UTM_PyQt6"))
sys.path.insert(0, os.path.abspath(_APP))

from utm_analysis import analyze, read_csv  # noqa: E402

BASE = os.path.abspath(os.path.join(_APP, "Test data", "8.6.20 - Tensile test to Failure"))
AREA_MM2 = GAUGE_MM = 80.0
STEP_PCT = 0.10                    # strain step of the common grid, in %
ROWS_PER_SLIDE = 22

RUNS = {
    "S25": dict(folder="Specimen_S25_V2_Spray_Video2", capture="20260817_103811",
                csv="UTM_Test_20260817_103930_100%infill_Videocapture_2.csv",
                label="S25 · VC2", colour="#1F6FB4", frames=1445,
                # From the video-replay check: every captured frame decoded and pushed back
                # through the app's own blob detector. Recorded here because a full decode of
                # 3 100 frames takes minutes and has no business running inside a deck build.
                replay_distinct=1.000, replay_two_markers=0.998),
    "S26": dict(folder="Specimen_S26_V2_Spray_Video3", capture="20260817_111525",
                csv="UTM_Test_20260817_111700_100%infill_Videocapture3.csv",
                label="S26 · VC3", colour="#D95F02", frames=1682,
                replay_distinct=1.000, replay_two_markers=0.999),
}
ORDER = ("S25", "S26")

# The three landmarks, and the fill each one wears wherever it appears (deck table, PDF table,
# plot marker). Keeping them in one dict is what stops the deck and the PDF drifting apart.
MARKS = {
    "yield":    dict(fill="#C8E6C9", edge="#2F9E44", short="Y", pretty="Yield (0.2 % offset)"),
    "UTS":      dict(fill="#FFF3CD", edge="#D29922", short="U", pretty="UTS (peak stress)"),
    "fracture": dict(fill="#FFCDD2", edge="#C0392B", short="F", pretty="Fracture"),
}

_cache = {}


def csv_path(tag):
    return os.path.join(BASE, RUNS[tag]["folder"], RUNS[tag]["csv"])


def capture_dir(tag):
    return os.path.join(BASE, RUNS[tag]["folder"], RUNS[tag]["capture"])


def result(tag):
    """analyze() output for one run, computed once."""
    if tag not in _cache:
        _cache[tag] = analyze(csv_path(tag), AREA_MM2, GAUGE_MM)
    return _cache[tag]


def curve(tag):
    """(strain %, stress MPa) sorted on strain — exactly the pair the deck plots."""
    c = np.asarray(result(tag)["curve"], float)
    c = c[np.argsort(c[:, 0])]
    return c[:, 0], c[:, 1]


def key_points(tag):
    """{name: (strain %, stress MPa)} for the three landmarks."""
    r = result(tag)
    return {"yield": (r["sy_ec"], r["sy"]),
            "UTS": (r["uts_ec"], r["uts"]),
            "fracture": (r["ef"] * 100.0, r["sigf"])}


def at(tag, e_pct):
    """Stress at a given strain, or None outside this run's own range.

    None matters: past its fracture strain a specimen has no stress, and printing an extrapolated
    number there would invite a comparison that does not exist.
    """
    x, y = curve(tag)
    if e_pct < x[0] - 1e-9 or e_pct > x[-1] + 1e-9:
        return None
    return float(np.interp(e_pct, x, y))


def grid_rows(step=STEP_PCT):
    """Both runs on ONE strain axis: [strain %, S25 MPa, S26 MPa, marker] with the exact
    yield/UTS/fracture samples inserted at their true strain."""
    emax = max(curve(t)[0][-1] for t in ORDER)
    rows = [[round(float(e), 3), at("S25", e), at("S26", e), ""]
            for e in np.arange(0.0, emax + step / 2, step)]

    for tag in ORDER:
        other = "S26" if tag == "S25" else "S25"
        for what, (e, s) in key_points(tag).items():
            rows.append([round(e, 3),
                         s if tag == "S25" else at(other, e),
                         s if tag == "S26" else at(other, e),
                         f"{tag} {what}"])

    rows.sort(key=lambda r: (r[0], r[3] == ""))       # a marked row wins its strain slot
    merged = []
    for r in rows:
        if merged and abs(merged[-1][0] - r[0]) < 1e-9:
            if r[3]:
                merged[-1][3] = (merged[-1][3] + " + " + r[3]).strip(" +")
                for i in (1, 2):
                    if r[i] is not None:
                        merged[-1][i] = r[i]
            continue
        merged.append(r)
    return merged


def full_rows(tag):
    """Every raw sample of one run: [n, strain %, stress MPa, marker].

    Landmarks are matched to the NEAREST raw sample rather than inserted, so this table stays a
    faithful dump of what the instrument recorded — nothing in it is synthetic.
    """
    x, y = curve(tag)
    marks = {}
    for what, (e, _s) in key_points(tag).items():
        marks[int(np.argmin(np.abs(x - e)))] = what
    return [[i + 1, float(x[i]), float(y[i]), marks.get(i, "")] for i in range(len(x))]


def slide_chunks(rows=None, per=ROWS_PER_SLIDE):
    rows = grid_rows() if rows is None else rows
    return [rows[i:i + per] for i in range(0, len(rows), per)]


def summary(tag):
    """The headline numbers, plus the capture facts the validation slides quote."""
    r, cfg = result(tag), RUNS[tag]
    return dict(tag=tag, label=cfg["label"], colour=cfg["colour"], frames=cfg["frames"],
                UTS=r["uts"], UTS_e=r["uts_ec"], sy=r["sy"], sy_e=r["sy_ec"],
                E=r["E"], E_R2=r["E_R2"], ef=r["ef"] * 100.0, sigf=r["sigf"],
                tough=r["tough"], anchor=r["anchor"], soft=r["soft"],
                gauge_share=r["gauge_share"], dur=r["dur"], rate=r["rate"] * 1000.0,
                n=len(read_csv(csv_path(tag))))


def header(tag):
    """The comment block the app writes at the top of every test CSV.

    Two separators are in use: most lines are `# Key: value`, but the grouped ones the app added
    later (`# DIC Health - ...`, `# DIC Coverage - ...`) use a dash. Splitting on the colon alone
    silently drops exactly the two lines a capture run most needs to prove.
    """
    out = {}
    with open(csv_path(tag), encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            s = line[1:].strip()
            for sep in (": ", " - "):
                if sep in s:
                    k, v = s.split(sep, 1)
                    out[k.strip()] = v.strip()
                    break
    return out


def capture_facts(tag):
    """Did the capture actually record what it claims? Frame counts, rate, and the SF11 link.

    Every sink (PNG stills and each AVI) must hold the SAME number of frames as the still index,
    and the gaps between stills must all be one frame apart — a writer that silently drops frames
    under load would show up here as a short AVI or an implied-dropped count, and would quietly
    ruin any extensometer comparison made from the video.
    """
    import csv as _csv
    import json

    cap = capture_dir(tag)
    with open(os.path.join(cap, "frames", "index.csv"), encoding="utf-8") as fh:
        stills = [float(r["t_monotonic_s"]) for r in _csv.DictReader(fh)]
    gaps = np.diff(stills) * 1000.0
    med = float(np.median(gaps))

    import cv2
    sinks = {}
    for nm in sorted(f for f in os.listdir(cap) if f.endswith(".avi")):
        c = cv2.VideoCapture(os.path.join(cap, nm))
        sinks[nm] = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        c.release()

    with open(os.path.join(cap, "run.json"), encoding="utf-8") as fh:
        run = json.load(fh)

    h = header(tag)
    return dict(stills=len(stills), sinks=sinks, fps=1000.0 / med, med_ms=med,
                p95_ms=float(np.percentile(gaps, 95)),
                dropped=int(np.sum(np.round(gaps / med) - 1)),
                all_equal=len(set([len(stills)] + list(sinks.values()))) == 1,
                span_s=stills[-1] - stills[0],
                run_json_matches=os.path.basename(run["csv"]) == RUNS[tag]["csv"],
                captured_from=run["captured_from"], captured_to=run["captured_to"],
                coverage=h.get("DIC Coverage", "—"), dic_health=h.get("DIC Health", "—"),
                px0=h.get("DIC Px0 reference", "—"))


def best_elastic_fit(tag):
    """The straightest run anywhere below 2 % strain — (E_GPa, lo %, hi %, R2).

    analyze() fits E over a FIXED 0.05-0.40 % window. Two specimens with different toe lengths do
    not have their toe in the same place, so that fixed window can land on curved data for one of
    them and report a modulus that is really a seating artefact. This searches for the window each
    specimen actually deserves, which is how the E discrepancy on these two runs was explained.
    """
    from utm_analysis import linfit
    e, s = curve(tag)
    e = e / 100.0
    best = None
    for i in range(0, len(e), 2):
        if e[i] > 0.015:
            break
        for j in range(i + 30, len(e), 2):
            if e[j - 1] > 0.02:
                break
            if e[j - 1] - e[i] < 0.003:
                continue
            slope, _ic, r2 = linfit(list(e[i:j]), list(s[i:j]))
            if best is None or r2 > best[3]:
                best = (slope / 1000.0, e[i] * 100.0, e[j - 1] * 100.0, r2)
    return best


if __name__ == "__main__":
    for t in ORDER:
        d = summary(t)
        print(f"{d['label']:<12} UTS {d['UTS']:6.2f}  sy {d['sy']:6.2f}  E {d['E']:5.3f}  "
              f"ef {d['ef']:5.2f} %  tough {d['tough']:5.0f}  anchor {d['anchor']:4.0f} N  "
              f"n {d['n']}")
        print(f"{'':<12} best-fit E {best_elastic_fit(t)[0]:.3f} GPa over "
              f"{best_elastic_fit(t)[1]:.2f}-{best_elastic_fit(t)[2]:.2f} %")
    g = grid_rows()
    print(f"\ngrid: {len(g)} rows at {STEP_PCT:.2f} % -> {len(slide_chunks(g))} slides, "
          f"{sum(1 for r in g if r[3])} marked")
    print(f"full: {len(full_rows('S25'))} + {len(full_rows('S26'))} raw samples")
