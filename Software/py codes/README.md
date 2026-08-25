# Software/py codes/

Standalone analysis and plotting scripts, one per test series. These sat loose in the repository
root until 2026-08-25.

They are **scripts, not a package** — nothing imports anything else here, so each one can be read
and run on its own.

## Run them from the REPOSITORY ROOT

Every data and figure path inside these files is written relative to the repo root, e.g.
`"Software/UTM_PyQt6/UTM_Test_20260604_110050_V2_Tension_T0.csv"` and
`"images/V6a/V6a_stress_strain.png"`. That was true when they lived in the root and it is still
true now — moving the file did not move the working directory they expect.

```
cd  <repo root>
python "Software/py codes/v6_compare.py"
```

Running one from inside this folder will fail on the first data file it opens.

`v6_compare.py`, `v6_fracture_montage.py` and `v6_quintet_plots.py` additionally locate
`Software/UTM_PyQt6` from `__file__` in order to import `utm_analysis`; those paths were adjusted
for the new depth when the files moved.

## What is here

| script | series |
|---|---|
| `stress_strain_8_6_19.py`, `staircase_analysis.py`, `staircase_engaged_analysis.py` | 8.6.19 staircase |
| `v4b_v4c_slope_plot.py`, `v4b_vs_v4c_compare.py` | V4b / V4c linearity |
| `v5_full_analysis.py`, `v5_v5b_compare.py`, `v5abc_compare.py` | V5 and the V5a/b/c set |
| `v6_compare.py`, `v6_quintet_plots.py`, `v6_fracture_montage.py` | V6 quintet |
| `v6a_analyze.py`, `v6a_plots.py`, `v6a_epla_offset.py`, `v6a_offset_window.py` | V6a 100 % infill |
| `tensile_failure_analysis.py`, `peak_strain_extraction.py`, `preload_schedule.py`, `generate_report.py` | general-purpose |

`staircase_analysis.py` expects a CSV as its argument and exits 1 with a usage message without one.
That is by design, not a broken path.

## Related

- `documentation/*.py` — the slide builders, which have their own conventions and are run the same
  way, from the repository root.
- `Software/UTM_PyQt6/utm_analysis.py` — the shared analyser these scripts increasingly defer to.
  `v6a_plots.py` and `v6a_analyze.py` have not been migrated to it yet; see `ROADMAP.md`.
