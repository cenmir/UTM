"""S37 (45 mm marker gauge) against the two 80 mm TPU runs, S35 and S36.

The question this answers: does shortening the marker spacing from 80 mm to 45 mm change the
material answer? It should not. DIC strain is a PIXEL ratio, (L_px - Px0)/Px0, so it does not
contain the gauge at all — only px_per_mm does. If the initial slope moves when the gauge moves,
something other than the material is being measured.

S36 is used as the reference because the deck already draws it as the representative TPU run
(trio_plots.REP). S35 is plotted too, because it is in fact the better-instrumented of the two
80 mm runs — 33 % DIC coverage against S36's 21 % — and the pair of them is the honest yardstick
for what "agreement" means on this material.

Both 80 mm runs stop near 12 % strain: the travelling marker left the frame at ~15 mm of crosshead
travel. S37's shorter pair needs less frame per mm of travel, which is what lifts it to 18.9 %.
"""
import glob
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "Software", "UTM_PyQt6"))
from utm_analysis import analyze, read_csv, read_meta                 # noqa: E402

AREA = 80.0
GRID, MUTED = "#DDDDDD", "#666666"
COL = {"S35": "#74c0fc", "S36": "#1f6fb4", "S37": "#e8590c"}
LO, HI = 0.05, 1.20          # common fit window: the overlap of all three own-fit windows


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _s37_csv():
    """S37's CSV, found by folder PREFIX rather than by exact name.

    The folder has already been renamed once (a "_Video15" suffix appended after the run), which
    silently broke both this path and the registry row. Matching on "Specimen_S37*" survives that
    class of rename; anything that cannot be found is raised rather than guessed at.
    """
    hits = sorted(glob.glob(os.path.join(
        ROOT, "Software", "UTM_PyQt6", "Test data", "8.6.20 - Tensile test to Failure",
        "Specimen_S37*", "*.csv")))
    if not hits:
        raise FileNotFoundError("no S37 CSV under Test data/8.6.20 - Tensile test to Failure")
    return hits[0]


def load():
    reg = {r["specimen"]: r for r in
           json.load(open(os.path.join(ROOT, "Software", "UTM_PyQt6", "registry.json")))
           if r.get("specimen")}
    paths = {s: os.path.join(ROOT, reg[s]["csv"]) for s in ("S35", "S36")}
    paths["S37"] = _s37_csv()
    out = {}
    for s, p in paths.items():
        gauge = float(read_meta(p).get("gauge") or 80.0)
        a = analyze(p, AREA, gauge)
        allrows = read_csv(p)
        rows = [r for r in allrows if r["lpx"] > 100]
        e = np.array([r["ec"] for r in rows]) * 100.0
        sig = np.array([(r["F"] + a["anchor"]) / AREA for r in rows])
        k = np.argsort(e)
        m = (e[k] >= LO) & (e[k] <= HI)
        slope, icept = np.polyfit(e[k][m] / 100.0, sig[k][m], 1)
        out[s] = {"e": e[k], "sig": sig[k], "a": a, "gauge": gauge,
                  "cov": len(rows) / len(allrows), "slope": slope, "icept": icept,
                  "r2": float(np.corrcoef(e[k][m], sig[k][m])[0, 1] ** 2)}
    return out


def fig(out="tpu_s37.png"):
    D = load()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.2, 4.4))

    for s in ("S35", "S36", "S37"):
        d = D[s]
        a1.plot(d["e"], d["sig"], color=COL[s], lw=1.8,
                label="%s  %.0f mm gauge  ·  %.0f %% DIC coverage" % (s, d["gauge"], d["cov"] * 100))
    a1.set_xlabel("DIC gauge strain (%)"); a1.set_ylabel("Engineering stress (MPa)")
    a1.set_title("The whole tracked record — the 45 mm pair reaches 18.9 %, not 12 %",
                 fontsize=10.5)
    a1.legend(fontsize=8.6, loc="upper left", frameon=False)
    a1.annotate("both 80 mm runs stop here:\nthe marker left the frame\nat ~15 mm of travel",
                xy=(12.2, 2.1), xytext=(12.9, 0.95), fontsize=8.4, color=MUTED,
                arrowprops=dict(arrowstyle="->", color="#999"))
    _style(a1)

    # the initial region, which is the actual question
    x = np.linspace(0, HI, 30)
    for s in ("S35", "S36", "S37"):
        d = D[s]
        k = d["e"] <= HI * 1.35
        a2.plot(d["e"][k], d["sig"][k], color=COL[s], lw=1.5, alpha=0.85,
                label="%s  measured" % s)
        a2.plot(x, d["icept"] + d["slope"] * x / 100.0, color=COL[s], lw=1.2, ls="--")
    a2.axvspan(LO, HI, color="#495057", alpha=0.10, zorder=0)
    a2.set_xlim(0, HI * 1.35)
    a2.set_xlabel("DIC gauge strain (%)"); a2.set_ylabel("Engineering stress (MPa)")
    a2.set_title("Initial slope, all three fitted over the SAME 0.05–1.20 % window",
                 fontsize=10.5)
    a2.legend(fontsize=8.6, loc="upper left", frameon=False)
    txt = "\n".join("%s   E = %.2f MPa   (R² %.4f)" % (s, D[s]["slope"], D[s]["r2"])
                    for s in ("S35", "S36", "S37"))
    sp = 100 * (D["S37"]["slope"] - D["S36"]["slope"]) / D["S36"]["slope"]
    ref = 100 * (D["S35"]["slope"] - D["S36"]["slope"]) / D["S36"]["slope"]
    a2.text(0.97, 0.06, txt + "\n\nS37 vs S36: %+.1f %%\nS35 vs S36: %+.1f %%  (the 80 mm pair)"
            % (sp, ref), transform=a2.transAxes, ha="right", va="bottom", fontsize=8.6,
            bbox=dict(boxstyle="round,pad=0.5", fc="#F7F9FB", ec="#AAB2BD", lw=1.0))
    _style(a2)

    fig.tight_layout()          # no suptitle: the slide title carries it
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


def facts():
    """Everything the S37 slides quote, read from the CSV rather than typed in."""
    p = _s37_csv()
    hdr = {}
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            hdr.setdefault("raw", []).append(line.rstrip())
    raw = "\n".join(hdr.get("raw", []))

    def grab(key, default=""):
        for ln in hdr.get("raw", []):
            if key in ln:
                return ln.lstrip("# ").strip()
        return default

    d = load()["S37"]
    rows = read_csv(p)
    a = d["a"]
    pos0 = sorted(r["pos"] for r in rows[:30])[15]
    travel = max(abs(r["pos"] - pos0) for r in rows)
    return {
        "csv": os.path.basename(p), "n": len(rows), "dur": rows[-1]["t"],
        "gauge": d["gauge"], "cov": d["cov"] * 100.0,
        "health": grab("DIC Health"), "px_per_mm": grab("px_per_mm"),
        "roundness": grab("Marker Roundness"), "cap": grab("Strain Cap"),
        "px0ref": grab("Px0 reference"),
        "E_own": a["E"] * 1000.0, "E_common": d["slope"], "r2": d["r2"],
        "eps_max": float(d["e"].max()), "sig_max": float(d["sig"].max()),
        "anchor": a["anchor"], "travel": travel,
        "motor_strain": travel / d["gauge"] * 100.0,
        "share": float(d["e"].max()) / 100.0 * d["gauge"] / travel * 100.0,
        "raw": raw,
    }


TRIO_COL = {"PLA": "#1f77b4", "PETG": "#7048e8", "TPU": "#e8590c"}


def trio():
    """PLA (S25), PETG (S30) and TPU (S37) on one set of axes.

    S37 rather than S36 for the TPU curve: it is the only TPU run that tracked most of its pull
    (95 % DIC coverage against 21 %), so it is the one that can be followed to the end of the test
    rather than to the point where the marker left the frame.
    """
    import trio_plots as TP
    out = {}
    for m, spec in (("PLA", "S25"), ("PETG", "S30")):
        e, s, a = TP.curve(spec)
        out[m] = {"e": e, "sig": s, "a": a, "spec": spec}
    d = load()["S37"]
    out["TPU"] = {"e": d["e"], "sig": d["sig"], "a": d["a"], "spec": "S37"}
    return out


def fig_trio(out="trio_s37.png"):
    D = trio()
    common = min(D[m]["e"].max() for m in D)          # PLA fractures first: everything is alive here
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.2, 4.5))

    for ax, upto, ttl in (
            (a1, common, "UP TO THE COMMON STRAIN REGION — 0 to %.1f %%, where all three are "
                         "still intact" % common),
            (a2, None, "THE FULL RECORD — each to its own fracture, or to where the test stopped")):
        for m in ("PLA", "PETG", "TPU"):
            e, s = D[m]["e"], D[m]["sig"]
            k = (e <= upto) if upto else np.ones_like(e, dtype=bool)
            ax.plot(e[k], s[k], color=TRIO_COL[m], lw=1.9,
                    label="%s  (%s)" % (m, D[m]["spec"]))
        ax.set_yscale("log")
        ax.set_xlabel("DIC gauge strain (%)")
        ax.set_ylabel("Engineering stress (MPa, log)")
        ax.set_title(ttl, fontsize=10.2)
        ax.legend(fontsize=9, frameon=False, loc="lower right")
        _style(ax)
    for m, txt in (("PLA", "fractures"), ("PETG", "fractures"), ("TPU", "test stopped —\nno fracture")):
        e, s = D[m]["e"], D[m]["sig"]
        a2.annotate(txt, xy=(e.max(), s[-1]), xytext=(e.max() + 0.6, s[-1] * (0.42 if m == "TPU" else 0.52)),
                    fontsize=8.2, color=TRIO_COL[m],
                    arrowprops=dict(arrowstyle="->", color=TRIO_COL[m], lw=1.0))
    a2.set_xlim(-0.6, max(D[m]["e"].max() for m in D) * 1.22)

    fig.tight_layout()          # no suptitle: the slide title carries it
    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


def trio_table():
    """Stress at matched strain + E, for the slide's table. Computed, not typed."""
    D = trio()
    common = min(D[m]["e"].max() for m in D)
    rows = []
    for tgt in (0.5, 1.0, 2.0, 4.0):
        if tgt > common:
            continue
        r = ["%.1f %%" % tgt]
        for m in ("PLA", "PETG", "TPU"):
            e, s = D[m]["e"], D[m]["sig"]
            k = np.abs(e - tgt) < 0.15
            r.append("%.2f MPa" % float(np.median(s[k])) if k.sum() else "—")
        rows.append(r)
    return D, common, rows


if __name__ == "__main__":
    D = load()
    for s in ("S35", "S36", "S37"):
        d = D[s]
        print("%s  gauge %2.0f  E(common) %6.2f MPa  R2 %.4f  coverage %3.0f %%  "
              "max eps %5.2f %%  anchor %4.1f N"
              % (s, d["gauge"], d["slope"], d["r2"], d["cov"] * 100, d["e"].max(),
                 d["a"]["anchor"]))
    fig(); fig_trio()
