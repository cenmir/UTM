# UTM — Mechanical Health TODO

**Opened 2026-08-27.** Everything in `TODO.md` and `Software/UTM_PyQt6/docs/ROADMAP.md` is software;
the development effort to date has been almost entirely software. This file is the mechanical
counterpart, and it is deliberately separate so it does not get buried under feature work again.

**Status: nothing here is scheduled.** It is a standing list for when rig time exists. Ordered by
what the existing data says is most likely to be costing accuracy, not by effort.

> The one item with a deadline is **§1 — the weekly check**, because the 7-week student campaign
> starts Monday 2026-08-31 and §1 is the failure mode that 40 mount/unmount cycles actually causes.

---

## 1. Alignment and fasteners — the known, recurring fault ⚠️ weekly during the campaign

The only mechanical failure on record. Load holders worked loose → crossheads sat out of alignment
→ the trapezoidal screws bound → the motor spent its torque on the machine instead of the specimen
and stalled at 2.6 kN. Diagnosed and fixed 2026-08-12 (re-aligned, re-tightened, screws lubricated).
`Software/UTM_PyQt6/docs/TEST_FAILURES.md` S15 has the write-up and the evidence trail.

**This is a wear-and-use fault, not a one-off.** Mounting and unmounting specimens is exactly what
loosens the holders, and ~40 student groups will do it a lot.

- [ ] **Weekly during the campaign:** load-holder fastener torque · crosshead alignment and
      squareness to the screws · screw lubrication.
- [ ] **Write down the torque values** once measured, so "tight" stops being a judgement call.
      Right now the correct state of this machine exists only as tacit knowledge.
- [ ] **Treat a stall-guard trip as a mechanical alarm.** If the guard fires, the first check is
      alignment and lubrication — not the motor, not the drivers, not the software.

---

## 2. Two motors share one step signal, and only one encoder is read ← highest-value fix

Straight from the firmware:

- `D32_Firmware/src/main.cpp:23-24` — **one** `STEP_PIN 14` / `DIR_PIN 27`, and **one**
  `MoToStepper stepper`. Both TMC2160 drivers are fed the same pulse train in parallel. There is no
  independent control of the two sides and no correction if they diverge.
- `D32_Firmware/src/main.cpp:35` — `#define SENS_IDX 0`, and `ProcessSensors()` only ever reads
  that one. **The second AS5600 is fitted, wired through the multiplexer and initialised in the
  `init(i)` loop — and then never read.** `Sensors` already exposes `readTotalPosition(int)` and
  carries `amsOffsets[2]`, so the capability is built and paid for.

**Why this matters mechanically.** If one side binds and its motor skips steps, the crosshead
**racks** — and nothing detects it. The reported position is one side's opinion. This is precisely
the S15 fault mode, and the instrument that would have caught it in seconds is already bolted to
the machine.

- [ ] **Read encoder 1 and report its difference against encoder 0.** The divergence between them is
      a direct, quantitative measure of racking and binding. Log it as a column and it becomes a
      health trace on every test run from then on.
- [ ] **Add a skew threshold** that warns, then halts. A cheap firmware-side safety net, strictly
      better than the software stall guard because it catches the cause rather than the symptom.
- [ ] **Check static squareness independently** — dial indicator across the crosshead at both
      screws, at several heights of travel. Establishes whether racking is dynamic (skipped steps)
      or built in.

---

## 3. Machine compliance — 71–81 % of crosshead travel never reaches the specimen

The MOT extensometer comparison (ROADMAP §3a) established that **only 19–29 % of crosshead motion
reaches the gauge**, and that the residual low-strain non-linearity is *the rig, not the material*:
our local strain rate climbs through the ramp while the XT-205's is flat from the moment it engages.

DIC makes this harmless for strain — that is the whole point of measuring on the specimen — but it
means every crosshead-derived number carries the machine in it, and it is a large number to not
understand.

### The specimen holder is printed 100 % PLA — that is almost certainly where it goes

The frame is 80×80 aluminium extrusion: E ≈ 70 GPa with a large second moment. At 3.8 kN it is
effectively rigid and is **not** the source. The **form-holder that grips the specimen is printed
PLA** — the same material as the specimen, in series with it, carrying the full test load.

Bulk stiffness alone does not explain the loss. A thick PLA holder with, say, 400 mm² of effective
section over a 50 mm load path is ~20 000 N/mm, which would cost only ~12 %. Reaching the observed
~870 N/mm series stiffness needs something far softer, so **the dominant term is local contact
crushing and bedding-in, not bulk holder compliance** — which is exactly what is expected and
observed.

That single fact explains the shape of the curve, not just its size: contact area grows as the
material crushes, so stiffness *increases* with load. That is the toe region, and it is why "our
local strain rate CLIMBS through the ramp while theirs is flat from the moment it engages."

- [ ] **Calculate bearing stress at the contact faces.** 3800 N divided by the actual bearing area
      at each PLA contact — specimen tab against holder, holder against its pins or bolts. PLA
      yields around 50–60 MPa, so anything under ~70 mm² of bearing area is **plastically crushing
      on every test**. One calculation, and it tells you whether the deformation is elastic and
      repeatable or permanent and accumulating.
- [ ] **Check the print orientation of the holder.** Printed PLA is anisotropic and layer adhesion
      is the weak direction. If the load pulls across layer lines rather than along them, that is
      both the compliance path and the eventual failure plane.
- [ ] **Measure the compliance curve with a rigid dummy specimen.** A steel bar of the same grip
      geometry, pulled the same way. **Be precise about what this isolates:** the dummy is still
      gripped by the PLA holder, so the curve is *frame + drivetrain + holder + contact*, with only
      the specimen removed. That is still the number you want — it is everything that is not the
      specimen — but it does not exonerate or implicate the holder on its own. To separate the
      holder, run the dummy again in a metal holder if one can be made.
- [ ] **Then separate the rest** one at a time: grip slip (mark the specimen at the jaw line) ·
      specimen shoulder deformation · frame flex · bearing axial play · screw and gearbox backlash.

### Consequences that are easy to miss

- [ ] **PLA creeps at room temperature, and the holder is under full load for the whole test.**
      This matters most for the *time-based* modes — **creep, relaxation, and the long dwells in
      staircase**. Establish whether the measured decay is specimen behaviour or holder creep
      before any of those results are published. A relaxation run against a rigid dummy would
      answer it directly: whatever force decay appears with no specimen present is the holder.
- [ ] **The compliance will drift across the 7-week campaign.** If the contact faces are crushing
      plastically, the holder gets progressively softer as surfaces bed in and yield, so week-1 and
      week-7 groups do not share a machine. **DIC protects the results** — strain is measured on the
      specimen — but any crosshead-derived quantity drifts, and this is another reason the student
      profile must pin the strain source to DIC.
- [ ] **Inspect the holder for cracking periodically**, especially around pin and bolt holes where
      stress concentrates. A PLA part taking 3.8 kN forty-plus times is a fatigue candidate, and the
      frame has stored elastic energy to release if it lets go.
- [ ] **Consider a metal holder** as the eventual fix. Not urgent — the machine measures correctly
      as it stands, because DIC bypasses the whole problem — but it would recover most of the lost
      travel, remove the creep question from the time-based modes, and stop the drift.

---

## 4. Backlash and lost motion — matters for the reversing test modes

Position is measured at the **motor shaft**, upstream of both the 20:1 EPL-Q64 planetary gearbox and
the Tr22x5 screw. Anything either of those loses is invisible to the position reading.

On a monotonic tensile pull this mostly does not matter. On **cyclic, staircase and relaxation**
modes it does — every direction reversal crosses the backlash dead zone, and the crosshead does not
move while it does. The note that "direct reversal auto-decels ~1 s" is a control observation
sitting on top of an unmeasured mechanical one.

- [ ] **Measure total lost motion at the crosshead** on reversal, with a dial indicator, at several
      loads. Planetary gearboxes of this class are typically 15–30 arcmin; trapezoidal screws add
      their own.
- [ ] **Decide whether the cyclic results already on record need a backlash caveat.**
- [ ] **Check the 4 × SKF-6005-2Z axial preload.** Deep-groove bearings taking a thrust load will
      have axial play unless preloaded, and that play sits directly in the load path.

---

## 5. Load train and load-cell health

- [ ] **Check for off-axis loading.** Any misalignment between the grips and the load cell puts a
      bending moment into a cell meant to read axial force. Same misalignment family as §1 — check
      at the same time.
- [ ] **Re-run the two-point calibration with a known reference weight**, at least once mid-campaign
      and after any mechanical work. Seven weeks and ~40 mountings is long enough to drift.
- [ ] **Record that nothing is near a ceiling.** Anyload 101BH-3t = 3 t ≈ 29 kN; the drivetrain is
      good for ~15 kN; a PLA fracture is ~3.8 kN. Worth writing down so the "torque ceiling" story
      does not resurface a third time.

---

## 6. Frame

- [ ] **T-slot fastener torque across the 80×80 extrusion joints.** Frame flex feeds straight into
      §3, and extrusion joints relax over time.
- [ ] **Look for stick-slip at 0.1 mm/s.** At ~24 RPM at the motor the drivetrain is deep in its
      full-torque region, so any judder is mechanical, not electrical.

---

## Reference

| | |
|---|---|
| Motors | 2 × Nema 23 AMP57TH76-4280, 1.85 Nm stall |
| Gearboxes | 2 × EPL-Q64 i20 (20:1 planetary) |
| Screws | 2 × Tr 22×5 TH22 trapezoidal, 5 mm pitch |
| Bearings | 4 × SKF-6005-2Z deep groove |
| Load cell | Anyload 101BH-3t (3 t ≈ 29 kN) |
| Encoders | 2 × AS5600 via TCA9548A at 0x70 — **only channel 0 is read** |
| Drivers | 2 × MKS TMC2160_57 — **both on one step/dir signal** |
| Frame | Aluminium extrusion 80×80 |
| Drivetrain capability | ~15 kN · PLA fracture ~3.8 kN (~25 %) |
