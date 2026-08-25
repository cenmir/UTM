# documentation/

The slide decks, the figures in them, and the code that builds both.

| folder | what |
|---|---|
| `scripts/` | 36 Python files — 16 deck builders and 20 data/plot modules they import |
| `figures/` | every figure the builders read or write |
| `decks/` | the built `.pptx` and the reference `.pdf`s |
| `posters/` | poster artwork |

## Run the builders from the REPOSITORY ROOT

```
cd  <repo root>
python documentation/scripts/generate_v6a_slides.py
```

Each builder `chdir`s to the repo root itself, so it works from anywhere — but its output lands
relative to that root, which is where the paths in this repo are all written from.

Nothing in `scripts/` is a package. The builders import the data modules by bare name
(`import petg_data as PD`), which works because Python puts the running script's own directory on
the path, and they all live together. Keep them together.

## A missing figure does NOT fail the build

`pic_or_ph()` substitutes a placeholder box for an image it cannot find, so a broken path produces
a deck that builds cleanly, reports the right slide count, and is quietly wrong. **After moving or
renaming anything, rebuild and compare the PICTURE count**, not just the slide count:

```
python -c "from pptx import Presentation as P; d=P('documentation/decks/V6a_8_6_20_slides.pptx'); \
print(len(d.slides._sldIdLst),'slides', sum(1 for s in d.slides for sh in s.shapes if sh.shape_type==13),'pictures')"
```

Known-good counts at the time of writing:

| deck | slides | pictures |
|---|---|---|
| `V6a_8_6_20_slides.pptx` | 125 | 90 |
| `V2_capture_validation.pptx` | 11 | 8 |
| `V5_8_6_20_slides.pptx` | 9 | 5 |
| `V5abc_comparison_slides.pptx` | 7 | 5 |
| `E_modulus_explained.pptx` | 5 | 5 |
| `V4_8_6_3_slides.pptx` | 5 | 1 |

## Two traps worth knowing

**Paths are built three different ways.** Some modules hop from `__file__` to the repo root, some
prefix a folder constant onto a bare filename (`FROOT + r"\Specimen_S4\S4.jpg"`,
`os.path.join("documentation", "figures", name)`), and some rely on the working directory. A
search-and-replace that rewrites a *bare filename* into a full path will silently double any
prefix that was already there. Rebuild and check picture counts.

**Long paths.** This repo sits under a deep OneDrive path. An un-normalised
`.../scripts/../../Software/...` can exceed Windows' 260-character limit and fail to open a file
that is plainly there. The root/APP constants are wrapped in `os.path.abspath()` for that reason —
keep it that way.
