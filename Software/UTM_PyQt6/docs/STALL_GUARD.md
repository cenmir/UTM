# The velocity stall guard

**Status: ENABLED by default since 2026-08-30.** Operator switch in
**Motor Control ▸ Stall guard (velocity)**.

> **2026-08-30 — turned back on for the student campaign, by the project owner's decision.**
> It was switched off on 2026-08-28 for the reasons set out below, which still stand: this
> guard fires on healthy motion, and the fault it was written for was fixed mechanically.
> The judgement that reversed it is about who is at the rig. With ~40 groups running pulls
> largely unattended over seven weeks, a guard that occasionally stops a good move is the
> cheaper failure than one that is absent when a genuine bind happens.
>
> If it cries wolf during the campaign, reach for the **grace period** (`_start_movement_grace_period`,
> which covers the acceleration ramp) before reaching for the default. A student who is told
> to untick a safety box will leave it unticked.

This is the guard that prints:

```
⚠ WARNING: MOTOR STALL DETECTED!
⚠ Motors stopped for safety!
Motors DISABLED (stopped)
```

It is **not** the 0.05 mm / 6 s position guard described in `ROADMAP.md`. There are two
independent stall detectors and only this one is switchable.

| | velocity guard (this file) | position guard |
|---|---|---|
| where | `main.py` `_handle_motor_stall`, in the velocity handler | `_policy_step` / auto-stop path |
| test | motor RPM below a fixed floor | crosshead advance over a time window |
| scales with commanded speed | **no** | yes (`_stall_threshold_mm`) |
| switchable | **yes, default ON** | no |

---

## What it does

Fires when **all** of these hold:

1. `stall_detection_enabled` — **on** unless the operator unticks the box
2. Motors enabled
3. Direction is not Stop
4. Past the 1-second movement-start grace period
5. Not in a preload
6. **Both** instantaneous and averaged RPM below **0.5**, for **3 consecutive** readings

Then it sends `EStop`, disables the motors and resets direction to Stop.

---

## Why it was written, and why that reason is gone

| Date | Event |
|---|---|
| **2026-06-22** | `a4573d8` adds the guard. The rig is stalling near 2.6 kN. |
| 2026-07-28 | S15 stalls at 2.6 kN. **S16 fractures at 3792 N the same day**, +46 % on the same rig at the same speed. |
| **2026-08-12** | `9061daf` — the root cause is found. |

The "torque ceiling" was never a motor limit. **The load holders had worked loose, the
crossheads sat out of alignment, and the motor was spending its torque on binding instead of
on the specimen.** Re-tightened and lubricated, the rig pulls 3.5 kN with no stutter. The
commit puts it plainly: *"A fastener, not a purchase and not a code change."*

Eleven 100 %-infill specimens had already fractured at 3586–3826 N across three months —
straight through the supposed ceiling. The evidence was on disk before the fault was found.

**A mechanical fault was met with a software guard.** The guard did real work at the time:
S15 and T7 were caught by it and excluded from the results rather than silently averaged in.
But the fault it was compensating for has been repaired, and the guard outlived it.

---

## Why it misfires now

Two design faults, both visible in an ordinary jog:

**The averaged term lags the ramp at both ends.** From a real run:

```
<< Going up fast!
Velocity:   2.76 RPM (avg:   0.14 RPM)     <- avg still ~0 while the motor is turning
Velocity:   3.84 RPM (avg:   0.72 RPM)
...
Velocity: 453.99 RPM (avg: 451.83 RPM)
<< Stop and halt!
Velocity:   3.22 RPM (avg:  18.14 RPM)
Velocity:   0.00 RPM (avg:   9.53 RPM)     <- instantaneous 0 while avg is still high
```

Requiring *both* below 0.5 papers over this, but only by accident: any window where the ramp
is slow enough that both terms sit low — and the 1-second grace period has already expired —
reads as a stall on a perfectly healthy motor.

**The threshold does not scale with the commanded speed.** 0.5 RPM at the motor is
**0.00208 mm/s** at the crosshead, whatever speed was asked for:

| crosshead | motor | verdict |
|---|---|---|
| 0.100 mm/s | 24.0 RPM | ok |
| 0.010 mm/s | 2.4 RPM | ok |
| 0.005 mm/s | 1.2 RPM | ok |
| 0.002 mm/s | 0.48 RPM | **reads as a stall** |

A test slower than ~0.002 mm/s can never run with this guard on. The position guard already
solves this properly — `_stall_threshold_mm` scales the bar with commanded speed.

---

## If it is to come back

A stall is a **collapse from a commanded speed**, not an absolute floor. Any redesign should:

- **Compare against the commanded speed**, not a constant. Expected RPM is known:
  `rpm = mm_s / 5 * 20 * 60`. Flag when measured falls below some fraction of it.
- **Detect the drop**, not the level. A genuine stall is a sudden fall from a speed that was
  being held; a ramp is a rise from zero. The two are distinguishable by sign and by whether
  the motor has ever reached its commanded speed during this move.
- **Wait until the move has actually reached speed** before arming at all, instead of a flat
  1-second grace period that has no relationship to the ramp length (`setRampLen(100)`).
- **Cross-check the second encoder.** `D32_Firmware/src/main.cpp:35` pins `SENS_IDX 0`, so one
  sensor is trusted with no corroboration. Two encoders disagreeing is a far better stall
  signal than one encoder reading low, and it also catches the crosshead racking that caused
  the original fault. See `MECHANICAL_TODO.md` §2.

**Do not re-enable it by default until at least the first two are done.**

---

## The lesson worth keeping

The rig was carrying a hardware limit for three weeks and four causes were ranked on the T7
slide — three electrical, one mechanical. The mechanical one was ranked **last**. It was the
mechanical one.

When the machine misbehaves, check the machine before adding a guard to the software. A guard
that compensates for a mechanical fault hides the fault, and then outlives the repair.
