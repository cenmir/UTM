# UTM — Rig / GUI Test Checklist

Features built in the app (`main.py`, kept unversioned) that need a **camera + rig** pass.
They compile and their logic is unit-tested offline, but only the machine can confirm behaviour.
Tick each off after testing; note anything that misbehaves.

---

## 1. DIC health HUD  ✅ CONFIRMED 2026-07-27  *(Phase C)*
A coloured badge on both test tabs: `DIC OK/WARN/BAD · N/2 markers · track % · jitter px`.
- [x] Start the camera with a good 2-marker specimen → badge goes **green "OK · 2/2 · track 100%"**.
- [x] Cover / occlude one marker → badge goes **red "BAD"** and shows `1/2` or `0/2` within ~1 s.
- [x] Uncover → returns to green.
- [x] Nudge the rig / add vibration → **jitter px** rises (amber "WARN" if it gets bad).
- [x] Stop the camera → badge greys to "DIC —".
- **Result:** PASS — live badge tracks markers and flips red on dropout.

## 2. Prepare specimen (one button)  ✅ CONFIRMED 2026-07-27
- [x] Click **Prepare specimen** → console logs `tared: position, force, DIC`.
- [x] Confirm force, position and DIC strain all read ~0 afterwards.
- **Result:** PASS — clears both consoles + the stress-strain plot, then tares position + force + DIC
  (DIC only when 2/2 markers are tracked; honestly reports "DIC skipped" otherwise). Load plot kept.

## (bonus) Release preload  ✅ CONFIRMED 2026-07-27
- [x] Preload → **Release preload** backs the load down to ~0 N (correct unloading direction) → re-preload works.
- **Result:** PASS — releases to ≤5 N; safety halt if load rises; cancel via button / manual dir / E-Stop.

## 3. Auto-stop at fracture  ✅ CONFIRMED 2026-07-28 (S16, via Fracture test button)
- [x] **Fracture test** on **S16** (100 % infill) → fractured; load collapsed **2992 → −417 N** and the motor stopped at the collapse.
- **Result:** PASS — auto-stop caught the fracture. UTS **47.4 MPa** (anchor-corrected, V6-consistent); registry `S16`. First successful post-stall-guard fracture.

## (feature) Stall guard  ✅ VALIDATED 2026-07-28 (S16)
- [x] During S16's ductile drawing (force 3374 → 3070 N while the crosshead kept advancing 5.1 → 7.8 mm) the guard correctly did **NOT** trip — the near-zero-only 6 s threshold is confirmed. (S15 stall = the failure case it's built for; see TEST_FAILURES.md.)

## (feature) Fracture test button  ✅ VALIDATED 2026-07-28 (S16) — checklist → auto-pull → auto-stop at fracture worked end-to-end.

## 4. Settings (dropdown + Load / Save…)  ✅ CONFIRMED 2026-07-27
- [x] Set inputs → **Save…** with a name → appears in the dropdown; the JSON captures the values.
- [x] Select a saved profile → **Load** → inputs (area/gauge/preload/speed/DIC mode/infill/auto-stop) restore.
- [x] **Default** present + pre-selected on startup.
- **Result:** PASS — "Test 0" saved preload 300 N / speed 0.2 mm/s and Load restored them. NOTE: selecting only browses; **Load** applies.

## 5. Generate report (button)  ✅ CONFIRMED 2026-07-28 (S16)
- [x] Report generated for S16 → one-page PDF + PNGs.
- [x] Every value verified against the CSV/analysis (UTS 47.4 / σ_y 47.0 / E 1.88 / ε_f 6.0 / anchor 418), settings + validation + plots all faithful. DIC-health header line present.
- **Result:** PASS — report is a faithful render of the CSV (raw header Max Stress 42.18 = anchor-corrected report UTS 47.4).

## 6. Strain-rate mode (BETA)  ⚠️ live motor control — scrap specimen first
### 6.1 — dead-DIC guard (do FIRST)
- [x] **S17, 2026-07-28:** covered a marker mid-run → guard FIRED ("DIC strain frozen — halted for safety"), no fracture (15.9 MPa). Guard *detection* ~1.5 s ✓.
- ⚠️ **Flaw exposed:** while blind, the controller RAMPED UP (0.2 → 0.4 mm/s cap) chasing the frozen strain → force spiked **753 → 1271 N**, total halt **2.94 s**, +0.63 mm.
- ✅ **FIX applied (main.py):** stale strain now **FREEZES speed at 0.5 s** (no blind ramp-up) + dead-DIC halt tightened **1.5 → 1.0 s** (`POLICY_STALE_FREEZE_S` / `POLICY_DEAD_DIC_S`).
- [x] **RE-TEST (T2/T3, fix on):** overshoot cut — T2 peak **0.22 mm/s / +175 N** (clean, no ramp); T3 0.36 mm/s / +407 N (partial ramp at high load) vs T1's 0.40 mm/s / +518 N. Both halted. Freeze then **tightened 0.5 → 0.2 s** to kill the residual pre-freeze ramp. **PASS.**
### 6.2 — strain-rate to fracture  ✅ PASS 2026-07-29 (50% infill)
- [x] **50% specimen (fractures ~1.4 kN, under today's ~2.6 kN torque ceiling):** strain-rate held **0.00051 /s vs 0.0005 target** while the crosshead speed **auto-adapted 0.10 → 0.05 mm/s** (fast in stiff elastic, slow in necking) — true constant-*gauge*-strain-rate control, not constant crosshead speed. **Fractured** (UTS 1387 N / 17.3 MPa nominal, 20.5 MPa anchor-corr, anchor 255 N) and **auto-stopped on load collapse**. Speed ≤ 0.2 cap, no stall.
- NOTE: the 100% attempts (S17/fresh) could NOT fracture — motor's variable **torque ceiling ~2.6 kN today** (see `project_motor_stall_limit`), NOT a strain-rate issue (a normal S15 pull also stalled ~2.6). Infill label left at 100% in the CSV header (cosmetic; set Infill=50 next time).

## 7. Advanced test modes — cyclic · staircase · relaxation · creep  (wired 2026-08-08)
UI: "Advanced test modes (BETA)" segment in Motor Control — enable checkbox (greys the whole
segment until ticked) → Test-type dropdown + per-mode settings + **?** help diagram → Start test.
Shares `_policy_step` with strain-rate; `_policy_step` extended to drive **tension / compression /
hold**, with **phase-aware guards** (stall guard silent during an intentional hold; dead-DIC guard
only for DIC-steered modes) + adaptive timeout (hold duration + 300 s).
All runs below on **scrap specimen #1** (100 % infill), 300 N preload → Prepare → run.

### Session 1 — holds  ✅ PASS 2026-08-08
- [x] **T1 Creep** (400 N / 60 s / 0.1): ramped, entered hold, parked **~395–403 N** with position frozen at 0.6135 mm for ~80 s; small compression nudges worked; clean "creep complete".
  - ⚠️ **Overshoot 400 → 448 N (+12 %)** on arrival = the ~1 s decel coast. **FIX:** `CreepPolicy.ease_frac` (taper the last 25 % of the approach). Sim on a T1-calibrated plant: **38.8 N → 0.6 N**.
- [x] **T2 Relaxation** (ε 0.010 / 60 s / 0.1): stopped ramping at ε 0.010 = **2145.9 N (26.8 MPa)**, held position 2.8252 mm, **force decayed 2145 → 2040 N (~5 %)** at flat strain — textbook stress relaxation. DIC 99 %.
  - NOTE: ε targets are **heavy** on stiff 100 % infill (E≈2.68 GPa → ~215 N per 0.001 strain). ε 0.010 ≈ 2.45 kN absolute, near the ~2.6 kN ceiling. Use **ε 0.003–0.005** for a gentle elastic relaxation.
- ✅ **Stall guard stayed silent through both holds** (crosshead frozen, load ≫ 200 N) — phase-aware fix validated on hardware.

### Session 2 — staircase, Linear vs Smooth  ✅ PASS 2026-08-08
Same specimen + identical settings (300 N start / 300 N step / 3 levels / 20 s dwell / 0.1), only the ramp shape differs.

| Level | T3 **Linear** peak | over | T4 **Smooth** peak | over |
|---|---|---|---|---|
| 300 N | 345.5 N | **+45.5 (15.2 %)** | 306.0 N | **+6.0 (2.0 %)** |
| 600 N | 646.8 N | **+46.8 (7.8 %)** | 604.8 N | **+4.8 (0.8 %)** |
| 900 N | 952.6 N | **+52.6 (5.8 %)** | 907.8 N | **+7.8 (0.9 %)** |

- [x] 3 levels hit in order; **dwells 20.3/20.2/20.0 s (T3), 20.4/20.5/20.0 s (T4)** — spot on.
- [x] **Stall guard silent through all 6 dwells** (20 s frozen at 300–950 N).
- [x] Sine speed profile visible in T4: **0.01 → 0.096 → 0.0025 mm/s** per ramp.
- [x] Bonus real data — **stress relaxation at every level**: T3 −4.4/−2.9/−2.4 %, T4 −3.9/−2.9/−2.1 %.
- ⚠️ Smooth **doubled ramp time** (25.3 s vs 12.7 s) because `sin(π·frac)` also eased the ramp *start*, which buys no accuracy. **FIX:** taper only the top `ease_frac` (matches creep). Sim on a T3/T4-calibrated plant (850 N/mm, 1.24 s decel): overshoot stays ≤1 N, ramp **27.0 s → 18.0 s** (linear 11.2 s).
- **Verdict:** Smooth is the better default — ~85–90 % less overshoot for ~60 % more ramp time.

### Session 3 — cyclic  ✅ PASS 2026-08-09 (specimen S20, 100 % infill, folder `8.7/`)
Low 100 / High 500 N / **5 cycles** / 0.1 mm/s, 300 N preload → Prepare. Both runs: **5 cycles, 10 reversals, no stall, clean finish.**

| | peaks (target 500 N) | troughs (target 100 N) |
|---|---|---|
| **T5 Triangle** | 556/566/573/574/588 → **+71.5 N** | 24/34/24/24 → **−73.6 N** |
| **T6 Sine** | 502/506/513/512/507 → **+7.9 N** | 78/79/79/74 → **−22.7 N** |

- Triangle really cycled ~26↔572 N; Sine ~78↔508 N. **Sine 9× tighter at the top, 3× at the bottom.**
- ⚠️ **Asymmetric turnaround:** unload→load takes **~2.0 s** vs **~1.3 s** load→unload, in both waveforms — that is why the low bound is always the worse one.
- **Stiffness stable** all 5 cycles (1204/1273/1212/1251/1246 N/mm) → no fatigue damage. Cycle 1 reads 760–780 N/mm = slack take-up (same engaged-regime effect as V4b/V4c).
- **Hysteresis ≈ 19–21 mJ/cycle** steady (includes rig friction → upper bound on material damping).
- **Shakedown** visible in T6: peak-position drift 0.027 → 0.012 → 0.005 → 0.001 mm.
- 🆕 **Dynamic modulus:** DIC resolved the small-amplitude strain on 8 strokes → **E_cyclic = 3.7–3.8 GPa** vs monotonic secant **2.60 GPa** (≈1.45×, classic unrelaxed > relaxed for a viscoelastic polymer). Stroke 1 (2.2 GPa) is slack-contaminated; ±8 % from ~1.3 px of travel.
- Sine's predicted ~16 s start crawl was real; durations 67 s (T5) vs 127 s (T6).
- Stall guard did **not** false-trip on the sine's low-speed zones.

### T6.2 — cyclic Sine RE-RUN  ✅ RAN 2026-08-09 (mixed: low bound fixed, high bound worse, flat bottoms)
T6 showed a **stepped, non-sinusoidal** wave and loose bounds. Three fixes landed (`control_policies.py`, and the deadband in `main.py`) — **T6.2 is the rig check**:
1. SetSpeed deadband **0.01 → 0.002 mm/s** for waveform modes (sine was quantised to only ~10 velocity steps — the visible faceting).
2. Velocity law `sin(pi*frac)` → **`2*sqrt(frac(1-frac))`** = a true sine in time (old law ~2× too slow near the bounds).
3. **Adaptive predictive reversal** — reverses early by `rate x decel`, with `decel` self-tuned per direction from the observed violation. Seeded at zero lead + gain 0.7 so it converges from below (seeding it high made cycles 1–3 reverse far too early; full gain rang).
- Sim (T5/T6-calibrated plant): settled bound error sine **3.2 → 1.2 N** high, **21.7 → 10.1 N** low; cycle time 17.0 → 12.1 s. Shape only 10.8 → 9.7 % RMS — the residual is the *mechanical* reversal, not the law.
- [x] **T6.2** — RAN 2026-08-09 (S20). 5 cycles, no stall. **Mixed: low bound fixed, high bound worse, and flat bottoms appeared.**

| | T6 | T6.2 |
|---|---|---|
| high bound | +7.9 N | **+15.6 N** ❌ not converging (511/520/512/516/519) |
| low bound | −19.2 N | **−2.8 N** ✅ converging (−39.6 → −19.8 → +9.9 → +2.6) |
| duration | 127 s | **95 s** ✅ |

  - ❌ **Flat bottoms** (visible in the plot as a long dwell between humps). Root cause found: the sine law clamped `frac` to the nominal bounds, so **below f_low it returned 0 and the 0.01 mm/s floor took over**. Every reversal undershoots past f_low, so every cycle fell into that dead zone. Proof from the CSV: commanded **0.0159 mm/s below the bound vs 0.0635 above**, and climb-out **10.4 / 10.6 s** for troughs that dipped below vs **5.8 / 6.4 s** for troughs that stayed above.
  - ❌ **High bound could not converge** — the lead was scaled by the load rate, but with a sine the rate → 0 *exactly at* the bound, so the lead vanished right when needed. Structural; no amount of adapted decel fixes it.
  - ❌ Run ended at a **133 N** trough because the low-side lead had grown that large and tripped the cycle-complete test early.

### T6.3 — cyclic Sine RE-RUN #2  ✅ PASS 2026-08-09 (both bounds converge, dead zone gone)
1. **Waveform shaped over the ACHIEVED extremes** (`_lo_seen`/`_hi_seen` + 5 % margin) instead of the nominal bounds → **no dead zone, no flat bottoms**; floor raised 0.01 → 0.02 mm/s.
2. **Lead adapted in FORCE units, not rate×time** — we backed off by `lead_used` and still ran `over` past the bound, so the true coast is `lead_used + over` = the next lead. Rate-independent → converges for any waveform. Gain 0.85. Final trough stops at the true bound with no lead.
- Sim (5 cycles): sine peaks **518/522/512/502/493**, troughs **71/56/66/87** (vs no-lead 518/528/534/533/535 and 71/48/34/28); crawl-at-floor **1.8 s**; **55 s** vs T6.2's measured 82 s.
- [x] **T6.3 — PASS 2026-08-09.** Both bounds now CONVERGE onto target, and the flat bottoms are gone.

| cycle | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| peaks (target 500) | 528.0 | 529.2 | 515.6 | 505.1 | **499.6 (−0.4)** |
| troughs (target 100) | 50.5 | 75.3 | 94.3 | **100.3 (+0.3)** | 74.0 (final Stop, no lead) |

  - **Dead zone eliminated** — climb-out from a *below-Low* trough: T6.2 **10.4 / 10.6 s** → T6.3 **7.1 / 5.6 / 5.3 s**. Commanded speed below the bound **0.0159 → 0.0281 mm/s**. T6.3 climbs out of a 94 N trough in 5.3 s where T6.2 needed 5.8 s starting from 110 N (already *above* the bound).
  - **Duration 127 s (T6) → 95 s (T6.2) → 65 s (T6.3).**
  - ⚠️ Don't read the "mean bound error" — it averages cycle 1's deliberate transient with cycle 5's near-zero. The lead seeds at 0 and grows by design; judge the **trend**.
  - Leftover (cosmetic): the final trough lands at 74 N (−26) because the last trough uses no lead and the Stop still coasts. Traded T6.2's +33 for −26. Half-lead on the final trough would split it.
- [x] **Release load** — renamed, drives past tared 0 to −(tared-away load) = true zero. Safety floor made relative. Speed **0.30 → 0.20 mm/s** (0.30 felt too fast on the rig).

---

## 8. Fracture protocols (destructive) — T7 ✅ / T7.2 ✅ PASS / T8 ⬜ TODO

The plain **Fracture test** button = a **monotonic (quasi-static) uniaxial tensile test to failure** (ASTM D638 / ISO 527): one continuous pull to load collapse → one E, one σ_y, one UTS. T7/T8 reach the same fracture but interrogate the specimen on the way, so **one specimen yields a curve instead of a point**. Both are in the advanced-mode dropdown behind a destructive-test confirmation.

**Motor note:** measured peaks in `8.6.20/` are **S16 3374.6 · V6a 3350.7 · V6c 3275.0 · V6d 3218.4 · V6e 3162.2 · V6b 3109.7 N** — six 100 % infill specimens over 3.1 kN, all fractured. Normal ceiling **3.2–3.4 kN**; the ~2.6 kN figure is a *thermally derated* session, NOT a hard limit. 100 % infill at the full 80 mm² fractures fine.

### Common to both
1. Mount specimen → preload **300 N** → **Prepare specimen** (now clears BOTH plots).
2. Tick **Advanced test modes**, pick the type, set params, **Start test** → confirm the destructive dialog.
3. At the end the console prints a **summary table** (per level / per cycle).
4. ⏸️ **Let the motor cool between T7 and T8** — back-to-back high-force runs are what produced the derated ~2.6 kN sessions.
5. A stall-guard trip is a *motor* result, not a protocol failure.

### T7 — Staircase → FRACTURE
| param | 100 % infill | 50 % infill |
|---|---|---|
| Start | **400 N** | 200 N |
| Step | **300 N** | 150 N |
| Dwell | **10 s** | 10 s |
| Speed | **0.100 mm/s** | 0.100 |
| Ramp | **Smooth** | Smooth |

~11 levels, **≈4–5 min**. Save as `_T7_StaircaseFracture`.
- **Dwell = 10 s is sufficient** (measured): 10 s captured **77 % / 67 %** of the full ~18 s drop in the T3 dwells. Enough for *yield detection*, where only consistency between levels matters and the 6–12 N drop is ~5× load-cell noise. NOT enough for quantitative viscoelastic work — use the dedicated Relaxation mode for that (10 s = only 41 % of an 81 s hold).
- **Keep Ramp = Smooth.** In Linear T3 the drop was 11.7 N at 345 N but only 6.3 N at 937 N — backwards for true relaxation. That is the 45–53 N arrival overshoot decaying during the dwell and masquerading as relaxation; Smooth cuts overshoot to 5–8 N.
- **Watch:** the `relax-drop` column — small and roughly linear while elastic, then an **abrupt jump** once a level passes yield. That is the yield-onset signature this protocol exists for.
- If late levels **crawl**, that's expected (the Smooth taper is calibrated for elastic stiffness; the specimen is far softer past yield) → switch to **Linear**.

### T8 — Progressive cyclic → FRACTURE
| param | 100 % infill | 50 % infill |
|---|---|---|
| 1st peak | **600 N** | 300 N |
| Peak step | **300 N** | 150 N |
| Unload to | **150 N** | 100 N |
| Speed | **0.100 mm/s** | 0.100 |

~10 cycles, **≈5–7 min**. Save as `_T8_ProgressiveCyclic`.
- 🔴 **Primary risk to watch:** if it stops after **cycle 1 or 2** announcing FRACTURE, the per-rising-stroke collapse watch has false-fired on the *intentional* unload — the exact failure mode this design guards against (armed only past halfway to the current target). **Stop, send the CSV, do not retry.**
- **Watch:** `unload-K` per cycle (stiffness degradation `D = 1 − Eᵢ/E₀`) and the rising trough position (permanent set).

**Sim status (elastic-plastic plant: yield 2900, break 3300, K 1210):** T7 fractures level 9 @222 s, relax-drop grows 2.8 → 26.0 N; T8 fractures cycle 8 @peak 3300 N after 7 clean cycles, peaks within ~5 N of target, trough position jumps 0.40 → 0.65 mm at yield. Three policy bugs already found and fixed by that sim (`self.step` shadowing `step()`; logged peak was the trigger not the true post-coast peak; fracture record mutated + duplicated the last row).

- **After T7/T8:** build the deck slides for all the control modes + fracture protocols.

---

## Rig facts to report back (these unblock the remaining test modes)
- [x] **Hold on STOP** — CONFIRMED 2026-07-27: after Stop, δ held at −1.9191 mm across 5/10/15 s (zero drift). Motor has holding torque → staircase / relaxation *dwell* works via Stop. (SetSpeed-0-specific hold not separately tested — not required.)
- [x] **Reversal** — CONFIRMED 2026-07-28 (video frame analysis): a DIRECT opposite-direction click auto-reverses cleanly — smooth decel → ~1 s stop (δ holds, no overshoot/jolt) → accel in the new direction. No manual Stop needed. Cyclic/creep can issue direct direction changes; velocity readout is signed (+ Down / − Up).
- [x] **Travel cap → 30 mm** (2026-07-28): lowered from 45 mm by visual inspection (45 looked too much). Counts from the tared zero; ~2x a PLA fracture test's ~8-15 mm. Optional: jog top→bottom to confirm physical stroke ≥ 30 mm.

## Known limitation logged (2026-07)
Multi-marker Poisson / true Cauchy from transverse dots is **not feasible** on the current
mini-dogbone: the gauge is too narrow for a transverse pair, and at ~20 px/mm the elastic width
change is sub-pixel. Path chosen instead: **analytical Cauchy stress** from measured axial strain
+ assumed ν≈0.35 for PLA, A = A₀(1 − ν·ε)². Real measured Poisson would need a gauge-zoomed camera
(higher px/mm) + dark backdrop, or a dedicated extensometer.
