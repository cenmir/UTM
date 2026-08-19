"""What the torque "ceiling" actually was — computed from the registry, not remembered.

The deck carried a hardware limit for three weeks: the motor stalls around 2.6 kN, so a 100 %
infill specimen at full cross-section (needs ~3.7 kN) cannot be fractured. Four causes were ranked
on p199, three of them electrical (driver Vref, thermal derating, PSU sag) and one mechanical
(binding). The mechanical one was ranked LAST.

It was the mechanical one. The load holders had worked loose, letting the crossheads sit out of
alignment, so part of the motor's torque went into binding instead of into the specimen. Re-aligned
and re-tightened, the rig pulls 3.5 kN with no stutter.

The evidence for "not a torque ceiling" was already on disk before the fault was found, which is
why this module computes it rather than asserting it: the same machine has fractured 100 % infill
specimens at 3.6-3.8 kN on eleven separate occasions spread over three months. A ceiling that ten
runs walk straight through is not a ceiling. What was intermittent was the load path.

The decisive pair is S15 and S16 — SAME DAY, 2026-07-28. S15 stalled at ~2.6 kN; S16 fractured at
3.79 kN. No electrical explanation survives that: Vref does not change between two specimens, and a
thermal limit gets WORSE as a session goes on, not 46 % better. A remount, on the other hand, is
exactly when alignment changes.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "..", "Software", "UTM_PyQt6", "registry.json")

# The operator's verification pull after re-aligning and re-tightening the load holders.
FIXED_KN = 3.5
NEEDED_KN = 3.7          # 100 % infill at the full 80 mm² cross-section
OLD_CEILING_KN = 2.6     # what the deck carried as the hardware limit

# The two stalls on record. Neither fractured, so neither is in the registry.
STALLS = [("S15", "2026-07-28", 2.6, "manual stop; the machine shook"),
          ("T7 / S20", "2026-08-09", 2.355, "staircase→fracture, 64 % of what it needed")]

# The rig assembly was realigned and the load holders re-tightened on 2026-08-12. Runs after this
# date carry a load path that is known-good; runs before it do not, and both stalls fall before it.
FIX_DATE = "2026-08-12"

# What each post-fix run was FOR. The registry comments carry this too, but at paragraph length.
ROLES = {
    "S24": ("100 % white PLA", "Frame capture VC1"),
    "S25": ("100 % white PLA", "Frame capture VC2 — extensometer basis"),
    "S26": ("100 % white PLA", "Frame capture VC3 — extensometer basis"),
    "S27": ("50 % white PLA", "50 % video pair VC4"),
    "S28": ("50 % white PLA", "50 % video pair VC5"),
    "S12": ("100 % BLACK PLA", "Black attempt VC6 — capture not filed"),
    "S13": ("100 % BLACK PLA", "Black preset VALIDATED VC7"),
}


def post_fix():
    """Every fractured run after the realignment: [(spec, date, material, role, peak, UTS, E)]."""
    out = []
    for r in _rows():
        date = str(r.get("date"))[:10]
        if date < FIX_DATE:
            continue
        uts, area = r.get("UTS_MPa"), r.get("area_mm2")
        if not uts or not area:
            continue
        spec = r.get("specimen")
        mat, role = ROLES.get(spec, ("—", "—"))
        out.append((spec, date, mat, role, float(uts) * float(area), float(uts),
                    r.get("E_GPa")))
    return sorted(out, key=lambda t: (t[1], t[0]))


def _rows():
    with open(REG, encoding="utf-8") as fh:
        r = json.load(fh)
    return r if isinstance(r, list) else r.get("tests", r.get("rows", []))


def peaks_100():
    """[(specimen, date, peak_N)] for every 100 % infill run that actually fractured."""
    out = []
    for r in _rows():
        if float(r.get("infill_pct") or 0) != 100.0:
            continue
        uts, area = r.get("UTS_MPa"), r.get("area_mm2")
        if not uts or not area:
            continue
        out.append((r.get("specimen"), str(r.get("date"))[:10], float(uts) * float(area)))
    return sorted(out, key=lambda t: t[1])


def stats():
    p = [x[2] for x in peaks_100()]
    n = len(p)
    mean = sum(p) / n
    sd = (sum((v - mean) ** 2 for v in p) / (n - 1)) ** 0.5
    return {"n": n, "min": min(p), "max": max(p), "mean": mean, "sd": sd,
            "cv": 100.0 * sd / mean,
            "over_ceiling": sum(1 for v in p if v > OLD_CEILING_KN * 1000)}


def same_day_pair():
    """The S15/S16 contradiction: a stall and a 3.8 kN fracture on one day."""
    s16 = [x for x in peaks_100() if x[0] == "S16"]
    if not s16:
        return None
    spec, date, peak = s16[0]
    stall = [s for s in STALLS if s[1] == date]
    if not stall:
        return None
    return {"date": date, "stall_spec": stall[0][0], "stall_kN": stall[0][2],
            "frac_spec": spec, "frac_N": peak,
            "ratio_pct": 100.0 * (peak / (stall[0][2] * 1000.0) - 1.0)}


if __name__ == "__main__":
    st = stats()
    print(f"100 % infill fractures on record: n = {st['n']}")
    for spec, date, pk in peaks_100():
        print(f"   {spec:>4}  {date}  {pk:7.0f} N")
    print(f"\n  range {st['min']:.0f}-{st['max']:.0f} N   mean {st['mean']:.0f} "
          f"± {st['sd']:.0f} N  (CV {st['cv']:.1f} %)")
    print(f"  above the supposed {OLD_CEILING_KN} kN ceiling: {st['over_ceiling']}/{st['n']}")
    sd = same_day_pair()
    if sd:
        print(f"\n  SAME DAY {sd['date']}: {sd['stall_spec']} stalled at {sd['stall_kN']} kN, "
              f"{sd['frac_spec']} fractured at {sd['frac_N']:.0f} N "
              f"(+{sd['ratio_pct']:.0f} % on the same rig, same speed)")

    pf = post_fix()
    print(f"\nAfter the realignment ({FIX_DATE}) — {len(pf)} runs, 0 stalls:")
    for spec, date, mat, role, pk, uts, E in pf:
        print(f"   {spec:>4}  {date}  {mat:<16}{role:<38}{pk:6.0f} N  "
              f"{uts:5.2f} MPa  {(E or 0):4.2f} GPa")
    h = [x for x in pf if "100 %" in x[2]]
    if h:
        p = [x[4] for x in h]
        print(f"\n  the {len(h)} × 100 % runs post-fix: {min(p):.0f}-{max(p):.0f} N "
              f"(mean {sum(p)/len(p):.0f} N) — every one above the {OLD_CEILING_KN} kN 'ceiling'")
    print(f"  stalls before the fix: {len(STALLS)}   ·   stalls after: 0")
