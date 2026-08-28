"""One-page tensile-test report for the UTM DIC rig.

Standalone engine + CLI that turns ONE test CSV into a dense landscape one-pager
(KPI strip · test settings · 4 plots · validation vs references) plus the four
graphs saved individually. Output PDFs are VECTOR with editable/selectable text
(pdf.fonttype 42) so the graphs can be copied/edited elsewhere.

Uses the shared analysis library (utm_analysis) so the numbers match every other
tool. The app calls build_report(csv, settings=...) from a "Generate report"
button, passing the live UI settings (specimen mode, preload, speed, ...); run
standalone it recovers what it can from the CSV metadata header.

    CLI:   python utm_report.py <test.csv> [--area 80] [--gauge 80] [--out DIR] [--no-graphs]
    App:   from utm_report import build_report; build_report(csv_path, settings=ui_dict)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # find utm_analysis alongside this file
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import FancyBboxPatch
matplotlib.rcParams["pdf.fonttype"] = 42        # embed TrueType -> editable/selectable text in the PDF
matplotlib.rcParams["ps.fonttype"] = 42
# OO API (Figure + FigureCanvasAgg) — no global backend switch, so build_report() is safe to call
# from inside the running Qt app (which owns the interactive backend) as well as standalone.
from utm_analysis import read_csv, analyze, read_meta

CHACON = {"uts": (32, 60), "sy": (30, 50), "E": (3.0, 5.5)}     # Chacón (2017) ranges
EPLA = {"uts": 58.0, "sy": 58.0, "E": 2.87, "ef": 8.0}          # add:north E-PLA datasheet
BLUE, RED, GREEN, PURPLE, GREY = "#1f77b4", "#d62728", "#2e7d32", "#6a1b9a", "#555555"
GREEN_BG, YELLOW_BG = "#e7f4e8", "#fff6da"


def _fmt(x):
    """Tidy a numeric-ish value for display (494.53299999999996 -> 494.533)."""
    try:
        return f"{float(x):g}"
    except (TypeError, ValueError):
        return str(x)


# read_meta() is imported from utm_analysis (shared, dependency-free).


# ---------- individual plot builders (reused for the one-pager AND the standalone graphs) ----------
def _plot_ss(ax, r, uts_d, sy_d, last_d):
    ymax = r["uts"] * 1.18
    xmax = last_d["ecz"] * 100 * 1.04
    if r["curve"]:
        xs, ys = zip(*r["curve"])
        ax.plot(xs, ys, "-", color=BLUE, lw=1.9, zorder=3)
    xe = [0.0, min(0.6, (sy_d["ecz"] + 0.004) * 100)]                 # elastic fit line
    ax.plot(xe, [10 * r["E"] * x + r["c1"] for x in xe], "--", color=GREY, lw=1.2, label="elastic fit")
    xo_end = min(xmax, 0.2 + (ymax - r["c1"]) / (10 * r["E"]))        # 0.2 % offset line, capped to the axes
    ax.plot([0.2, xo_end], [10 * r["E"] * (x - 0.2) + r["c1"] for x in (0.2, xo_end)],
            ":", color="#999", lw=1.1, label="0.2 % offset")
    ax.plot(r["uts_ec"], r["uts"], "o", color=RED, ms=8, mec="black", mew=0.5, zorder=5, label="UTS")
    if r.get("sy") is not None and r.get("sy_ec") is not None:
        ax.plot(r["sy_ec"], r["sy"], "s", color=GREEN, ms=7, mec="black", mew=0.5, zorder=5, label="σ_y")
    ax.plot(last_d["ecz"] * 100, last_d["sig"], "x", color="black", ms=9, mew=2, zorder=5, label="fracture")
    ax.set_xlim(-0.05, xmax); ax.set_ylim(0, ymax)
    ax.set_xlabel("Engineering strain, DIC  (%)"); ax.set_ylabel("Engineering stress  (MPa)")
    ax.set_title("Stress–strain", fontsize=11, fontweight="bold")
    ax.grid(alpha=0.3); ax.legend(fontsize=7.5, loc="lower right")


def _plot_lt(ax, seg, t0, uts_d, last_d, preload):
    ax.plot([d["t"] - t0 for d in seg], [d["Ftrue"] for d in seg], "-", color=BLUE, lw=1.9)
    ax.axhline(preload, ls=(0, (4, 3)), color="#c0392b", lw=1.2, zorder=1)         # curve starts at the held preload
    ax.text(0.015, preload, f" preload ≈ {preload:.0f} N", transform=ax.get_yaxis_transform(),
            va="top", ha="left", fontsize=8, color="#c0392b", fontweight="bold")
    ax.plot(uts_d["t"] - t0, uts_d["Ftrue"], "v", color=RED, ms=9, mec="black", mew=0.5)
    ax.plot(last_d["t"] - t0, last_d["Ftrue"], "x", color="black", ms=9, mew=2)
    ax.set_xlabel("Time from ramp start  (s)"); ax.set_ylabel("Force  (N)")
    ax.set_title("Load vs time", fontsize=11, fontweight="bold"); ax.grid(alpha=0.3)


def _plot_sd(ax, seg, uts_d, preload_stress):
    ax.plot([d["travel"] for d in seg], [d["sig"] for d in seg], "-", color=PURPLE, lw=1.9)
    ax.axhline(preload_stress, ls=(0, (4, 3)), color="#c0392b", lw=1.2, zorder=1)   # preload stress = anchor / area
    ax.text(0.015, preload_stress, f" preload ≈ {preload_stress:.1f} MPa", transform=ax.get_yaxis_transform(),
            va="top", ha="left", fontsize=8, color="#c0392b", fontweight="bold")
    ax.plot(uts_d["travel"], uts_d["sig"], "v", color=RED, ms=9, mec="black", mew=0.5)
    ax.set_xlabel("Crosshead travel  (mm)"); ax.set_ylabel("Engineering stress  (MPa)")
    ax.set_title("Stress vs crosshead", fontsize=11, fontweight="bold"); ax.grid(alpha=0.3)


def _plot_ed(ax, test, gauge, last_d):
    tr = [d["travel"] for d in test]; ec = [d["ecz"] for d in test]
    ax.plot(tr, ec, "-", color="#e08214", lw=1.9, label="DIC gauge")
    if tr:
        mt = max(tr) * 1.02
        ax.plot([0, mt], [0, mt / gauge], ":", color=GREY, lw=1.2, label="ideal (all travel→gauge)")
    ax.set_xlabel("Crosshead travel  (mm)"); ax.set_ylabel("Engineering strain, DIC")
    # Named for what the reader should take from it. The dotted line is "if every millimetre of
    # crosshead became gauge strain"; the gap between it and the measured curve IS the machine
    # compliance — the same effect that makes the crosshead read stiffer while the specimen softens.
    # NOT "strain rate": neither axis is time, so there is no dε/dt on this plot.
    ax.set_title("DIC strain vs crosshead — the compliance gap", fontsize=11, fontweight="bold")
    ax.grid(alpha=0.3); ax.legend(fontsize=7.5, loc="upper left")


def _kpi(fig, x, w, label, value, color=BLUE):
    ax = fig.add_axes([x, 0.845, w, 0.075]); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.03, 0.05), 0.94, 0.9, boxstyle="round,pad=0.02",
                                fc="#f4f7fb", ec=color, lw=1.3, transform=ax.transAxes))
    ax.text(0.5, 0.60, value, ha="center", va="center", fontsize=15, fontweight="bold", color=color)
    ax.text(0.5, 0.20, label, ha="center", va="center", fontsize=8.5, color="#333")


def _verdict(v, lo, hi):
    return ("PASS", GREEN) if lo <= v <= hi else ("low" if v < lo else "high", "#b8860b")


def build_report(csv_path, settings=None, out_dir=None, individual_plots=True):
    """Analyse one test CSV and write the one-pager (PDF+PNG) and the four graphs (PDF).
    Returns the list of written file paths. `settings` (from the app UI) overrides/augments
    the CSV metadata — e.g. {'id','specimen_mode','preload','speed','area','gauge','comment'}."""
    settings = dict(settings or {})
    meta = read_meta(csv_path)
    area = float(settings.get("area") or meta.get("area") or 80.0)
    gauge = float(settings.get("gauge") or meta.get("gauge") or 80.0)

    data = read_csv(csv_path)
    r = analyze(data, area, gauge)
    mv, fr = r["mv_i"], r["fr_i"]
    t0 = data[mv]["t"]
    seg = data[mv:fr]                                   # motion → fracture (force / travel valid)
    test = [d for d in seg if d["lpx"] > 100]           # DIC-valid subset (strain)
    uts_d = max(test, key=lambda d: d["sig"])
    sy_d = next(d for d in test if r["E"] * 1000 * (d["ecz"] - 0.002) + r["c1"] >= d["sig"])
    last_d = max(test, key=lambda d: d["t"])
    preload = r["anchor"]; preload_stress = preload / area   # held preload (self-calibration anchor) & its stress

    stem = os.path.splitext(os.path.basename(csv_path))[0]
    # default output: a central "reports" folder next to this script (Software/UTM_PyQt6/reports)
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(out_dir, exist_ok=True)

    # ---------- one-pager ----------
    fig = Figure(figsize=(16, 9)); FigureCanvasAgg(fig); fig.patch.set_facecolor("white")
    spec_id = settings.get("id") or stem
    fig.text(0.5, 0.965, f"UTM TENSILE REPORT — {spec_id}", ha="center", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.935, "DIC gauge strain (ENGINEERING: ΔL/L₀) · engineering stress (F/A₀) · anchor self-calibration",
             ha="center", fontsize=10.5, color="#666")

    kpis = [("UTS", f"{r['uts']:.1f} MPa", RED), ("Yield σ_y", f"{r['sy']:.1f} MPa", GREEN),
            ("Modulus E", f"{r['E']:.2f} GPa", PURPLE), ("Failure ε_f", f"{r['ef']*100:.1f} %", "#e08214"),
            ("Toughness", f"{r['tough']:.0f} kJ/m³", BLUE), ("Preload anchor", f"{r['anchor']:.0f} N", GREY)]
    for i, (lab, val, col) in enumerate(kpis):
        _kpi(fig, 0.035 + i * 0.157, 0.150, lab, val, col)

    # settings / metadata panel (from UI settings, falling back to CSV header)
    sett = fig.add_axes([0.035, 0.44, 0.245, 0.37]); sett.axis("off")
    sett.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01", fc="#fbfbfb", ec="#ccc", lw=1))
    def g(k, d="—"):
        v = settings.get(k, None)
        return d if v in (None, "") else v
    lines = [
        ("Specimen", str(g("id", spec_id))),
        ("DIC mode", str(g("specimen_mode"))),
        ("Preload target", f"{g('preload')} N" if g('preload') != "—" else "—"),
        ("Test speed", f"{g('speed')} mm/s" if g('speed') != "—" else "—"),
        ("Cross-section", f"{area:.0f} mm²"),
        ("Gauge length L₀", f"{gauge:.0f} mm"),
        ("Infill (label)", (f"{meta.get('infill')} %" if meta.get('infill') else str(g('infill', '—')))),
        ("Force calib", f"sc {_fmt(g('scale', meta.get('scale','—')))} / off {_fmt(g('offset', meta.get('offset','—')))}"),
        ("Comment", str(g("comment", meta.get("comment", "—")))),
        ("Test date", str(meta.get("date", "—"))[:22]),
        ("Duration", str(meta.get("duration", f"{r['dur']:.0f} s"))),
    ]
    sett.text(0.04, 0.95, "TEST SETTINGS", fontsize=11, fontweight="bold", color="#333", va="top")
    for j, (k, v) in enumerate(lines):
        y = 0.85 - j * 0.077
        sett.text(0.04, y, k, fontsize=9, color="#666", va="top")
        sett.text(0.52, y, str(v)[:30], fontsize=9, color="black", va="top", fontweight="bold")

    # validation-vs-references panel
    val = fig.add_axes([0.035, 0.05, 0.245, 0.33]); val.axis("off")
    val.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01", fc="#fbfbfb", ec="#ccc", lw=1))
    val.text(0.04, 0.94, "VALIDATION vs REFERENCES", fontsize=11, fontweight="bold", color="#333", va="top")
    val.text(0.04, 0.83, "prop", fontsize=8, color="#888", va="top")
    val.text(0.30, 0.83, "meas", fontsize=8, color="#888", va="top")
    val.text(0.55, 0.83, "Chacón", fontsize=8, color="#888", va="top")
    val.text(0.82, 0.83, "E-PLA k", fontsize=8, color="#888", va="top")
    rowspec = [("UTS", r["uts"], "MPa", CHACON["uts"], EPLA["uts"]),
               ("σ_y", r["sy"], "MPa", CHACON["sy"], EPLA["sy"]) if r.get("sy") is not None
               else ("σ_y", None, "not reached", None, None),
               ("E", r["E"], "GPa", CHACON["E"], EPLA["E"])]
    for j, (name, v, unit, rng, spec) in enumerate(rowspec):
        y = 0.71 - j * 0.13
        verdict, vc = _verdict(v, *rng)
        val.text(0.04, y, name, fontsize=9.5, color="black", va="top", fontweight="bold")
        val.text(0.30, y, f"{v:.1f}", fontsize=9.5, va="top")
        val.text(0.55, y, f"{rng[0]:g}–{rng[1]:g} {verdict}", fontsize=8.5, color=vc, va="top", fontweight="bold")
        val.text(0.82, y, f"×{spec / v:.2f}", fontsize=9, va="top")
    efk = EPLA["ef"] / (r["ef"] * 100) if r["ef"] else 0
    val.text(0.04, 0.32, "ε_f", fontsize=9.5, color="black", va="top", fontweight="bold")
    val.text(0.30, 0.32, f"{r['ef']*100:.1f} %", fontsize=9.5, va="top")
    val.text(0.55, 0.32, "(range 3–7 %)", fontsize=8.5, color="#888", va="top")
    val.text(0.82, 0.32, f"×{efk:.2f}", fontsize=9, va="top")
    ov = all(rng[0] <= v <= rng[1] for _, v, _, rng, _ in rowspec[:2])   # strength inside journal
    val.text(0.04, 0.13, ("✓ strength inside journal range (k≈1)" if ov else "⚠ strength outside journal range"),
             fontsize=8.8, color=(GREEN if ov else "#b8860b"), va="top", fontweight="bold")

    # four plots (right two-thirds)
    _plot_ss(fig.add_axes([0.345, 0.50, 0.28, 0.30]), r, uts_d, sy_d, last_d)
    _plot_lt(fig.add_axes([0.705, 0.50, 0.28, 0.30]), seg, t0, uts_d, last_d, preload)
    _plot_sd(fig.add_axes([0.345, 0.055, 0.28, 0.30]), seg, uts_d, preload_stress)
    _plot_ed(fig.add_axes([0.705, 0.055, 0.28, 0.30]), test, gauge, last_d)

    pdf = os.path.join(out_dir, stem + "_report.pdf")
    png = os.path.join(out_dir, stem + "_report.png")
    fig.savefig(pdf); fig.savefig(png, dpi=150)
    outputs = [pdf, png]

    # ---------- individual graphs (vector PDF, for copy-paste elsewhere) ----------
    if individual_plots:
        singles = [("stress_strain", lambda ax: _plot_ss(ax, r, uts_d, sy_d, last_d)),
                   ("load_time", lambda ax: _plot_lt(ax, seg, t0, uts_d, last_d, preload)),
                   ("stress_disp", lambda ax: _plot_sd(ax, seg, uts_d, preload_stress)),
                   ("strain_disp", lambda ax: _plot_ed(ax, test, gauge, last_d))]
        for name, fn in singles:
            f = Figure(figsize=(6.2, 4.4)); FigureCanvasAgg(f)
            ax = f.add_subplot(111); fn(ax); f.tight_layout()
            base = os.path.join(out_dir, f"{stem}_{name}")
            f.savefig(base + ".pdf")               # vector (editable)
            f.savefig(base + ".png", dpi=150)      # image (easy to copy/paste)
            outputs.extend([base + ".pdf", base + ".png"])
    return outputs


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: python utm_report.py <test.csv> [--area 80] [--gauge 80] [--out DIR] [--no-graphs]")
        sys.exit(0)
    csv = args[0]
    opt = {}
    for i, a in enumerate(args):
        if a == "--area" and i + 1 < len(args): opt["area"] = float(args[i + 1])
        if a == "--gauge" and i + 1 < len(args): opt["gauge"] = float(args[i + 1])
    out = args[args.index("--out") + 1] if "--out" in args else None
    graphs = "--no-graphs" not in args
    settings = {k: opt[k] for k in ("area", "gauge") if k in opt}
    paths = build_report(csv, settings=settings, out_dir=out, individual_plots=graphs)
    print("Report written:")
    for p in paths:
        print("  " + p)
