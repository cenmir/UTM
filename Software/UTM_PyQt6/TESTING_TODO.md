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
- [ ] Set a target dε/dt, start a scrap pull → holds the strain rate, stops at set strain or fracture.
- [ ] Watch the dead-DIC guard: if strain freezes >1.5 s while moving, it should halt.

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
