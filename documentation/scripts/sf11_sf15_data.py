"""Evidence for the SF11 (auto-metadata link) and SF15 (test registry) proof slides.

Everything is read from the files at build time — the CSV headers, the run.json manifests and
registry.json — so the slides cannot drift from what is on disk.

Nothing here re-decides a link. The capture-to-CSV match was made at save time from timestamps
(largest overlap between the capture window and the sample window). This only reads back what was
recorded, and checks whether the two halves still agree.
"""
import datetime
import glob
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "Software", "UTM_PyQt6", "Test data")
REG = os.path.join(ROOT, "Software", "UTM_PyQt6", "registry.json")


def _hdr(csv_path):
    out = {}
    with io.open(csv_path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if not ln.startswith("#"):
                break
            if ln.startswith("# Test Date:"):
                out["date"] = ln.split(":", 1)[1].strip()
            elif ln.startswith("# Duration:"):
                out["dur"] = float(re.search(r"[\d.]+", ln).group())
            elif ln.startswith("# Capture:"):
                out["cap"] = ln.split(":", 1)[1].strip()
    return out


def link_health():
    """How many of each half's stored pointers resolve, and how many round-trip."""
    runs = glob.glob(os.path.join(DATA, "**", "run.json"), recursive=True)
    csvs = glob.glob(os.path.join(DATA, "**", "*.csv"), recursive=True)
    json_ok = 0
    for r in runs:
        d = json.load(io.open(r, encoding="utf-8"))
        json_ok += os.path.isfile(os.path.join(ROOT, d.get("csv", "")))
    hdr_tot = hdr_ok = round_trip = 0
    for c in csvs:
        h = _hdr(c)
        cap = h.get("cap")
        if not cap:
            continue
        hdr_tot += 1
        full = cap if os.path.isabs(cap) else os.path.join(ROOT, cap)
        if not os.path.isdir(full):
            continue
        hdr_ok += 1
        rj = os.path.join(full, "run.json")
        if os.path.isfile(rj):
            back = json.load(io.open(rj, encoding="utf-8")).get("csv", "")
            back = back if os.path.isabs(back) else os.path.join(ROOT, back)
            round_trip += os.path.normcase(os.path.abspath(back)) == os.path.normcase(
                os.path.abspath(c))
    return {"runs": len(runs), "json_ok": json_ok,
            "hdr_tot": hdr_tot, "hdr_ok": hdr_ok, "round_trip": round_trip}


def example(spec="S37"):
    """One run's two halves, verbatim, for showing side by side."""
    folder = glob.glob(os.path.join(DATA, "**", f"Specimen_{spec}_*"), recursive=True)[0]
    csv_path = sorted(glob.glob(os.path.join(folder, "*.csv")))[0]
    h = _hdr(csv_path)
    cap = h["cap"] if os.path.isabs(h["cap"]) else os.path.join(ROOT, h["cap"])
    d = json.load(io.open(os.path.join(cap, "run.json"), encoding="utf-8"))
    return {"csv_name": os.path.basename(csv_path), "cap_line": h["cap"],
            "cap_dir": os.path.basename(cap.rstrip("/\\")),
            "json_csv": d.get("csv", ""), "json_name": d.get("csv_name", ""),
            "from": d.get("captured_from", ""), "to": d.get("captured_to", "")}


def windows(pairs=(("S30", "S31"), ("S33", "S34"))):
    """Same-session pairs: each test's window and the window of the capture it links to."""
    rows = []
    for a, b in pairs:
        for spec in (a, b):
            folder = glob.glob(os.path.join(DATA, "**", f"Specimen_{spec}_*"), recursive=True)[0]
            for c in sorted(glob.glob(os.path.join(folder, "*.csv"))):
                h = _hdr(c)
                if "date" not in h or "cap" not in h:
                    continue
                t0 = datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M:%S")
                t1 = t0 + datetime.timedelta(seconds=h.get("dur", 0))
                cap = h["cap"] if os.path.isabs(h["cap"]) else os.path.join(ROOT, h["cap"])
                rj = os.path.join(cap, "run.json")
                if not os.path.isfile(rj):
                    continue
                d = json.load(io.open(rj, encoding="utf-8"))
                cf = datetime.datetime.fromisoformat(d["captured_from"])
                ct = datetime.datetime.fromisoformat(d["captured_to"])
                inside = t0 <= cf and ct <= t1
                rows.append([spec, f"{t0:%H:%M:%S} – {t1:%H:%M:%S}",
                             f"{cf:%H:%M:%S} – {ct:%H:%M:%S}",
                             os.path.basename(cap.rstrip("/\\")),
                             "inside" if inside else "overlaps"])
                break
    return rows


def registry_facts():
    rows = json.load(io.open(REG, encoding="utf-8"))
    mats = {}
    for r in rows:
        mats[r.get("material") or "?"] = mats.get(r.get("material") or "?", 0) + 1
    complete = sum(1 for r in rows if r.get("E_GPa"))
    return {"n": len(rows), "materials": mats, "complete": complete,
            "unresolved": sum(1 for r in rows if not os.path.isfile(os.path.join(ROOT, r["csv"])))}


def registry_listing(contains="TPU"):
    """The CLI's own output, captured by running it — not a re-render of registry.json."""
    cmd = [sys.executable, os.path.join(ROOT, "Software", "UTM_PyQt6", "utm_registry.py"),
           "list", "--contains", contains]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout
    return out.replace("\r\n", "\n").strip("\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(link_health())
    print(registry_facts())
    for r in windows():
        print(r)
    print(registry_listing())
