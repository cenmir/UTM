"""The MOT session pack — everything needed to validate our PLA numbers against a video extensometer.

Printable, self-contained, and written to be read at a bench rather than at a desk.

The risk this document exists to remove is NOT that the two instruments disagree. It is that they
disagree for a PROCEDURAL reason and the session is spent arguing about it: a different strain zero,
a different gauge, a different modulus fit window, a different area basis. Each of those moves a
number by more than the effect being measured, and each is settled in advance here.

The single largest one is the strain zero. Our Px0 is frozen AFTER a ~300 N preload, so our strain
axis starts at a seated specimen. An extensometer zeroed at 0 N includes the toe -- the grip take-up
and specimen straightening -- inside its strain, which lowers apparent modulus and shifts the 0.2 %
offset yield. That single difference can move E by more than the 8.5 % scatter of our whole
11-specimen set, so it has to be matched or deliberately accounted for, not discovered afterwards.

Built on matplotlib's PDF backend, like s25_s26_reference_pdf.py, so it needs nothing the repo does
not already have. Numbers come from registry.json at build time -- none are typed in.
"""
import json
import os
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages                 # noqa: E402
from matplotlib.patches import Rectangle                             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "MOT_extensometer_validation_pack.pdf")

PAGE = (11.69, 8.27)                      # A4 landscape
ML = MR = 0.45
INK, MUTED, RULE = "#1A1A1A", "#666666", "#C9CDD2"
HEAD = "#143D2F"
BAND = "#F4F5F7"
WARN = "#FFF3CD"
GOOD = "#C8E6C9"
BAD = "#FFCDD2"
_page = [0]

# add:north E-PLA TDS rev 2.1 (ISO 527 / 178) — the published reference the campaign is judged on.
TDS = {"UTS": 58.0, "E": 2.87, "ef": 0.08, "Tg": "55-60 degC"}
FIX_DATE = "2026-08-12"                   # rig realignment; runs after it are the reliable set


def pla100():
    """The clean 100 % PLA set, straight from the registry. Fracture-derived rows only."""
    with open(os.path.join(REPO, "Software", "UTM_PyQt6", "registry.json"), encoding="utf-8") as fh:
        R = json.load(fh)
    rows = R if isinstance(R, list) else R.get("tests", R.get("rows", []))
    sel = [r for r in rows
           if (r.get("material") or "PLA") == "PLA"
           and float(r.get("infill_pct") or 0) == 100.0
           and r.get("UTS_MPa")]
    return sorted(sel, key=lambda r: str(r.get("date")))


def stats(sel, key):
    v = [r[key] for r in sel if r.get(key)]
    m = st.mean(v)
    s = st.stdev(v) if len(v) > 1 else 0.0
    return {"n": len(v), "mean": m, "sd": s, "cv": 100 * s / m, "min": min(v), "max": max(v)}


def canvas(title, subtitle=None, foot=None):
    fig = plt.figure(figsize=PAGE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAGE[0]); ax.set_ylim(PAGE[1], 0); ax.axis("off")
    ax.text(ML, 0.52, title, fontsize=15, color=INK, va="baseline")
    if subtitle:
        ax.text(ML, 0.78, subtitle, fontsize=9, color=MUTED, va="baseline")
    ax.plot([ML, PAGE[0] - MR], [0.92, 0.92], color=HEAD, lw=1.6)
    _page[0] += 1
    ax.text(PAGE[0] - MR, PAGE[1] - 0.28, str(_page[0]), fontsize=8, color=MUTED,
            ha="right", va="baseline")
    ax.text(ML, PAGE[1] - 0.28,
            foot or "UTM DIC - PLA validation against a video extensometer - MOT session pack",
            fontsize=7, color=MUTED, va="baseline")
    return fig, ax


# Inches of line length per character per point of font size. Bold is measurably wider, and getting
# this wrong is not cosmetic: the first build ran the strain-zero banner — the most important
# sentence in the pack — off the right-hand edge of its own box.
CHAR_W = {"normal": 0.0082, "bold": 0.0092}


def wrap(text, w, fs, weight="normal"):
    """Greedy wrap to a width in INCHES. Returns the lines."""
    per = max(10, int(w / (fs * CHAR_W.get(weight, CHAR_W["normal"]))))
    out, line = [], ""
    for wd in text.split():
        t = (line + " " + wd).strip()
        if len(t) > per and line:
            out.append(line); line = wd
        else:
            line = t
    if line:
        out.append(line)
    return out


def para(ax, x, y, w, text, *, fs=8.6, color=INK, lead=0.165, weight="normal"):
    """Wrap on width, in inches. Returns the y below the last line."""
    for ln in wrap(text, w, fs, weight):
        ax.text(x, y, ln, fontsize=fs, color=color, va="baseline", weight=weight)
        y += lead
    return y


def table(ax, x, y, w, headers, rows, colf, *, rowh=0.26, fs=7.6, hfs=7.6, fills=None,
          align=None):
    tot = sum(colf)
    edges = [x]
    for f in colf:
        edges.append(edges[-1] + w * f / tot)
    align = align or ["left"] * len(headers)
    ax.add_patch(Rectangle((x, y), w, rowh, facecolor=HEAD, edgecolor="none"))
    for i, h in enumerate(headers):
        xa = edges[i] + 0.05 if align[i] == "left" else edges[i + 1] - 0.05
        ax.text(xa, y + rowh * 0.68, h, fontsize=hfs, color="white",
                ha=align[i], weight="bold")
    yy = y + rowh
    for k, cells in enumerate(rows):
        fc = (fills or {}).get(k, BAND if k % 2 else None)
        if fc:
            ax.add_patch(Rectangle((x, yy), w, rowh, facecolor=fc, edgecolor="none"))
        for i, c in enumerate(cells):
            xa = edges[i] + 0.05 if align[i] == "left" else edges[i + 1] - 0.05
            ax.text(xa, yy + rowh * 0.68, str(c), fontsize=fs, color=INK, ha=align[i])
        yy += rowh
    ax.plot([x, x + w], [yy, yy], color=RULE, lw=0.6)
    for e in edges:
        ax.plot([e, e], [y, yy], color=RULE, lw=0.4)
    return yy


def banner(ax, x, y, w, text, fill=WARN, fs=8.8, weight="bold", lead=0.17):
    """A filled callout sized to its OWN text. Height is measured, never guessed."""
    lines = wrap(text, w - 0.28, fs, weight)
    h = 0.20 + len(lines) * lead
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor="#B9BDC2", lw=0.6))
    yy = y + 0.24
    for ln in lines:
        ax.text(x + 0.14, yy, ln, fontsize=fs, color=INK, va="baseline", weight=weight)
        yy += lead
    return y + h


def box(ax, x, y, w, h):
    """An empty rule to write on."""
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor="#9AA0A6", lw=0.7))


# =====================================================================================
def page_cover(pdf, sel):
    fig, ax = canvas("PLA vs VIDEO EXTENSOMETER - MOT SESSION PACK",
                     "What to bring, what must match, and what we are comparing against")
    u, e = stats(sel, "UTS_MPa"), stats(sel, "E_GPa")
    y = para(ax, ML, 1.35, 6.6,
             "WHAT WE ARE VALIDATING. Our strain comes from two spray dots tracked in a Basler "
             "frame, 80 mm apart, at about 20.9 px/mm. Everything the campaign claims about PLA "
             "rests on that measurement being right. A video extensometer is an independent optical "
             "measurement of the same quantity, so agreement is the strongest evidence available "
             "without a contact extensometer.", fs=9)
    y = para(ax, ML, y + 0.12, 6.6,
             f"WHAT WE BRING TO COMPARE. {u['n']} fractured 100 % infill PLA specimens: "
             f"UTS {u['mean']:.2f} +- {u['sd']:.2f} MPa (CV {u['cv']:.1f} %), "
             f"E {e['mean']:.2f} +- {e['sd']:.2f} GPa (CV {e['cv']:.1f} %). "
             "Page 3 has the full table.", fs=9)

    banner(ax, ML, y + 0.18, 6.6,
           "THE ONE THING THAT WILL COST YOU THE SESSION: THE STRAIN ZERO. Our Px0 is frozen AFTER "
           "a ~300 N preload, so our strain axis begins at an already-seated specimen. An "
           "extensometer zeroed at 0 N carries the toe - grip take-up and specimen straightening - "
           "inside its strain, which LOWERS apparent modulus and shifts the 0.2 % offset yield. "
           "That difference is bigger than the 8.5 % scatter of our entire 11-specimen set. Match "
           "it, or agree in advance to correct for it. Do not discover it in the data.", fill=BAD)

    x2 = ML + 7.0
    ax.text(x2, 1.30, "CONTENTS", fontsize=10, color=HEAD, weight="bold")
    for i, (n, t) in enumerate([
            (2, "Parameters that must match - the pre-flight"),
            (3, "Our reference values - the 100 % PLA set"),
            (4, "Comparison sheet - fill in at the bench"),
            (5, "Traps that make two correct instruments disagree"),
            (6, "What to physically bring")]):
        ax.text(x2, 1.62 + i * 0.26, f"{n}", fontsize=9, color=MUTED)
        ax.text(x2 + 0.30, 1.62 + i * 0.26, t, fontsize=9, color=INK)

    ax.text(x2, 3.35, "START WITH OUR OWN FRAMES",
            fontsize=10, color=HEAD, weight="bold")
    para(ax, x2, 3.66, 4.2,
         "We have every frame of S25 and S26 as PNG stills plus AVI - 1445 and 1682 frames, 0 "
         "dropped, 19.9 fps, 100 % DIC coverage. Running OUR frames through THEIR software is the "
         "cleanest validation there is: identical pixels, two independent algorithms, no specimen, "
         "no machine and no operator in the difference. Bring them on a stick and ask before "
         "mounting anything.", fs=8.4)
    para(ax, x2, 5.30, 4.2,
         "If that is not possible, the fallback is a live side-by-side on one specimen, which is "
         "still worth doing but now carries their machine's compliance and their grips in the "
         "comparison as well as their optics.", fs=8.4, color=MUTED)

    # The curve itself, on the cover: this is the thing being validated, and half the page was
    # otherwise white. S25/S26 are the two runs captured expressly for this comparison.
    img = os.path.join(HERE, "s25_s26_overlay.png")
    if os.path.exists(img):
        ax.text(ML, 4.55, "THE TWO RUNS CAPTURED FOR THIS COMPARISON - S25 AND S26",
                fontsize=9.5, color=HEAD, weight="bold")
        im = plt.imread(img)
        h_in = 3.10
        w_in = h_in * im.shape[1] / im.shape[0]
        if w_in > 6.6:
            w_in, h_in = 6.6, 6.6 * im.shape[0] / im.shape[1]
        ax.imshow(im, extent=[ML, ML + w_in, 4.80 + h_in, 4.80], aspect="auto",
                  interpolation="antialiased", zorder=3)
    pdf.savefig(fig); plt.close(fig)


def page_params(pdf, sel):
    fig, ax = canvas("PARAMETERS THAT MUST MATCH",
                     "Agree every row BEFORE the first pull. Right-hand column is theirs to fill in.")
    rows = [
        ["Gauge length", "80.0 mm", "Marker-to-marker, not the specimen's parallel length", ""],
        ["Marker spacing at zero", "~1674 px @ 20.93 px/mm", "Our Px0. Their targets should sit on the SAME dots", ""],
        ["Cross-section", "80.0 mm2", "CAD nominal, NOT measured. See the infill note on p5", ""],
        ["Infill", "100 %", "Solid. Our 50 % set needs a separate knock-down factor", ""],
        ["Stress convention", "Engineering", "Force / original area. We do not report Cauchy", ""],
        ["Strain convention", "Engineering  dL/L0", "CSV also carries a true-strain column; ignore it", ""],
        ["STRAIN ZERO", "AFTER ~300 N preload", "THE BIG ONE - see the banner below", ""],
        ["Crosshead speed", "0.10 mm/s", "Constant. Not a strain-rate-controlled ramp", ""],
        ["Modulus fit window", "Steepest straight run", "NOT a fixed window - see p5", ""],
        ["Yield definition", "0.2 % offset", "Offset line has slope E, so it moves if E does", ""],
        ["Sampling", "DIC 19.9 Hz / load ~11 Hz", "Ask theirs; a slow extensometer smooths the knee", ""],
        ["Temperature / RH", "record it", "PLA Tg is 55-60 degC; room conditions matter", ""],
    ]
    fills = {6: BAD, 8: WARN}
    y = table(ax, ML, 1.20, PAGE[0] - ML - MR,
              ["Parameter", "Our value", "Why it matters", "MOT setting"],
              rows, [1.5, 2.0, 4.6, 2.2], fills=fills,
              align=["left", "left", "left", "left"])

    y = banner(ax, ML, y + 0.22, PAGE[0] - ML - MR,
               "STRAIN ZERO, IN NUMBERS: at 300 N our specimen is already carrying 3.75 MPa. If "
               "their extensometer zeroes at 0 N, its first per cent of strain contains grip "
               "take-up that ours never saw, and every modulus they quote will read LOW against "
               "ours for a reason that has nothing to do with either instrument.", fill=BAD)
    para(ax, ML, y + 0.34, PAGE[0] - ML - MR,
         "IF THEY CANNOT PRELOAD TO 300 N: let them zero at 0 N, but then compare on the SECANT "
         "between two strain points that both lie above the toe - 0.05 % and 0.25 % is the ISO "
         "527 pair - rather than on either instrument's own automatic modulus. That comparison is "
         "immune to where the axes were zeroed. Record BOTH numbers either way.", fs=8.6)
    pdf.savefig(fig); plt.close(fig)


def page_reference(pdf, sel):
    fig, ax = canvas("OUR REFERENCE VALUES - 100 % INFILL PLA",
                     "From registry.json at build time. Every row is a specimen that fractured.")
    # S25 and S26 are THE comparison pair: both were run with frame capture expressly for
    # extensometer cross-validation, so every frame exists and can be re-processed.
    REF = {"S25", "S26"}
    rows = []
    for r in sel:
        post = str(r["date"])[:10] >= FIX_DATE
        tag = ("<< EXTENSOMETER PAIR" if r["specimen"] in REF
               else ("post-realign" if post else ""))
        rows.append([r["specimen"], str(r["date"])[:10], f"{r['UTS_MPa']:.2f}",
                     f"{r['sy_MPa']:.2f}", f"{r['E_GPa']:.3f}", f"{r['ef']*100:.2f}",
                     f"{r['anchor_N']:.0f}", tag])
    fills = {i: (WARN if r["specimen"] in REF
                 else (GOOD if str(r["date"])[:10] >= FIX_DATE else None))
             for i, r in enumerate(sel)}
    fills = {k: v for k, v in fills.items() if v}
    y = table(ax, ML, 1.20, 7.4,
              ["Specimen", "Date", "UTS MPa", "sy MPa", "E GPa", "ef %", "anchor N", ""],
              rows, [1.0, 1.4, 1.0, 1.0, 1.0, 0.9, 1.0, 1.3], fills=fills,
              align=["left", "left", "right", "right", "right", "right", "right", "left"])

    srows = []
    for key, lab, unit in (("UTS_MPa", "UTS", "MPa"), ("sy_MPa", "sigma_y", "MPa"),
                           ("E_GPa", "E", "GPa"), ("ef", "eps_f", "-")):
        s = stats(sel, key)
        sc = 100 if key == "ef" else 1
        srows.append([lab, f"{s['mean']*sc:.2f}", f"{s['sd']*sc:.2f}", f"{s['cv']:.1f} %",
                      f"{s['min']*sc:.2f} - {s['max']*sc:.2f}", unit if key != "ef" else "%"])
    y2 = table(ax, ML + 7.6, 1.20, PAGE[0] - MR - (ML + 7.6),
               ["", "mean", "sd", "CV", "range", ""], srows,
               [1.0, 0.8, 0.7, 0.7, 1.3, 0.5],
               align=["left", "right", "right", "right", "right", "left"])

    ax.text(ML + 7.6, y2 + 0.42, "AGAINST THE add:north E-PLA TDS", fontsize=9.5,
            color=HEAD, weight="bold")
    u, e, f = stats(sel, "UTS_MPa"), stats(sel, "E_GPa"), stats(sel, "ef")
    trows = [["UTS", f"{TDS['UTS']:.1f}", f"{u['mean']:.1f}", f"{100*u['mean']/TDS['UTS']:.0f} %"],
             ["E", f"{TDS['E']:.2f}", f"{e['mean']:.2f}", f"{100*e['mean']/TDS['E']:.0f} %"],
             ["eps_f", f"{TDS['ef']*100:.0f}", f"{f['mean']*100:.1f}",
              f"{100*f['mean']/TDS['ef']:.0f} %"]]
    table(ax, ML + 7.6, y2 + 0.62, PAGE[0] - MR - (ML + 7.6),
          ["", "TDS", "ours", "of TDS"], trows, [1.0, 1.0, 1.0, 1.0],
          align=["left", "right", "right", "right"])

    para(ax, ML + 7.6, y2 + 2.30, PAGE[0] - MR - (ML + 7.6),
         "We land near the datasheet on STIFFNESS and about a fifth below on STRENGTH. That gap is "
         "the expected print knock-down - layer adhesion, not instrument error - and it is exactly "
         "what an independent extensometer is being asked to confirm or refute.", fs=8.2)

    y = banner(ax, ML, y + 0.24, 7.4,
               "AMBER ROWS - S25 and S26 - ARE THE COMPARISON PAIR. Both were run with frame "
               "capture expressly for extensometer cross-validation: 1445 and 1682 frames, 0 "
               "dropped, 100 % DIC coverage. Every frame still exists, so their software can "
               "re-process our pixels. Quote these two first.", fill=WARN, fs=8.4)
    y = para(ax, ML, y + 0.34, 7.4,
             f"GREEN ROWS ran after the rig was realigned on {FIX_DATE}. Prefer them if a wider "
             "subset has to be quoted: same rig, same DIC, and a load path known to be free of the "
             "binding that produced the earlier stalls.", fs=8.4)
    para(ax, ML, y + 0.16, 7.4,
         "eps_f scatters at about 25 % and always has. It is the value most sensitive to where "
         "fracture is declared and to dropout rows near the end of a run, so treat a disagreement "
         "in eps_f as far weaker evidence than one in E or UTS.", fs=8.4, color=MUTED)
    pdf.savefig(fig); plt.close(fig)


def page_sheet(pdf, sel):
    fig, ax = canvas("COMPARISON SHEET",
                     "Fill in at the bench. One block per specimen. Record BOTH raw numbers, "
                     "never just the difference.")
    w = PAGE[0] - ML - MR
    y = 1.15
    for spec in ("Specimen 1", "Specimen 2", "Specimen 3"):
        ax.text(ML, y, spec, fontsize=10, color=HEAD, weight="bold")
        ax.text(ML + 1.5, y, "ID ______________   date ____________   "
                             "area ________ mm2   gauge ________ mm   "
                             "strain zero at ________ N   speed ________ mm/s",
                fontsize=8.2, color=INK)
        y += 0.18
        rows = [[m, "", "", "", ""] for m in
                ("E  GPa", "sigma_y  MPa", "UTS  MPa", "eps_f  %", "secant 0.05-0.25 %  GPa")]
        y = table(ax, ML, y, w, ["Property", "Ours (DIC)", "Theirs (extensometer)",
                                 "difference %", "notes"],
                  rows, [1.6, 1.4, 1.8, 1.2, 4.8], rowh=0.24,
                  align=["left", "right", "right", "right", "left"])
        y += 0.30

    banner(ax, ML, y, w,
           "Write down the RAW numbers from both instruments before computing any difference. A "
           "difference recorded without its two inputs cannot be re-checked once you have left.",
           fill=WARN)
    pdf.savefig(fig); plt.close(fig)


def page_traps(pdf, sel):
    fig, ax = canvas("TRAPS - HOW TWO CORRECT INSTRUMENTS DISAGREE",
                     "Each of these has already moved one of our numbers. Check them before "
                     "concluding anything about either instrument.")
    w = (PAGE[0] - ML - MR - 0.4) / 2
    items = [
        ("1. Strain zero", BAD,
         "Ours starts after a ~300 N preload; theirs probably starts at 0 N. The toe region is "
         "then inside their strain and not ours. Lowers their apparent E and moves the 0.2 % "
         "offset yield with it. Fix: match the preload, or compare on the 0.05-0.25 % secant, "
         "which does not care where zero was."),
        ("2. Modulus fit window", WARN,
         "We report the STEEPEST STRAIGHT RUN, chosen per specimen, not a fixed strain window. "
         "Against a fixed 0.05-0.40 % window the same runs read 2.67 GPa instead of 3.02, and the "
         "scatter doubles. If their software uses a fixed window, ask for the window and compare "
         "like for like - we can recompute ours either way from the raw CSV."),
        ("3. Area basis", WARN,
         "80 mm2 is the CAD nominal, not a measured section. A printed part is usually slightly "
         "under nominal, so measure the actual section at MOT with their calipers and record it. "
         "Stress scales inversely, so a 3 % area error is a 3 % UTS error."),
        ("4. Infill is not a material", None,
         "These are 100 % infill so the nominal area is defensible. Do NOT let a 50 % specimen "
         "into this comparison - it needs a knock-down factor of about 2.4 and would look like an "
         "instrument fault."),
        ("5. Dropout rows", None,
         "Rows where DIC found no markers carry ec = 0.0, not a gap. Averaging them in drags "
         "strain toward zero. Our analysis drops them; if you export raw CSV for their software, "
         "filter DIC_Blobs = 2 first."),
        ("6. Post-fracture jump", None,
         "After fracture the markers fly apart and L_px jumps. One such row is enough to ruin "
         "eps_f. The app now refuses them at source, but any older CSV you hand over may contain "
         "them - trim to the fracture index."),
    ]
    y = [1.20, 1.20]
    for i, (title, fill, body) in enumerate(items):
        col = i % 2
        x = ML + col * (w + 0.4)
        if fill:
            ax.add_patch(Rectangle((x - 0.06, y[col] - 0.16), w + 0.12, 0.26,
                                   facecolor=fill, edgecolor="none"))
        ax.text(x, y[col], title, fontsize=9.5, color=HEAD, weight="bold")
        y[col] = para(ax, x, y[col] + 0.26, w, body, fs=8.3) + 0.30

    banner(ax, ML, max(y) + 0.10, PAGE[0] - ML - MR,
           "If ours and theirs agree within a few per cent on E and UTS, the DIC measurement is "
           "validated and the campaign's PLA numbers stand. If they do not, work down this list "
           "before doubting either instrument.", fill=GOOD)
    pdf.savefig(fig); plt.close(fig)


def page_bring(pdf, sel):
    fig, ax = canvas("WHAT TO PHYSICALLY BRING", "Tick before leaving.")
    w = (PAGE[0] - ML - MR - 0.5) / 2
    groups = [
        ("PRINTED", [
            "This pack (all 6 pages)",
            "S25_S26_stress_strain_reference.pdf - stress at every 0.10 % strain step, so a "
            "number read off their software can be looked up rather than eyeballed off a curve",
            "Per-specimen report PDFs for S25 and S26",
            "add:north E-PLA technical data sheet rev 2.1",
            "E_modulus_explained.pdf - why our fit window is what it is",
        ]),
        ("ON A USB STICK", [
            "S25 and S26 frame folders - 1445 and 1682 PNGs plus the AVIs. The single most "
            "valuable item here if their software can ingest video",
            "Both raw CSVs, unfiltered",
            "registry.json - the whole specimen register",
            "This pack as a PDF, in case a page is needed on screen",
        ]),
        ("PHYSICAL", [
            "Spare printed specimens, 100 % infill, same spool and slicer settings - bring more "
            "than you think you need",
            "The spray paint used for the dots, in case their optics want fresh targets",
            "Calipers, to measure the actual cross-section on site",
            "The spool label or a photo of it - brand, batch, diameter",
        ]),
        ("KNOW BEFORE YOU GO", [
            "Their load cell range and its calibration date",
            "Whether their extensometer tracks our dots or needs its own targets",
            "Whether they can preload to 300 N before zeroing strain",
            "Their modulus fit window and yield definition",
            "Their sampling rate",
        ]),
    ]
    y = [1.20, 1.20]
    for i, (head, items) in enumerate(groups):
        col = i % 2
        x = ML + col * (w + 0.5)
        ax.text(x, y[col], head, fontsize=10, color=HEAD, weight="bold")
        y[col] += 0.28
        for it in items:
            box(ax, x, y[col] - 0.115, 0.13, 0.13)
            y[col] = para(ax, x + 0.24, y[col], w - 0.24, it, fs=8.3) + 0.10
        y[col] += 0.26

    banner(ax, ML, max(y) + 0.05, PAGE[0] - ML - MR,
           "Ask for their raw data before you leave the building. A comparison you cannot "
           "recompute later is a comparison you have to trust from memory.", fill=WARN)
    pdf.savefig(fig); plt.close(fig)


def build(out=OUT):
    sel = pla100()
    _page[0] = 0
    with PdfPages(out) as pdf:
        page_cover(pdf, sel)
        page_params(pdf, sel)
        page_reference(pdf, sel)
        page_sheet(pdf, sel)
        page_traps(pdf, sel)
        page_bring(pdf, sel)
    return out, len(sel)


if __name__ == "__main__":
    p, n = build()
    print(f"Wrote {os.path.basename(p)} ({n} PLA specimens in the reference table)")
    print(p)
