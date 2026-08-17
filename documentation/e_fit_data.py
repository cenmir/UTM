"""How the elastic-modulus fit window is chosen, and what each choice costs.

E is the slope of the straight part of the stress-strain curve, so measuring it means picking WHICH
part to fit. analyze() uses a fixed 0.05-0.40 % strain window for every specimen. That is a
defensible convention — ISO 527 fixes a window too — but it assumes every specimen's curve is
straight in the same place, and ours are not: the local slope rises through the first half-percent
before yielding takes it back down, and how far it has risen by 0.40 % differs specimen to specimen.

This module measures that, three ways, on every 100 % infill run on record, so the choice can be
made on evidence rather than on which standard is quoted. It changes NOTHING in utm_analysis — it
is a read-only preview of what each option would report.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", "Software", "UTM_PyQt6"))
sys.path.insert(0, _APP)
sys.path.insert(0, _HERE)

from utm_analysis import analyze, linfit          # noqa: E402
import utm_registry as R                          # noqa: E402

REPO = os.path.abspath(os.path.join(_HERE, ".."))
ISO_WINDOW = (0.05, 0.25)          # ISO 527-1 fixes a low-strain window of this shape
OURS_WINDOW = (0.05, 0.40)         # what utm_analysis.analyze() uses today
DATASHEET_E = 2.87                 # add:north E-PLA TDS, GPa — see reference_addnorth_tds
R2_FLOOR = 0.999                   # a "straight run" has to actually be straight

METHODS = (("ISO fixed", "#C0392B"), ("Ours fixed", "#D29922"), ("Steepest run", "#2F9E44"))

_cache = {}


def curve(row):
    """(strain %, stress MPa, analyze result) for one registry row."""
    key = row["csv"]
    if key not in _cache:
        p = os.path.join(REPO, *key.split("/"))
        r = analyze(p, row.get("area_mm2") or 80.0, row.get("gauge_mm") or 80.0)
        c = np.asarray(r["curve"], float)
        c = c[np.argsort(c[:, 0])]
        _cache[key] = (c[:, 0], c[:, 1], r)
    return _cache[key]


def window_fit(x, y, lo, hi):
    """Slope in GPa over a fixed strain window, or None if too few samples land in it."""
    m = (x >= lo) & (x < hi)
    if m.sum() < 8:
        return None
    slope, _ic, r2 = linfit(list(x[m] / 100.0), list(y[m]))
    return slope / 1000.0, r2, m.sum()


def steepest_run(x, y, *, max_pct=2.0, min_span=0.25, r2_floor=R2_FLOOR):
    """ASTM-style: the STEEPEST genuinely-straight stretch below max_pct strain.

    Steepest rather than straightest. Maximising R² alone rewards any smooth stretch, including the
    compliant toe and the early part of the yield knee — both are smooth, neither is the modulus.
    Requiring R² >= floor first and then taking the steepest survivor is what picks the elastic
    region out, and the span floor stops it collapsing onto a handful of points.
    """
    best = None
    for i in range(0, len(x), 2):
        if x[i] > max_pct - min_span:
            break
        for j in range(i + 25, len(x), 2):
            if x[j - 1] > max_pct:
                break
            if x[j - 1] - x[i] < min_span:
                continue
            slope, _ic, r2 = linfit(list(x[i:j] / 100.0), list(y[i:j]))
            if r2 >= r2_floor and (best is None or slope > best[0]):
                best = (slope, x[i], x[j - 1], r2)
    if best is None:
        return None
    return best[0] / 1000.0, best[1], best[2], best[3]


def local_slope(x, y, *, span=0.20, step=0.02, max_pct=1.6):
    """Rolling slope: E measured over a short window centred at each strain.

    This is the picture the fixed window cannot show — whether the curve is even straight where the
    window is looking.
    """
    centres, slopes = [], []
    c = span / 2 + 0.01
    while c <= max_pct:
        m = (x >= c - span / 2) & (x < c + span / 2)
        if m.sum() >= 10:
            slope, _ic, _r2 = linfit(list(x[m] / 100.0), list(y[m]))
            centres.append(c)
            slopes.append(slope / 1000.0)
        c += step
    return np.array(centres), np.array(slopes)


def specimens(infill=100.0):
    rows = [r for r in R.load()
            if r.get("infill_pct") == infill and r.get("specimen") and r.get("E_GPa")]
    rows.sort(key=lambda r: r.get("date") or "")
    return rows


def table(infill=100.0):
    """[{specimen, test, iso, ours, steep, lo, hi, r2, ratio}] for every run at this infill."""
    out = []
    for row in specimens(infill):
        x, y, _r = curve(row)
        iso = window_fit(x, y, *ISO_WINDOW)
        ours = window_fit(x, y, *OURS_WINDOW)
        steep = steepest_run(x, y)
        if not (iso and ours and steep):
            continue
        out.append(dict(specimen=row["specimen"], test=row.get("test") or "—",
                        iso=iso[0], ours=ours[0], steep=steep[0],
                        lo=steep[1], hi=steep[2], r2=steep[3],
                        ratio=steep[0] / ours[0]))
    return out


def summary(rows=None):
    """mean / CV / distance-from-datasheet for each of the three methods."""
    rows = rows if rows is not None else table()
    out = {}
    for key, label in (("iso", "ISO fixed"), ("ours", "Ours fixed"), ("steep", "Steepest run")):
        a = np.array([r[key] for r in rows], float)
        out[key] = dict(label=label, mean=a.mean(),
                        cv=100 * a.std(ddof=1) / a.mean(),
                        vs_tds=100 * (a.mean() - DATASHEET_E) / DATASHEET_E)
    return out


if __name__ == "__main__":
    rows = table()
    print(f"{'spec':<6}{'test':<6}{'ISO':>8}{'ours':>8}{'steep':>8}{'window %':>14}{'R2':>8}"
          f"{'ratio':>7}")
    for r in rows:
        print(f"{r['specimen']:<6}{r['test']:<6}{r['iso']:>8.3f}{r['ours']:>8.3f}{r['steep']:>8.3f}"
              f"{f'{r['lo']:.2f}-{r['hi']:.2f}':>14}{r['r2']:>8.4f}{r['ratio']:>7.2f}")
    print()
    for k, s in summary(rows).items():
        print(f"{s['label']:<14} mean {s['mean']:.3f} GPa   CV {s['cv']:4.1f} %   "
              f"vs datasheet {s['vs_tds']:+5.1f} %")
