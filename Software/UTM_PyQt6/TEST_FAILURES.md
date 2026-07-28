# UTM — Test Failure Log

Records of tests that did NOT complete, with data-backed analysis and predicted causes.

---

## S15 — 2026-07-28 — motor STALL at ~2.6 kN (no fracture)  ❌ FAILED

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
- **32.4 MPa ≪ ~46 MPa** where a V6 100 % specimen fractures → this was **NOT a fracture; the motor stalled.**

### Root cause (predicted)
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
- ⏳ **Before re-test:** let the motor **cool**, check **driver current (Vref)**, check for **binding**.
- ⏳ **Specimen design:** for 100 % infill, use a **smaller cross-section** (thinner / narrower gauge) so fracture force stays under ~2.6 kN — same stress, less force.
- ⏳ **Re-test** with a **fresh** specimen (S15 is now cycled) after cooldown.
