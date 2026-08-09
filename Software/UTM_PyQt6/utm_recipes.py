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


def ensure_default(directory=RECIPES_DIR):
    """Guarantee a 'Default' settings profile exists (created from the dataclass defaults if
    missing). The dropdown then always has at least 'Default'; users Save... their own on top.
    Idempotent — if the user has customised 'Default', it is left untouched."""
    d = find("Default", directory)
    if d is None:
        d = TestRecipe(name="Default", notes="Baseline setup — Save... your own settings on top.")
        d.save(directory)
    return d


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
