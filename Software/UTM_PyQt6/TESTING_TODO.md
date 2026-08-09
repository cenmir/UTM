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

### T6.2 — cyclic Sine RE-RUN  ⬜ TODO (validates the waveform/reversal fixes)
T6 showed a **stepped, non-sinusoidal** wave and loose bounds. Three fixes landed (`control_policies.py`, and the deadband in `main.py`) — **T6.2 is the rig check**:
1. SetSpeed deadband **0.01 → 0.002 mm/s** for waveform modes (sine was quantised to only ~10 velocity steps — the visible faceting).
2. Velocity law `sin(pi*frac)` → **`2*sqrt(frac(1-frac))`** = a true sine in time (old law ~2× too slow near the bounds).
3. **Adaptive predictive reversal** — reverses early by `rate x decel`, with `decel` self-tuned per direction from the observed violation. Seeded at zero lead + gain 0.7 so it converges from below (seeding it high made cycles 1–3 reverse far too early; full gain rang).
- Sim (T5/T6-calibrated plant): settled bound error sine **3.2 → 1.2 N** high, **21.7 → 10.1 N** low; cycle time 17.0 → 12.1 s. Shape only 10.8 → 9.7 % RMS — the residual is the *mechanical* reversal, not the law.
- [ ] **T6.2** — same settings as T6 (Low 100 / High 500 / 5 cycles / 0.1 / **Sine**). Save as `_T6.2_Sine`.
  - Check: flanks visibly smoother (less stepped) · peaks near 500 · troughs closer to 100 than T6's 78 · still 5 cycles / no stall.
- [ ] **Release load** (renamed from "Release preload") — now drives past tared 0 to **−(tared-away load)** = true zero absolute force, so the specimen can be unclamped. Safety floor made relative (`target − 50 N`); the old fixed −50 N would have aborted the release. Quick non-destructive check before T6.2.

- **After T6.2:** build the deck slides for the 4 control modes (results + why each mode matters).

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
