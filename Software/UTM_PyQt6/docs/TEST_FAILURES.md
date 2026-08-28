# UTM — Test Failure Log

Records of tests that did NOT complete, with data-backed analysis and predicted causes.

---

## S15 — 2026-07-28 — crosshead BIND at ~2.6 kN (no fracture)  ✅ RESOLVED 2026-08-12

- **Specimen:** S15, 100 % infill, spray markers (V2 batch). CSV: `8.6.20 - Tensile test to Failure/Specimen_S15_V2_Spray/UTM_Test_20260728_182021.csv`.
- **How run:** preload 500 N → release → **Fracture test** button (0.1 mm/s tension, auto-stop armed).
- **Symptom:** heavy jitter / whole machine shaking; crosshead stopped advancing; operator had to Stop manually and release down.

### What the data shows
| t (s) | Force (N) | pos (mm) | pos rate (mm/s) |
|---|---|---|---|
| 60→120 | 0 → **2592** | 0 → 4.69 | ~0.10 (normal) |
| 140 | 2555 | 4.750 | 0.003 |
| 160→250 | 2514 → 2442 | 4.76 → 4.82 | **≈ 0 (frozen)** |

- Normal pull to **2592 N (32.4 MPa)** by t≈120 s, then the crosshead **froze**: 4.69 → 4.82 mm over the next **130 s** while commanded 0.1 mm/s. Force then **relaxed** 2592 → 2442 N (constant-strain relaxation).
- **32.4 MPa ≪ ~46 MPa** where a V6 100 % specimen fractures → this was **NOT a fracture.** The motor stalled — but against a binding drivetrain, not against the specimen. See root cause below.

### ✅ ROOT CAUSE — RESOLVED 2026-08-12. It was NEVER a torque limit.

**The load holders had worked loose**, letting the crossheads sit out of alignment, so the motor
spent its torque on binding instead of on the specimen — the trapezoidal screws were biting.
Re-aligned, re-tightened and the screws lubricated, the rig pulls **3.5 kN with no stutter**.
Deck **p183** (root cause) and **p184** (the post-fix register); full write-up in `ROADMAP.md`.

- **The evidence was on disk before the fault was found.** The same machine has fractured 100 %
  infill at **3586–3826 N on 11 specimens** across three months — 11 of 11 straight through the
  supposed "2.6 kN ceiling". Decisive pair: **S15 stalled at 2.6 kN and S16 fractured at 3792 N on
  the SAME DAY** (2026-07-28), +46 % on the same rig at the same speed.
- **The three electrical causes below are exonerated** — none of them can be intermittent between
  two consecutive specimens. The mechanical cause, ranked LAST at the time, was it.
- **Runs after 2026-08-12 are the reliable set**: S24, S25, S26, S27, S28, S12, S13 — 7 runs,
  0 stalls, the five 100 % ones peaking 3693–3822 N.

**The machine is rated to ~15 kN** (see `PROJECT_REQUIREMENTS.md`): 2 × Nema 23 at 1.85 Nm through
20:1 gearboxes = 37 Nm per Tr22x5 screw, and the Anyload 101BH-3t cell reads to 29 kN. A 3.8 kN
fracture is ~25 % of capacity. **There is no force ceiling anywhere near a PLA tensile test, at any
infill.** A recurrence means the mechanics have been disassembled and reassembled wrong, or the
screws have run dry — not that the motor is undersized.

### Original root cause (predicted 2026-07-28 — SUPERSEDED, kept for the record)
- **Motor/drive hit its usable force ceiling (~2.6 kN) and stalled.** A stalled stepper skips steps → the shaking. 100 % infill at 80 mm² needs **~3.7 kN** to fracture — beyond reach here.
- Earlier V6 100 % runs fractured at ~46 MPa ≈ **~3.2 kN at the load cell**, so the motor *has* pulled harder before. Stalling ~20 % lower this time ⇒ **derating**, most likely:
  1. **Thermal** (top suspect) — motor hot after the preload cycle + a long 250 s pull.
  2. **Driver current (Vref)** set below spec.
  3. **Mechanical binding / friction** on the screw or rails.
- Load cell is NOT the limit (ANYLOAD 3 t / 29 kN). **The motor is the bottleneck.**

### Software check
- **Fracture test code reviewed — no bug.** It correctly commanded a 0.1 mm/s tension pull; the load rose normally. Auto-stop correctly did **not** fire (no load collapse = no fracture — a stall is a different failure mode).

### Actions taken / recommended
- ✅ **Stall guard added** (software): during an auto-stop / Fracture-test pull, if the crosshead advances **< 0.05 mm in 6 s** while under load (> 200 N), it auto **Stop + E-Stop** and pops up "Stall guard activated". Would have halted this in ~6 s instead of 130 s of shaking.
- ✅ **Before re-test:** ~~cool the motor, check Vref~~ — **check crosshead alignment, load-holder tightness and screw lubrication.** That was the fault.
- ~~⏳ **Specimen design:** for 100 % infill, use a smaller cross-section so fracture force stays under ~2.6 kN.~~ **WITHDRAWN 2026-08-12** — there is no 2.6 kN ceiling. 80 mm² at 100 % infill is correct and has fractured 11 times.
- ⏳ **Re-test** with a **fresh** specimen (S15 is now cycled) after cooldown.
