# Gauge length, the modulus, and why the numbers moved

**Findings from 2026-08-30.** Four X-PLA specimens, 100 % infill, 80 mm² section, pulled to
fracture at 0.1 mm/s — one each at 80, 70, 60 and 50 mm gauge.

---

## 1. The gauge is 60 mm, not 80 mm

At 80 mm the marker dots land on the **fillets** of this dogbone, not inside the parallel
section. Confirmed on the fractured specimen: both dots sat at the shoulder transitions, and
the specimen broke *at* the lower one.

That is wrong twice over:

- Strain then averages over a region of **changing cross-section**, so it is not the gauge
  strain the stress is paired with.
- A fillet is a **stress concentration**. The material there strains more than the uniform
  gauge, so markers on it over-read strain and *understate* E.
- A specimen that breaks outside the gauge section is **not a valid tensile result** under
  ASTM D638 / ISO 527.

60 mm keeps both markers well inside the parallel section with clearance at each end, and has
a second benefit: L₀ drops to ~1270 px, which clears the framing check for a 30 mm pull
**without moving the camera**. At 80 mm the check failed by 38 px.

**Defaults changed 2026-08-30:** `main.py` runtime, the `.ui` spin box, and `utm_recipes`
all now start at 60 mm.

> ⚠ The gauge is a property of the SPECIMEN, not of the app. Measure the parallel section with
> calipers and put the real number in. 60 mm is the right default for the current dogbone; it
> is not a constant of nature.

---

## 2. What the four runs actually measured

| | 80 mm | 70 mm | 60 mm | 50 mm | spread |
|---|---|---|---|---|---|
| **UTS** | 41.02 | 40.78 | 40.46 | 40.22 MPa | **2.0 %** |
| **ε_f** | 2.89 | 2.85 | 2.81 | 3.20 % | 13 % |
| E *(adaptive rule)* | 3.240 | 4.705 | 3.503 | 2.756 GPa | **55 %** |
| σ_y *(adaptive)* | 37.65 | 32.89 | 33.94 | **1.28** MPa | broken |

**Strength is measured well.** Four specimens, UTS agreeing to 2.0 % — about 0.8 % CV on
printed dogbones. `UTS ≈ 40.6 MPa` for this X-PLA is defensible.

**The modulus was not.** 55 % spread on identical material. And it is *not* specimen scatter:
if it were, UTS would scatter too, and it does not. The fault is entirely in the small-strain
region where E is fitted.

Two causes, and only one of them is a defect:

- **PLA has no linear region.** E falls monotonically with strain in every run — 3.1 GPa at
  0.2-0.5 % down to 2.2 GPa at 0.7-1.3 % on the same specimen. "The modulus" is a property of
  the window you choose. That is real physics and worth teaching.
- **The adaptive `steepest straight run` rule picks a different window every run** — from
  0.01-0.26 % to 0.44-0.69 %. That turns genuine non-linearity into apparent randomness. The
  70 mm run's 4.705 GPa came from a window starting at 0.01 % strain: pure toe, physically
  meaningless.

---

## 3. ISO 527-1 fixes most of it

The standard removes the decision by prescribing the window, and removes the seating slack by
**correcting** for it rather than preloading it away:

```python
window = (eps >= 0.0005) & (eps <= 0.0025)        # ISO 527 strain window, 0.05-0.25 %
E_fit, intercept = np.polyfit(eps[window], sigma[window], 1)
eps_corrected = eps + intercept / E_fit            # slide the axis: the toe is the FIXTURE
offset_line = E_fit * (eps_corrected - 0.002)      # R_p0.2 is where the curve crosses it
```

Applied to the same four runs:

| | adaptive rule | **ISO 527-1** |
|---|---|---|
| E spread | 54.9 % | **28.7 %** |
| σ_y | one run gave 1.28 MPa | **all four sane, 14.3 % spread** |

```
gauge   E GPa    toe shift   Rp0.2    Rm      eps_break
80 mm   3.462    +0.047 %    35.41    40.93   2.93 %
70 mm   4.604    +0.152 %    33.14    40.78   3.00 %
60 mm   4.098    +0.109 %    30.74    40.20   2.92 %
50 mm   3.772    +0.153 %    31.39    38.96   3.35 %

E 3.984 GPa (28.7 %) · Rp0.2 32.67 MPa (14.3 %) · Rm 40.22 MPa (4.9 %)
```

**The toe correction is the part the analyser is missing**, and it is what fixed the broken
1.28 MPa yield. That value came from the offset line crossing almost immediately because the
strain zero sat slightly negative; sliding the axis so the fitted line passes through the
origin removes exactly that failure mode.

---

## 4. Preload: 100 N, not 300 N

**ISO 527 does not prescribe a preload force.** It handles seating slack by the toe correction
above — in evaluation, not in the fixture. So the preload only has to be *consistent* and
*small enough not to eat the fit window*.

Why 300 N is wrong for an ISO evaluation, on this specimen:

| preload | stress | strain already used up (E ≈ 3.5 GPa) | ISO window 0.05-0.25 % |
|---|---|---|---|
| 50 N | 0.63 MPa | 0.018 % | barely touched |
| **100 N** | **1.25 MPa** | **0.036 %** | **mostly intact** |
| 300 N | 3.75 MPa | **0.107 %** | **half the window gone** |

L₀ is frozen AFTER the preload, so whatever is already stretched into the specimen is excluded
by design. At 300 N that is 0.107 % strain — the recorded 0.05 % is really 0.157 %, and the
whole fit sits **above** the window the standard asks for.

**Use 100 N, the same every run.** Lower is better if it still seats the specimen; the toe
correction handles the rest.

The residual 29 % E spread points the same way: the **toe shift varied 3×** across these four
runs (+0.047 % to +0.153 %), and their L₀ was frozen at 0, 49, 101 and 105 N. Consistent
seating is the next lever.

---

## 5. What to quote, and with what confidence

| quantity | confidence | note |
|---|---|---|
| **UTS** | high | 2 % across four specimens. No fit window involved. |
| **ε_f** | good | 13 %. |
| **σ_y** | fair, with ISO | 14 % — and only after the toe correction. |
| **E** | quote WITH ITS WINDOW | 29 % even under ISO. Never compare two runs fitted differently. |

For the student campaign: UTS and ε_f are the numbers to build exercises on. E is a good
teaching topic precisely *because* it is not a single number — but it must be reported with
the strain window beside it, or forty groups will conclude the material varies when it is the
method that does.

---

## 6. What we cannot say

**Whether gauge length itself affects the result.** One specimen per gauge means gauge effect
and specimen scatter are perfectly confounded. E vs gauge correlates at r = +0.41 and E vs
preload at r = +0.21 — at n = 4 neither means anything.

**n ≥ 3 per gauge** would separate them. Given how tight UTS is, gauge length is unlikely to be
the driver.

---

## 7. Open

- [ ] Implement ISO 527-1 in `utm_analysis.py` — prescribed window + toe correction — reported
      **alongside** the existing `E` so historical numbers stay recoverable.
- [ ] Clamp any fit whose window starts below ~0.1 % strain. That is what produced 4.7 GPa.
- [ ] Standardise the preload at 100 N and check whether the toe shift tightens.
- [ ] The 80 mm specimen fractured **at a fillet**. If that recurs, the fillet radius is too
      tight and it is a specimen-design problem, not a test one.
