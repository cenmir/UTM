"""Test recipes for the UTM — save/load a named test setup (dimensions, specimen DIC preset,
preload, speed, mode + params) as JSON so a repeat test is one click.

Pure data (no PyQt): the app reads a recipe and applies it to its widgets, or reads the widgets
and saves a new recipe. Recipes live in Software/UTM_PyQt6/recipes/*.json (tracked).

    python utm_recipes.py list
    python utm_recipes.py show "V6 100% infill tensile"
"""
from dataclasses import dataclass, asdict, field, fields
import json, os, sys

RECIPES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipes")


@dataclass
class TestRecipe:
    name: str = "unnamed"
    material: str = "PLA"
    infill_pct: float = 100.0
    specimen_mode: str = "White"          # DIC preset: White (dark dots) / Black (light dots)
    area_mm2: float = 80.0
    gauge_mm: float = 80.0
    preload_N: float = 470.0
    test_speed_mm_s: float = 0.1
    # "manual", or the EXACT advanced-test-mode dropdown label ("Cyclic", "Staircase",
    # "Relaxation", "Creep", "Staircase → FRACTURE", "Progressive cyclic → FRACTURE").
    # Storing the label verbatim keeps load/save a straight lookup with no translation table.
    mode: str = "manual"
    strain_rate: float = 0.0005           # used by the strain-rate fracture test (1/s)
    # Per-mode settings, keyed by that same label:
    #   {"Cyclic": {"low": 100.0, "high": 500.0, "cycles": 5, "speed": 0.1, "waveform": "Sine"}, ...}
    # A dict rather than flat fields so a new mode needs no schema change, and so EVERY mode's
    # params round-trip (not just the selected one) — switching mode after a load keeps sane values.
    mode_params: dict = field(default_factory=dict)
    auto_stop_fracture: bool = True       # auto-halt the pull on load collapse
    notes: str = ""

    def path(self, directory=RECIPES_DIR):
        return os.path.join(directory, _slug(self.name) + ".json")

    def save(self, directory=RECIPES_DIR):
        p = self.path(directory)
        os.makedirs(directory, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        return p

    @classmethod
    def from_dict(cls, d):
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def _slug(name):
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name).strip()) or "recipe"


def list_recipes(directory=RECIPES_DIR):
    """All recipes in the folder, sorted by name (empty list if the folder is missing)."""
    if not os.path.isdir(directory):
        return []
    out = []
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".json"):
            try:
                out.append(TestRecipe.load(os.path.join(directory, fn)))
            except Exception:
                continue
    return sorted(out, key=lambda r: r.name.lower())


def find(name, directory=RECIPES_DIR):
    """Find a recipe by exact name or slug (case-insensitive)."""
    s = _slug(name).lower()
    for r in list_recipes(directory):
        if r.name.lower() == str(name).lower() or _slug(r.name).lower() == s:
            return r
    return None


DEFAULT = "Default"

# Superseded 2026-08-12 by the single "Default" profile below. Kept only so ensure_default() can
# recognise and retire the files it wrote in earlier sessions.
_RETIRED_DEFAULTS = ("Default 100% infill", "Default 50% infill")

# Back-compat alias: main.py and older code referred to the 100 % starter by name.
DEFAULT_100 = DEFAULT


def _starter_recipes():
    """The one profile the app always offers.

    Was two (100 % and 50 % infill). One is enough: infill is a LABEL that enters no calculation,
    and every force parameter here is a starting point the operator adjusts per specimen anyway —
    two near-identical profiles just meant two things to keep in sync and one more decision at the
    start of a test. Carries params for EVERY mode, so switching Test type after a Load gives sane
    values rather than leftovers from whatever was loaded before.

    Force parameters are sized for a 100 % infill specimen (fractures near 3.2-3.4 kN). On a 50 %
    specimen (~1.4 kN tared) they are conservative: the fracture protocols simply take more levels
    to get there, which costs time, not a specimen.
    """
    common = dict(material="PLA", specimen_mode="White", area_mm2=80.0, gauge_mm=80.0,
                  test_speed_mm_s=0.1, mode="manual", strain_rate=0.0005, auto_stop_fracture=True)
    return [
        TestRecipe(
            name=DEFAULT, infill_pct=100.0, preload_N=300.0, **common,
            mode_params={
                "Cyclic": {"low": 200.0, "high": 1500.0, "cycles": 5, "speed": 0.1,
                           "waveform": "Sine"},
                "Staircase": {"start": 500.0, "step": 400.0, "levels": 4, "dwell": 30.0,
                              "speed": 0.1, "ramp": "Smooth"},
                "Relaxation": {"strain": 0.004, "duration": 120.0, "speed": 0.1},
                "Creep": {"load": 1200.0, "duration": 120.0, "speed": 0.1},
                "Staircase → FRACTURE": {"start": 500.0, "step": 300.0, "dwell": 10.0,
                                         "speed": 0.1, "ramp": "Smooth"},
                "Progressive cyclic → FRACTURE": {"first_peak": 600.0, "peak_step": 300.0,
                                                  "unload_to": 200.0, "speed": 0.1},
            },
            notes="Starter profile. Preload 300 N, infill label 100 %. Non-destructive modes stay "
                  "well below yield; fracture protocols step to ~3.2 kN in ~10 levels/cycles. "
                  "WARNING: a thermally derated session can stall before a 100 % infill specimen "
                  "fractures (T7 on S20 stalled at 2355 N tared) — let the motor cool, or run a "
                  "50 % specimen. Adjust the forces to the specimen before a destructive run."),
    ]


def ensure_default(directory=RECIPES_DIR):
    """Guarantee the starter profile exists, and retire the two it replaced.

    Idempotent, and a profile the operator has customised under a different name is untouched. The
    two old starters ARE deleted: they were written by the app, not by the operator, and leaving
    them would defeat the point of collapsing to one."""
    for old in _RETIRED_DEFAULTS:
        try:
            path = os.path.join(directory, _slug(old) + ".json")
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass                                  # a stale starter is cosmetic; never block startup
    r = _starter_recipes()[0]
    cur = find(r.name, directory)
    if cur is None:
        r.save(directory)
        cur = r
    return cur


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    if args and args[0] == "show" and len(args) > 1:
        r = find(args[1])
        print(json.dumps(asdict(r), indent=2, ensure_ascii=False) if r else "not found")
        return 0
    rs = list_recipes()
    print(f"{len(rs)} recipe(s) in {RECIPES_DIR}:")
    for r in rs:
        print(f"  • {r.name}: {r.infill_pct:.0f}% infill · preload {r.preload_N:.0f} N · "
              f"{r.test_speed_mm_s:.3f} mm/s · mode={r.mode} · DIC={r.specimen_mode}")
        p = r.mode_params.get(r.mode) if isinstance(r.mode_params, dict) else None
        if p:
            print("      " + " · ".join(f"{k}={v}" for k, v in p.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
