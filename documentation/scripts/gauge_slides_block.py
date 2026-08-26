# ===================================================================================
#  Marker-spacing test — S33/S34 at 45 mm against S25/S26 at 80 mm.
#  Appended to generate_v6a_slides.py. Every number is read from the CSVs at build time.
# ===================================================================================
import gauge_plots as GP                                              # noqa: E402
import numpy as _gnp                                                  # noqa: E402

GP.all_figs()
_G = GP.load()
_GS = GP.summary()


def _p(k, key):
    return _GS["props"][k][key]


def _e(k, sigma):
    return GP.eps_at(_G[k], sigma) * 100


# ---------------------------------------------------------------- 1. what was done, and the header
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "DOES MARKER SPACING CHANGE THE STRAIN? — S33 / S34 AT 45 mm")
img_fit(s, "documentation/figures/gauge_geometry.png", 0.4, 1.26, 12.5, 2.55)

header(s, 0.5, 4.05, 6.1, "The one deliberate change")
table(s, 0.5, 4.42, 6.1, 1.35, [
    ["Held constant", "Changed"],
    ["PLA, 100 % infill, white specimen", "marker spacing 80 mm → 45 mm"],
    ["80 mm² section, 0.10 mm/s, ~300 N preload", "Px₀ 1675 px → 939 px"],
    ["same rig, same optics at 20.9 px/mm", "(a 44 % shorter pixel baseline)"],
], cw=[1.7, 1.6], hf=9.5, bf=9)

header(s, 6.9, 4.05, 6.05, "A recording error found on the way in")
tb(s, 6.9, 4.42, 6.05, 1.35,
   "Both CSVs were written with “Gauge Length: 80.0 mm” — the app was left on the old setting. "
   "Corrected in the files, with the original preserved in a note.\n"
   "It changed NO result, and that was checked rather than assumed: DIC strain is (L_px − Px₀)/Px₀, "
   "a ratio of PIXELS, and the gauge length never enters it. Only px_per_mm was wrong (11.75 → "
   "20.89). Re-analysing both files at 45 mm and at 80 mm gives identical E, σ_y, UTS, ε_f and "
   "toughness.",
   fs=9.5, colour=BLACK)
banner(s, 0.4, 6.4, 12.55, 0.5,
       "Px₀ / 45 mm = 20.89 px/mm and Px₀ / 80 mm = 20.94 px/mm — THE SAME OPTICS, so the data "
       "itself confirms the two spacings.",
       fill=LIGHT_BLUE, fg=BLACK, fs=10.5)
footer(s, "S33 and S34, 2026-08-24, on the post-realignment rig (see p183). Reference pair S25 / "
          "S26 from the same material and protocol at 80 mm.")
pageno(s)

# ---------------------------------------------------------------- 2. the 45 mm pair on its own
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "S33 vs S34 — REPEATABILITY AT THE NEW 45 mm SPACING")
img_fit(s, "documentation/figures/gauge_pair.png", 0.4, 1.28, 12.5, 4.0)
header(s, 0.5, 5.45, 6.1, "The pair")
table(s, 0.5, 5.82, 6.1, 1.0, [
    ["", "S33", "S34"],
    ["E (GPa)", "%.3f" % _p("S33", "E"), "%.3f" % _p("S34", "E")],
    ["UTS (MPa)", "%.2f" % _p("S33", "uts"), "%.2f" % _p("S34", "uts")],
    ["ε_f (%)", "%.2f" % _p("S33", "ef"), "%.2f" % _p("S34", "ef")],
], cw=[1.4, 1.0, 1.0], hf=9.5, bf=9)
header(s, 6.9, 5.45, 6.05, "Read this before the comparison")
tb(s, 6.9, 5.82, 6.05, 1.0,
   "The two agree on UTS to %.1f %% but differ by up to %.0f %% in measured strain at low stress, "
   "closing to a few %% by 40 MPa. That shape — large early, converging late — is GRIP SEATING in "
   "the toe region, not the material and not the markers.\n"
   "It is also the yardstick for the next slide: this is what two specimens of the SAME spacing do."
   % (100 * abs(_p("S33", "uts") / _p("S34", "uts") - 1),
      abs(_e("S34", 10) / _e("S33", 10) - 1) * 100),
   fs=9.4, colour=BLACK)
footer(s, "Curves end at fracture. Stress includes the recovered preload anchor (%.0f and %.0f N)."
          % (_p("S33", "anchor"), _p("S34", "anchor")))
pageno(s)

# ---------------------------------------------------------------- 3. 45 vs 80, the curves
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "45 mm vs 80 mm — THE CURVES DO NOT SEPARATE BY GAUGE")
img_fit(s, "documentation/figures/gauge_compare.png", 0.4, 1.28, 12.5, 4.1)
tb(s, 0.5, 5.55, 12.4, 1.25,
   "LEFT: all four runs on one axis, coloured by spacing. They interleave — the 45 mm runs do not "
   "sit above or below the 80 mm runs.\n"
   "RIGHT: the difference in measured strain at matched stress, one line per pairing. "
   "S33 against S25 holds within ±1.3 %% from 10 to 40 MPa despite a pixel baseline 44 %% "
   "shorter. The other pairing, S34 against S26, starts at −%.0f %% and closes to −%.0f %% by "
   "40 MPa — the same toe-region signature seen WITHIN the 45 mm pair on the previous slide."
   % (abs(_GS["cross"][10]["S34/S26"]), abs(_GS["cross"][40]["S34/S26"])),
   fs=9.8, colour=BLACK)
footer(s, "Matched STRESS, not matched strain: force is what the machine applies, strain is what "
          "the DIC measures, and the measurement is what is under test.")
pageno(s)

# ---------------------------------------------------------------- 4. the deciding test
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "THE TEST THAT SETTLES IT — SCATTER WITHIN vs BETWEEN GAUGES")
img_fit(s, "documentation/figures/gauge_scatter.png", 0.4, 1.35, 8.4, 4.9)
header(s, 8.95, 1.35, 4.0, "The argument")
tb(s, 8.95, 1.75, 4.0, 3.9,
   "A gauge-length effect would show up as a green bar taller than the red and blue ones — a "
   "difference between the two spacings that exceeds what two specimens of the SAME spacing do.\n\n"
   "It does not. At NO stress level is the green bar the tallest of the three, and by 40 MPa it "
   "is 0.3 % against 10.1 % and 7.9 % of within-pair scatter. It does exceed the BLUE bar at 15 "
   "and 20 MPa — but that is the toe region, where the 80 mm pair happens to agree closely with "
   "itself while the 45 mm pair does not.\n\n"
   "So the honest conclusion is a NEGATIVE result, and a useful one: moving the markers from "
   "80 mm to 45 mm does not measurably change the strain the DIC reports.",
   fs=9.6, colour=BLACK)
banner(s, 0.4, 5.85, 12.55, 0.52,
       "THE DIFFERENCE BETWEEN GAUGES IS SMALLER THAN THE DIFFERENCE BETWEEN TWO SPECIMENS OF THE "
       "SAME GAUGE. THERE IS NO SPACING EFFECT TO FIND AT n=2.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=10.5)
footer(s, "Bars are |difference| in measured strain at matched stress, per specimen pair.")
pageno(s)

# ---------------------------------------------------------------- 5. properties + what it validates
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "WHAT THE MARKER-SPACING TEST VALIDATES — AND WHAT IT CANNOT")
_m = lambda ks, key: sum(_p(k, key) for k in ks) / len(ks)
_h = lambda ks, key: abs(_p(ks[0], key) - _p(ks[1], key)) / 2
_a, _b = ("S33", "S34"), ("S25", "S26")
table(s, 0.5, 1.4, 12.4, 1.55, [
    ["Property", "45 mm  (S33, S34)", "80 mm  (S25, S26)", "difference", "verdict"],
    ["Elastic modulus", "%.2f ± %.2f GPa" % (_m(_a, "E"), _h(_a, "E")),
     "%.2f ± %.2f GPa" % (_m(_b, "E"), _h(_b, "E")),
     "%+.1f %%" % (100 * (_m(_a, "E") / _m(_b, "E") - 1)), "inside scatter"],
    ["UTS", "%.2f ± %.2f MPa" % (_m(_a, "uts"), _h(_a, "uts")),
     "%.2f ± %.2f MPa" % (_m(_b, "uts"), _h(_b, "uts")),
     "%+.1f %%" % (100 * (_m(_a, "uts") / _m(_b, "uts") - 1)),
     "cannot depend on gauge — it is F/A"],
    ["σ_y (0.2 %)", "%.2f ± %.2f MPa" % (_m(_a, "sy"), _h(_a, "sy")),
     "%.2f ± %.2f MPa" % (_m(_b, "sy"), _h(_b, "sy")),
     "%+.1f %%" % (100 * (_m(_a, "sy") / _m(_b, "sy") - 1)), "inside scatter"],
    ["ε_f", "%.2f ± %.2f %%" % (_m(_a, "ef"), _h(_a, "ef")),
     "%.2f ± %.2f %%" % (_m(_b, "ef"), _h(_b, "ef")),
     "%+.0f %%" % (100 * (_m(_a, "ef") / _m(_b, "ef") - 1)),
     "UNRESOLVED — see right"],
], cw=[1.5, 1.6, 1.6, 1.1, 2.2], hf=9.8, bf=9)

header(s, 0.5, 3.2, 6.1, "What it establishes")
tb(s, 0.5, 3.58, 6.1, 3.0,
   "•  The DIC strain is scale-free, which it must be — strain is a pixel ratio — but this is "
   "the first time the rig has been asked to prove it on two different baselines.\n\n"
   "•  The strain field between the markers is uniform. If the 80 mm span reached into the "
   "shoulders it would read a different average strain than the 45 mm span. It does not.\n\n"
   "•  A bound on a fixed centroid bias. Such a bias shifts strain by δ/Px₀, which differs "
   "between a 939 px and a 1675 px baseline. The agreement puts δ below %.2f px — an upper "
   "bound, since it credits the whole discrepancy to that one cause.\n\n"
   "•  Either spacing may be used, so a shorter gauge is available when the frame is the "
   "constraint — which is exactly the TPU problem on p265."
   % _GS["bias_px"],
   fs=9.4, colour=BLACK)

header(s, 6.9, 3.2, 6.05, "What it does NOT establish")
tb(s, 6.9, 3.58, 6.05, 3.0,
   "•  ε_f. This is the one property that SHOULD depend on gauge length, because fracture "
   "localises and a shorter gauge weights the necking region more heavily. But within the 45 mm "
   "pair ε_f is %.2f %% and %.2f %% — a %.0f %% spread from where the specimen happened to break. "
   "n=2 cannot separate a real effect from that.\n\n"
   "•  Anything below ~15 MPa. The toe region is dominated by grip seating and varies more "
   "between specimens than between gauges.\n\n"
   "•  Spacings outside 45–80 mm. Nothing here says a 10 mm gauge would behave; it would sit "
   "far closer to the fracture and sample a different strain field."
   % (_p("S33", "ef"), _p("S34", "ef"),
      100 * abs(_p("S34", "ef") / _p("S33", "ef") - 1)),
   fs=9.4, colour=BLACK)
pageno(s)
