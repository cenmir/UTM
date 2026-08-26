# ===================================================================================
#  S37 — the 45 mm marker-gauge TPU run, 2026-08-26.
#
#  S35 and S36 both lost the travelling marker at ~15 mm of crosshead travel, which capped
#  them near 12 % strain. Shortening the marker pair to 45 mm needs less frame per mm of
#  travel, and that is the whole point of this run.
#
#  Every number is read from the CSV at build time through tpu_s37_compare, so a re-run
#  after new data cannot silently disagree with the slides.
# ===================================================================================
import tpu_s37_compare as S37                                          # noqa: E402

S37.fig()
S37.fig_trio()
_F = S37.facts()
_S37 = S37.load()

# ---------------------------------------------------------------- A. S37 test setup
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "S37 · TPU WITH A 45 mm MARKER GAUGE — THE TEST SETUP")
tb(s, 0.4, 1.13, 12.55, 0.46,
   "One change, made for one reason: S35 and S36 both lost the travelling marker at ~15 mm of "
   "crosshead travel. A shorter marker pair needs less frame per mm of travel.",
   fs=11.5, italic=True, colour=GREY_TEXT)

header(s, 0.45, 1.68, 6.15, "What changed from S35 / S36 — and why")
table(s, 0.45, 2.06, 6.15, 2.5, [
    ["Setting", "S35 · S36", "S37", "Reason"],
    ["Marker gauge", "80 mm", "45 mm", "the binding constraint — a shorter pair travels fewer "
     "pixels per mm, so it stays in frame further"],
    ["Specimen mode", "White", "Black", "this specimen is BRIGHT dots on dark speckle: "
     "THRESH_BINARY, the opposite polarity to the earlier TPU"],
    ["Roundness gate", "0.25", "0.16", "these sprayed dots score 0.18–0.24 where the earlier TPU "
     "dots scored 0.50–0.65. A one-off, not a new default"],
    ["Cross-section", "80 mm²", "80 mm²", "unchanged — only the marker SPACING differs, so the "
     "stress axis stays directly comparable"],
], cw=[1.15, 0.95, 0.8, 3.25], hf=9.5, bf=8.5)

header(s, 6.85, 1.68, 6.1, "Held identical, so the comparison stays valid")
table(s, 6.85, 2.06, 6.1, 1.45, [
    ["Held constant", "Value"],
    ["Crosshead rate", "0.1 mm/s"],
    ["Preload", "20 N  (Px₀ frozen at 19 N)"],
    ["Auto-stop at fracture", "OFF — TPU does not break"],
    ["Strain cap", "60 %"],
], cw=[2.4, 3.6], hf=9.5, bf=9)
tb(s, 6.85, 3.62, 6.1, 1.7,
   "Why the gauge can change without invalidating anything: DIC strain is a PIXEL ratio, "
   "(L_px − Px₀)/Px₀. The gauge length does not appear in it at all — only px_per_mm depends on "
   "the gauge, and that scales millimetres, not strain.\n\n"
   "So if the initial slope moves when the gauge moves, something other than the material is "
   "being measured. That is exactly what the next slide tests.",
   fs=9.6, colour=BLACK)

kpi(s, 0.45, 5.45, 2.0, "Gauge", "%.0f mm" % _F["gauge"], fill=LIGHT_BLUE)
kpi(s, 2.6, 5.45, 2.0, "px per mm", "20.47", fill=LIGHT_BLUE)
kpi(s, 4.75, 5.45, 2.0, "Roundness gate", "0.16", fill=YELLOW_WARN)
kpi(s, 6.9, 5.45, 2.0, "Samples", "%d" % _F["n"], fill=LIGHT_BLUE)
kpi(s, 9.05, 5.45, 2.0, "Duration", "%.0f s" % _F["dur"], fill=LIGHT_BLUE)
banner(s, 0.4, 6.45, 12.55, 0.48,
       "THE 0.16 ROUNDNESS GATE IS A ONE-OFF FOR THIS SPECIMEN, RECORDED IN THE CSV HEADER. THE "
       "STANDING DEFAULT IS 0.40 — THE PROPER FIX IS BETTER MARKER PREPARATION, NOT A LOOSER GATE.",
       fill=YELLOW_WARN, fg=BLACK, fs=10)
footer(s, "Specimen S37, TPU 95A, 100 %% infill, 80 mm² section. %s" % _F["csv"])
pageno(s)

# ---------------------------------------------------------------- B. S37 results
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "S37 · WHAT THE 45 mm GAUGE BOUGHT — THE RESULT")
tb(s, 0.4, 1.13, 12.55, 0.46,
   # No % operator on this string, so a doubled %% would render literally.
   "The run tracked 95 % of its samples and reached 18.9 % strain, against 21–33 % coverage "
   "and ~12 % strain on the two 80 mm runs.",
   fs=11.5, italic=True, colour=GREY_TEXT)

kpi(s, 0.45, 1.66, 2.4, "DIC coverage", "%.0f %%" % _F["cov"], fill=GREEN_PASS)
kpi(s, 3.0, 1.66, 2.4, "Max DIC strain", "%.1f %%" % _F["eps_max"], fill=GREEN_PASS)
kpi(s, 5.55, 1.66, 2.4, "Elastic modulus", "%.1f MPa" % _F["E_own"], fill=GREEN_PASS)
kpi(s, 8.1, 1.66, 2.4, "Peak stress", "%.2f MPa" % _F["sig_max"], fill=LIGHT_BLUE)
kpi(s, 10.65, 1.66, 2.3, "Travel", "%.1f mm" % _F["travel"], fill=LIGHT_BLUE)

header(s, 0.45, 2.75, 6.15, "The record itself")
table(s, 0.45, 3.13, 6.15, 1.8, [
    ["Quantity", "S37 (45 mm)", "S36 (80 mm)"],
    ["DIC coverage", "%.0f %% of samples" % _F["cov"], "21 %"],
    ["Frames tracked 2/2", "90 %  (3154 / 3499)", "—"],
    ["Max DIC strain", "%.2f %%" % _F["eps_max"], "11.68 %"],
    ["Crosshead travel", "%.1f mm" % _F["travel"], "15.1 mm"],
    ["Gauge share of travel", "%.0f %%" % _F["share"], "62 %"],
], cw=[2.0, 2.0, 2.15], hf=9.5, bf=8.8)

header(s, 6.85, 2.75, 6.1, "Two things to read carefully")
tb(s, 6.85, 3.13, 6.1, 2.6,
   "GAUGE SHARE FELL TO %.0f %%, from ~62 %% on the 80 mm runs. Expected, not a fault: the marked "
   "span is a smaller fraction of the specimen, so it receives a smaller share of the crosshead. "
   "45/80 of 62 %% is 35 %% — the measured %.0f %% sits right there.\n\n"
   "THE HEADER'S “Max Strain: 0.5788” IS NOT DIC STRAIN. It is Motor_Strain — travel divided by "
   "gauge, %.1f mm / %.0f mm = %.1f %%. The DIC strain maxes at %.2f %%. On the 80 mm specimens "
   "the two sat closer together and this never stood out; at 45 mm the header reads three times "
   "the real strain, so a report skimmed from the header alone would be badly misread."
   % (_F["share"], _F["share"], _F["travel"], _F["gauge"], _F["motor_strain"], _F["eps_max"]),
   fs=9.5, colour=BLACK)

banner(s, 0.4, 6.45, 12.55, 0.48,
       "NO FRACTURE: TPU DID NOT BREAK, SO PEAK STRESS AND STRAIN ARE LOWER BOUNDS SET BY WHERE "
       "THE TEST WAS STOPPED — NOT MEASUREMENTS OF STRENGTH OR ELONGATION AT BREAK.",
       fill=YELLOW_WARN, fg=BLACK, fs=10)
footer(s, "Anchor %.0f N, added back so the 20 N preload is present in the stress. %s"
          % (_F["anchor"], _F["csv"]))
pageno(s)

# ---------------------------------------------------------------- C. S36 vs S37
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "S36 vs S37 — DOES THE 45 mm GAUGE CHANGE THE ANSWER?")
img_fit(s, "documentation/figures/tpu_s37.png", 0.4, 1.22, 12.55, 4.10)
header(s, 0.45, 5.42, 6.15, "The initial slope, on a matched window")
tb(s, 0.45, 5.80, 6.15, 1.1,
   "Fitted over the SAME 0.05–1.20 %% strain window for all three, so no run is credited with a "
   "window that flatters it:\n"
   "S35 %.2f MPa   ·   S36 %.2f MPa   ·   S37 %.2f MPa\n"
   "S37 differs from S36 by %+.1f %% — and the two 80 mm runs differ from EACH OTHER by %+.1f %%."
   % (_S37["S35"]["slope"], _S37["S36"]["slope"], _S37["S37"]["slope"],
      100 * (_S37["S37"]["slope"] - _S37["S36"]["slope"]) / _S37["S36"]["slope"],
      100 * (_S37["S35"]["slope"] - _S37["S36"]["slope"]) / _S37["S36"]["slope"]),
   fs=9.6, colour=BLACK)
header(s, 6.85, 5.42, 6.1, "What that settles")
tb(s, 6.85, 5.80, 6.1, 1.1,
   "The gauge change moves the modulus by LESS than the run-to-run scatter of the original pair — "
   "the answer the pixel-ratio argument predicts. S37 lands between S35 and S36.\n"
   "Stress at matched strain runs 2–8 % below S36: ordinary specimen scatter for an elastomer, "
   "and it does not touch E, which is a slope and so is offset-independent.",
   fs=9.6, colour=BLACK)
footer(s, "S35 is the better-instrumented of the two 80 mm runs (33 % DIC coverage against S36's "
          "21 %); both are plotted so the comparison does not rest on picking one.")
pageno(s)

# ---------------------------------------------------------------- D. the trio, with S37
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PLA vs PETG vs TPU — MATCHED STRAIN, THEN EACH TO ITS OWN END")
img_fit(s, "documentation/figures/trio_s37.png", 0.4, 1.22, 12.55, 4.00)
_TD, _COMMON, _TROWS = S37.trio_table()
header(s, 0.45, 5.34, 6.6, "Stress at matched DIC strain")
table(s, 0.45, 5.70, 6.6, 1.0,
      [["Strain", "PLA (S25)", "PETG (S30)", "TPU (S37)"]] + _TROWS,
      cw=[1.3, 1.8, 1.8, 1.7], hf=9.0, bf=8.2)
header(s, 7.25, 5.34, 5.7, "Why the comparison is drawn twice")
tb(s, 7.25, 5.70, 5.7, 1.25,
   "LEFT is the only region where all three are still intact — PLA fractures first, at %.1f %%. "
   "Comparing beyond it would set a broken specimen against an unbroken one.\n"
   "RIGHT lets each run to its own end, which is the honest picture of how differently the three "
   "fail: PLA and PETG fracture; TPU never does, and the test is stopped by hand."
   % _COMMON,
   fs=9.4, colour=BLACK)
footer(s, "Log stress on both panels — the three span two decades, and TPU is a flat line on a "
          "linear axis. TPU is S37 here, the only TPU run that tracked most of its pull.")
pageno(s)
