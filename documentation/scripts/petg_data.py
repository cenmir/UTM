"""PETG (S30, S31) against PLA (S25, S26) — the numbers, and what literature says to expect.

WHICH RUNS COUNT, AND FOR WHAT
------------------------------
S29 is excluded entirely: it was loaded repeatedly before it finally fractured, so its curve is
not a single monotonic pull and nothing derived from it describes virgin material.

S31 tracked only **57 %** of frames. The cause is known and is not the material: the sprayed dots
carry a crescent of overspray fused to the rim, which drops circularity onto the 0.50 gate
(measured 0.49-0.51), so noise flipped markers in and out frame by frame. `min_circularity` was
loosened to 0.40 for the campaign after S31 ran.

That split matters, and it is not "throw S31 away":

  * UTS and sigma_y come from the LOAD CELL and the nominal area. They do not touch the DIC, so
    S31 is fully valid for them and its 2.9 % agreement with S30 on UTS is a real repeatability
    result.
  * E, eps_f and toughness are STRAIN quantities and depend on tracking. S31's differ from S30 by
    17 %, 51 % and 48 % — which is the signature of 57 % coverage, not of a different specimen.
    S30 (89 %) is the representative run for those.

So: strength from both, stiffness and ductility from S30 alone, and the slide says which is which.

WHAT LITERATURE SAYS TO EXPECT
------------------------------
The ORDERING is the robust prediction and the thing worth testing; absolute values move with print
settings, spool and machine. For 100 % infill printed parts:

    PLA   stronger and much stiffer, and brittle    UTS 50-60 MPa, E 3.0-3.6 GPa, eps_f 3-8 %
    PETG  a little weaker, far less stiff, tougher  UTS 45-53 MPa, E 1.7-2.1 GPa, eps_f 5-25 %

⚠ The PETG spool's own datasheet has NOT been obtained yet — see the roadmap. The bands above are
typical published values for printed PETG, so treat the PETG comparison as a SANITY CHECK on the
ordering, not as the like-for-like datasheet validation PLA already has against add:north E-PLA.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP = os.path.abspath(os.path.join(REPO, "Software", "UTM_PyQt6"))
sys.path.insert(0, APP)
import utm_analysis as UA                                             # noqa: E402

D = os.path.join(APP, "Test data", "8.6.20 - Tensile test to Failure")
RUNS = {
    "S30": (os.path.join(D, "Specimen_S30_V3_PETG_Spray_Video9",
                         "UTM_Test_20260822_180547.csv"), "PETG", 89),
    "S31": (os.path.join(D, "Specimen_S31_V3_PETG_Spray_Video10",
                         "UTM_Test_20260822_181957.csv"), "PETG", 57),
    "S32": (os.path.join(D, "Specimen_S32_V3_PETG_Spray_Video11",
                         "UTM_Test_20260824_104255.csv"), "PETG", 65),
    "S25": (os.path.join(D, "Specimen_S25_V2_Spray_Video2",
                         "UTM_Test_20260817_103930_100%infill_Videocapture_2.csv"), "PLA", 100),
    "S26": (os.path.join(D, "Specimen_S26_V2_Spray_Video3",
                         "UTM_Test_20260817_111700_100%infill_Videocapture3.csv"), "PLA", 100),
}
PETG_REP, PLA_REP = "S30", "S25"        # representative runs for STRAIN quantities
STRAIN_OK = {"S30", "S25", "S26"}       # tracked well enough for E / eps_f / toughness

# S32's FORCE ANCHOR FAILED and every stress it derives is shifted because of it. The anchor is
# recovered from the settled post-fracture tail, which should read -(the tared-away preload), about
# -300 N on this rig; S30 ends at -311 N and S25 at -280. S32's tail settled at +936 N - the
# specimen never fully released - so analyze() computed anchor -1044 N and shifted the entire stress
# axis DOWN by 13 MPa, reporting UTS 25.92 where the raw peak load says 38.97 uncorrected.
#
# The peak LOAD is untouched by any of that: 3117.5 N straight off the load cell, the highest of the
# three PETG runs. So S32 is quoted on FORCE, and its stress is re-derived with the rig's usual
# preload substituted for the failed recovery - stated as an assumption, never as a measurement.
ANCHOR_FAILED = {"S32"}
ASSUMED_PRELOAD_N = 300.0

# Typical published ranges for 100 % infill printed parts. Ordering is the prediction under test.
LIT = {"PLA":  {"UTS": (50, 60), "E": (3.0, 3.6), "ef": (3, 8)},
       "PETG": {"UTS": (45, 53), "E": (1.7, 2.1), "ef": (5, 25)}}

_cache = {}


def get(key):
    if key not in _cache:
        p, mat, track = RUNS[key]
        a = UA.analyze(p, 80.0, 80.0)
        a["material"], a["track"], a["key"] = mat, track, key
        _cache[key] = a
    return _cache[key]


def all_runs():
    return {k: get(k) for k in RUNS}


def pct(a, b):
    """b relative to a, in per cent."""
    return 100.0 * (b / a - 1.0)


def peak_load_N(key):
    """Peak load straight from the load cell - immune to the anchor and to DIC tracking alike."""
    a = get(key)
    return a["uts_F"] if key not in ANCHOR_FAILED else a["uts_F"] - a["anchor"] + ASSUMED_PRELOAD_N


def uts_corrected(key):
    """UTS, with a failed anchor replaced by the rig's usual preload. Returns (value, is_assumed)."""
    a = get(key)
    if key not in ANCHOR_FAILED:
        return a["uts"], False
    raw_peak = a["uts_F"] - a["anchor"]           # undo the bad anchor -> load-cell peak
    return (raw_peak + ASSUMED_PRELOAD_N) / 80.0, True


def summary():
    """The comparison the slides are built from."""
    P, L = get(PETG_REP), get(PLA_REP)
    out = {"petg": P, "pla": L, "cmp": {}}
    for k in ("uts", "sy", "E", "ef", "tough"):
        out["cmp"][k] = pct(L[k], P[k])
    return out


def expectation_table():
    """(property, what literature predicts, what we measured, does it agree)."""
    P, L = get(PETG_REP), get(PLA_REP)
    rows = []
    for key, lab, higher, unit, scale in (
            ("uts", "UTS", "PLA", "MPa", 1.0),
            ("E", "Stiffness E", "PLA", "GPa", 1.0),
            ("ef", "Ductility ε_f", "PETG", "%", 100.0),
            ("tough", "Toughness", "PETG", "kJ/m³", 1.0)):
        pv, lv = P[key] * scale, L[key] * scale
        measured = "PLA" if lv > pv else "PETG"
        rows.append({"key": key, "label": lab, "unit": unit,
                     "expect": higher, "measured": measured,
                     "pla": lv, "petg": pv, "agree": higher == measured,
                     "delta_pct": pct(lv, pv)})
    return rows


if __name__ == "__main__":
    R = all_runs()
    print("%-5s %-5s %6s %7s %7s %7s %7s %8s" %
          ("run", "mat", "track", "UTS", "sy", "E GPa", "ef %", "tough"))
    for k in ("S30", "S31", "S25", "S26"):
        a = R[k]
        print("%-5s %-5s %5d%% %7.2f %7.2f %7.3f %7.2f %8.0f"
              % (k, a["material"], a["track"], a["uts"], a["sy"], a["E"],
                 a["ef"] * 100, a["tough"]))
    print("\nDoes it behave as literature predicts?")
    for r in expectation_table():
        print("  %-14s expect %-4s higher | measured %-4s higher  %-3s   PLA %8.2f  PETG %8.2f %s"
              % (r["label"], r["expect"], r["measured"], "OK" if r["agree"] else "NO",
                 r["pla"], r["petg"], r["unit"]))
    print("\nStrength repeatability (load-cell only, unaffected by tracking):")
    print("  PETG S30 vs S31 UTS  %.2f vs %.2f  -> %+.1f %%"
          % (get("S30")["uts"], get("S31")["uts"], pct(get("S30")["uts"], get("S31")["uts"])))
    print("  PLA  S25 vs S26 UTS  %.2f vs %.2f  -> %+.1f %%"
          % (get("S25")["uts"], get("S26")["uts"], pct(get("S25")["uts"], get("S26")["uts"])))
