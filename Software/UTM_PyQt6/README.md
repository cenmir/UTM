# Software/UTM_PyQt6/

The UTM DIC application. `python main.py` from **this** directory starts it.

## Why the modules are flat

The 15 `.py` files beside `main.py` are the application. They import each other by bare module
name — `from camera_manager import CameraManager` — so they have to sit together on the path.
That is why they were left loose when everything else was filed away in 2026-08-25: putting them
in a subfolder would mean turning the app into a package and rewriting every import, which is a
different job with a different risk.

| module | role |
|---|---|
| `main.py` | the window, the control loop, the CSV writer |
| `camera_manager.py` | Basler capture, blob detection, DIC strain |
| `serial_manager.py` | the link to the rig firmware |
| `control_policies.py` | closed-loop test modes (strain rate, cyclic, staircase, …) |
| `utm_analysis.py` | the shared analyser: E, σ_y, UTS, ε_f, force anchor, fracture detection |
| `utm_registry.py` · `utm_report.py` | the test registry and the one-click per-test report |
| `utm_recipes.py` | saved settings profiles (`recipes/`) — Default, TPU |
| `utm_capture.py` · `utm_capdlg.py` | frame/video capture and its setup dialog |
| `utm_camdlg.py` · `utm_autocal.py` | DIC camera setup and auto-calibration |
| `utm_dic.py` · `utm_wizard.py` | DIC health readout and the guided wizard |
| `theme.py` · `widgets.py` | look and custom controls |

## Folders

| folder | what |
|---|---|
| `tools/` | diagnostic and build scripts — ROI picker, blob checker, DIC replay, exe build |
| `tests script/` | camera and phase-8.6 test scripts |
| `docs/` | ROADMAP, TESTING_TODO, TEST_FAILURES, RECALIBRATE_ROI, COMMANDS |
| `ui/` | the Qt Designer `.ui` file, and `ui/help/` — the mode-help images |
| `recipes/` | saved settings profiles, seeded on first launch (Default, TPU) |
| `output/` | everything the app and its tools WRITE: `captures/`, `diagnostics/`, `setup_output/`, `full_frame_output/`, `test_images/`. Gitignored in one line |
| `Test data/` | every test CSV and its per-specimen folder — see below |

`CAPTURE_ROOT`, the `.ui` path, `ui/help` and `RECIPES_DIR` are all built from `__file__`, so they
follow the module — but they do NOT follow a folder that moves underneath them. A wrong one does
not raise; it points at a directory that is not there, and the symptom is a capture that never
appears or a help image that is blank. If you move any of these, check
`main.py` (`UI_FILE`, `CAPTURE_ROOT`, the `ui/help` lookup) and `utm_recipes.RECIPES_DIR`.

## Running anything in `tools/` or `tests script/`

From **this** directory, not from inside the subfolder:

```
cd Software/UTM_PyQt6
python tools/dic_replay.py
```

Their data and output paths are relative to this directory, and the ones that import app modules
carry a two-line header putting the parent on `sys.path`.

## Test data

Everything lives under **`Test data/`**, in two folders:

| folder | what | registry rows |
|---|---|---|
| `Test data/8.6.20 - Tensile test to Failure/` | the tensile-to-fracture campaign — one folder per specimen (`Specimen_S<n>_…`), each holding the CSV, its generated report/plots, and the frame-capture folder if the run recorded one | 27 |
| `Test data/Smart Features - Advanced Test Modes/` | the closed-loop protocol runs (cyclic, staircase, relaxation, creep) plus the older `8.6.3/` set | 7 |

They were gathered under one parent in the 2026-08 reorganisation; before that they sat loose in
this directory. **`registry.json` records every test by path**, and the deck builders in
`documentation/` read those same paths, so a move here invalidates both. Both were repointed at
the time, and the check is one line:

Run it **from the repository root**, not from this directory — the paths in `registry.json` are
stored relative to the root, so from here every one of them looks missing:

```
python -c "import json,os; r=json.load(open('Software/UTM_PyQt6/registry.json')); print(sum(1 for x in r if not os.path.isfile(x['csv'])),'unresolved of',len(r))"
```

That must print `0 unresolved`. If it does not, repoint by searching for each CSV's **basename**
rather than assuming where the folder went — specimen folders get renamed too (S37's gained a
`_Video15` suffix after its run, which broke its row and a hard-coded path in the deck scripts).

**The CSVs themselves are gitignored** (`*.csv`), as are the capture folders (`**/frames*/`,
`*.avi`, `*.mkv`, `*.tif`) — one specimen's stills run to 1.7 GB, and the tree as a whole is 54 GB.
What IS committed per specimen is the small stuff: `run.json`, the generated report PDF/PNGs, and
photographs. So the folder structure is in git while the bulk data stays local.
