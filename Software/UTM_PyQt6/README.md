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
| `tests/` | camera and phase-8.6 test scripts |
| `docs/` | ROADMAP, TESTING_TODO, TEST_FAILURES, RECALIBRATE_ROI, COMMANDS |
| `ui/` · `ui_help/` | Qt Designer `.ui` files and the mode-help HTML |
| `recipes/` | saved settings profiles (seeded on first launch) |
| `diagnostics/` | images and video the tools write. Gitignored — pure scratch |
| `captures/` · `setup_output/` · `full_frame_output/` · `test_images/` | script output, gitignored |
| `8.6.20 - …/` · `8.6.3/` · `CSV files/` · `SF9 - …/` | test data |

## Running anything in `tools/` or `tests/`

From **this** directory, not from inside the subfolder:

```
cd Software/UTM_PyQt6
python tools/dic_replay.py
```

Their data and output paths are relative to this directory, and the ones that import app modules
carry a two-line header putting the parent on `sys.path`.

## Test data stays where it is

The data folders are **not** filed under a common parent, deliberately. `registry.json` records
each test by path, and the deck builders in `documentation/` read those same paths; moving the
folders would invalidate a committed record of every test ever run, for a tidiness gain in
directories that are gitignored anyway.
