# UTM — Rig / GUI Test Checklist

Features built in the app (`main.py`, kept unversioned) that need a **camera + rig** pass.
They compile and their logic is unit-tested offline, but only the machine can confirm behaviour.
Tick each off after testing; note anything that misbehaves.

---

## 1. DIC health HUD  *(Phase C — built 2026-07)*
A coloured badge on both test tabs: `DIC OK/WARN/BAD · N/2 markers · track % · jitter px`.
- [ ] Start the camera with a good 2-marker specimen → badge goes **green "OK · 2/2 · track 100%"**.
- [ ] Cover / occlude one marker → badge goes **red "BAD"** and shows `1/2` or `0/2` within ~1 s.
- [ ] Uncover → returns to green.
- [ ] Nudge the rig / add vibration → **jitter px** rises (amber "WARN" if it gets bad).
- [ ] Stop the camera → badge greys to "DIC —".
- **Expect:** the badge should have *predicted* the V6c / V6e end-of-test dropouts before the CSV did.

## 2. Prepare specimen (one button)
- [ ] Click **Prepare specimen** → console logs `tared: position, force, DIC`.
- [ ] Confirm force, position and DIC strain all read ~0 afterwards.

## 3. Auto-stop at fracture (checkbox)  ⚠️ keep a hand near E-Stop the first time
- [ ] Tick **Auto-stop at fracture**, do a **scrap** tension pull to fracture.
- [ ] Motor should **Stop** right at the load collapse; console logs `fracture detected — motor stopped`.
- [ ] If it stops too early/late, the tunable knobs are arm 30 % / collapse 50 % / DIC-jump 3 % in `utm_analysis.LiveFractureDetector`.

## 4. Recipes (dropdown + Load / Save…)
- [ ] Pick a starter recipe (e.g. *V6 100% infill tensile*) → **Load** → dimensions / preload / speed / DIC-mode inputs update.
- [ ] Change some inputs → **Save…** with a name → it appears in the dropdown and reloads correctly.

## 5. Generate report (button)
- [ ] After a test, click **Generate report** → a one-page PDF + individual PNGs land in `Software/UTM_PyQt6/reports/`.
- [ ] Check the stress-strain / load-time / preload markers look right.

## 6. Strain-rate mode (BETA)  ⚠️ live motor control — scrap specimen first
- [ ] Set a target dε/dt, start a scrap pull → holds the strain rate, stops at set strain or fracture.
- [ ] Watch the dead-DIC guard: if strain freezes >1.5 s while moving, it should halt.

---

## Rig facts to report back (these unblock the remaining test modes)
- [ ] **Does `SetSpeed 0` hold the motor still** (no drift)? — needed for staircase / relaxation *dwell*.
- [ ] **Clean reversal sequence** — is it `Stop` → `SetSpeed` → direction? — needed for cyclic / creep.
- [ ] **Usable crosshead stroke (mm)** — to finalise the 45 mm travel safety cap.

## Known limitation logged (2026-07)
Multi-marker Poisson / true Cauchy from transverse dots is **not feasible** on the current
mini-dogbone: the gauge is too narrow for a transverse pair, and at ~20 px/mm the elastic width
change is sub-pixel. Path chosen instead: **analytical Cauchy stress** from measured axial strain
+ assumed ν≈0.35 for PLA, A = A₀(1 − ν·ε)². Real measured Poisson would need a gauge-zoomed camera
(higher px/mm) + dark backdrop, or a dedicated extensometer.
