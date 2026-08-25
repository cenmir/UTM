"""Deviation between S27 and S28, and the 50 %-vs-100 % comparison against S26.

Two curves that "look identical" is not a measurement. Putting them on a COMMON strain axis and
subtracting is: it turns agreement into a number per strain, which is what a repeatability claim
actually rests on, and it is the same treatment the S25/S26 pair got.

Also carries the before/after of the E fit-window switch, so the change to analyze() is auditable
from the deck rather than only from the commit.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
_APP = os.path.abspath(os.path.join(_HERE, "..", "..", "Software", "UTM_PyQt6"))
sys.path.insert(0, _APP)

import s27_s28_data as S                                            # noqa: E402
from utm_analysis import analyze                                    # noqa: E402
import utm_registry as _REG                                         # noqa: E402

STEP_PCT = 0.10
ROWS_PER_SLIDE = 22
MARKS = {
    "yield":    dict(fill="#C8E6C9", edge="#2F9E44", short="Y", pretty="Yield (0.2 % offset)"),
    "UTS":      dict(fill="#FFF3CD", edge="#D29922", short="U", pretty="UTS (peak stress)"),
    "fracture": dict(fill="#FFCDD2", edge="#C0392B", short="F", pretty="Fracture"),
}


def key_points(tag):
    r = S.run(tag)["r"]
    return {"yield": (r["sy_ec"], r["sy"]),
            "UTS": (r["uts_ec"], r["uts"]),
            "fracture": (r["ef"] * 100, r["sigf"])}


def at(tag, e_pct):
    x, y = S.curve(tag)
    if e_pct < x[0] - 1e-9 or e_pct > x[-1] + 1e-9:
        return None
    return float(np.interp(e_pct, x, y))


def grid_rows(a="S27", b="S28", step=STEP_PCT):
    """[strain %, σ_a, σ_b, Δ, %Δ, marker] on one strain axis, landmarks inserted at true strain."""
    emax = max(S.curve(a)[0][-1], S.curve(b)[0][-1])
    rows = [[round(float(e), 3), at(a, e), at(b, e), ""]
            for e in np.arange(0.0, emax + step / 2, step)]
    for tag in (a, b):
        other = b if tag == a else a
        for what, (e, sg) in key_points(tag).items():
            rows.append([round(e, 3),
                         sg if tag == a else at(a, e),
                         sg if tag == b else at(b, e),
                         f"{tag} {what}"])
    rows.sort(key=lambda r: (r[0], r[3] == ""))
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
    out = []
    for e, va, vb, mk in merged:
        d = (vb - va) if (va is not None and vb is not None) else None
        pct = (100.0 * d / va) if (d is not None and va) else None
        out.append([e, va, vb, d, pct, mk])
    return out


def slide_chunks(rows=None, per=ROWS_PER_SLIDE):
    rows = grid_rows() if rows is None else rows
    return [rows[i:i + per] for i in range(0, len(rows), per)]


def deviation_stats(a="S27", b="S28"):
    """How far apart the two curves run, over the strain range they SHARE."""
    rows = [r for r in grid_rows(a, b) if r[3] is not None]
    d = np.array([r[3] for r in rows])
    p = np.array([r[4] for r in rows if r[4] is not None])
    e = np.array([r[0] for r in rows])
    return dict(n=len(d), lo=float(e.min()), hi=float(e.max()),
                mean_abs=float(np.abs(d).mean()), max_abs=float(np.abs(d).max()),
                at_max=float(e[int(np.argmax(np.abs(d)))]),
                rms=float(np.sqrt((d ** 2).mean())),
                mean_pct=float(np.abs(p).mean()), max_pct=float(np.abs(p).max()))


def e_switch_table():
    """Before/after of the fit-window change, per run, straight from the CSVs."""
    out = []
    for r in _REG.load():
        if not r.get("specimen") or r.get("UTS_MPa") is None:
            continue
        p = os.path.join(_REG.REPO_ROOT, *r["csv"].split("/"))
        try:
            a = analyze(p, r.get("area_mm2") or 80.0, r.get("gauge_mm") or 80.0)
        except Exception:
            continue
        out.append(dict(specimen=r["specimen"], test=r.get("test") or "—",
                        infill=r.get("infill_pct") or 0.0,
                        E_old=a["E_fixed"], E_new=a["E"], lo=a["E_lo"], hi=a["E_hi"],
                        r2=a["E_R2"], sy=a["sy"], uts=a["uts"]))
    out.sort(key=lambda x: (x["infill"], x["specimen"]))
    return out


def e_switch_summary():
    rows = e_switch_table()
    out = {}
    for inf in (50.0, 100.0):
        sel = [r for r in rows if r["infill"] == inf]
        if not sel:
            continue
        o = np.array([r["E_old"] for r in sel])
        n = np.array([r["E_new"] for r in sel])
        out[inf] = dict(n=len(sel), old_mean=o.mean(), new_mean=n.mean(),
                        old_cv=100 * o.std(ddof=1) / o.mean(),
                        new_cv=100 * n.std(ddof=1) / n.mean())
    return out


if __name__ == "__main__":
    st = deviation_stats()
    print(f"S27 vs S28 deviation over ε {st['lo']:.2f}-{st['hi']:.2f} % ({st['n']} points):")
    print(f"  mean |Δσ| {st['mean_abs']:.3f} MPa   RMS {st['rms']:.3f}   "
          f"max {st['max_abs']:.3f} at ε {st['at_max']:.2f} %")
    print(f"  mean |Δ| {st['mean_pct']:.2f} %   worst {st['max_pct']:.2f} %")
    g = grid_rows()
    print(f"  table: {len(g)} rows -> {len(slide_chunks(g))} slides, "
          f"{sum(1 for r in g if r[5])} landmarks")
    print()
    for inf, s in e_switch_summary().items():
        print(f"  {inf:.0f} % infill (n={s['n']}): E {s['old_mean']:.3f} -> {s['new_mean']:.3f} GPa, "
              f"CV {s['old_cv']:.1f} -> {s['new_cv']:.1f} %")
