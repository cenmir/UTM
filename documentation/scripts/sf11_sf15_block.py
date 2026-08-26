# ===================================================================================
#  SF11 (auto-metadata link) and SF15 (test registry) — the two features that were
#  built and working but had no slide of their own, so the proof table could only
#  point at their cards.
#
#  Every number is read from the files at build time by sf11_sf15_data, and the
#  registry listing is captured by RUNNING the CLI rather than re-rendering its JSON.
# ===================================================================================
import sf11_sf15_data as SFD                                           # noqa: E402

_LH = SFD.link_health()
_EX = SFD.example("S37")
_WIN = SFD.windows()
_RF = SFD.registry_facts()
_LIST = SFD.registry_listing("TPU")

# ---------------------------------------------------------------- SF11
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF11 · AUTO-METADATA LINK — AND THAT BOTH HALVES STILL AGREE")
tb(s, 0.4, 1.13, 12.55, 0.46,
   "Saving writes each half of the link into the other's folder, so a capture and its load file "
   "can always find each other. The test is whether they still round-trip.",
   fs=11.5, italic=True, colour=GREY_TEXT)

header(s, 0.45, 1.66, 6.15, "The two halves, on one run (S37)")
table(s, 0.45, 2.04, 6.15, 2.2, [
    ["Written into", "Field", "Value"],
    ["the CSV header", "# Capture:", _EX["cap_line"]],
    ["the capture folder", "csv", _EX["json_csv"]],
    ["  (run.json)", "csv_name", _EX["json_name"]],
    ["", "captured_from / to", "%s → %s" % (_EX["from"][11:], _EX["to"][11:])],
], cw=[1.25, 1.35, 3.55], hf=9.0, bf=7.4)

header(s, 0.45, 4.42, 6.15, "Do they still point at each other?")
_rt = [["Check", "Result"],
       ["run.json → its CSV", "%d / %d resolve" % (_LH["json_ok"], _LH["runs"])],
       ["CSV header → its capture folder", "%d / %d resolve" % (_LH["hdr_ok"], _LH["hdr_tot"])],
       ["full round-trip, CSV → folder → back to the SAME CSV",
        "%d / %d" % (_LH["round_trip"], _LH["runs"])]]
table(s, 0.45, 4.80, 6.15, 1.1, _rt, cw=[3.9, 2.25], hf=9.0, bf=8.4)

header(s, 6.85, 1.66, 6.1, "Matched by OVERLAP, never by recency")
table(s, 6.85, 2.04, 6.1, 1.7,
      [["Run", "Test window", "Capture window", "Folder", ""]] +
      [[r[0], r[1], r[2], r[3][-6:], r[4]] for r in _WIN],
      cw=[0.55, 1.7, 1.7, 1.15, 1.0], hf=9.0, bf=8.0)
tb(s, 6.85, 4.42, 6.1, 1.5,
   "Two same-session pairs. Each capture window sits INSIDE its own test window — the link is "
   "made from the largest overlap between the two intervals, not from whichever capture happened "
   "last.\n\n"
   "These four were saved promptly, so recency would have agreed. It stops agreeing the moment "
   "two runs are saved after the fact, or a specimen folder holds more than one capture — S12's "
   "holds two. A mislabelled link is worse than none, because it looks authoritative.",
   fs=9.3, colour=BLACK)

banner(s, 0.4, 6.15, 12.55, 0.80,
       "THE LINK WAS ALWAYS CORRECT; THE STORED POINTER WAS NOT. BOTH HALVES RECORDED ABSOLUTE "
       "PATHS, WHICH DIED WHEN A CAPTURE FOLDER WAS FILED INTO ITS SPECIMEN FOLDER — 0/14 AND "
       "1/20 RESOLVED. NOW STORED REPO-RELATIVE, AND EVERY EXISTING FILE REPAIRED FROM THE "
       "csv_name THAT DID SURVIVE.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=10)
footer(s, "One capture is honestly unrecoverable: S29's folder was not kept, so its header is "
          "left pointing where it pointed rather than at an invented path.")
pageno(s)

# ---------------------------------------------------------------- SF15
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF15 · TEST REGISTRY — ONE QUERYABLE INDEX OF EVERY RUN")
tb(s, 0.4, 1.13, 12.55, 0.46,
   "%d runs, each with its computed properties and its force anchor, addressable by specimen, "
   "material or test label instead of by a path typed into a script."
   % _RF["n"],
   fs=11.5, italic=True, colour=GREY_TEXT)

header(s, 0.45, 1.66, 7.3, "The CLI, run for this slide")
tb(s, 0.45, 2.04, 7.3, 0.32,
   "python Software/UTM_PyQt6/utm_registry.py list --contains TPU",
   fs=9.5, font="Consolas", colour=BLACK)
tb(s, 0.45, 2.44, 7.3, 1.55, _LIST, fs=8.0, font="Consolas", colour=BLACK)
tb(s, 0.45, 4.05, 7.3, 0.8,
   "Captured by RUNNING the command at build time, not re-rendered from the JSON — so this slide "
   "cannot show a table the tool would not.",
   fs=9.0, italic=True, colour=GREY_TEXT)

header(s, 8.0, 1.66, 4.95, "What it holds")
table(s, 8.0, 2.04, 4.95, 1.3, [
    ["", "Runs"],
    ["PLA", str(_RF["materials"].get("PLA", 0))],
    ["PETG", str(_RF["materials"].get("PETG", 0))],
    ["TPU", str(_RF["materials"].get("TPU", 0))],
    ["with a full property set", "%d of %d" % (_RF["complete"], _RF["n"])],
], cw=[3.0, 1.95], hf=9.5, bf=8.8)
tb(s, 8.0, 3.62, 4.95, 1.3,
   "The rest are runs analyze() cannot complete — an abandoned pull, or one that never fractured. "
   "The row is KEPT rather than dropped: a blank property is a fact about the run, and deleting it "
   "would quietly shrink the denominator.",
   fs=9.2, colour=BLACK)

header(s, 0.45, 4.90, 12.5, "What it is actually worth — two bugs it caught")
tb(s, 0.45, 5.28, 12.5, 1.15,
   "•  THE FRACTURE CUT THAT NEVER RAN. Two deck scripts asked analyze() for \"fracture_i\"; the "
   "key is \"fr_i\", so .get() returned None every time and the PLA and PETG curves carried "
   "post-fracture data. Found by enumerating every run through the registry and re-analysing — "
   "with paths hard-coded into each script, there was nothing to enumerate.\n"
   "•  A RENAME, CAUGHT IN ONE LINE. S37's folder gained a “_Video15” suffix after its run. The "
   "registry reported one unresolved row immediately; the alternative was a deck build failing "
   "later with no clue why.",
   fs=9.4, colour=BLACK)

banner(s, 0.4, 6.48, 12.55, 0.44,
       "%d ROWS, %d UNRESOLVED PATHS. THE REGISTRY IS WHAT MAKES “EVERY RUN ON RECORD” A QUERY "
       "RATHER THAN A CLAIM." % (_RF["n"], _RF["unresolved"]),
       fill=GREEN_PASS, fg=DARK_GREEN, fs=10.5)
footer(s, "Auto-populated on save (SF11) and by utm_registry.py scan. Properties are re-analysed "
          "from the CSVs, never copied from a previous result.")
pageno(s)
