"""Test registry for the UTM DIC rig — one queryable index of every tensile test.

Scans test CSVs, runs the shared analysis (utm_analysis), and records each test's identity
(specimen, test label, date) + settings (area, gauge, comment) + computed properties
(E, sigma_y, UTS, epsilon_f, toughness, ANCHOR) into registry.json. So you can list/compare
tests without hard-coding CSV paths into every script — and the post-fracture anchor is
captured once, here, instead of re-derived everywhere.

    python utm_registry.py scan "Software/UTM_PyQt6/Test data/8.6.20 - Tensile test to Failure"
    python utm_registry.py list                  # whole registry as a table
    python utm_registry.py list --contains V6     # filter by test label / specimen / path
    python utm_registry.py add <one_test.csv>      # add/update a single test

No matplotlib / PyQt — pure data. registry.json lives next to this file by default.
"""
import sys, os, json, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utm_analysis import analyze, read_meta

DEFAULT_REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")
INFILL_BY_PREFIX = [("V6", 100), ("V5", 50)]     # their convention (override via add(..., extra=...))


def parse_ids(csv_path):
    """Pull specimen / test label / date from the folder + filename conventions, e.g.
    ...\\Specimen_S7_V2_Spray\\UTM_Test_20260617_165405_V6a_TensionFailure.csv
    -> specimen 'S7', test 'V6a', date '2026-06-17 16:54:05'."""
    name = os.path.basename(csv_path)
    folder = os.path.basename(os.path.dirname(csv_path))
    out = {"specimen": None, "test": None, "date": None}
    m = re.search(r"Specimen_(S\d+)", folder)
    if m:
        out["specimen"] = m.group(1)
    m = re.search(r"UTM_Test_(\d{8})_(\d{6})_+(.+?)_TensionFailure", name)
    if m:
        d, t, label = m.groups()
        out["test"] = label
        out["date"] = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"
    return out


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rel_to_repo(path):
    """Public alias of _rel, for SF11's manifest and CSV header.

    Both halves of the capture link used to be written with os.path.abspath(). That records where
    a file was at save time, which stops being true the moment the capture folder is filed into
    its specimen folder or the tree is reorganised — measured 2026-08-26, 0 of 14 stored run.json
    paths and 1 of 20 "# Capture:" headers still resolved, even though every link had been made
    correctly. The registry already solved this here; the manifest simply never used it.
    """
    return _rel(path)


def _rel(csv_path):
    """Store the CSV path relative to the repo root, forward-slashed.

    Every row seeded by the CLI is relative ("Software/UTM_PyQt6/8.6.20 - .../x.csv"), but SF11's
    auto-add hands `add()` whatever absolute path the app just saved to. Since rows are de-duplicated
    by exact string match on "csv", an absolute row and a relative row for the SAME file are two
    different rows — so re-scanning a folder would silently duplicate anything the app registered.
    Relativising here fixes both halves at once, and keeps the registry portable between machines.
    """
    p = os.path.abspath(csv_path)
    try:
        if os.path.commonpath([p, REPO_ROOT]) == REPO_ROOT:
            p = os.path.relpath(p, REPO_ROOT)
    except ValueError:                       # different drive — keep it absolute
        pass
    return p.replace("\\", "/")


def _record(csv_path, extra=None):
    """Build one registry record from a CSV (parsed ids + metadata + shared analysis)."""
    extra = extra or {}
    ids = parse_ids(csv_path)
    meta = read_meta(csv_path)
    area = float(extra.get("area") or meta.get("area") or 80.0)
    gauge = float(extra.get("gauge") or meta.get("gauge") or 80.0)
    r = analyze(csv_path, area, gauge)
    infill = next((v for pref, v in INFILL_BY_PREFIX if ids["test"] and ids["test"].startswith(pref)), None)
    if infill is None and meta.get("infill"):                # fall back to the CSV header's Infill label
        try:
            infill = float(meta["infill"])
        except (ValueError, TypeError):
            pass
    rec = {
        "csv": _rel(csv_path),
        "specimen": ids["specimen"], "test": ids["test"], "date": ids["date"] or meta.get("date"),
        # From the CSV header, not hard-coded. This field read "PLA" for every test ever recorded,
        # which is how S30, S31 and S32 — all PETG — entered the registry labelled PLA and had to be
        # corrected by hand. Older CSVs carry no Material: line, and those really were PLA.
        "material": (extra.get("material") or meta.get("material") or "PLA"), "infill_pct": infill,
        "area_mm2": area, "gauge_mm": gauge, "comment": meta.get("comment"),
        "UTS_MPa": round(r["uts"], 2), "sy_MPa": (round(r["sy"], 2) if r.get("sy") is not None else None), "E_GPa": round(r["E"], 3),
        "ef": round(r["ef"], 4), "tough_kJm3": int(round(r["tough"])), "anchor_N": int(round(r["anchor"])),
    }
    rec.update({k: v for k, v in extra.items() if k not in ("area", "gauge")})
    return rec


def load(registry_path=DEFAULT_REGISTRY):
    if os.path.exists(registry_path):
        with open(registry_path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(rows, registry_path=DEFAULT_REGISTRY):
    rows.sort(key=lambda r: (r.get("date") or "", r.get("test") or ""))
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def add(csv_path, registry_path=DEFAULT_REGISTRY, extra=None):
    """Analyse one CSV and add/replace its record (keyed by csv path)."""
    rec = _record(csv_path, extra)
    rows = [r for r in load(registry_path) if r.get("csv") != rec["csv"]]
    rows.append(rec)
    save(rows, registry_path)
    return rec


def scan(folder, registry_path=DEFAULT_REGISTRY, pattern="**/*TensionFailure*.csv"):
    """Walk a folder and add every matching test CSV. Returns (added, skipped[(path, err)])."""
    rows = load(registry_path)
    added, skipped = [], []
    for p in sorted(glob.glob(os.path.join(folder, pattern), recursive=True)):
        try:
            rec = _record(p)
        except Exception as e:                      # non-fracture / unreadable CSVs are skipped, not fatal
            skipped.append((p, str(e))); continue
        rows = [r for r in rows if r.get("csv") != rec["csv"]]
        rows.append(rec); added.append(rec)
    save(rows, registry_path)
    return added, skipped


_COLS = [("test", "test", 6), ("specimen", "spec", 5), ("infill_pct", "infill", 6),
         ("UTS_MPa", "UTS", 7), ("sy_MPa", "sy", 7), ("E_GPa", "E", 6), ("ef", "ef", 7),
         ("tough_kJm3", "tough", 6), ("anchor_N", "anchor", 6), ("date", "date", 19)]


def print_table(rows, contains=None):
    if contains:
        c = contains.lower()
        rows = [r for r in rows
                if c in f"{r.get('test')}{r.get('specimen')}{r.get('csv')}".lower()]
    hdr = "  ".join(f"{h:>{w}}" for _, h, w in _COLS)
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print("  ".join(f"{('' if r.get(k) is None else str(r.get(k))):>{w}}" for k, _, w in _COLS))
    print(f"\n{len(rows)} test(s).")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    usage = "usage: python utm_registry.py scan <folder> | list [--contains X] | add <csv>"
    if not args or args[0] in ("-h", "--help"):
        print(usage); return 0
    cmd = args[0]
    if cmd == "scan" and len(args) >= 2:
        added, skipped = scan(args[1])
        print(f"Added/updated {len(added)} test(s); skipped {len(skipped)}.")
        for p, e in skipped:
            print(f"  skip {os.path.basename(p)}: {e}")
        print_table(load())
    elif cmd == "add" and len(args) >= 2:
        rec = add(args[1])
        print(f"Added {rec['test']} / {rec['specimen']}: UTS {rec['UTS_MPa']} MPa, anchor {rec['anchor_N']} N")
    elif cmd == "list":
        contains = args[args.index("--contains") + 1] if "--contains" in args and len(args) > args.index("--contains") + 1 else None
        print_table(load(), contains)
    else:
        print(usage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
