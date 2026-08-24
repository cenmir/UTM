# UTM DIC — Innovation & Automation Roadmap

Status of the "smart UTM" features (automated test modes, live DIC, one-click workflow, safety).
Living source of truth; the V6a deck's roadmap slides are generated to match this.

**Legend:** ✅ done + **rig-validated** · 🟢 built (offline/sim-validated) · 🟡 partial / in progress · ⬜ planned · 🔴 blocked by hardware

_Last updated: 2026-08-21 — MOT extensometer comparison analysed, the Black preset moved off Otsu
to a fixed threshold, two pair-plausibility guards added, and the motor "torque ceiling" resolved as
a misalignment; deck now pages 141-247 (107 slides). Earlier milestones: 2026-08-18 S13 + S27/S28 +
the E fit window + SF13; 2026-08-11 T6.5 + T9; 2026-07-29 full rig-test campaign._

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
- **Release load — TWO depths** (2026-08-13). The reading is tared at the preload, so tared 0 N and
  true 0 N are ~300 N apart on this rig and "release" means two different things:
  **Release to preload** stops at tared ~0 N (test load gone, preload STILL on — the specimen stays
  mounted and tensioned for the next run), **Release fully** drives on to −(tared-away) = true zero
  so the specimen can be unclamped. One shared loop and one shared safety net (rise cap · relative
  compression floor · timeout); only the target differs.
  **Two buttons, deliberately not a tickbox:** the depth decides how far a motor travels toward
  compression, so it must be named on the control being pressed rather than held in state set
  minutes earlier. Mid-release the pressed button becomes *Cancel release* and the other greys out,
  so there is never a second live motion button. Costs one 26 px row inside the control panel's own
  scroll area — the main page budget is untouched (+11 px headroom either way).
- **Fracture test** button — checklist → arm auto-stop → tension pull → auto-stop at fracture.
- **Auto-stop at fracture** — live load-collapse detector on a manual pull.
- **Strain-rate fracture test** — closed-loop constant *gauge* strain rate → fracture → auto-stop.
- **Safety net (3 layers):** load-collapse fracture detector · **stall guard** (crosshead frozen <0.05 mm/6 s under load — in BOTH the auto-stop path and the strain-rate loop) · **10 kN / 30 mm** force/travel backstop · **dead-DIC guard** (freeze speed at 0.2 s, halt at 1.0 s).
- **CSV richness** — `DIC_Blobs` health column + `# DIC Health` header + infill label.
- **SF12 — DIC auto-calibration + live parameter readout** (2026-08-14). The preset's exposure and
  threshold were chosen once by hand under one set of LEDs; when the lighting drifts they quietly
  stop being right and the first symptom is a ruined test. `utm_autocal.py` scores a frame's
  TRACKABILITY (pure NumPy/OpenCV, no camera or Qt, so it is testable): two blobs is a hard gate,
  then **contrast margin** dominates — how far the markers sit from the cut — because that predicts
  whether tracking SURVIVES a flicker, where the other terms only describe how comfortable it is
  now. Headroom (clipping), area-in-band and circularity make up the rest.
  `Settings ▸ Auto-calibrate DIC…` sweeps exposure × threshold, scores several frames per setting
  (a single frame can look excellent on noise alone), and **proposes** — a dialog with the
  before/after table; Cancel restores the camera exactly. Threshold picks the CENTRE of the widest
  working band, not the peak: a setting with room either side survives a drift, a peak on a cliff
  does not. Measured: the rig's fixed 150 finds **0 blobs** on a dim frame where auto picks 70 and
  succeeds. The sweep is relative to the current exposure, so a badly-wrong start can leave the
  optimum outside the range — a winner at either END is flagged, and re-running converges
  (9 → 25 → 50 ms against a true 60 ms, score 0.00 → 0.92).
  ⚠️ **Session-only** — the preset in `camera_manager.py` is untouched, so a restart returns to the
  hand-set values. Refuses to run mid-capture (would put mixed settings in one recording).
  **Two routes, `Settings ▸ DIC camera setup`:** *Auto-calibrate…* (the sweep) and *Set parameters
  manually…* — a dialog for exposure / threshold / Otsu / area gates / circularity with a **live
  trackability readout** that re-scores the current frame on every keystroke, so you can see whether
  a value tracks before committing. Exposure is pushed to the sensor as you drag it (the feed
  reacts), which is exactly why Cancel restores it. Typing numbers blind is how the preset came to
  be wrong in the first place. Kept as two ACTIONS rather than a Manual/Auto radio pair: a mode
  whose only effect is to open a dialog is not a mode, and a stale radio would claim a state the
  camera is not in.
  Live parameters now show in the **DIC Camera group titles** (`exp 50.0 ms · thr 150 · 35 fps ·
  419×2348 · mean 171`) — free real estate, since the info row is full and the page has ~11 px of
  vertical headroom. Otsu presets read `thr auto (Otsu)`, not a misleading `thr 0`.
- **SF11 — auto-metadata / capture↔CSV link** (2026-08-14). A run left three artefacts with nothing
  joining them: the CSV, the report, and a multi-gigabyte capture folder. Pressing Save now:
  writes `# Capture: <folder>` into the CSV header and `run.json` (csv path, File ID, geometry,
  recording window, app version) into the capture folder, so **either half finds the other**;
  appends the row to `registry.json` (default ON); optionally builds the report (default OFF).
  The capture is matched to the data by **time-window OVERLAP, not recency** — run two tests before
  saving and "most recent" silently attaches the wrong frames to the force data, and a mislabelled
  link is worse than none because it looks authoritative. `utm_analysis.read_meta` parses the new
  key (splitting on the FIRST colon only, or a Windows drive letter truncates the path).
  Registry auto-add self-skips on a non-destructive run — `analyze()` needs a fracture — and says so
  rather than raising. ⬜ Per-specimen FOLDERING is deliberately not included: silently redirecting
  where a file lands is riskier than the typing it saves.
- **GUI responsiveness** (2026-08-13) — the app was spending **~700 ms of every wall-clock second**
  on the single GUI thread, which is what the lag was. Measured, not guessed (`perf_probe.py`):
  one matplotlib redraw of these figures costs **22.5 ms** (14.2 ms of it is the datetime axis), and
  one camera frame costs **5.9 ms** on the GUI thread. Four fixes, none of which touch a measurement:
  - **Hidden tabs no longer redraw.** Only one plot tab is ever on screen, yet both canvases redrew
    every tick — half the plotting was invisible by construction. The dirty flag stays SET so the tab
    catches up when shown (`_on_plot_tab_changed`, deferred one event-loop turn because on the
    tab-changed signal the new page is not visible yet). On the Console tab, plotting cost is zero.
  - **Camera feed throttled to 12 fps.** Every frame is still GRABBED and MEASURED at 35 fps — only
    the picture is throttled. 35 back-to-back frames: **206 ms → 16 ms**.
  - **Centroids ship with the frame** (`frame_ready(ndarray, list)`). The GUI used to re-run
    `detect_blobs` on the frame it had just been handed — a second detection pass, a second
    `blobs_detected`/`error_occurred` per frame (**double-counting every dropout in the health HUD**),
    and a chance to pair markers with the wrong frame once the GUI fell behind. A correctness fix as
    much as a speed one. PyQt truncates args for the 1-arg slots in `camera_setup`/`check_blobs`.
  - **Repeat spam coalesced** — the per-frame `print` now fires on a CHANGE of marker count then at
    most 1 Hz; identical `[Camera Error]` lines collapse to one per second with a repeat count. The
    HUD still sees every frame, so tracking % stays exact. Display-rate default **0.01 s → 0.10 s**
    (it was polling at 100 Hz for data that arrives at 11 Hz).
  - **Net ≈ 700 → 285 ms/s.** ⬜ Remaining lever if it still lags: **blit the live traces** (~22 ms →
    ~2 ms), which needs stepped axis limits so the background cache is not invalidated every sample.
- **Calibrate Px₀ + frozen-reference overlay** (2026-08-12/13) — the DIC zero was previously only
  reachable through *Prepare test*, i.e. **after** preload, which silently discards everything
  already stretched into the specimen (~2500 µε at 300 N = 96× the noise floor). Now an explicit
  **Calibrate Px₀** button freezes the reference before preload, behind a mounted-specimen
  confirmation that turns into a warning above 25 N; *Prepare test* no longer overwrites a Px₀ that
  was captured at a lower load. The live feed then draws **both** marker pairs — frozen in cyan
  (dashed, larger ring, over a **near-black casing**) and live in green (solid) — plus a per-marker
  travel caliper and a `Px0 1665 → now 1725 px (+60)` caption on a filled plate.
  The casing is not decoration: the frozen ring straddles the EDGE of the speckle blob, so one
  stroke crosses near-black and near-white within a few pixels and no flat colour survives it. It
  must OPPOSE the mark — cyan needs a dark casing (a white one, which suited an earlier dark-blue
  trial, washed the travel arrows out against the bright specimen).
  Draw order matters as much as colour: **live first, frozen dashes on top**. Underneath a solid
  green line the frozen line showed only a hairline of colour, which averages to teal at the ~0.4
  display scale; on top, the dash gaps show green and both read fully saturated.
  ⚠️ Cyan is the operator's choice on RIG visibility, and it is the weakest pair against the live
  green on paper: OKLab ΔE×100 worst case across protan/deutan/tritan is **5.1**, vs dark blue 44.5
  · violet 33.9 · magenta 29.3 · royal blue 26.0. Acceptable ONLY because the overlay never relies
  on hue alone — dash pattern and ring **radius** both separate the pairs independently. The radius
  is load-bearing: at the instant of calibration the pairs are exactly concentric, so same-size rings
  would vanish into each other. Makes a bad tare — slack specimen, tare under load, a marker that jumped blobs — visible on
  the feed instead of only in the strain number. Two arrows growing outward = stretch; both pointing
  the same way = the whole field translated (rig slip / camera knock), which strain alone hides.
- **Dark / light theme** (2026-08-12) — **dark is the default**; `View ▸ Appearance` or Ctrl+Shift+D /
  Ctrl+Shift+L, remembered across restarts. `theme.py` holds both palettes. A theme is not just a Qt
  stylesheet: the two embedded matplotlib canvases are plain artists that know nothing about Qt and
  must be restyled explicitly (facecolour, spines, ticks, labels, grid, hover box, crosshairs, traces)
  and redrawn, and the custom-painted `RangeSlider` groove needs its own setter because QSS cannot
  reach a `paintEvent`. LIGHT is deliberately an EMPTY stylesheet — the app's original look — so
  switching back is a true revert rather than a second theme to keep in sync.
  ⚠️ **Not given an SF number, on purpose:** the SF registry tracks TEST capability, not chrome. The
  admission test ("can the operator invoke it?") is necessary but not sufficient — it also has to
  change what the rig can measure or how safely it runs.

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

> ## ▶ NEXT UP — everything above the line was CLEARED on 2026-08-12
>
> **✅ Cleared 2026-08-12** (all verified against the raw CSVs, then re-checked in the rendered files):
> the S22 cycle count (15 → **16**, and now **computed** by `sf9_data.n_cyc_s22` from the load extrema
> so it cannot drift again) · "one rig run" → **two** · the 0.9 % cross-protocol caveat · the stale
> **13/17** KPI tiles (now derived from `N_DONE`) · deck slide 169 rebuilt **8 → 16 cards** ·
> the **infill-label reset** (root-caused and fixed) · the **`main.py` snapshot commit**.
>
> **⬜ Rig time — these need a specimen and the machine; nothing else blocks them:**
> 1. **T6.6, the damage curve.** Fresh 50 % specimen, 400→1100 N, 12 cycles, sine, 0.100 mm/s, ONE
>    uninterrupted run, baseline E on cycle 2. ~40 min. The only route to D = 1 − Eᵢ/E₀.
> 2. **✅ Black-specimen DIC check — CLEARED 2026-08-18 by S13.** Deck **p225–231**. The Black
>    preset had never run on a real specimen; its ROI was still the pre-recalibration crop, too
>    small in both directions to hold a 1665 px marker pair, so a marker was cropped off the sensor
>    before detection ran (`f122259`). With that fixed: markers found on **99.9 %** of frames, noise
>    **11.9 µε against 14.3 µε** for the white pair (17 % QUIETER, common 10 s window), and every
>    mechanical property closer to the white mean than the two white runs are to each other
>    (UTS 0.7 % vs 2.2 %, E 4.5 % vs 17.1 %, ε_f 3.8 % vs 31.6 %). Black is cleared for use.
>    S12 was the first attempt and did not come out; its folder is kept for the record.
>    ▸ n = 1. A second black specimen would turn this into a repeat, but nothing is blocked on it.
> 3. **Live Px₀ overlay — VALIDATE ON THE RIG.** Built and render-checked 2026-08-13 (`db7ad37`)
>    against a synthetic frame only. On a real specimen, confirm: the frozen cyan pair lands on the
>    markers and does not drift; the green pair separates from it as load rises; the caption Δ agrees
>    with the strain readout (Δpx/Px₀ = ε); and the calipers grow OUTWARD rather than both one way.
>    Blocked behind a lighting problem the operator is working on.
>
> 4. **✅ Capture feature — VALIDATED ON THE RIG 2026-08-17** (built 2026-08-13,
>    `18551c4`…`670d630`). Three pulls to fracture with PNG + AVI on: S24 (VC1), S25 (VC2), S26
>    (VC3). S25/S26 gave 3 127 stills and 3 × 3 127 AVI frames across raw/boost/speckle, **0
>    dropped**, 19.9 fps, all four sinks in step, `run.json` → CSV correct, **100 % DIC coverage**,
>    and both videos open ≈0.6 s before the crosshead moves and run 4.6 s past fracture. Replaying
>    every frame through the app's own detector found 2 markers on 99.8 / 99.9 %. Deck p217–222.
>    S24 logged only 27 % DIC coverage — frames all present and distinct, so the loss was in the
>    load↔DIC matching step; it has not recurred and is not currently reproducible.
>
> 5. **✅ S27 / S28 ANALYSED 2026-08-18 — the 50 % infill video pair.** Deck **p232–236**, plus
>    **p237–242** for the deviation and the 50-vs-100 comparison. The pair is the tightest on
>    record: **UTS 19.87 vs 19.91 MPa (0.2 % apart)**, ε_f 4.0/4.2 %, E 1.22/1.26 GPa, both with
>    full capture integrity. **The infill knock-down is confirmed as an infill effect and not an
>    instrument one:** 50 % needs k ≈ 2.4 against literature while 100 % lands at k ≈ 1.05–1.24, on
>    the same rig, the same DIC and now the same E rule. This closes the MOT extensometer
>    prerequisite.
>
> 6. **⬜ WHY DID DIC DELIVERY SLOW? — NARROWED 2026-08-21, still open.** Measured across three
>    runs (filtering `L_px > 100 AND DIC_Time_s > 0`; the uncovered rows carry 0.000, not NaN, and
>    a first pass that missed that produced "7323 s lost in a 95 s run"):
>
>    | run | mode | tracked 2/2 | DISTINCT readings reaching a load row | median gap | gaps > 250 ms | coverage |
>    |---|---|---|---|---|---|---|
>    | S26 | White | 99.9 % | **11.1 Hz** | 100 ms | 0 | **99.9 %** |
>    | S29 | Black | 100 % | 8.9 Hz | 101 ms | 33 (10 % of run) | 78.8 % |
>    | S13 | Black | 99.9 % | **5.3 Hz** | 147 ms | 175 (**51 % of run**) | 47.4 % |
>
>    ▸ **Coverage tracks delivery rate almost exactly**, so the 100 ms matching window is NOT the
>    fault — it is doing its job on readings that never arrive. S26 sits at the ceiling the load
>    sampling allows (~11.4 Hz); the other two are genuinely below it.
>    ▸ **The loss is DOWNSTREAM OF DETECTION.** Camera 19.9 fps with 0 dropped, detector finds two
>    markers on ~100 % of frames, and S29's own `# DIC Loop` header line reads TOTAL 50.2 ms
>    (19.9 Hz) with detect at 1.0 ms. Frames are found and strain is computed; the readings do not
>    reach the consumer.
>    ▸ **Both degraded runs are BLACK-mode, the healthy one is White.** That is the strongest lead
>    and it is only n = 3 — worth confirming on the next Black run before believing it.
>    ▸ Do NOT widen the 100 ms window: it would pair load samples with staler strain and hide this.

> **✅ MOT VIDEO-EXTENSOMETER COMPARISON — ANALYSED 2026-08-20. Deck p245–247.**
>    XT-205, gauge 80.0033 mm, 20 Hz, strain only, stops at 0.401 %. MOT matched our 300 N preload
>    and 0.10 mm/s, and their gauge equals ours, so the strain zero and the rate needed no correction.
>    ▸ **THE RESULT: our DIC is more CONSISTENT.** Residual scatter over the same 0.05–0.35 %
>    interval — RMS **23.5 / 23.6 µε** against the XT-205's **44.9**. But quote it carefully: the
>    XT-205 holds the QUIETEST baseline of the three (median |r| 12 µε vs our 13 and 17) and loses
>    on RMS only through a few large excursions (p95 116 µε vs our 45). Ours is not finer, it is
>    more consistent. Our two runs agree with each other to 0.4 %.
>    ▸ **The rate ratio does NOT test our scale**, and the deck says so: MOT reads 2.21× faster
>    (7.42 vs 2.67/4.06 ×10⁻⁴/s), which is the expected direction because only **19–29 % of our
>    crosshead motion reaches the gauge** and that fraction belongs to the MACHINE.
>    ▸ **⬜ STILL OPEN — ask MOT for their LOAD or CROSSHEAD-DISPLACEMENT channel.** With either,
>    strain can be compared at matched force or matched displacement, which cancels the compliance
>    term and turns this into a real scale check. Cheap to ask, and the only thing left.
>    ▸ Side finding, and the clearest evidence yet on the seating question: **our local strain rate
>    CLIMBS through the ramp while theirs is flat from the moment it engages.** That is why S25 and
>    S26 differ by 52 % on early-strain rate but agree to 1.4 % force-matched. The residual
>    low-strain compliance is the RIG, not PLA non-linearity.
>
> **⬜ NEW CAMPAIGN — PETG and TPU against PLA.** IN PROGRESS.
>    ▸ **REDO S29 FIRST — it produced NO valid properties.** Two tracking faults, both now fixed:
>    attempt 1 tracked at 17 % (Otsu below PETG's window → fixed threshold 149), attempt 2 tracked
>    at 100 % and was still lost when ONE frame in 1222 read the mount holder as a marker and the
>    bogus strain jump tripped the fracture detector AT PEAK LOAD, auto-stopping an intact
>    specimen at 2931 N / 36.6 MPa. Its registry row has the fracture-derived fields nulled.
>    Black tape on the mount edge is still worth adding as belt-and-braces. Everything on record so far is PLA, so every claim the rig
>    makes is single-material; a second and third polymer is what turns "the rig measures PLA" into
>    "the rig measures polymers".
>    ▸ **The question is whether the TREND comes out right**, not just whether the numbers do.
>    Expected ordering, from the datasheets: **PLA stiffest and most brittle** (E ~2.9 GPa, ε_f
>    ~8 %), **PETG less stiff but far more ductile** (E ~1.5–2.1 GPa, ε_f tens of %), **TPU a
>    different class entirely** — elastomeric, E in the low MPa, strain to break in the hundreds of
>    %. If the rig reproduces that ordering it is measuring material, not itself.
>    ▸ **PETG gets a like-for-like reference check**, the same treatment PLA got against the
>    add:north E-PLA TDS: find the TDS for the actual filament used, and compare E / σ_y / UTS /
>    ε_f the same way, with the same infill knock-down caveat. **Log the exact brand, spool and
>    print settings at test time** — the PLA reference only worked because the filament was known.
>    ▸ **Two things to decide before TPU, not after:** (a) ε_f in the hundreds of % will run past the
>    30 mm travel cap and probably out of the DIC field — expect the markers to leave the ROI, so
>    treat TPU as a crosshead-strain test with DIC as a bonus, or shorten the gauge; (b) the
>    load-collapse fracture detector is tuned for a brittle drop — a TPU that draws without ever
>    collapsing may never trigger it, exactly like the ductile 100 % PLA case that made
>    load-collapse the ONLY detector. Check the guard before spending a specimen.
>    ▸ Run them on the post-realignment rig (above), same 0.10 mm/s, same preload discipline, so
>    material is the only variable that moves.
>
> **⬜ Software, in the order I would take it:**
> 7. **✅ SF13 — guided wizard. BUILT 2026-08-18.** `Software/UTM_PyQt6/utm_wizard.py` +
>    View ▸ Guided wizard (Ctrl+Shift+G). **Optional and OFF by default**, at the operator's
>    request: it encodes a real procedure but somebody who knows it does not need a panel reciting
>    it, and a checklist that cannot be dismissed is just a wider warning.
>    It is a VIEW — `steps()` is a pure read of flags that already existed, so it cannot disagree
>    with the app, and an AST check in the suite proves it reaches no control path at all. The one
>    new piece of state is `_prepared_t`, stamped by Prepare test, which was the only step with no
>    durable trace. Nine steps; the Px₀ row is the point of it — under the after-preload convention
>    a Px₀ frozen unloaded shows a warning instead of a tick.
>    Extended the same day at the operator's request: the **data-streams** step (load cell +
>    position gate the run; velocity is reported but never blocks), **"Choose specimen mode"** as an
>    instruction rather than a value, each optional step saying **WHERE** it lives
>    (Settings ▸ Capture settings), and the run step naming all three routes — fracture test, a
>    manual pull, or an advanced mode. Twelve rows, nine of them blocking.
>    ▸ **✅ RIG-VALIDATED 2026-08-21** — the operator confirms the panel works on the machine.
>    ▸ **Auto-calibrate added as an OPTIONAL step 2026-08-22**, between choosing the specimen
>    mode and applying the preload — it needs the camera live and the mode chosen, and nothing
>    after it depends on it. INFO, so it can never gate a test. It reads the live exposure and
>    threshold and says they were **carried over from the last run** until it has been used,
>    because a value measured on a different specimen looks exactly like one measured on this
>    one. `_autocal_t` is stamped on apply, the same durable-trace trick as `_prepared_t`.
> 8. **✅ Registry hygiene — DONE 2026-08-18**, as part of the S27/S28 analysis. **28 → 24 rows**:
>    the duplicate saves of one run (S27 ×2, S28 ×3, S12 ×2) are gone, so no specimen is
>    double-weighted in an average any more; S27/S28 carry `infill_pct = 50` instead of the 100 the
>    infill-label defect wrote after a restart; the video runs carry VC1–VC7 labels; and every row
>    was re-scanned onto the new steepest-run E basis so the file is internally consistent.
> 9. **⬜ DECK — SLIDES FOR THE SMART FEATURES THAT HAVE NONE.** Agreed 2026-08-21. The SF grid now
>    runs SF1–SF19 (**16 rig-validated · 2 built · 1 hardware-blocked**), but five features have no
>    proof slide, and three of them had been sitting on the grid marked "plan" months after
>    shipping. Structure agreed with the operator:
>    ▸ **TWO OVERVIEW SLIDES, ~10 cards each** — SF1–SF10 and SF11–SF19 — so the whole feature set
>    can be walked through without the single dense grid. No images needed; build these first.
>    ▸ **THEN A COUPLE OF SLIDES PER MISSING FEATURE**, with screenshots the OPERATOR supplies:
>
>    | SF | Feature | Status | Screenshots needed from the rig |
>    |---|---|---|---|
>    | 11 | Auto-metadata link (capture ↔ CSV) | ✅ | the `# Capture:` CSV header · a `run.json` · the Save dialog with its registry / report tick-boxes |
>    | 12 | DIC auto-calibration | 🟢 | the auto-calibrate dialog **with its before/after table** · the manual-parameters dialog showing the live trackability readout · ideally a feed at a bad threshold (0 blobs) beside a good one (2/2) |
>    | 13 | Guided wizard | ✅ | the dock open EARLY (Connect is NEXT) and again LATE (most steps ticked) · the View ▸ Guided wizard menu item |
>    | 18 | Live Px₀ overlay | 🟢 | the feed at zero strain and again under load, with the frozen cyan pair and the live green pair separated. **⚠ BLOCKED — this is the same lighting problem holding up the overlay's rig validation, so it is the one item that cannot be shot today** |
>    | 19 | Video + image capture | ✅ | the Capture settings dialog · the CAP / REC indicator lit in the HUD |
>
>    ▸ **SF19's frames need no operator time** — one still from each of the three AVI styles
>    (raw / boost / speckle) can be pulled straight out of the S25/S26/S13 captures already on disk.
>    ▸ **SF19 is the subtle one.** p219–224 already exists but is a DATA-VALIDATION slide
>    ("frame capture, checked against the test data"); there is no slide that explains the FEATURE —
>    PNG + three AVI styles, adaptive speckle, multi-select, 0 dropped at 19.9 fps.
>    ▸ Estimated **12 slides → p248–259**. Overview pair first; the per-feature slides land as the
>    screenshots arrive, so the deck is never blocked on one of them.
>
> 11. **✅ A MATERIAL SETTING OWNS THE STRAIN WINDOW — no per-test edit, nothing to revert.** Added
>    2026-08-24 at the operator's suggestion, twice: first that TPU should not need a constant
>    edited before every run, then — the sharper point — that it did not belong in the DIC
>    camera's specimen-mode dropdown either. **Specimen mode selects optical POLARITY and a TPU
>    specimen can be printed black or white**; bundling the two would have forced every elastomer
>    to be black. So the window moved to a **Material dropdown in Settings, beside Infill**:
>    PLA and PETG keep the tight 0.85–1.25 × Px₀, TPU and `Other` carry 0.85–1.60.
>    ▸ **It fixed a second bug the operator had already paid for by hand.** `utm_registry.py`
>    hard-coded `"material": "PLA"` on every record ever written, and nothing in the UI ever set
>    it — which is how S30, S31 and S32, all PETG, entered the registry labelled PLA. The
>    material now travels CSV header → `read_meta` → registry. Old headers carry no `Material:`
>    line and fall back to PLA, which is what they actually were.
>    ▸ The remembered material is re-applied at startup, so a restart cannot leave an elastomer
>    on PLA's window while the dropdown reads TPU — that failure would have surfaced mid-pull,
>    as a lost-marker abort, on a specimen that was tracking perfectly.
>    ▸ **Why an elastomer needs it:** 1.25 means 25 % strain. PLA breaks at 4–6 % and PETG at
>    8 %, so the window never sees anything but a genuinely impossible pair. TPU reaches the
>    rig's ~34 % travel limit as REAL strain and would have every frame past 25 % rejected as
>    "a marker has been lost" — silently, with the readout simply ceasing to update mid-pull.
>    ▸ **The window is now ASYMMETRIC, which made it stricter as well as looser.** Tension only
>    pulls markers apart, so a separation far BELOW Px₀ is not something a tensile test can
>    produce. Measured over every frame of S13: the LOWER bound fired once (a post-fracture
>    frame at 0.063 × Px₀) and the UPPER bound fired NEVER — and S29's mount swap, the
>    incident these guards exist for, sat at 1.11 × Px₀, inside the old window, caught by the
>    RATE guard instead. So the old symmetric ±25 % implied a 0.75 floor where 0.85 is right.
>    ▸ Both specimen dropdowns now build from `SPECIMEN_PRESETS` instead of two hand-written
>    `["White", "Black"]` lists, so the next preset needs one edit rather than three.
>    ▸ `PAIR_MAX_STEP_PX_PER_S` is untouched and needs no per-material value: an elastomer
>    strains enormously but not instantaneously.
>
> 10. **🟡 REVERT `min_circularity` 0.40 → 0.50 WHEN PETG/TPU ENDS.** Loosened 2026-08-22 for the
>    campaign, in `camera_manager.py` (the Black preset AND the class default, which mirrors it).
>    ▸ **Why it was loosened.** The PETG dots have a crescent of overspray FUSED to the rim. The dot
>    is round; dot-plus-crescent is not. On capture `20260822_174204` marker 2 measures 17 131 px²
>    against a clean dot's 11 140 and scores **0.49–0.51 circularity across the run** — straddling a
>    0.50 gate, so noise flipped it either side frame by frame and 18 % of frames lost it.
>    ▸ **Threshold could not fix it:** NO fixed threshold yields exactly two blobs on those frames.
>    The failure is SHAPE, not brightness. Swept on the real capture, the 2-blob rate went
>    **0.50 → 81.8 %, 0.45 → 100 %, 0.40 → 100 %, 0.25 → 100 %**, with 3+ blobs staying at 0.0 %
>    throughout — so 0.40 is mid-plateau, not a cliff, and admits nothing extra.
>    ▸ **This is a real loosening and must not become permanent.** 0.50 exists to keep grips and
>    fixture edges out, and it earned its place. It is safe here only because the run is short, Px₀
>    is set, and the pair-plausibility guards catch a wrong pair anyway.
>    ▸ **The proper fix is the SPECIMEN, and it should be done before the next batch:** mask around
>    each dot so overspray cannot land touching it, spray lighter from further back, and use MATTE
>    white — marker 2's core blows out to 255 from a specular sheen while its rim stays mid-grey. A
>    clean dot scores **0.76** and needs none of this.
>    ▸ Revert together with the note in `camera_manager.py`, and re-run `black_preset_check` and
>    `petg_tracking_check`.
>
> **✅ The E fit window — DECIDED AND IMPLEMENTED 2026-08-18.** `utm_analysis.analyze()` now
>   reports the **steepest straight run** as `E`, keeping the old fixed-window value beside it as
>   `E_fixed` so no historical number is lost. Registry re-scanned; deck **p223–224** (evidence) and
>   **p237** (what it moved) regenerate from the data. Measured over every run on record:
>
>   | rule for the window | mean E (100 %) | CV 100 % | CV 50 % | vs add:north TDS |
>   |---|---|---|---|---|
>   | ISO fixed 0.05–0.25 % | 2.56 GPa | 17.5 % | — | −10.9 % |
>   | fixed 0.05–0.40 % (the old rule) | 2.67 GPa | 13.2 % | 23.6 % | −7.0 % |
>   | **steepest straight run** | **3.02 GPa** | **8.5 %** | **12.6 %** | **+5.1 %** |
>
>   Scatter fell in BOTH materials, which is the case: a rule chasing noise would have raised it.
>   **UTS, ε_f, toughness and the anchor were verified bit-identical on all 20 runs** — a silent
>   change to UTS would have invalidated the campaign. σ_y moves (the 0.2 % offset line has slope E)
>   by −1.7 % typically and −10.2 % worst; its own scatter improves at 100 % (5.1 → 4.3 %) and is
>   flat at 50 % (7.7 → 8.0 %), so σ_y is unchanged in quality rather than improved.
>
>   Two implementation notes worth keeping: the R² floor is **relative** (within 0.0005 of the
>   straightest the record can offer, capped at 0.999) because an absolute floor alone fell back to
>   the fixed window on the noisier 50 % runs — two rules over one dataset is worse than either;
>   and the window search uses **prefix sums** for O(1) fits, because the naive version took ~5 s
>   per test behind the Generate-report button.
>
>   Still open, and NOT settled by this: whether the low-strain compliance is residual seating or
>   genuine PLA non-linearity. The 50 % pair was expected to help — a seating effect should not
>   scale with infill — but n = 2 per group cannot carry it. Also verify the ISO/ASTM clause numbers
>   against the source standards before publication. Prior art:
>   `documentation/E_modulus_explained.pptx` slide 5 (the original S16 observation).
>
> **✅ MOTOR TORQUE CEILING — RESOLVED 2026-08-12. It was never a torque limit.** The load holders
> had worked loose, letting the crossheads sit out of alignment, so the motor was spending torque on
> binding instead of on the specimen. Re-aligned and re-tightened, the rig pulls **3.5 kN with no
> stutter**. Deck **p183** (root cause) and **p184** (the post-fix register).
>   ▸ The evidence was on disk before the fault was found: the same machine has fractured 100 %
>   infill at **3586–3826 N on 11 specimens** across three months — 11 of 11 straight through a
>   "2.6 kN ceiling". Decisive pair: **S15 stalled at 2.6 kN and S16 fractured at 3792 N on the SAME
>   DAY** (2026-07-28), +46 % on the same rig at the same speed.
>   ▸ Of the four ranked causes on the old T7 slide, the three electrical ones (Vref, thermal
>   derating, PSU sag) are **exonerated** — none of them can be intermittent between two consecutive
>   specimens. The mechanical one, ranked LAST, was it.
>   ▸ **Runs after 2026-08-12 are the reliable set**: S24, S25, S26, S27, S28, S12, S13 — 7 runs,
>   0 stalls, the five 100 % ones peaking 3693–3822 N. Both stalls on record fall before the line.
>   ▸ Still open, and unrelated: wiring the TMC2160's SPI to the ESP32 so motor current and thermal
>   status become a logged channel. Now a nice-to-have for diagnostics, not a blocker (§4).
>
> **✅ Cleared 2026-08-17/18 — GUI and pipeline, all bench-verified offscreen:**
> **Return to 0 mm** gated on SIGNED tension (50 N) instead of magnitude — `abs()` was blocking the
> one state the button exists for, since a fractured specimen reads −(tared away); an obstruction
> guard on the load CHANGE replaces the crash protection `abs()` was incidentally giving (`0ed4f79`)
> · **Generate report** saves into the specimen folder beside the CSV, asks where with that as the
> default, follows a filename you typed, follows an OPENED csv, and no longer nags to save after you
> have saved — that prompt was gated on `data_unsaved`, which every incoming load sample sets
> (`1c32a09`, `414f716`, `c870c28`, `478c194`) · **Tare DIC** is one click, no dialog; Calibrate Px₀
> keeps its confirmation · **Px₀ has exactly ONE owner — Calibrate Px₀** (`949ce20`, `6d41d49`).
> Tare DIC clears the console, the blob history, the measured rates and the strain queue and leaves
> the reference alone; **Prepare test tares DIC readouts + position + force**, reports the Px₀ in
> force and warns when none is set, but never captures one. This reverses `f945bb9` and removes the
> ordering hazard with it — nothing in Prepare touches Px₀, so it can no longer be frozen at 0 N by
> a force tare running first; the dependency now runs the other way (**Calibrate Px₀ BEFORE
> Prepare**) and the tooltip says so · **Black preset ROI** (`f122259`) ·
> **blob disambiguation** — a third qualifying blob no longer discards the frame, and a pairing
> nowhere near Px₀ is reported as a dropout rather than invented (`3f614dc`) · **speckle video
> polarity** rebuilt on specimen-mode change, which would otherwise have written a negative
> (`ef1b74b`) · **preload default 470 → 300 N**, matching what the rig is actually run at
> (`a339904`) · the central `reports/` folder deleted, nothing writes there any more.
>
> **Merge:** done — `snapshot/main-py-2026-08-12` is fully merged into `main` (0 commits behind) and
> `main` is pushed to `github.com/AdithyaSivakumar-3/UTM`.
>
> **✅ Cleared 2026-08-13** — live Px₀ overlay · GUI responsiveness (~700 → ~285 ms/s) · Release
> load split into "to preload" / "fully" · live stress-strain put on the report's basis (dropout
> rows, anchor, % units, downsampler pairing bug) · E-modulus explainer deck (5 slides) · **frame
> capture: PNG + AVI, 3 view styles, adaptive speckle, multi-select, folder choice, size warning** ·
> Px₀ ownership (Prepare test no longer moves it) · a QSettings bool that never restored false.

- ✅ **POSTERS — BUILT 2026-08-12, THREE EDITIONS from one content spec.**
  `documentation/generate_poster.py` → **`documentation/posters/`** (pptx + pdf for each):
  - **`Smart_UTM_poster_A0`** — conference wall poster, 3 columns.
  - **`Smart_UTM_poster_A4`** — conference handout, 2 columns. A genuine condensation, not a shrunken
    A0 (scaling A0 → A4 puts body text at ~5 pt).
  - **`Smart_UTM_progress_A4`** — progress report for a supervisor / manager. Different question,
    different poster: status · milestones · results · **the decisions needed from the reader** · next.
    The "asks" panel is the payload and carries the most visual weight after the headline.
  - **Features run in NUMERIC order SF1 → SF16 on every edition**, as a full-width band UNDER the
    column flow so they read left-to-right in order. They cannot go through the column flow: with 16
    cards it split them so SF7 landed at the top of column 3 while SF1 sat at the bottom of column 2.
    Status is carried by colour + chip instead of by grouping, so a **legend block is mandatory**.
  - **Rig photographs are background-removed cutouts** (`documentation/rig_cutouts.py`), which is why
    two of them can sit side by side without reading as a collage. Model choice matters: the default
    u2net is a salient-object model and keeps the wall and carpet visible THROUGH the frame openings,
    so the rig prints as a solid slab — **isnet-general-use** cuts the openings properly. A 15 px
    morphological close first heals the slender members it otherwise chews through.
  - **Layout follows the researched #evenbetterposter / "Generation-2" billboard format**, not a generic
    grid: attendee studies show 82 % prefer a billboard headline for the main message, but 67 % still
    prefer IMRaD for *rigor* — so METHODS ("How it works") and LIMITATIONS get full panels instead of
    sidebars. Headline: *"One specimen now yields a CURVE, not a point."*
  - Structure: title · billboard · 6-KPI strip · THE MACHINE (photo + labelled schematic) · WHY · HOW IT
    WORKS · 3 EVIDENCE panels with figures · 16 feature cards · LIMITATIONS.
  - **Feature cards carry no figure** — 16 thumbnails swamp even an A0 (first attempt overflowed 153 in
    into 100 in of column). Visual proof lives in the 4 evidence panels.
  - Every number is imported live from `sf9_data.py` + `registry.json`; nothing is typed by hand.
  - New assets: `documentation/feat_prepare_specimen.png` + `feat_release_load.png` (SF2/SF8 had no proof
    figure at all — generated by `documentation/poster_assets.py`); `rig_photo.jpg`, `rig_photo_detail.jpg`,
    `rig_cut_full.png` / `rig_cut_detail.png` (background-removed cutouts of the 2026-08-12 rig
    photos) and `rig_schematic.png`.
  - **SF15/16 added to the registry below** — the test registry and the dead-DIC guard + hard backstops
    were built and validated but had never been carded. (SF17 was added and then RETIRED the same day.)
  - Layout engine notes: text heights are measured against the real Calibri metrics (a character-average
    estimate over-wrapped the 104 pt headline and left 1.5 in of dead space); section headers must be
    measured UPPERCASED because that is how they are drawn; columns are balanced by binary-searching the
    shortest feasible column height, since greedy packing left the last column a third empty.
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

- ⬜ **RECORD THE FRACTURE TEST ON VIDEO — for independent analysis in the extensometer software at MOT.**
  **This is the only INDEPENDENT check of the DIC channel that exists.** Everything validated so far
  checks our DIC against itself or against the crosshead; nothing has ever compared it to a second,
  established strain instrument. If MOT's extensometer software reads the same strain from the same
  footage, the whole DIC chain — px/mm calibration, centroid algorithm, L₀ tare, engineering-strain
  definition — is corroborated from outside. If it does not, we find out before publishing.
  Two parts, and **the software half must land first** — a fracture run is one irreversible shot.
  1. **App — frame capture (does not exist today).** The camera pipeline computes centroids and throws
     the frames away. Add an opt-in **"Record frames"** toggle to the two fracture protocols that saves
     the raw Basler frames as an image sequence (or a low-compression video) next to the CSV, plus a
     sidecar mapping **frame index → PC and MCU timestamps** so any frame ties back to a load sample.
     Reuse the three-timestamp architecture already in the CSV.
     - **Compression is not free:** heavy H.264 destroys the sub-pixel correlation the extensometer
       software depends on. Prefer an image sequence or a lossless/near-lossless codec.
     - **Storage, at the current ROI** (2348 × 419 mono8 ≈ 0.98 MB/frame): ~10 MB/s at 10 fps, ~34 MB/s
       at the camera's 35 fps. A 200 s pull is therefore ~2 GB at 10 fps or ~7 GB at 35 fps. Fine as a
       one-off; do NOT leave it on by default.
     - Confirm the sensor is **global shutter** before relying on the footage — a rolling shutter shears
       a moving specimen and would corrupt the comparison.
  2. **Rig run + cross-check.** Pull one specimen to fracture with recording on, then run the same
     footage through the extensometer software at MOT and overlay its strain trace on ours.
     - Put a **scale reference in the same focal plane** as the specimen (the software needs its own
       px/mm; do not let it inherit ours, or the comparison is circular).
     - Keep the LEDs on and DC-driven — mains flicker aliases against the frame rate.
     - Record the ACTUAL frame rate, not the nominal one.
  **Done =** a fracture run whose footage loads in MOT's software, and a plot of their strain vs ours
  over the same interval with the deviation quoted — ideally within the **26 µε** noise floor in the
  elastic region, and with any divergence past yield explained (their gauge and ours may not span the
  same material).
  *(If this gets carded as a feature it becomes **SF18** — numbering is append-only, see §3c.)*

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
| **15** | **Test registry** — every run auto-indexed with E/σ_y/UTS/ε_f/toughness **and its force anchor** | ✅ rig-validated |
| **16** | **Dead-DIC guard + hard backstops** — freeze speed at 0.2 s of frozen strain, halt at 1.0 s; 10 kN / 30 mm caps | ✅ rig-validated |
| ~~17~~ | ~~Simulate-first harness~~ — **RETIRED 2026-08-12, never publish it as an SF.** It is a DEVELOPER practice, not a rig feature: `control_sim` is imported 0 times by `main.py` and has no serial/camera path, so an operator can never invoke it — and it is the one entry that made "every feature validated on the rig" false, since its 9/9 checks are all against a simulated spring plant. It lives on, correctly, as a METHODS bullet on the posters ("Simulated before hardware"). The number is burnt, not reused: the next feature carded is SF18. | — retired |

SF1–SF10 and SF15–SF16 (**12 features**) are built and rig-validated; SF11–SF13 are planned and SF14
is hardware-blocked. **SF17 was retired** — see the struck row above. **Group the poster by status, not by number** — the numbers are IDs, so a
status-grouped layout reads correctly without renumbering anything.

⚠️ **SF15–SF17 were added 2026-08-12** while building the poster — all three were built and in daily use but had never been carded. **SF17 was then retired the same day**: a card has to be something the OPERATOR uses on the rig, and a developer-only simulation harness is not that. Test for admitting a feature: *can the person running a test invoke it, or does it act on the machine during a run?* If not, it belongs in METHODS, not in the feature registry.

⚠️ **`utm_registry` (SF15) is also not wired into `main.py`** — it is a CLI you run (`scan`/`list`/`add`), not something that fires on save. It stays carded because it is operator/analyst-facing and produces a real artifact, but do NOT describe it as automatic; the automation is SF11, still planned.

⚠️ **SF10 (auto-preload) was not in the original SF1–SF8 set** — added here because the poster is meant to
show *all* smart features and auto-preload is a real, validated one that was simply never carded.

- ⬜ **p188 edge-tracking: track MINIMUM width, not the average.** The slide currently specifies
  "average width over 100s of rows". Necking is **local** — averaging over the gauge measures average
  thinning and systematically **under-corrects exactly where the correction matters** (at the neck,
  which is where fracture happens). Change the spec to the minimum width along the gauge before
  building it. Cheap to fix now, expensive after the rig is built. Reasoning on deck p210.

- ✅ **T6.4 / T6.5 / T7.3 DONE 2026-08-11 (S22).** Cyclic near yield validated: **12.3 px strain
  excursion vs T6.3's 3.6** (p189 predicted 13.1), **6 closed loops**, area **14.2→10.9 kJ/m³** and
  unload E **1.49→1.43 GPa** both falling monotonically at **R² ≥ 0.99**, peaks held to ±3.4 N.
  T6.4 lost the camera at t ≈ 145 s (45 % of frames) so only 3 loops survive there — **T6.5 is the
  slide-ready run**. S22 then pulled to fracture: **residual strength −8.5 % on tared load** after
  **16** cycles (8 in T6.4 + 8 in T6.5) at 79 % of UTS. Yield knee moved UP to 811-931 N (virgin 694) = load memory at the prior
  cycling peak. ε_f 3.60 %. Deck **p211-212**.
  - ⚠️ **CORRECTION 2026-08-12 — the TRUE-stress fatigue loss was quoted wrong.** "−6.1 %" appears in
    the registry and earlier notes but does not reproduce from its own inputs. Recomputed by
    `sf9_data.py`: T7.3 19.74 MPa vs **S18 21.19 = −6.8 %** (same protocol, so this is the correct
    baseline); vs the S18/S21 mean 21.285 = −7.2 %; vs S21 alone = −7.6 %. Virgin spread S18↔S21 is
    **0.9 %**, not 0.7 %. Always quote the loss **with its baseline**, never bare. The conclusion is
    unchanged — the loss is many times the virgin spread — only the number moves.
- ✅ **T9 — CREEP RESOLVED, 2026-08-11 (S23, 50 % infill), two runs.** Deck **p213-215**.
  - **Run 1, zero-load baseline (928 s, crosshead frozen, 20.57 ± 0.23 N):** drift **+0.2893 µε/s**
    (R² 0.896) = **+268 µε**; slope 95 % CI ±0.0019 µε/s, so subtracting it over 900 s costs only
    **±2 µε**. Half-slopes 0.345/0.277 (ratio 0.80) = **LINEAR**, the drift signature.
    **DIC noise floor re-measured: 26 µε** over a full 900 s window — the ±12 µε quoted elsewhere is
    a 40 s window and understates long-hold noise. Use 26 for any long-hold claim.
  - **Run 2, 600 N tared for 877 s:** load held **596.55 ± 1.30 N (±0.22 %)** = 7.46 MPa engineering /
    **11.30 MPa true** (anchor 307.1 N) = 53 % of UTS. Raw +1334 µε − 254 µε drift (19 % of raw) =
    **net creep +1080 µε = 41× the noise floor**. **Findley n = 0.484** and half-slopes 1.48 → 0.59
    µε/s (ratio 0.40) — decelerating primary creep, so the **pre-registered shape discriminator
    passes on its own**, independent of the subtraction. J = 0.863 → 1.008 GPa⁻¹ (+16.7 %).
    Crosshead had to advance **+172 µm** while the DIC gauge extended only +107 µm → only **62 % of
    crosshead motion was specimen** (the strongest DIC-necessity argument in the creep mode).
    DIC 100 % frames. **Bonus:** fixed-grip relaxation tail 598 → 582 N over 300 s (−2.8 %).
  - Open: creep/instantaneous 16.8 % is an **upper bound** (ε_inst tared at preload); n = 1 specimen at
    one stress level — a compliance CURVE needs 3-4 levels.
- ⬜ **T6.6 — the clean damage curve.** Fresh 50 % specimen, 400→1100 N, **12 cycles**, sine, 0.100 mm/s,
  ONE continuous run (no pause — E recovers across a rest). Baseline E on **cycle 2**, never cycle 1.
  Still the only missing piece: T6.4 lost DIC, T6.5 started already damaged, and E recovered over the
  40 min between them, so **D = 1 − Eᵢ/E₀ is not computable from the T6.4/T6.5 pair**.
- ⬜ **Infill label bug.** The CSV `Infill` header writes **100 %** after an app restart regardless of the
  setting — T6.4 / T6.5 / T9a / T9b all say 100 % on 50 % specimens (T7.3 is correct). It is a label that
  enters no calculation (area and gauge are entered separately), so **no measured number is affected**;
  the registry carries the true value. Fix the field's restart default in `main.py`.

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
- ✅ **NOT A TORQUE CEILING AT ALL — RESOLVED 2026-08-12. It was crosshead misalignment.** The load
  holders had worked loose, so the crossheads sat out of alignment and the motor spent torque on
  binding instead of on the specimen. Re-aligned and re-tightened, the rig pulls **3.5 kN with no
  stutter**. Deck **p183** (root cause) / **p184** (post-fix register); `documentation/torque_fix_data.py`
  recomputes the evidence from `registry.json`.
  - **The three electrical suspects are exonerated** — driver current (Vref), driver thermal
    derating, PSU voltage sag. Mechanical binding, which every earlier revision of this file ranked
    LAST, was the answer.
  - **Why only binding fits:** 100 % infill has fractured at **3586–3826 N on 11 specimens** across
    three months (mean 3726 ± 75 N, CV 2.0 %) — 11 of 11 straight through the supposed 2.6 kN
    ceiling. Decisive: **S15 stalled at 2.6 kN and S16 fractured at 3792 N on the SAME DAY**
    (2026-07-28), +46 % on the same rig at the same speed. Vref does not change between two
    specimens; thermal derating gets worse through a session, not better; PSU sag cannot let a
    *higher* load through. Only binding is intermittent, and it changes at a remount.
  - **The drivetrain arithmetic was right all along and pointed here:** 2 × 1.85 Nm × 20:1 into a
    5 mm lead gives **≥12.5 kN even at a pessimistic 15 % screw efficiency = 3.4× the 3.7 kN
    needed**, yet T7 stopped at 72 %. That gap was never electrical — it was friction in a
    misaligned load path.
  - 🟢 **Still worth doing, now for diagnostics rather than as a fix:** the drivers are **MKS
    TMC2160_57**, SPI Trinamic parts. Wiring CS/SCK/MOSI/MISO to the ESP32 would let motor current
    be set in code (`GLOBALSCALER` + `IRUN`) and **`DRV_STATUS` (otpw/ot) + StallGuard** be logged —
    which would have distinguished binding from derating directly instead of by inference. Deck p202.
  - ⚠️ **Historical note, kept deliberately:** revisions of this file have twice stated a wrong
    ceiling — first a flat "~2.6 kN" requiring reduced cross-sections (corrected 2026-08-09), then a
    "variable 3.2–3.4 kN torque capacity" (corrected 2026-08-12). Both were inferences from a
    symptom whose cause was mechanical. See `TEST_FAILURES.md` (S15) and memory
    `project_motor_stall_limit`.
  - **Runs after 2026-08-12 are the reliable set** — S24, S25, S26, S27, S28, S12, S13: 7 runs,
    0 stalls, the five 100 % ones peaking 3693–3822 N. Prefer them when a number must be defended.
- ⚠️ **Multi-marker transverse Poisson** infeasible on the current mini-dogbone (gauge too narrow for a transverse pair; elastic width change sub-pixel at ~20 px/mm). Needs a gauge-zoomed camera + dark backdrop, or a dedicated extensometer.

---

## 5. Research & documentation to-dos
- ⬜ **Chacón reference — measurement basis:** confirm whether Chacón et al. measured PLA properties on a **printed specimen** or on **raw filament / bulk material** — decides whether our (infill-corrected) values are directly comparable.
- ⬜ **Moisture effect:** check whether specimen / ambient **moisture** shifts strength or stiffness vs literature (PLA is mildly hygroscopic) — dry / condition specimens and compare.
- ⬜ **Camera-parameter sensitivity:** enumerate every camera parameter controlled in software (exposure, gain, threshold, ROI, px/mm, …) and study how varying each affects the DIC results and the **noise floor**.
- ⬜ **Black-specimen DIC check (100% infill):** every specimen tested so far is WHITE (black dots, DIC "White" mode). Print/mark a **BLACK** specimen (white dots, DIC "Black" mode) and confirm the camera tracks strain just as reliably. **Done = ** a full pull with 2/2 markers held to fracture, tracking % and L_px jitter no worse than a white specimen, and E/UTS within the white-specimen scatter. Needs a `camera_setup.py --mode white` pre-flight (the flag names the DOT colour, not the body). Also unblocks the matte-black backdrop that multi-marker Poisson wants (§3).
- ⬜ **Cross-validate the DIC against MOT's extensometer software** — record a fracture test and have a
  second, established strain instrument read the same footage. Full spec in §3a; repeated here because
  it is the one validation that comes from OUTSIDE this project.
- ⬜ **UTM instruction manual (for students):** short, crisp usage guide with clear photos of the rig + UI screenshots — Connect → Calibrate → Mount → Prepare → Run → Save → Report.

---

## 6. Key files
- **App:** `main.py` (control loop, live hook `on_load_cell_data`, CSV export, UI).
- **Engine/analysis:** `utm_analysis.py`, `control_policies.py`, `control_sim.py`, `utm_dic.py`.
- **Workflow/data:** `utm_recipes.py` + `recipes/`, `utm_registry.py` + `registry.json`, `utm_report.py`.
- **Records:** `TESTING_TODO.md` (test checklist), `TEST_FAILURES.md` (S15 stall), this file.
