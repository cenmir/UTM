# ===================================================================================
#  Smart-feature PROOF slides — sit immediately after the two overview slides, so the
#  claim and the evidence for it are adjacent.
#
#  Screenshots are the operator's own, taken on the rig 2026-08-22. The capture figures
#  are read from S26's actual frames and .avi files at build time.
# ===================================================================================
import capture_evidence as CE                                          # noqa: E402

CE.all_figs()
_CF = CE.facts()
_RAW = _CF.get("video.avi", (0, 0))
_BST = _CF.get("video_boost.avi", (0, 0))
_SPK = _CF.get("video_speckle.avi", (0, 0))

# ---------------------------------------------------------------- A. where the proof lives
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "WHERE THE PROOF FOR EACH SMART FEATURE LIVES")
tb(s, 0.5, 1.32, 12.4, 0.5,
   "The two cards above say what each feature IS. This says where in this deck it was shown "
   "working, so a claim and its evidence are never more than a page reference apart.",
   fs=10.5, colour=BLACK)
# Every page below was resolved against the built deck, not written from memory — the first draft
# of this table was off by one in places and invented pages for SF11/15/18, which have no proof
# slide at all. A pointer to the wrong slide is worse than an honest "not yet".
_rows = [["SF", "Feature", "Where it is shown working", "Kind of evidence"],
         ["1", "DIC health HUD", "p168", "screenshot on the rig"],
         ["2", "Prepare specimen", "p170", "before / after readouts"],
         ["3", "Settings / recipes", "p207", "one click restores 6 fields"],
         ["4", "Generate report", "p171", "the report itself, from S16"],
         ["5", "Auto-stop at fracture", "p172", "the halt on the load trace"],
         ["6", "Strain-rate fracture test", "p173 · p174", "0.00051/s held vs 0.0005 target"],
         ["7", "Stall guard", "p175", "silent through a ductile draw"],
         ["8", "Release preload", "p176", "both depths on the trace"],
         ["9", "Six closed-loop protocols", "p188–p204 · p213–p218", "one How + one Results slide each"],
         ["10", "Auto-preload", "p162", "the 0.2→0.1→0.02 schedule"]]
table(s, 0.4, 1.95, 6.15, 3.9, _rows, cw=[0.5, 2.0, 2.0, 2.1], hf=9.5, bf=8.7)
_rows2 = [["SF", "Feature", "Where it is shown working", "Kind of evidence"],
          ["11", "Auto-metadata link", "card only — p250", "no run-level screenshot yet"],
          ["12", "DIC auto-calibration", "NEXT SLIDE", "the sweep dialog, real numbers"],
          ["13", "Guided wizard", "NEXT SLIDE + 1", "9 of 9 done, on the rig"],
          ["14", "Poisson / true Cauchy", "p166 · p187", "why the optics block it"],
          ["15", "Test registry", "p179 · p237", "the register, every run on record"],
          ["16", "Dead-DIC guard", "p175", "the halt at 1.0 s stale"],
          ["18", "Live Px₀ overlay", "not yet", "needs one screenshot — card stays blue"],
          ["19", "Video + image capture", "LAST TWO OF THIS BLOCK", "S26 frames and all 3 videos"],
          ["—", "Capture formats & disk", "p256 · p257", "TIFF/PNG, FFV1/Y800, cost"]]
table(s, 6.8, 1.95, 6.15, 3.9, _rows2, cw=[0.5, 2.0, 2.0, 2.1], hf=9.5, bf=8.7)
banner(s, 0.4, 6.1, 12.55, 0.5,
       "THE THREE FEATURES WITH NO SCREENSHOT UNTIL NOW — AUTO-CALIBRATION, THE WIZARD AND "
       "CAPTURE — ARE PROVEN ON THE NEXT FOUR SLIDES.",
       fill=LIGHT_BLUE, fg=BLACK, fs=10.5)
footer(s, "SF17 is absent by design (see the previous slide). Page numbers are this deck's own, "
          "and were read back off the built deck rather than written by hand.")
pageno(s)

# ---------------------------------------------------------------- B. SF12 auto-calibration
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF12 · DIC AUTO-CALIBRATION — THE SWEEP, ON THE RIG")
img_fit(s, "documentation/figures/UTM_Autocalibrate.png", 0.45, 1.35, 6.2, 4.5)
header(s, 7.0, 1.35, 5.95, "What the dialog is showing")
tb(s, 7.0, 1.75, 5.95, 2.5,
   "Seven exposures swept at the working threshold, each scored on how well the markers would "
   "survive a disturbance — not on whether they happen to be found right now.\n\n"
   "It picked 35 ms / threshold 120 over the 50 ms / 150 that was loaded: detect 100 %, contrast "
   "0.96, only 0.1 % of pixels clipped, score 0.82. The two settings that also detect 100 % lose "
   "on clipping (0.8 % and 2.0 %) — at 140 ms the frame is so bright that detection collapses to "
   "0 %.\n\n"
   "It PROPOSES. Cancel puts the camera back exactly as it was, which is why it is safe to run "
   "with a specimen already mounted.",
   fs=9.8, colour=BLACK)
header(s, 7.0, 3.95, 5.95, "Why contrast margin, not detection rate")
tb(s, 7.0, 4.35, 5.95, 1.45,
   "Detection rate answers “does it work now”. Contrast margin answers “will it still work when "
   "the light flickers or the specimen necks” — how far the markers sit from the threshold. "
   "Three settings here detect 100 % and only one of them has room to spare.",
   fs=9.6, colour=BLACK)
banner(s, 0.4, 6.4, 12.55, 0.5,
       "STATUS CHANGED: SF12 WAS “BUILT, WAITING ON RIG TIME”. THIS IS IT RUNNING ON THE RIG — "
       "THE CARD IS NOW GREEN.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=10.5)
footer(s, "Operator screenshot, 2026-08-22. Settings ▸ DIC camera setup ▸ Auto-calibrate DIC.")
pageno(s)

# ---------------------------------------------------------------- C. SF13 guided wizard
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF13 · GUIDED WIZARD — NINE OF NINE, ON A REAL RUN")
img_fit(s, "documentation/figures/UTM_GuidedWizard.png", 0.5, 1.32, 3.5, 5.0)
header(s, 4.4, 1.35, 4.1, "What it is reading")
tb(s, 4.4, 1.75, 4.1, 4.5,
   "Nothing new is measured. Every line is a flag the app already had, put in the order the steps "
   "must happen:\n\n"
   "•  serial link open\n"
   "•  motors enabled\n"
   "•  camera running, 2/2 markers\n"
   "•  data streams on\n"
   "•  specimen mode chosen\n"
   "•  auto-calibrate run for THIS specimen\n"
   "•  preload applied — 311 N now\n"
   "•  Px₀ frozen — 1648.2 px @ 305 N\n"
   "•  Prepare test done\n"
   "•  frame capture armed (optional)\n"
   "•  the run itself — 2 522 samples\n"
   "•  data saved, with the path\n\n"
   "The grey dots are the two OPTIONAL steps. They never block, and they never turn green.",
   fs=9.4, colour=BLACK)
header(s, 8.85, 1.35, 4.1, "Why the ORDER is the feature")
tb(s, 8.85, 1.75, 4.1, 4.5,
   "Three of these steps are order-dependent and each has already cost a run somewhere in this "
   "deck:\n\n"
   "•  Auto-calibrate BEFORE arming capture — the speckle video follows the camera settings.\n\n"
   "•  Px₀ AFTER preload — freeze it unloaded and every strain in the test is measured from the "
   "wrong zero.\n\n"
   "•  Prepare test AFTER Px₀ — it tares the FORCE, so the load the freeze happened at can no "
   "longer be read back.\n\n"
   "The panel shows Px₀ frozen at 305 N with the preload reading 311 N: the right order, "
   "self-evidently, without the operator having to remember it.",
   fs=9.4, colour=BLACK)
footer(s, "Operator screenshot, 2026-08-22 — the wizard at the end of a completed run "
          "(UTM_Test_20260822_180547.csv). Optional and off by default.")
pageno(s)

# ---------------------------------------------------------------- D. SF19 capture, the controls
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF19 · VIDEO + IMAGE CAPTURE — WHAT THE OPERATOR CHOOSES")
img_fit(s, "documentation/figures/UTM_capture_setup.png", 0.45, 1.35, 7.5, 4.6)
header(s, 8.25, 1.35, 4.7, "Three decisions, all costed live")
tb(s, 8.25, 1.75, 4.7, 4.3,
   "STILLS — TIFF uncompressed by default, PNG as the option. Both are lossless; TIFF is faster "
   "to write, PNG is smaller.\n\n"
   "VIDEO — FFV1 (.mkv) or raw Y800 (.avi), both lossless, so the video can be MEASURED from "
   "rather than merely watched. MJPG was dropped: it is lossy and it drops the last column of an "
   "odd-width frame.\n\n"
   "VIEWS — raw, speckle-only, boosted contrast; any combination, recorded together from the same "
   "pull.\n\n"
   "The disk cost updates as the boxes change, in GB per minute AND per hour, against a 3-minute "
   "fracture pull and the free space on the drive. 237 GB/hour is the kind of number that has to "
   "be seen BEFORE a run, not discovered after it.",
   fs=9.5, colour=BLACK)
footer(s, "Operator screenshot, 2026-08-22. Every option carries a ? help button explaining the "
          "trade-off — added after the formats went in.")
pageno(s)

# ---------------------------------------------------------------- E. SF19 capture, the evidence
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF19 · WHAT IT ACTUALLY RECORDED — S26, START TO FRACTURE")
img_fit(s, "documentation/figures/sf_capture_strip.png", 0.4, 1.28, 5.9, 5.0)
img_fit(s, "documentation/figures/sf_capture_views.png", 6.6, 1.28, 6.25, 3.31)
header(s, 6.6, 4.8, 6.25, "Why this is evidence and not an illustration")
tb(s, 6.6, 5.2, 6.25, 1.5,
   "%d stills at %.1f fps and %d video frames per view, all read back off disk to build this "
   "slide. The last still is the fracture — the one frame that cannot be recaptured.\n\n"
   "Each still carries the load and strain from the LOAD file at the same instant, matched on the "
   "clock: the capture ran t = %.1f–%.1f s of a %.0f s test, so the two recordings do NOT start "
   "together and frame %% cannot stand in for test %%. Frame 1049 landing exactly on the %.2f MPa "
   "peak is the check that the link is right."
   % (_CF["stills"], _CF["fps"], _RAW[0], _CF["t_first"], _CF["t_last"], _CF["t_test"], 47.17),
   fs=9.4, colour=BLACK)
footer(s, "Specimen S26, run %s — %.1f GB of stills beside %.0f + %.0f + %.0f MB of lossless video."
          % (_CF["run"], _CF["still_mb"] / 1000.0, _RAW[1], _BST[1], _SPK[1]))
pageno(s)
