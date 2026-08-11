# UTM DIC — Innovation & Automation Roadmap

Status of the "smart UTM" features (automated test modes, live DIC, one-click workflow, safety).
Living source of truth; the V6a deck's roadmap slides are generated to match this.

**Legend:** ✅ done + **rig-validated** · 🟢 built (offline/sim-validated) · 🟡 partial / in progress · ⬜ planned · 🔴 blocked by hardware

_Last updated: 2026-07-29 — full rig-test campaign complete (see `TESTING_TODO.md`)._

---

## 1. Implemented & validated

### Shared foundations (offline modules, tracked in git)
| Feature | Module | Status | Evidence |
|---|---|---|---|
| Shared analysis library (E, σ_y, UTS, ε_f, toughness, anchor, fracture detector) | `utm_analysis.py` | ✅ | Reproduces V5/V6 deck numbers (UTS 46.2 / E 2.60 etc.) |
| Closed-loop control engine (Force/Strain-rate/Cyclic/Staircase/Relaxation/Creep policies + sim) | `control_policies.py`, `control_sim.py` | 🟢 | 9/9 sim checks pass |
| Recipes / settings (save + reload test setups, always-present Default) | `utm_recipes.py` | ✅ | Round-trip verified on the rig |
| Test registry (one queryable index of every test + anchor) | `utm_registry.py`, `registry.json` | ✅ | Seeded 8.6.20 tests; S16 added |
| One-click per-specimen report (PDF + PNGs) | `utm_report.py` | ✅ | Every KPI verified vs CSV (S16) |
| Live-DIC helpers (health + multi-marker geometry) | `utm_dic.py` | 🟢 | Self-tested (ν=0.35 recovered) |

### App features (in `main.py`, snapshot `a3b187f`) — all rig-validated
- **DIC health HUD** — OK/WARN/BAD badge (markers · tracking % · jitter) on both test tabs.
- **Prepare specimen** — one-button tare (position + force + DIC), clears consoles + stress-strain plot; DIC tares only at green 2/2.
- **Settings** — Load / Save… + always-present **Default** (auto-stop ON), infill label.
- **Generate report** — one button → PDF + PNGs.
- **Release preload** — controlled return to ~0 N.
- **Fracture test** button — checklist → arm auto-stop → tension pull → auto-stop at fracture.
- **Auto-stop at fracture** — live load-collapse detector on a manual pull.
- **Strain-rate fracture test** — closed-loop constant *gauge* strain rate → fracture → auto-stop.
- **Safety net (3 layers):** load-collapse fracture detector · **stall guard** (crosshead frozen <0.05 mm/6 s under load — in BOTH the auto-stop path and the strain-rate loop) · **10 kN / 30 mm** force/travel backstop · **dead-DIC guard** (freeze speed at 0.2 s, halt at 1.0 s).
- **CSV richness** — `DIC_Blobs` health column + `# DIC Health` header + infill label.

### Rig-validation highlights (2026-07-28/29)
- **S16** — first successful 100 % infill fracture: UTS 47.4 MPa (anchor-corrected), auto-stop caught it, stall guard correctly silent through the ductile draw.
- **#6.1** — dead-DIC guard fires on marker loss; staged freeze/halt tuned (T2/T3: overshoot 518 → 175 N).
- **#6.2** — strain-rate to fracture on a 50 % specimen: **held 0.00051 /s vs 0.0005 target** while the crosshead **auto-adapted 0.10 → 0.05 mm/s** (fast in stiff elastic, slow in necking) = true constant-strain-rate control; fractured (UTS 17.3 MPa nominal), auto-stopped on load collapse.
- **3 rig facts resolved:** Stop holds position · direct reversal auto-decels ~1 s · travel cap 30 mm.

---

## 2. Partial / in progress
- 🟡 **Closed-loop test modes (Phase B):** strain-rate ✅ done & validated. The other four — **cyclic, staircase, relaxation, creep** — are **🟢 WIRED** ("Advanced test modes" segment: enable checkbox → Test-type dropdown + per-mode settings + **?** help diagram + Start test), sharing the same `_policy_step` loop + safety net. `_policy_step` drives **tension / compression / hold** with **phase-aware guards** (stall guard silent during an intentional hold; dead-DIC guard only for DIC-steered modes) + adaptive timeout.
  - ✅ **Rig-validated 2026-08-08 (scrap #1, 100 % infill):** **creep** (held ~400 N, 80 s) · **relaxation** (ε 0.010 → force decayed 2145→2040 N at fixed strain) · **staircase Linear vs Smooth** (3 levels, 20 s dwells; Smooth cut arrival overshoot **45/47/53 N → 6/5/8 N**). Stall guard silent through all 8 intentional holds. Two overshoot fixes landed (creep + staircase now taper the last 25 % of each approach). See `TESTING_TODO.md` §7.
  - ✅ **Session 3 — cyclic DONE** (T5 Triangle, T6 Sine → T6.3 after the sine/reversal fixes). All six modes are now rig-validated; only the **deck slides** remain (§3a).
- 🟡 **Multi-marker Poisson / true Cauchy:** math ready in `utm_dic.py`; needs a 4-marker specimen preset + camera wiring. Also limited by the current mini-dogbone (narrow gauge, sub-pixel transverse change) → see §4.

---

## 3. Remaining / planned  (checklist)

### 3a. Near-term deliverables  ⭐ next up
- ⬜ **POSTER — "Smart features of the UTM" (one page).** A single visual summary of everything the rig
  now does automatically, for the lab wall / open days / conference. Use the **SF registry in §3c** (SF1–SF14) so poster, deck and roadmap agree. Should cover: DIC health HUD ·
  Prepare specimen · recipes (2 starter profiles) · one-click report · auto-stop at fracture ·
  strain-rate closed loop · the **6 control modes** · the **3-layer safety net** (load-collapse detector ·
  stall guard · 10 kN/30 mm backstop · dead-DIC guard). One proof plot per feature — all of them already
  exist as `feat_*.png` / the new `ui_help/*.png` diagrams. Decide size (A0 vs A1) before laying out.
- 🟡 **DECK — bring `documentation/V6a_8_6_20_slides.pptx` up to current progress.**
  ✅ **SF9 built 2026-08-10 — 15 slides, pages 186-200, deck now 60 slides:** overview of all six modes (real measured signatures, not schematics) · 2 slides per mode (how it works + settings + **software limits**, then results with graphs and tables) · **T7 failure analysis** (why it stalled, ranked causes, mitigations). Numbers are computed by `documentation/sf9_data.py` from the rig CSVs and imported by the generator, so nothing on these slides is transcribed by hand.
  ✅ **Also built 2026-08-10/11 — deck is now 70 slides, pages 141-210:** T7 Vref answer (p200) ·
  two plain-English explainers for the T8 findings (p203/204) · SF3 "what Settings actually saves"
  (p205) · datasheet comparison rebuilt on the add:north TDS (p206) · two reference pages on strain
  and stress conventions (p209/210). `feat_dic_halt.png` regenerated from its CSV — it had no
  generator in the repo. Page numbers moved bottom-right (they were printing under the footer).
  ⬜ **Still to slide:**
  - ~~The 6 control modes~~ ✅ SF9
  - ~~Session 1–2 creep/relaxation/staircase~~ ✅ SF9 (measured overshoot +45.5/+46.8/+52.6 → +6.0/+4.8/+7.8 N)
  - ~~Cyclic T5/T6 → T6.3~~ ✅ SF9 (peak error 71 → 15 N; convergence 528 → 500 N shown)
  - ~~T7.2 staircase→fracture~~ ✅ SF9
  - ~~T8 progressive cyclic→fracture~~ ✅ SF9 (the crosshead-vs-DIC headline is the verdict banner on p198)
  - **Cross-protocol result:** T7.2 21.19 vs T8 21.38 MPa = 0.9 %, stated with the different-specimen
    caveat (that spread contains specimen scatter too; n=2 can't separate them).
  - ~~Motor torque ceiling / T7~~ ✅ SF9 p199 (dedicated failure-analysis slide)
  - **Workflow slides:** recipes (2 starter profiles), destructive-test confirmation, speed-scaled stall guard.
  - **Rebuild the SF grid (slide 169):** it shows only 8 cards and its banner still reads *"Engine ready to add 4 more modes: cyclic · staircase · relaxation · creep"* — those are all done now. Take it to **14 cards from §3c**, grouped built vs planned.
- ⬜ **BLACK-SPECIMEN DIC TEST — rig run, not just research.** Tracked in §5 below; repeated here so it is
  not lost among the reading tasks. Every specimen to date is WHITE; the "Black" DIC preset has never been
  exercised on the rig.

- 🟢 **Wire the control modes into the Motor-Control UI — DONE** ("Advanced test modes" segment, 6 modes incl. the two fracture protocols). ✅ **Recipes now store the mode + every mode's params** (`TestRecipe.mode` + `mode_params`, 2026-08-09) — one `_mode_widget_map()` drives both save and load. ✅ **All 6 modes rig-validated:** creep · relaxation · staircase · cyclic (T6.3) · staircase→fracture (T7.2) · **progressive-cyclic→fracture (T8, 2026-08-09 — 8 clean cycles, no false-fire, 25 % stiffness loss resolved, true UTS 21.38 MPa vs T7.2's 21.19 = 0.9 % apart)**. ⬜ Remaining: **deck slides** — scoped in §3a above.
### 3c. Smart-feature registry (SF numbers) — canonical list

The **SF number is a stable identifier, not a ranking or an ordering**. Numbering is **append-only**:
SF1–SF8 are already printed in the V6a deck (slide 169) and must never be renumbered. Poster, deck and
this file all cite the same numbers.

| SF | Feature | Status |
|---|---|---|
| 1 | DIC health HUD — live 2/2 · tracking % · jitter | ✅ rig-validated |
| 2 | Prepare specimen — one-click tare of position + force + DIC | ✅ rig-validated |
| 3 | Settings save / load (recipes) — reuse a whole setup | ✅ rig-validated |
| 4 | Generate report — one-click PDF + PNGs | ✅ rig-validated |
| 5 | Auto-stop at fracture — halts on load collapse | ✅ rig-validated |
| 6 | Strain-rate fracture test — constant *gauge* dε/dt | ✅ rig-validated |
| 7 | Stall guard — halts a frozen motor under load | ✅ rig-validated |
| 8 | Release load — controlled return through 0 to −preload | ✅ rig-validated |
| **9** | **Advanced test modes** — 6 closed-loop modes: cyclic · staircase · relaxation · creep · staircase→FRACTURE · progressive-cyclic→FRACTURE | ✅ **rig-validated 2026-08-09 (T8 closed the set)** |
| **10** | **Auto-preload** — speed-schedule 0.2→0.1→0.02 mm/s, stops at 1.03× target to offset PLA relaxation | ✅ rig-validated |
| **11** | **Auto-metadata + foldering** + one-click per-specimen deck (`utm_slides.py`) | ⬜ planned |
| **12** | **DIC auto-calibrate** — auto-exposure/threshold sweep · auto-follow ROI through the draw | ⬜ planned |
| **13** | **Guided workflow + live analysis overlay** — wizard · live E / predicted UTS / fracture flag · dashboard + audio cue | ⬜ planned |
| **14** | **Multi-marker Poisson / true Cauchy** — 4-marker preset, live ν | 🔴 hardware-blocked (optics) |

SF1–SF10 are built and rig-validated; SF11–SF14 are planned. **Group the poster by status, not by
number** — the numbers are IDs, so a status-grouped layout reads correctly without renumbering anything.

⚠️ **SF10 (auto-preload) was not in the original SF1–SF8 set** — added here because the poster is meant to
show *all* smart features and auto-preload is a real, validated one that was simply never carded.

- ⬜ **p188 edge-tracking: track MINIMUM width, not the average.** The slide currently specifies
  "average width over 100s of rows". Necking is **local** — averaging over the gauge measures average
  thinning and systematically **under-corrects exactly where the correction matters** (at the neck,
  which is where fracture happens). Change the spec to the minimum width along the gauge before
  building it. Cheap to fix now, expensive after the rig is built. Reasoning on deck p210.

- ✅ **T6.4 / T6.5 / T7.3 DONE 2026-08-11 (S22).** Cyclic near yield validated (12.4 px vs 3.6, loop
  21.7→10.9 kJ/m³, bounds ±1 N) and S22 pulled to fracture: **residual strength −8.5 %** after 15 cycles
  at 79 % of UTS, **12× the 0.7 % virgin baseline spread**. Yield knee moved UP to 811-931 N (virgin 694)
  = load memory at the prior cycling peak. ε_f 3.60 %.
- ⬜ **T6.6 — the clean damage curve.** Fresh 50 % specimen, 400→1100 N, **12 cycles**, sine, 0.100 mm/s,
  ONE continuous run (no pause — E recovers across a rest). Baseline E on **cycle 2**, never cycle 1.
- ⬜ **T9 — creep that actually resolves** (rig run, ~17 min). T1 held 398 N for 40 s at 4.98 MPa and
  saw **nothing**, correctly: the fitted rate was **+0.002 ± 0.060 µε/s**, so the 95 % bound is
  **<0.12 µε/s = under 5 µε across the whole hold**. The hold was ~20× too short and the stress ~2×
  too low — PLA is glassy at room temperature (Tg ≈ 60–63 °C) and barely creeps at 11 % of UTS.
  **Settings: 50 % infill · hold 600 N tared (11.3 MPa = 53 % UTS, 86 % of the 694 N yield knee) ·
  900 s · ramp 0.10 mm/s.** Stay BELOW the yield knee — above it you get tertiary creep running to
  failure, which is a different experiment. A typical 6 % creep strain is ≈450 µε = **20× the
  detection floor**; even 1 % is 3×. **Run a 900 s zero-load baseline first** so thermal drift can be
  separated from creep (over 900 s even 0.05 µε/s of drift is 45 µε). Scoped on deck p196.

- ⬜ **T6.4 — cyclic hysteresis near yield** (rig run, ~6 min). T5/T6.3 cycled at only **14 % of
  fracture load**, so there was almost no hysteresis to measure, and what loop there was got
  fabricated by a **2.1 s reversal lag** (load +97 N while strain −893 µε = backlash being re-taken).
  DIC is NOT the limit — the centroid resolves 0.1 px steps at ±0.02 px noise.
  **Settings: 50 % infill · Low 400 N · High 1100 N · 8 cycles · Sine · 0.10 mm/s.**
  The **400 N floor is the point** — never unload through the slack band, so backlash is crossed once
  at the start instead of twice every cycle. Gives a **13.1 px strain loop (3.6× T6.3)**; peak is 79 %
  of fracture and 58 % above the 694 N yield knee, so loop area should GROW cycle-to-cycle if damage
  accumulates. Arm auto-stop (T8 fractured at 1397 N). Scoped on deck p189.

### 3b. Longer-range features
- ✅ **Strain nomenclature settled (2026-08-11).** Everything user-facing now says **engineering**
  (ΔL/L₀): report axes, live plot legend, the strain-source dropdown and the `Eng ε:` readout. The
  dropdown branches on a stable `userData` key instead of display text — it was matching on the
  visible string, so a rename would have silently plotted the wrong array. **CSV columns
  `DIC_Cauchy`/`DIC_True` deliberately unchanged** (every past test and `utm_analysis` read them);
  the tooltip documents the mapping. See [[reference_addnorth_tds]] and deck p209.
- ⬜ **Multi-marker Poisson** — 4-marker preset in the dropdown, `detect_blobs`/`tare_dic`/`calculate_dic_strain` for 4 markers, new CSV columns (lateral strain / ν / current area / Cauchy), live ν readout. Needs a matte-black backdrop and/or a gauge-zoomed camera.
- ⬜ **Phase D — UX layer:** guided Connect→Calibrate→Mount→Prepare→Recipe→Run→Save wizard; live analysis overlay (live E / predicted UTS / fracture flag); glanceable dashboard + audio cue on fracture; event-annotation hotkey.
- ⬜ **DIC auto-calibrate (Phase C remainder):** auto-exposure/threshold sweep on Start Camera; auto-follow ROI (shift offset to keep markers centred through ductile draw).
- ⬜ **Auto-metadata + foldering** and **one-click per-specimen deck** (extract pptx builders → `utm_slides.py`).
- ⬜ **Deferred script migration:** `v6a_plots.py` / `v6a_analyze.py` → shared `utm_analysis` (when it grows a live-plotting return).

### Repo / version-control housekeeping
- ✅ **App source fully version-controlled (2026-08-09).** The 7 missing modules are now tracked: `camera_manager.py`, `serial_manager.py`, `camera_setup.py`, `roi_tool.py`, `widgets.py`, `build_exe.py`, `requirements.txt`. Verified every module the app imports is in git (the first pass walked only `.py` and missed the `.ui` file — see below). `requirements.txt` was also wrong — **opencv-python** and **pypylon** were missing entirely (the app could not be installed from it) and **scipy** was listed but unused; each entry now names the modules that need it. `main.py` stays uncommitted between explicit named snapshots, by choice.
- ✅ **`.gitignore` completed (2026-08-09).** Extended for the scratch artifacts that were burying real changes: debug frames (`binary_*.png`, `live_frame`, `test_*.png`, `utm_annotated`), output dirs (`full_frame_output/`, `setup_output/`, `test_images/`), the rig data folders (`8.6.3/`, `8.7/`, `8.6.20 …/`) and session video/photos. **Targeted patterns, not a blanket `*.png`**, so the `ui_help/` diagrams and the deck plots stay tracked (verified with `git check-ignore`). `git status` under `Software/UTM_PyQt6` went **36 untracked → 0**.
- ⬜ **`main.py` snapshot commit.** `main.py` is deliberately left uncommitted between explicit named snapshots (last: `a3b187f`, 2026-07-29). Since then it has accumulated a lot of unversioned work — advanced-mode UI (6 modes incl. both fracture protocols) · recipe mode/params wiring · speed-scaled stall guard · finer SetSpeed deadband · Release-load-to-true-zero (0.20 mm/s) · Prepare clears both plots · destructive-test confirm dialog w/ specimen echo · policy-log summary printer. **Take a snapshot when the current test campaign settles** (after T8 + deck).
- ⚠️ **Caught while doing this:** `ui/utm_mainwindow.ui` (53 KB Qt Designer file) was **untracked** — `main.py:48` does `uic.loadUi(...)` on it and `build_exe.py` bundles it via `--add-data`, so **a fresh clone could not have started the app**. Now tracked, along with the camera/DIC diagnostic scripts, the phase-8.6 validation suite and the `COMMANDS.txt` / `RECALIBRATE_ROI.md` docs.

---

## 4. Hardware constraints (not software — track separately)
- 🔴 **Motor torque ceiling is VARIABLE — normally 3.2–3.4 kN, degrading to ~2.6 kN on a bad session.** Measured peaks in `8.6.20/`: **S16 3374.6 · V6a 3350.7 · V6c 3275.0 · V6d 3218.4 · V6e 3162.2 · V6b 3109.7 N** — six 100 % infill specimens over 3.1 kN, **all fractured successfully**. So 100 % full-area fracture is **NOT** blocked in general; it only fails in a degraded session (S15 2593 N; 2026-08-09 **T7 on S20 stalled at 2355 N tared ≈ 2655 N absolute** — an earlier note here said 1888 N/2190 N, which was a mid-run screenshot reading, not the peak; corrected from the CSV). Torque-capacity issue, **not** speed or the strain-rate mode. Suspects in order: stepper **driver current (Vref)**, **driver thermal derating**, **PSU voltage sag under load**, mechanical binding.
  - ⚠️ **Raising Vref is NOT a software change today.** The firmware drives the motors with **STEP/DIR/ENABLE only** — no SPI, no UART, no TMCStepper library — so nothing in `main.py` or the firmware can alter motor current. It is a physical adjustment on the driver board.
  - 🟢 **But it COULD be.** The drivers are **MKS TMC2160_57** — SPI Trinamic parts. Wiring CS/SCK/MOSI/MISO to the ESP32 would allow setting run current in code (`GLOBALSCALER` + `IRUN`) and **reading `DRV_STATUS` (otpw/ot) and StallGuard** — turning the thermal-derating theory into a logged channel instead of an inference. Deck p200.
  - **Drivetrain is not the limit:** 2 × 1.85 Nm × 20:1 into a 5 mm lead gives **≥12.5 kN even at a pessimistic 15 % screw efficiency = 3.4× the 3.7 kN needed**, yet T7 stopped at 72 %. A mechanical-sizing explanation does not survive that arithmetic; an electrical one does. Practical workaround on a weak day: **50 % specimens** (fracture ≈1.7 kN true). See `TEST_FAILURES.md` (S15) and memory `project_motor_stall_limit`.
  - ⚠️ Earlier revisions of this file (and the app help text) quoted a flat "~2.6 kN ceiling" and claimed 100 % infill needed a reduced cross-section — **that was wrong**, contradicted by the six peaks above. Corrected 2026-08-09.
- ⚠️ **Multi-marker transverse Poisson** infeasible on the current mini-dogbone (gauge too narrow for a transverse pair; elastic width change sub-pixel at ~20 px/mm). Needs a gauge-zoomed camera + dark backdrop, or a dedicated extensometer.

---

## 5. Research & documentation to-dos
- ⬜ **Chacón reference — measurement basis:** confirm whether Chacón et al. measured PLA properties on a **printed specimen** or on **raw filament / bulk material** — decides whether our (infill-corrected) values are directly comparable.
- ⬜ **Moisture effect:** check whether specimen / ambient **moisture** shifts strength or stiffness vs literature (PLA is mildly hygroscopic) — dry / condition specimens and compare.
- ⬜ **Camera-parameter sensitivity:** enumerate every camera parameter controlled in software (exposure, gain, threshold, ROI, px/mm, …) and study how varying each affects the DIC results and the **noise floor**.
- ⬜ **Black-specimen DIC check (100% infill):** every specimen tested so far is WHITE (black dots, DIC "White" mode). Print/mark a **BLACK** specimen (white dots, DIC "Black" mode) and confirm the camera tracks strain just as reliably. **Done = ** a full pull with 2/2 markers held to fracture, tracking % and L_px jitter no worse than a white specimen, and E/UTS within the white-specimen scatter. Needs a `camera_setup.py --mode white` pre-flight (the flag names the DOT colour, not the body). Also unblocks the matte-black backdrop that multi-marker Poisson wants (§3).
- ⬜ **UTM instruction manual (for students):** short, crisp usage guide with clear photos of the rig + UI screenshots — Connect → Calibrate → Mount → Prepare → Run → Save → Report.

---

## 6. Key files
- **App:** `main.py` (control loop, live hook `on_load_cell_data`, CSV export, UI).
- **Engine/analysis:** `utm_analysis.py`, `control_policies.py`, `control_sim.py`, `utm_dic.py`.
- **Workflow/data:** `utm_recipes.py` + `recipes/`, `utm_registry.py` + `registry.json`, `utm_report.py`.
- **Records:** `TESTING_TODO.md` (test checklist), `TEST_FAILURES.md` (S15 stall), this file.
