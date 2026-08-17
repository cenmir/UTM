"""The full-resolution S25 / S26 stress-strain reference document (PDF).

The deck can only carry the 64-row resampled comparison — 1 671 raw samples is 66 slides nobody
would page through. This is where the raw samples live: every point the instrument recorded, in
print, so a number read off the extensometer software can be looked up rather than eyeballed off a
curve.

Built with matplotlib's PDF backend (the same one utm_report.py uses) rather than a Word/reportlab
dependency the repo does not have. Pages are drawn in INCHES on a single full-bleed axis, which is
what makes a hand-laid-out table honest about where its columns are.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages                # noqa: E402
from matplotlib.patches import Rectangle                            # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s25_s26_data as D                                            # noqa: E402
import s25_s26_plots as P                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "S25_S26_stress_strain_reference.pdf")

PAGE = (11.69, 8.27)                     # A4 landscape
MARGIN_L = MARGIN_R = 0.45
TOP_RULE = 0.92                          # baseline of the page heading
INK, MUTED, RULE = "#1A1A1A", "#666666", "#C9CDD2"
HEAD_BG = "#143D2F"                      # the deck's header green, so the two documents match
BAND = "#F4F5F7"                         # zebra stripe

_page_no = [0]


def _canvas(pdf_title, subtitle=None):
    """A blank page whose coordinate system is INCHES from the top-left."""
    fig = plt.figure(figsize=PAGE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAGE[0])
    ax.set_ylim(PAGE[1], 0)              # y grows downward, like a page
    ax.axis("off")

    ax.text(MARGIN_L, 0.52, pdf_title, fontsize=15, color=INK, va="baseline")
    if subtitle:
        ax.text(MARGIN_L, 0.78, subtitle, fontsize=9, color=MUTED, va="baseline")
    ax.plot([MARGIN_L, PAGE[0] - MARGIN_R], [TOP_RULE, TOP_RULE], color=HEAD_BG, lw=1.6)

    _page_no[0] += 1
    ax.text(PAGE[0] - MARGIN_R, PAGE[1] - 0.28, str(_page_no[0]), fontsize=8,
            color=MUTED, ha="right", va="baseline")
    ax.text(MARGIN_L, PAGE[1] - 0.28,
            "UTM DIC · 8.6.20 tensile-to-failure · S25 / S26 frame-capture runs · "
            "engineering stress on 80 mm², DIC gauge strain on 80 mm",
            fontsize=7, color=MUTED, va="baseline")
    return fig, ax


def _fill_for(mark):
    """The landmark colours for a row label like 'S25 yield' or 'S25 UTS + S26 yield'."""
    for word in mark.split():
        if word in D.MARKS:
            return D.MARKS[word]
    return None


def _block(ax, x, y, width, rows, headers, colf, *, rowh=0.118, fs=6.4, hfs=6.6):
    """One column-block of a table. Returns the y just below it.

    `rows` are (cells, mark) — cells is one string per column, and a non-empty mark fills the row
    with that landmark's colour. Cells are right-aligned, because a table of numbers that does not
    line up on the decimal point is a table you have to read twice.
    """
    tot = sum(colf)
    edges = [x]
    for f in colf:
        edges.append(edges[-1] + width * f / tot)

    ax.add_patch(Rectangle((x, y), width, rowh, facecolor=HEAD_BG, edgecolor="none"))
    for i, h in enumerate(headers):
        ax.text(edges[i + 1] - 0.04, y + rowh * 0.72, h, fontsize=hfs, color="white",
                ha="right", weight="bold")

    yy = y + rowh
    for k, (cells, mark) in enumerate(rows):
        m = _fill_for(mark) if mark else None
        if m:
            ax.add_patch(Rectangle((x, yy), width, rowh, facecolor=m["fill"],
                                   edgecolor=m["edge"], lw=0.7))
        elif k % 2:
            ax.add_patch(Rectangle((x, yy), width, rowh, facecolor=BAND, edgecolor="none"))
        for i, cell in enumerate(cells):
            ax.text(edges[i + 1] - 0.04, yy + rowh * 0.72, cell, fontsize=fs,
                    color=INK, ha="right", weight="bold" if mark else "normal")
        yy += rowh
    ax.plot([x, x + width], [yy, yy], color=RULE, lw=0.6)
    return yy


# Page budget, computed rather than typed — the cover's contents list has to survive a change of
# density or an extra specimen without silently pointing at the wrong page.
GRID_PER_BLOCK, GRID_BLOCKS = 22, 3
FULL_PER_BLOCK, FULL_BLOCKS = 53, 5


def _layout():
    def npages(n, per):
        return max(1, -(-n // per))
    n_grid = npages(len(D.grid_rows()), GRID_PER_BLOCK * GRID_BLOCKS)
    counts = {t: npages(len(D.full_rows(t)), FULL_PER_BLOCK * FULL_BLOCKS) for t in D.ORDER}
    first = {"cover": 1, "elastic": 2, "grid": 3, "grid_n": n_grid}
    p = 3 + n_grid
    for t in D.ORDER:
        first[t] = p
        p += counts[t]
    first["total"] = p - 1
    first.update({f"{t}_n": counts[t] for t in D.ORDER})
    return first


def _span(lo, n):
    return f"p{lo}" if n == 1 else f"p{lo}-{lo + n - 1}"


def _legend_strip(ax, y):
    """The three landmark fills, spelled out, on every table page."""
    x = MARGIN_L
    ax.text(x, y + 0.09, "Highlighted rows:", fontsize=7.5, color=MUTED, va="baseline")
    x += 1.05
    for m in D.MARKS.values():
        ax.add_patch(Rectangle((x, y - 0.03), 0.20, 0.13, facecolor=m["fill"],
                               edgecolor=m["edge"], lw=0.9))
        ax.text(x + 0.26, y + 0.09, m["pretty"], fontsize=7.5, color=INK, va="baseline")
        x += 1.85


# ---------------------------------------------------------------- pages

def page_cover(pdf):
    fig, ax = _canvas("S25 vs S26 — STRESS-STRAIN REFERENCE",
                      "Every recorded data point of both frame-capture fracture runs, for "
                      "line-by-line comparison against extensometer software")

    img = P.overlay(os.path.join(HERE, "s25_s26_overlay.png"))
    ax.imshow(plt.imread(img), extent=(MARGIN_L, 7.55, 5.35, 1.15), aspect="auto",
              interpolation="antialiased")

    x0 = 7.75
    ax.text(x0, 1.32, "HEADLINE NUMBERS", fontsize=9, color=MUTED, weight="bold")
    rows = []
    a, b = D.summary("S25"), D.summary("S26")
    for lbl, ka, fmt in (("UTS", "UTS", "{:.2f} MPa"), ("at strain", "UTS_e", "{:.2f} %"),
                         ("σ_y (0.2 %)", "sy", "{:.2f} MPa"), ("at strain", "sy_e", "{:.2f} %"),
                         ("E (fixed window)", "E", "{:.3f} GPa"), ("ε_f", "ef", "{:.2f} %"),
                         ("σ at fracture", "sigf", "{:.2f} MPa"),
                         ("Toughness", "tough", "{:.0f} kJ/m³"),
                         ("Force anchor", "anchor", "{:.0f} N"),
                         ("Load samples", "n", "{:.0f}"),
                         ("Captured frames", "frames", "{:.0f}")):
        rows.append(([lbl, fmt.format(a[ka]), fmt.format(b[ka])], ""))
    _block(ax, x0, 1.45, 3.5, rows, ["", "S25 · VC2", "S26 · VC3"], [1.5, 1.0, 1.0], rowh=0.185,
           fs=7.6, hfs=7.6)

    L = _layout()
    ax.text(MARGIN_L, 5.75, "WHAT IS IN THIS DOCUMENT", fontsize=9, color=MUTED, weight="bold")
    ax.text(MARGIN_L, 5.98,
            f"•  p{L['elastic']}   Why the reported E differs between the two runs — and why σ_y "
            f"follows it\n"
            f"•  {_span(L['grid'], L['grid_n'])}   COMPARISON TABLE — both runs resampled onto one "
            f"common strain axis ({D.STEP_PCT:.2f} % steps), the form to read across\n"
            f"•  {_span(L['S25'], L['S25_n'])}   FULL RESOLUTION · S25 — all "
            f"{len(D.full_rows('S25'))} raw samples in acquisition order\n"
            f"•  {_span(L['S26'], L['S26_n'])}   FULL RESOLUTION · S26 — all "
            f"{len(D.full_rows('S26'))} raw samples in acquisition order\n\n"
            "Stress is ENGINEERING stress (force ÷ 80 mm² nominal), anchor-corrected: the preload "
            "tared away at the start of the test is\n"
            "added back, which is why these values exceed the tared reading in the CSV header. "
            "Strain is DIC gauge strain over an 80 mm\n"
            "gauge, zeroed at Px₀. Both are exactly what the app's own report button computes — "
            "utm_analysis.analyze(), no separate maths.",
            fontsize=8.3, color=INK, va="top", linespacing=1.5)
    _legend_strip(ax, 7.55)
    pdf.savefig(fig)
    plt.close(fig)


def page_elastic(pdf):
    fig, ax = _canvas("WHY THE TWO RUNS REPORT A DIFFERENT E",
                      "The fit window is fixed; the toe it lands on is not")
    img = P.elastic(os.path.join(HERE, "s25_s26_elastic.png"))
    ax.imshow(plt.imread(img), extent=(MARGIN_L, 11.24, 4.55, 1.15), aspect="auto",
              interpolation="antialiased")

    a, b = D.summary("S25"), D.summary("S26")
    ba, bb = D.best_elastic_fit("S25"), D.best_elastic_fit("S26")
    ax.text(MARGIN_L, 5.05,
            f"analyze() fits E over a FIXED 0.05–0.40 % strain window. A specimen that seats more "
            f"slowly has a longer toe, so that window lands further down the curve\n"
            f"and returns a softer modulus. Searching instead for each specimen's own straightest "
            f"run:\n\n"
            f"     S25   fixed window {a['E']:.3f} GPa   →   straightest run "
            f"{ba[0]:.3f} GPa over {ba[1]:.2f}–{ba[2]:.2f} %   (R² {ba[3]:.4f})\n"
            f"     S26   fixed window {b['E']:.3f} GPa   →   straightest run "
            f"{bb[0]:.3f} GPa over {bb[1]:.2f}–{bb[2]:.2f} %   (R² {bb[3]:.4f})\n\n"
            f"σ_y is a CONSEQUENCE of this. The 0.2 % offset line has slope E, so a softer E tilts "
            f"it down, meets the curve later, and pushes σ_y toward UTS:\n"
            f"S25 reports σ_y at {100 * a['sy'] / a['UTS']:.1f} % of its UTS, S26 at "
            f"{100 * b['sy'] / b['UTS']:.1f} %. The σ_y spread ({a['sy']:.1f} vs {b['sy']:.1f} MPa) "
            f"is largely the E spread re-expressed.\n\n"
            f"UTS needs no fit at all and agrees to "
            f"{100 * abs(b['UTS'] - a['UTS']) / a['UTS']:.1f} % — it is the number to quote when "
            f"comparing against the extensometer.",
            fontsize=8.6, color=INK, va="top", linespacing=1.55)
    pdf.savefig(fig)
    plt.close(fig)


def pages_grid(pdf, per_block=GRID_PER_BLOCK, blocks=GRID_BLOCKS):
    """The common-strain comparison table — same rows the deck carries, at print density."""
    rows = D.grid_rows()
    fmt = lambda v: "—" if v is None else f"{v:.2f}"                       # noqa: E731
    body = []
    for e, s25, s26, mk in rows:
        diff = f"{s26 - s25:+.2f}" if (s25 is not None and s26 is not None) else "—"
        body.append(([f"{e:.2f}", fmt(s25), fmt(s26), diff, mk], mk))

    per_page = per_block * blocks
    pages = [body[i:i + per_page] for i in range(0, len(body), per_page)]
    for pi, chunk in enumerate(pages, 1):
        fig, ax = _canvas(f"COMPARISON TABLE — COMMON STRAIN AXIS  ({pi}/{len(pages)})",
                          f"Both runs resampled to {D.STEP_PCT:.2f} % strain steps · "
                          f"{len(rows)} rows · exact yield / UTS / fracture samples inserted at "
                          f"their true strain")
        width = (PAGE[0] - MARGIN_L - MARGIN_R - 0.5 * (blocks - 1)) / blocks
        for bi in range(blocks):
            part = chunk[bi * per_block:(bi + 1) * per_block]
            if not part:
                break
            _block(ax, MARGIN_L + bi * (width + 0.5), 1.20, width, part,
                   ["ε (%)", "S25 σ", "S26 σ", "Δ", "landmark"],
                   [0.85, 0.95, 0.95, 0.85, 1.7], rowh=0.185, fs=7.4, hfs=7.4)
        ax.text(MARGIN_L, 6.75,
                "σ in MPa. Δ = S26 − S25. “—” means that strain is past that specimen's fracture, "
                "so it has no stress there.",
                fontsize=7.8, color=MUTED, va="baseline")
        _legend_strip(ax, 7.15)
        pdf.savefig(fig)
        plt.close(fig)


def pages_full(pdf, tag, per_block=FULL_PER_BLOCK, blocks=FULL_BLOCKS):
    """Every raw sample of one run."""
    rows = D.full_rows(tag)
    body = [([str(n), f"{e:.4f}", f"{s:.3f}", mk[:1].upper() if mk else ""], mk)
            for n, e, s, mk in rows]
    d = D.summary(tag)

    per_page = per_block * blocks
    pages = [body[i:i + per_page] for i in range(0, len(body), per_page)]
    for pi, chunk in enumerate(pages, 1):
        fig, ax = _canvas(f"FULL RESOLUTION — {d['label']}   ({pi}/{len(pages)})",
                          f"All {len(rows)} recorded samples in acquisition order · "
                          f"UTS {d['UTS']:.2f} MPa · σ_y {d['sy']:.2f} MPa · E {d['E']:.3f} GPa · "
                          f"ε_f {d['ef']:.2f} % · {d['frames']} frames captured")
        width = (PAGE[0] - MARGIN_L - MARGIN_R - 0.28 * (blocks - 1)) / blocks
        for bi in range(blocks):
            part = chunk[bi * per_block:(bi + 1) * per_block]
            if not part:
                break
            _block(ax, MARGIN_L + bi * (width + 0.28), 1.15, width, part,
                   ["#", "ε (%)", "σ (MPa)", ""], [0.8, 1.15, 1.15, 0.4],
                   rowh=0.113, fs=6.1, hfs=6.4)
        _legend_strip(ax, 7.45)
        ax.text(PAGE[0] - MARGIN_R, 7.54, "Y = yield   U = UTS   F = fracture",
                fontsize=7.5, color=MUTED, ha="right", va="baseline")
        pdf.savefig(fig)
        plt.close(fig)


def build(out=OUT):
    _page_no[0] = 0
    with PdfPages(out) as pdf:
        page_cover(pdf)
        page_elastic(pdf)
        pages_grid(pdf)
        for tag in D.ORDER:
            pages_full(pdf, tag)
        info = pdf.infodict()
        info["Title"] = "S25 vs S26 — stress-strain reference (8.6.20 tensile to failure)"
        info["Subject"] = ("Full-resolution stress-strain data for the two frame-capture fracture "
                           "runs, for extensometer cross-validation")
        info["Author"] = "UTM DIC rig · Jönköping University"
    return out, _page_no[0]


if __name__ == "__main__":
    path, n = build()
    print(f"wrote {path}  ({n} pages, {os.path.getsize(path)/1e6:.2f} MB)")
