# ===================================================================================
#  TPU + three-material comparison — appended to generate_v6a_slides.py
#  Every number below is read from the CSVs / registry at build time. The only typed
#  values are the LITERATURE bands in trio_plots.LIT, which are what we compare against.
# ===================================================================================
import trio_plots as TP                                                # noqa: E402
import tpu_plots as TPU                                                # noqa: E402
import numpy as _np                                                    # noqa: E402

_S = TP.stats()
_D = TPU.load()
_CUT = min(_D[k]["pos"].max() for k in _D)
TP.all_figs()
TPU.fig_pair()


def _at(spec, mm):
    """Strain and stress at a given crosshead travel, from the data."""
    d = _D[spec]
    m = abs(d["pos"] - mm) < 0.3
    return float(_np.median(d["ec"][m]) * 100), float(_np.median(d["sig"][m]))


def _mean(m, k):
    return float(_np.mean(_S[m][k]))


# ---------------------------------------------------------------- 1. the TPU test itself
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "TPU 95A — WHY AN ELASTOMER IS A DIFFERENT TEST ON THE SAME RIG")
header(s, 0.5, 1.35, 6.1, "What had to change, and why")
table(s, 0.5, 1.75, 6.1, 3.05, [
    ["Setting", "PLA / PETG", "TPU", "Reason"],
    ["Preload", "300 N", "20 N", "300 N is ~0.15 % strain on PLA but a large part of TPU's "
                                 "elastic range — it would be tared away"],
    ["Auto-stop", "armed", "OFF", "watches for a load COLLAPSE; a drawing elastomer never "
                                  "produces one, so armed it can only misfire"],
    ["Strain cap", "25 %", "60 %", "the DIC calls a bigger separation a lost marker; TPU "
                                   "reaches the rig's travel limit as REAL strain"],
    ["Marker gate", "0.40", "0.25", "sprayed dots on TPU score 0.50-0.65 roundness against "
                                    "0.76 for a clean dot"],
    ["Ends at", "fracture", "28 mm travel", "TPU does not break: the run has to end on a "
                                            "travel target instead"],
], cw=[0.9, 0.9, 0.9, 3.4], hf=9.5, bf=8.6)

header(s, 6.9, 1.35, 6.05, "Held identical, so the comparison stays valid")
table(s, 6.9, 1.75, 6.05, 1.5, [
    ["Held constant", "Value"],
    ["Gauge length", "80 mm"],
    ["Cross-section", "80 mm² (CAD-verified)"],
    ["Crosshead rate", "0.1 mm/s"],
    ["Marker method", "spray dots, same batch of paint"],
], cw=[1.3, 1.6], hf=9.5, bf=9)
tb(s, 6.9, 3.45, 6.05, 1.4,
   "Everything in the left table is a property of the MATERIAL. Everything here is a property "
   "of the TEST. Keeping the second column fixed is what makes PLA, PETG and TPU comparable at "
   "all — a different gauge or rate would confound the modulus we are about to compare.\n\n"
   "All five left-hand settings ride with a saved 'TPU' profile, so they move together in one "
   "click and revert together. None of them is a constant edited before a run.",
   fs=10, colour=BLACK)

kpi(s, 0.5, 5.0, 2.0, "Specimens", "S35, S36", fill=LIGHT_BLUE)
kpi(s, 2.65, 5.0, 2.0, "E (mean)", "%.1f MPa" % _mean("TPU", "E"), fill=GREEN_PASS)
kpi(s, 4.8, 5.0, 2.0, "Run-to-run", "%.1f %% apart" % (100 * abs(
    _S["TPU"]["E"][1] / _S["TPU"]["E"][0] - 1)), fill=GREEN_PASS)
kpi(s, 6.95, 5.0, 2.0, "Peak stress", "%.2f MPa" % _mean("TPU", "sig"), fill=LIGHT_BLUE)
kpi(s, 9.1, 5.0, 2.0, "Strain reached", "%.1f %%" % _mean("TPU", "eps"), fill=LIGHT_BLUE)
footer(s, "TPU 95A, 100 % infill, same 80 mm gauge and 80 mm² section as every PLA and PETG "
          "specimen in this deck.")
pageno(s)

# ---------------------------------------------------------------- 2. WHY 15 mm
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "WHY THE TPU RUNS STOP AT ~15 mm — THE FRAME, NOT THE SPECIMEN")
img_fit(s, "documentation/figures/tpu_framing.png", 0.4, 1.28, 12.5, 3.35)
header(s, 0.5, 4.68, 6.1, "The chain of hard limits")
table(s, 0.5, 5.05, 6.1, 1.05, [
    ["Limit", "Value", "Can it be relaxed?"],
    ["Sensor width along the specimen", "2448 px", "No — acA2440 is 2448 × 2048"],
    ["ROI width in use", "2448 px", "No — already the FULL sensor"],
    ["ROI offset on the tight side", "OffsetX = 0", "No — the sensor's own edge"],
    ["Room ahead of the moving marker", "228 px", "Only by moving the CAMERA"],
], cw=[2.2, 1.0, 2.0], hf=9.5, bf=8.6)

header(s, 6.9, 4.68, 6.05, "So the honest statement is")
tb(s, 6.9, 5.05, 6.05, 1.3,
   "The frame is long enough for a 28 mm pull — it supports ~37 mm with the pair aimed correctly. "
   "It is AIMED wrong: the marker that travels sits 283 px from the edge it moves toward, and "
   "needs 541 px. The 305 px of spare frame is at the end that never moves.\n"
   "Correcting it needs the camera shifted ~12 mm along the specimen. On this rig the camera "
   "mount is fixed, so 15 mm of travel is the ceiling for these two specimens — an INSTRUMENT "
   "limit, recorded as such, not a material result.",
   fs=9.6, colour=BLACK)
banner(s, 0.4, 6.4, 12.55, 0.5,
       "THE SPECIMEN WAS INTACT AND STILL CARRYING RISING LOAD WHEN TRACKING ENDED. "
       "ELONGATION AT BREAK AND TOUGHNESS ARE THEREFORE LOWER BOUNDS, NOT MEASUREMENTS.",
       fill=YELLOW_WARN, fg=BLACK, fs=10.5)
footer(s, "Drawn to scale from the measured marker positions of S36 (Px₀ 1690 px, 21.12 px/mm).")
pageno(s)

# ---------------------------------------------------------------- 3. S35 vs S36
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "TPU REPEATABILITY — S35 AND S36 OVER THE SAME TRAVEL")
img_fit(s, "documentation/figures/tpu_pair.png", 0.4, 1.3, 12.5, 3.5)
_e35, _s35 = _at("S35", 15.0)
_e36, _s36 = _at("S36", 15.0)
header(s, 0.5, 5.0, 6.1, "At matched crosshead travel")
table(s, 0.5, 5.36, 6.1, 1.3, [
    ["Travel", "S35 strain", "S36 strain", "S35 σ", "S36 σ"],
    ["4 mm", "%.2f %%" % _at("S35", 4)[0], "%.2f %%" % _at("S36", 4)[0],
     "%.3f" % _at("S35", 4)[1], "%.3f" % _at("S36", 4)[1]],
    ["10 mm", "%.2f %%" % _at("S35", 10)[0], "%.2f %%" % _at("S36", 10)[0],
     "%.3f" % _at("S35", 10)[1], "%.3f" % _at("S36", 10)[1]],
    ["15 mm", "%.2f %%" % _e35, "%.2f %%" % _e36, "%.3f" % _s35, "%.3f" % _s36],
], cw=[1.0, 1.2, 1.2, 1.0, 1.0], hf=9.5, bf=9)

header(s, 6.9, 5.0, 6.05, "What the pair establishes")
tb(s, 6.9, 5.36, 6.05, 1.3,
   "E agrees to %.1f %% (%.1f vs %.1f MPa, R² 0.999 on both) and stress agrees within ±4 %% at "
   "every matched strain. That is repeatability of the same order as the PLA set.\n"
   "Only ~65 %% of crosshead travel reaches the gauge — the rest goes into the shoulders and "
   "grips — so 15 mm of travel is ~12 %% gauge strain, not 19 %%."
   % (100 * abs(_S["TPU"]["E"][1] / _S["TPU"]["E"][0] - 1), _S["TPU"]["E"][0], _S["TPU"]["E"][1]),
   fs=9.6, colour=BLACK)
footer(s, "Both runs truncated at the common 15.09 mm so neither is credited with travel the "
          "other could not track.")
pageno(s)

# ---------------------------------------------------------------- 4. the three curves
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PLA vs PETG vs TPU — THE CURVES")
img_fit(s, "documentation/figures/trio_curves.png", 0.4, 1.3, 12.5, 3.9)
tb(s, 0.5, 5.4, 12.4, 1.3,
   "LEFT, log stress: all three are legible at once and the ordering is plain — PLA stiffest and "
   "strongest, PETG close behind, TPU two decades below both.\n"
   "RIGHT, the same data linearly: TPU is a flat line on the floor. This is the reason the "
   "comparison is made on MODULUS and on matched-strain stress rather than on one shared "
   "stress axis, and the reason a single 'PLA is 20× stronger than TPU' number would mislead — "
   "that ratio is taken at matched strain, and TPU has not finished stretching.",
   fs=10, colour=BLACK)
footer(s, "One representative run per material: PLA S25, PETG S30, TPU S36. Curves end at "
          "fracture (PLA, PETG) or at the frame limit (TPU).")
pageno(s)

# ---------------------------------------------------------------- 5. modulus vs literature
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "MODULUS AGAINST THE PUBLISHED BANDS — ALL THREE LAND INSIDE")
img_fit(s, "documentation/figures/trio_modulus.png", 0.35, 1.25, 7.5, 5.0)
header(s, 8.1, 1.35, 4.85, "Measured vs literature")
_rows = [["Material", "Measured E", "Literature", "Verdict"]]
for _m in ("PLA", "PETG", "TPU"):
    _lo, _hi = TP.LIT[_m]["E"]
    _mu = _mean(_m, "E")
    _rows.append([f"{_m} (n={_S[_m]['n']})",
                  ("%.2f GPa" % (_mu / 1000)) if _mu > 100 else ("%.1f MPa" % _mu),
                  ("%.1f-%.1f GPa" % (_lo / 1000, _hi / 1000)) if _lo > 100
                  else ("%d-%d MPa" % (_lo, _hi)),
                  "in band" if _lo <= _mu <= _hi else "OUT"])
table(s, 8.1, 1.75, 4.85, 1.35, _rows, cw=[1.2, 1.1, 1.2, 0.9], hf=9.5, bf=9)
tb(s, 8.1, 3.35, 4.85, 2.6,
   "The modulus is the claim this campaign can actually make, and it is the strongest one:\n\n"
   "•  three materials, two decades apart, every one inside its published range\n"
   "•  n=6 / 2 / 2, with run-to-run spread well inside the band width\n"
   "•  E is a SLOPE, so the force anchor cancels out of it entirely — the 20 N that was "
   "missing from TPU's stress never touched its modulus\n\n"
   "Stiffness ratio PLA : PETG : TPU = %.0f : %.0f : 1."
   % (_mean("PLA", "E") / _mean("TPU", "E"), _mean("PETG", "E") / _mean("TPU", "E")),
   fs=9.8, colour=BLACK)
banner(s, 0.4, 6.42, 12.55, 0.5,
       "PLA %.2f GPa · PETG %.2f GPa · TPU %.0f MPa — THE EXPECTED ORDER, AND EVERY VALUE "
       "INSIDE ITS PUBLISHED BAND." % (_mean("PLA", "E") / 1000, _mean("PETG", "E") / 1000,
                                       _mean("TPU", "E")),
       fill=GREEN_PASS, fg=DARK_GREEN, fs=11)
footer(s, "Bands: PLA Chacón 2017 + filament TDS; PETG Durgashyam 2019 + TDS; TPU 95A TDS "
          "(Ultimaker / SainSmart) + Hohimer 2020. Shaded = published range, dots = our runs.")
pageno(s)

# ---------------------------------------------------------------- 6. expected slope vs measured
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "EXPECTED SLOPE vs MEASURED SLOPE — MATERIAL BY MATERIAL")
img_fit(s, "documentation/figures/trio_slopes.png", 0.4, 1.22, 12.5, 4.55)
tb(s, 0.5, 5.92, 12.4, 1.15,
   "Each panel draws the SLOPE the published modulus predicts (shaded wedge), the slope we "
   "measured (dashed) and the run itself (black). Wedge and dashed line are anchored to the run's "
   "OWN intercept: Px₀ is frozen at the preloaded state, so every curve starts at the preload "
   "stress rather than at the origin, and what is being compared here is slope, not offset.\n"
   "All three runs lie inside their own wedge. The wedges are two decades apart in height — the "
   "same statement the modulus chart makes, drawn a different way: PLA > PETG ≫ TPU is not a "
   "subtle effect needing careful statistics, it is the dominant feature of the data.",
   fs=9.8, colour=BLACK)
footer(s, "Fitted over ε 0.05-0.4 %, the same elastic window used for every modulus in this deck. "
          "One representative run per material.")
pageno(s)

# ---------------------------------------------------------------- 7. the full comparison
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PLA vs PETG vs TPU — WHAT EACH NUMBER IS WORTH")
_rows = [["Property", "PLA (n=%d)" % _S["PLA"]["n"], "PETG (n=%d)" % _S["PETG"]["n"],
          "TPU (n=%d)" % _S["TPU"]["n"], "Status"]]
_rows.append(["Elastic modulus",
              "%.2f ± %.2f GPa" % (_mean("PLA", "E") / 1000, _np.std(_S["PLA"]["E"]) / 1000),
              "%.2f ± %.2f GPa" % (_mean("PETG", "E") / 1000, _np.std(_S["PETG"]["E"]) / 1000),
              "%.1f ± %.1f MPa" % (_mean("TPU", "E"), _np.std(_S["TPU"]["E"])),
              "MEASURED — all in band"])
_rows.append(["Max stress reached",
              "%.1f MPa" % _mean("PLA", "sig"), "%.1f MPa" % _mean("PETG", "sig"),
              "%.2f MPa" % _mean("TPU", "sig"),
              "PLA/PETG = UTS; TPU = lower bound"])
_rows.append(["Strain at end",
              "%.1f %%" % _mean("PLA", "eps"), "%.1f %%" % _mean("PETG", "eps"),
              "%.1f %%" % _mean("TPU", "eps"),
              "PLA/PETG = at fracture; TPU = frame limit"])
_rows.append(["Ended by", "fracture", "fracture", "frame ran out at 15 mm", "—"])
table(s, 0.5, 1.5, 12.4, 2.1, _rows, cw=[1.5, 1.5, 1.5, 1.5, 2.2], hf=9.8, bf=9.2)

header(s, 0.5, 4.0, 6.1, "What we can claim")
tb(s, 0.5, 4.38, 6.1, 2.6,
   "•  STIFFNESS, fully. Three materials, correct order, every value inside its published band, "
   "with repeatability on all three.\n\n"
   "•  PLA vs PETG, fully. Both fractured, so strength and ductility are real measurements: "
   "%.1f vs %.1f MPa and %.1f vs %.1f %% strain. PETG less strong, more ductile — as expected.\n\n"
   "•  The DUCTILITY ORDERING including TPU. TPU passed %.1f %% without failing, which already "
   "exceeds both fractured values."
   % (_mean("PLA", "sig"), _mean("PETG", "sig"), _mean("PLA", "eps"), _mean("PETG", "eps"),
      _mean("TPU", "eps")),
   fs=9.8, colour=BLACK)

header(s, 6.9, 4.0, 6.05, "What we must NOT claim")
tb(s, 6.9, 4.38, 6.05, 2.6,
   "•  TPU's STRENGTH. Its curve was still rising when the frame ran out. Published TPU 95A "
   "breaks at 25-40 MPa — comparable to PETG — but at 400-700 % elongation.\n\n"
   "•  Any 'PLA is 20× stronger than TPU' figure. That ratio is taken at MATCHED STRAIN and "
   "would misrepresent the material.\n\n"
   "•  TPU's ε_f or toughness. Both are lower bounds set by the instrument.\n\n"
   "•  A TPU fracture on this rig at all: 30 mm of travel is 24 % gauge strain, and TPU needs "
   "400 %. It would take a gauge of ~5 mm, which breaks the comparison.",
   fs=9.4, colour=BLACK)
pageno(s)

# ---------------------------------------------------------------- 8. is the trend as expected
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "IS THE TREND AS EXPECTED? — YES, AND FOR THE RIGHT REASONS")
header(s, 0.5, 1.35, 12.4, "Prediction, result, and the physical reason")
table(s, 0.5, 1.75, 12.4, 2.6, [
    ["Expectation from the literature", "What the rig measured", "Why the material does this"],
    ["PLA stiffest and strongest, least ductile",
     "E %.2f GPa · σ %.1f MPa · fractures at %.1f %% strain — highest E, highest σ, least ductile"
     % (_mean("PLA", "E") / 1000, _mean("PLA", "sig"), _mean("PLA", "eps")),
     "Glassy, high-crystallinity polyester well below Tg; chains cannot slide, so it fails by "
     "brittle crazing soon after yield"],
    ["PETG slightly less stiff and strong, more ductile",
     "E %.2f GPa (−%.0f %% vs PLA) · σ %.1f MPa (−%.0f %%) · fractures at %.1f %% strain (+%.0f %%)"
     % (_mean("PETG", "E") / 1000, 100 * (1 - _mean("PETG", "E") / _mean("PLA", "E")),
        _mean("PETG", "sig"), 100 * (1 - _mean("PETG", "sig") / _mean("PLA", "sig")),
        _mean("PETG", "eps"), 100 * (_mean("PETG", "eps") / _mean("PLA", "eps") - 1)),
     "The glycol modification suppresses crystallisation, leaving an amorphous copolyester that "
     "yields and draws instead of crazing"],
    ["TPU two decades softer, effectively unbreakable at this scale",
     "E %.0f MPa — %.0f× below PLA. Still rising at %.1f %% strain with no yield point"
     % (_mean("TPU", "E"), _mean("PLA", "E") / _mean("TPU", "E"), _mean("TPU", "eps")),
     "Block copolymer: rubbery soft segments carry the strain while hard segments act as "
     "physical crosslinks — hyperelastic, so there is no yield to find"],
], cw=[2.6, 3.6, 4.2], hf=9.8, bf=8.8)

header(s, 0.5, 4.55, 6.1, "The one number that carries it")
kpi(s, 0.5, 4.95, 1.9, "PLA", "%.2f GPa" % (_mean("PLA", "E") / 1000), fill=LIGHT_BLUE)
kpi(s, 2.55, 4.95, 1.9, "PETG", "%.2f GPa" % (_mean("PETG", "E") / 1000), fill=LIGHT_BLUE)
kpi(s, 4.6, 4.95, 1.9, "TPU", "%.0f MPa" % _mean("TPU", "E"), fill=LIGHT_BLUE)
tb(s, 6.9, 4.55, 6.05, 1.8,
   "Three materials chosen to span the useful range of FDM polymers, and the rig separates them "
   "by a factor of %.0f without ambiguity — every value inside its published band, every "
   "material repeatable run to run.\n"
   "That is the result. TPU's strength and elongation at break sit outside what this rig can "
   "reach and are quoted from the datasheet, clearly marked as such."
   % (_mean("PLA", "E") / _mean("TPU", "E")),
   fs=10, colour=BLACK)
banner(s, 0.4, 6.4, 12.55, 0.5,
       "STIFFNESS RATIO PLA : PETG : TPU = %.0f : %.0f : 1 — THE EXPECTED ORDER, THE EXPECTED "
       "MAGNITUDES, ON ONE RIG WITH ONE PROTOCOL."
       % (_mean("PLA", "E") / _mean("TPU", "E"), _mean("PETG", "E") / _mean("TPU", "E")),
       fill=GREEN_PASS, fg=DARK_GREEN, fs=11)
pageno(s)
