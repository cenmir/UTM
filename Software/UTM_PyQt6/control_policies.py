"""Software closed-loop control policies for the UTM  (Phase-0 F2 engine + Phase-B modes).

The auto-preload loop already proved the rig can be closed-loop-controlled in software:
read a live signal at ~11 Hz, compute the error, nudge SetSpeed. This module generalises
that ONE pattern into reusable *policies* so every test mode shares it.

Design contract (keeps hardware I/O and safety in the app, logic here):
  • A policy is PURE LOGIC + its own state. `step(Signals) -> Command`.
  • `Signals`  = the live readings the app already has (time, load N, position mm, DIC strain).
  • `Command`  = desired crosshead SPEED (mm/s, magnitude) + DIRECTION + a `done` flag.
  • The APP applies the command: maps direction to the firmware (Down = tension on this rig),
    throttles SetSpeed, and enforces the universal SAFETY NET (overshoot cap, max-force / max-
    travel limits, timeout, EStop, stall) ON TOP of whatever a policy asks for.

Validate every policy in `control_sim.py` (replay a CSV, or a spring plant) BEFORE any rig run.
No PyQt / hardware / matplotlib imports here — just logic, so it is unit-testable and safe.
"""
import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


# ----------------------------------------------------------------------------------------
@dataclass
class Signals:
    t: float                       # seconds (monotonic clock the app already keeps)
    load: float                    # N   — current force (anchor/tare per the app's convention)
    pos: float                     # mm  — crosshead position / travel from tare
    strain: Optional[float] = None # DIC gauge (Cauchy) strain, or None if DIC not tracking


@dataclass
class Command:
    speed: float                   # mm/s, magnitude (>= 0). The app clamps to MAX and throttles.
    direction: str = "tension"     # "tension" | "compression" | "hold"
    done: bool = False             # True -> the mode finished; the app stops & resets
    message: str = ""              # short status for the console/status bar


def _interp(knots: List[Tuple[float, float]], x: float) -> float:
    """Piecewise-linear interpolation over (x, y) knots (same helper the preload used)."""
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y1
    return knots[-1][1]


class ControlPolicy:
    """Base class. Subclasses implement step(); may override start_message()."""
    name = "policy"

    def step(self, s: Signals) -> Command:                       # pragma: no cover - interface
        raise NotImplementedError

    def start_message(self) -> str:
        return f"{self.name}: started"


# ========================================================================================
# Phase-0 F2 — the existing auto-preload, now a policy (must reproduce current behaviour)
# ========================================================================================
class ForceRampPolicy(ControlPolicy):
    """Ramp in tension to a target force with a load-fraction speed schedule, stopping at
    `factor`x target (the 1.03x offsets PLA stress relaxation). This IS the current
    `_preload_check` / `_preload_speed` behaviour, extracted verbatim."""
    name = "force-ramp (preload)"
    KNOTS = [(0.0, 0.20), (0.10, 0.20), (0.15, 0.10), (0.50, 0.10), (0.90, 0.02), (1.0, 0.02)]

    def __init__(self, target_load: float, factor: float = 1.03, direction: str = "tension"):
        self.target = float(target_load)
        self.factor = factor
        self.direction = direction

    def step(self, s: Signals) -> Command:
        if self.target <= 0:
            return Command(0, "hold", done=True, message="invalid target")
        if s.load >= self.factor * self.target:
            return Command(0, "hold", done=True,
                           message=f"reached {s.load:.1f} N (target {self.target:.0f} N x{self.factor:.2f})")
        spd = _interp(self.KNOTS, s.load / self.target)
        return Command(spd, self.direction)

    def start_message(self) -> str:
        return f"Force-ramp to {self.target:.0f} N (stop at {self.factor:.2f}x)"


# ========================================================================================
# Phase-B — closed-loop test modes (all reuse the same step() contract)
# ========================================================================================
class StrainRatePolicy(ControlPolicy):
    """TRUE material strain-rate control: adjust crosshead speed so the DIC gauge strain rate
    d(ε)/dt tracks `target_rate` (1/s) — compliance-free, unlike constant crosshead speed.
    Feed-forward start + proportional correction from the measured rate; falls back to a
    nominal speed while DIC is unavailable. Stops at `stop_strain` or on load collapse."""
    name = "strain-rate"

    def __init__(self, target_rate: float, gauge_mm: float, stop_strain: Optional[float] = None,
                 nominal_gauge_share: float = 0.5, kp: float = 0.6,
                 speed_limits: Tuple[float, float] = (0.005, 1.8), collapse_frac: float = 0.5):
        self.target_rate = float(target_rate)
        self.gauge = float(gauge_mm)
        self.stop_strain = stop_strain
        self.kp = kp
        self.smin, self.smax = speed_limits
        self.collapse_frac = collapse_frac
        # feed-forward: crosshead speed ~ target_rate * L0 / (fraction of travel reaching the gauge)
        self._speed = min(self.smax, max(self.smin,
                          target_rate * gauge_mm / max(0.1, nominal_gauge_share)))
        self._hist: List[Tuple[float, float]] = []   # (t, strain) window for rate estimate
        self._peak = 0.0
        self._armed = False

    def step(self, s: Signals) -> Command:
        self._peak = max(self._peak, s.load)
        if self._peak > 0 and s.load >= 0.3 * self._peak:
            self._armed = True
        if self._armed and s.load < self.collapse_frac * self._peak:
            return Command(0, "hold", done=True, message="load collapse (fracture)")
        if s.strain is not None:
            if self.stop_strain is not None and s.strain >= self.stop_strain:
                return Command(0, "hold", done=True, message=f"reached ε {s.strain:.4f}")
            self._hist.append((s.t, s.strain))
            self._hist = [(t, e) for (t, e) in self._hist if t >= s.t - 0.6]   # ~0.6 s window
            if len(self._hist) >= 2 and self._hist[-1][0] > self._hist[0][0]:
                measured = (self._hist[-1][1] - self._hist[0][1]) / (self._hist[-1][0] - self._hist[0][0])
                err = self.target_rate - measured
                self._speed = min(self.smax, max(self.smin, self._speed + self.kp * err * self.gauge))
        return Command(self._speed, "tension")

    def start_message(self) -> str:
        return f"Strain-rate control @ {self.target_rate:.2e} /s (feed-fwd {self._speed:.3f} mm/s)"


class CyclicPolicy(ControlPolicy):
    """Load-unload between two FORCE bounds for N cycles (hysteresis / stiffness degradation).

    `waveform`:
      - 'triangle' - constant-speed ramps up and down (sharp velocity reversal at each peak).
      - 'sine'     - speed follows 2*sqrt(frac*(1-frac)), the profile that makes the FORCE a true
                     sine in time. Smooth, rounded cycles; better hysteresis loops. LOW frequency
                     only -- the rig cannot do fatigue-rate cycling.

    Bound accuracy: the crosshead needs 1-2 s to turn round, so a reversal commanded AT the bound
    always coasts past it. `predictive` reverses early by a FORCE offset that is adapted from the
    overshoot actually observed (see `_adapt`). Rig runs T5/T6/T6.2 drove both design choices here.
    """
    name = "cyclic"

    def __init__(self, f_low: float, f_high: float, cycles: int, speed: float = 0.1,
                 waveform: str = "triangle", predictive: bool = True,
                 min_speed: float = 0.02, adapt_gain: float = 0.85, shape_margin: float = 0.05):
        self.f_low, self.f_high, self.cycles, self.speed = f_low, f_high, cycles, speed
        self.waveform = waveform
        self.predictive = predictive
        self.min_speed = min_speed
        self.adapt_gain = adapt_gain
        self.shape_margin = shape_margin
        self.span = max(1e-6, f_high - f_low)
        self.dir = "tension"
        self.done_cycles = 0
        # Reversal lead as a FORCE offset per direction, seeded at 0 so it grows from below.
        # (T6.2 showed a rate-scaled lead cannot work for a sine: the rate -> 0 exactly at the
        # bound, so the lead vanishes right when it is needed and the loop never converges.
        # A force-domain lead is rate-independent and converges for any waveform.)
        self._lead = {"tension": 0.0, "compression": 0.0}
        self._pend: Optional[Tuple[str, float, float]] = None   # (bound, extreme, lead_used)
        self._started = False                # the initial ramp-in to f_low has finished
        # Actual travel achieved. The waveform is shaped over THIS range, not the nominal bounds,
        # so there is no dead zone. (T6.2: troughs undershot to 60-80 N; below f_low the clamped
        # frac made the law return 0 and the speed floor took over -> the flat bottoms, and a
        # climb-out of 10.5 s vs 6.1 s for troughs that stayed above the bound.)
        self._lo_seen = f_low
        self._hi_seen = f_high

    def _adapt(self, s: Signals) -> None:
        """Once the crosshead has turned round, fold the observed bound violation into the lead.
        We backed off by `lead_used` and still ran `over` past the bound, so the true coast is
        `lead_used + over` -- which is exactly the lead to use next time. Damped by `adapt_gain`
        (converges ~C, 0.7C, 0.91C, 0.97C ... of the true coast). Also records the achieved
        extreme so the waveform is shaped over the real travel."""
        if self._pend is None:
            return
        bound, extreme, lead_used = self._pend
        if bound == "high":
            extreme = max(extreme, s.load)
            turned = s.load < extreme - 0.02 * self.span
            over, d = extreme - self.f_high, "tension"
        else:
            extreme = min(extreme, s.load)
            turned = s.load > extreme + 0.02 * self.span
            over, d = self.f_low - extreme, "compression"
        self._pend = (bound, extreme, lead_used)
        if turned:
            g = self.adapt_gain
            want = lead_used + over
            self._lead[d] = min(0.45 * self.span, max(0.0, (1.0 - g) * self._lead[d] + g * want))
            if bound == "high":
                self._hi_seen = extreme
            else:
                self._lo_seen = extreme
            self._pend = None

    def _wave_speed(self, load: float) -> float:
        """Triangle = constant speed. Sine = 2*sqrt(frac*(1-frac)) over the ACHIEVED range, widened
        by `shape_margin` so the profile never bottoms out onto the floor at the turnarounds."""
        if self.waveform != "sine":
            return self.speed
        m = self.shape_margin * max(1e-6, self._hi_seen - self._lo_seen)
        lo, hi = self._lo_seen - m, self._hi_seen + m
        frac = min(1.0, max(0.0, (load - lo) / max(1e-6, hi - lo)))
        return max(self.min_speed, self.speed * 2.0 * math.sqrt(frac * (1.0 - frac)))

    def step(self, s: Signals) -> Command:
        self._adapt(s)
        # Initial ramp-in: below the low bound there is no waveform to shape yet, so run at full
        # speed rather than crawling (T6 wasted ~16 s doing that).
        if not self._started:
            if s.load >= self.f_low:
                self._started = True
            else:
                return Command(self.speed, "tension", message="ramp-in to low bound")
        lead = min(self._lead[self.dir], 0.45 * self.span) if self.predictive else 0.0
        if self.dir == "tension" and s.load >= self.f_high - lead:
            self.dir = "compression"
            self._pend = ("high", s.load, lead)
        elif self.dir == "compression":
            # The final trough only has to STOP, not reverse, so it needs no lead - using one made
            # T6.2 finish at 133 N instead of ~100 N.
            final = (self.done_cycles + 1) >= self.cycles
            if s.load <= self.f_low + (0.0 if final else lead):
                self.dir = "tension"
                self._pend = ("low", s.load, lead)
                self.done_cycles += 1
                if self.done_cycles >= self.cycles:
                    return Command(0, "hold", done=True, message=f"{self.cycles} cycles complete")
        return Command(self._wave_speed(s.load), self.dir,
                       message=f"cycle {self.done_cycles + 1}/{self.cycles}")

    def start_message(self) -> str:
        pred = "predictive" if self.predictive else "no-lead"
        return (f"Cyclic {self.waveform} ({pred}) {self.f_low:.0f}-{self.f_high:.0f} N "
                f"x{self.cycles} @ {self.speed:.3f} mm/s")


class StaircasePolicy(ControlPolicy):
    """Step the load up through `levels` (N); at each level HOLD for `dwell_s` (records the
    stress-relaxation at that step) before advancing. Automates the manual V4b/V4c staircases."""
    name = "staircase"

    def __init__(self, levels: List[float], dwell_s: float, speed: float = 0.1,
                 ramp_shape: str = "linear", ease_frac: float = 0.25):
        self.levels = list(levels)
        self.dwell = dwell_s
        self.speed = speed
        self.ramp_shape = ramp_shape
        self.ease_frac = ease_frac
        self.i = 0
        self.holding = False
        self.hold_start = 0.0

    def _ramp_speed(self, load: float) -> float:
        """Constant speed for 'linear'. For 'smooth', run at full speed until the load is within
        `ease_frac` of the target level, then taper toward the crawl so the level is approached
        gently (same scheme as CreepPolicy). The crosshead needs ~1 s to decelerate, so a full-speed
        arrival coasts past the level: rig run T3 overshot 300/600/900 N by 45/47/53 N, while an
        eased arrival (T4) cut that to 6/5/8 N. Only the TOP of the ramp is tapered — easing the
        start buys no accuracy and doubled the ramp time in T4."""
        if self.ramp_shape != "smooth" or self.ease_frac <= 0:
            return self.speed
        target = self.levels[self.i]
        prev = self.levels[self.i - 1] if self.i > 0 else 0.0
        span = target - prev
        if span <= 1e-6:
            return self.speed
        frac = min(1.0, max(0.0, (load - prev) / span))
        if frac <= 1.0 - self.ease_frac:
            return self.speed
        return max(0.01, self.speed * (1.0 - frac) / self.ease_frac)

    def step(self, s: Signals) -> Command:
        if self.i >= len(self.levels):
            return Command(0, "hold", done=True, message="staircase complete")
        target = self.levels[self.i]
        if not self.holding:
            if s.load >= target:
                self.holding = True
                self.hold_start = s.t
                return Command(0, "hold", message=f"hold level {self.i + 1} @ {target:.0f} N")
            return Command(self._ramp_speed(s.load), "tension",
                           message=f"ramp to level {self.i + 1} ({target:.0f} N)")
        if s.t - self.hold_start >= self.dwell:
            self.i += 1
            if self.i >= len(self.levels):
                return Command(0, "hold", done=True, message="staircase complete")
            self.holding = False
            return Command(self._ramp_speed(s.load), "tension", message=f"ramp to level {self.i + 1}")
        return Command(0, "hold", message=f"dwell {s.t - self.hold_start:.0f}/{self.dwell:.0f} s")

    def start_message(self) -> str:
        return f"Staircase {self.ramp_shape} {self.levels} N, dwell {self.dwell:.0f} s"


class RelaxationPolicy(ControlPolicy):
    """Ramp to a target STRAIN (or load if no DIC), then HOLD the crosshead still (speed 0)
    and log the force decay for `duration_s` — a stress-relaxation test."""
    name = "stress-relaxation"

    def __init__(self, target_strain: float, duration_s: float, speed: float = 0.1,
                 target_load: Optional[float] = None):
        self.target_strain = target_strain
        self.target_load = target_load
        self.duration = duration_s
        self.speed = speed
        self.phase = "ramp"
        self.hold_start = 0.0

    def step(self, s: Signals) -> Command:
        if self.phase == "ramp":
            reached = (s.strain is not None and s.strain >= self.target_strain) \
                      or (self.target_load is not None and s.load >= self.target_load)
            if reached:
                self.phase = "hold"
                self.hold_start = s.t
                return Command(0, "hold", message="holding strain — logging relaxation")
            return Command(self.speed, "tension", message="ramp to hold strain")
        if s.t - self.hold_start >= self.duration:
            return Command(0, "hold", done=True, message="relaxation complete")
        return Command(0, "hold", message=f"relax {s.t - self.hold_start:.0f}/{self.duration:.0f} s")

    def start_message(self) -> str:
        return f"Relaxation: hold ε {self.target_strain:.3f} for {self.duration:.0f} s"


class CreepPolicy(ControlPolicy):
    """Ramp to a target LOAD, then hold the FORCE ~constant with small speed corrections and
    log the strain creep for `duration_s`."""
    name = "creep"

    def __init__(self, target_load: float, duration_s: float, ramp_speed: float = 0.1,
                 hold_speed: float = 0.01, tol_N: float = 5.0, ease_frac: float = 0.25):
        self.target_load = target_load
        self.duration = duration_s
        self.ramp_speed = ramp_speed
        self.hold_speed = hold_speed
        self.tol = tol_N
        self.ease_frac = ease_frac
        self.phase = "ramp"
        self.hold_start = 0.0

    def _approach_speed(self, load: float) -> float:
        """Full ramp speed until (1 - ease_frac)x target, then taper toward the crawl. The crosshead
        needs ~1 s to decelerate, so a full-speed arrival coasts past the target: rig run T1 asked for
        400 N and peaked at 448 N (+12%) before nudging back. Easing the last stretch removes that."""
        if self.ease_frac <= 0 or self.target_load <= 0:
            return self.ramp_speed
        r = load / self.target_load
        if r <= 1.0 - self.ease_frac:
            return self.ramp_speed
        return max(self.hold_speed, self.ramp_speed * max(0.0, (1.0 - r) / self.ease_frac))

    def step(self, s: Signals) -> Command:
        if self.phase == "ramp":
            if s.load >= self.target_load:
                self.phase = "hold"
                self.hold_start = s.t
            else:
                return Command(self._approach_speed(s.load), "tension", message="ramp to creep load")
        if s.t - self.hold_start >= self.duration:
            return Command(0, "hold", done=True, message="creep complete")
        if s.load < self.target_load - self.tol:
            return Command(self.hold_speed, "tension", message="creep: hold load (+)")
        if s.load > self.target_load + self.tol:
            return Command(self.hold_speed, "compression", message="creep: hold load (−)")
        return Command(0, "hold", message=f"creep {s.t - self.hold_start:.0f}/{self.duration:.0f} s")

    def start_message(self) -> str:
        return f"Creep: hold {self.target_load:.0f} N for {self.duration:.0f} s"


# ==========================================================================================
#  FRACTURE PROTOCOLS — non-monotonic routes to failure.
#
#  The plain "Fracture test" button runs a MONOTONIC (quasi-static) uniaxial tensile test to
#  failure: one continuous pull at constant crosshead speed until load collapse (ASTM D638 /
#  ISO 527). It yields ONE modulus, ONE yield point, ONE UTS. The two policies below reach the
#  same fracture but interrogate the specimen repeatedly on the way, so a single specimen
#  yields a CURVE of properties instead of a single point.
#
#  Fracture detection here is LOAD-COLLAPSE ONLY (the DIC lpx-jump test misfires on ductile
#  draw — see the V6 campaign). Crucially it must never confuse an INTENTIONAL unload with a
#  fracture, which is why the watch is armed per rising-stroke rather than globally.
# ==========================================================================================


class StaircaseToFracturePolicy(ControlPolicy):
    """(Protocol B) Step the load up in equal increments, dwelling at each level, and KEEP
    STEPPING until the specimen fractures. Incremental step loading.

    Versus a monotonic pull, one specimen gives you:
      • modulus re-measured on every step        -> stiffness vs load (damage accumulation)
      • a mini stress-relaxation at every level  -> viscoelastic response mapped across stress
      • sharp YIELD ONSET: the dwell drop is small and flat while elastic, then grows abruptly
        once the level passes yield -- far better resolved than a 0.2% offset on one curve.

    `log` accumulates one dict per completed level for the app/analysis to write out."""
    name = "staircase-fracture"

    def __init__(self, start_N: float, step_N: float, dwell_s: float, speed: float = 0.1,
                 ramp_shape: str = "smooth", ease_frac: float = 0.25, max_levels: int = 60):
        self.start_N, self.step_N, self.dwell = start_N, step_N, dwell_s
        self.speed = speed
        self.ramp_shape = ramp_shape
        self.ease_frac = ease_frac
        self.max_levels = max_levels
        self.level = start_N
        self.n = 0
        self.holding = False
        self.hold_start = 0.0
        self.log: List[dict] = []
        self._cur: dict = {}
        # Shared detector (utm_analysis) -- correct here because the load never intentionally
        # falls: the only drops are the few-% relaxation during a dwell, far above its 50%
        # collapse threshold. Imported lazily so this module stays import-light.
        from utm_analysis import LiveFractureDetector
        self._det = LiveFractureDetector()

    def _ramp_speed(self, load: float) -> float:
        """Taper only the TOP of each step, exactly as StaircasePolicy (rig T3/T4: eased arrival
        cut level overshoot from 45-53 N to 5-8 N without doubling the ramp time)."""
        if self.ramp_shape != "smooth" or self.ease_frac <= 0:
            return self.speed
        prev = self.level - self.step_N
        span = self.level - prev
        if span <= 1e-6:
            return self.speed
        frac = min(1.0, max(0.0, (load - prev) / span))
        if frac <= 1.0 - self.ease_frac:
            return self.speed
        return max(0.01, self.speed * (1.0 - frac) / self.ease_frac)

    def step(self, s: Signals) -> Command:
        if self._det.update(s.load):
            self.log.append({"event": "fracture", "level": self.n + 1,
                             "level_N": self.level, "load": s.load, "pos": s.pos,
                             "strain": s.strain, "t": s.t})
            return Command(0, "hold", done=True,
                           message=f"FRACTURE on level {self.n + 1} ({self.level:.0f} N)")
        if self.n >= self.max_levels:
            return Command(0, "hold", done=True,
                           message=f"{self.n} levels reached without fracture (cap)")
        if not self.holding:
            if s.load >= self.level:
                self.holding = True
                self.hold_start = s.t
                self._cur = {"level": self.n + 1, "level_N": self.level, "arrive_load": s.load,
                             "arrive_pos": s.pos, "arrive_strain": s.strain, "t": s.t}
                return Command(0, "hold", message=f"hold {self.level:.0f} N")
            return Command(self._ramp_speed(s.load), "tension",
                           message=f"level {self.n + 1} -> {self.level:.0f} N")
        if s.t - self.hold_start >= self.dwell:
            self._cur.update({"end_load": s.load, "end_pos": s.pos, "end_strain": s.strain,
                              "relax_drop_N": self._cur.get("arrive_load", s.load) - s.load})
            self.log.append(self._cur)
            self.n += 1
            self.level += self.step_N
            self.holding = False
            return Command(self._ramp_speed(s.load), "tension",
                           message=f"level {self.n + 1} -> {self.level:.0f} N")
        return Command(0, "hold",
                       message=f"level {self.n + 1} dwell {s.t - self.hold_start:.0f}/{self.dwell:.0f} s")

    def start_message(self) -> str:
        return (f"Staircase to FRACTURE: {self.start_N:.0f} N +{self.step_N:.0f} N steps, "
                f"dwell {self.dwell:.0f} s, {self.ramp_shape} ramp @ {self.speed:.3f} mm/s")


class ProgressiveCyclicPolicy(ControlPolicy):
    """(Protocol A) Load-unload-reload with a RISING peak every cycle, until fracture.

    Each unload is a measurement, not just a return trip -- it gives the UNLOADING MODULUS at
    that damage state, so one specimen yields:
      • stiffness degradation  D = 1 - E_i/E_0   (the standard continuum-damage measure) vs stress
      • permanent set / residual strain per cycle (ratcheting)
      • hysteresis energy per cycle, evolving toward failure

    Fracture watch: a per-rising-stroke load-collapse check, NOT the always-on shared detector.
    The deliberate unload to `f_low` drops far below half the running peak and would trip that
    detector every single cycle. The watch is armed only once the load has climbed past halfway
    to the current target -- the specimen already survived the previous (lower) peak, so failure
    can only occur in new territory above it."""
    name = "progressive-cyclic"

    def __init__(self, start_N: float, step_N: float, f_low: float = 100.0, speed: float = 0.1,
                 collapse_frac: float = 0.6, max_cycles: int = 40, adapt_gain: float = 0.85):
        self.start_N, self.step_N, self.f_low = start_N, step_N, f_low
        self.speed = speed
        self.collapse_frac = collapse_frac
        self.max_cycles = max_cycles
        self.adapt_gain = adapt_gain
        self.target = start_N
        self.n = 0
        self.dir = "tension"
        # Force-domain adaptive reversal lead, same scheme validated on the rig in T6.3
        # (peaks converged 528/529/516/505/500 onto a 500 N bound).
        self._lead = {"tension": 0.0, "compression": 0.0}
        self._pend: Optional[Tuple[str, float, float, float]] = None
        self._peak = 0.0            # running peak of the current rising stroke
        self._armed = False         # collapse watch armed for this stroke
        self.log: List[dict] = []
        self._cyc: dict = {}

    def _span(self) -> float:
        return max(1.0, self.target - self.f_low)

    def _adapt(self, s: Signals) -> None:
        """Turn the observed bound violation into the next lead (see CyclicPolicy._adapt)."""
        if self._pend is None:
            return
        bound, extreme, lead_used, ref = self._pend
        if bound == "high":
            if s.load > extreme:
                # The crosshead coasts ~150 N past the trigger, so the TRUE peak is only known
                # once the stroke turns. Overwrite the logged trigger value as it climbs --
                # the unloading modulus and the damage curve both need the real peak.
                extreme = s.load
                self._cyc.update({"peak_load": s.load, "peak_pos": s.pos, "peak_strain": s.strain})
            turned, over, d = s.load < extreme - 0.02 * self._span(), extreme - ref, "tension"
        else:
            if s.load < extreme:
                extreme = s.load
                if self.log:
                    self.log[-1].update({"trough_load": s.load, "trough_pos": s.pos,
                                         "trough_strain": s.strain})
            turned, over, d = s.load > extreme + 0.02 * self._span(), ref - extreme, "compression"
        self._pend = (bound, extreme, lead_used, ref)
        if turned:
            g = self.adapt_gain
            self._lead[d] = min(0.4 * self._span(),
                                max(0.0, (1.0 - g) * self._lead[d] + g * (lead_used + over)))
            self._pend = None

    def step(self, s: Signals) -> Command:
        self._adapt(s)
        lead = min(self._lead[self.dir], 0.4 * self._span())
        if self.dir == "tension":
            if s.load > self._peak:
                self._peak = s.load
            if s.load >= self.f_low + 0.5 * (self.target - self.f_low):
                self._armed = True
            if self._armed and s.load < self.collapse_frac * self._peak:
                # A FRESH dict -- `_cyc` is the same object already appended at the last trough,
                # so updating and re-appending it would rewrite that row and duplicate it.
                self.log.append({"event": "fracture", "cycle": self.n + 1,
                                 "target_N": self.target, "fracture_peak": self._peak,
                                 "pos": s.pos, "strain": s.strain, "t": s.t})
                return Command(0, "hold", done=True,
                               message=f"FRACTURE on cycle {self.n + 1} (peak {self._peak:.0f} N)")
            if s.load >= self.target - lead:
                self._cyc = {"cycle": self.n + 1, "target_N": self.target, "peak_load": s.load,
                             "peak_pos": s.pos, "peak_strain": s.strain, "t_peak": s.t}
                self._pend = ("high", s.load, lead, self.target)
                self.dir = "compression"
                return Command(self.speed, "compression",
                               message=f"cycle {self.n + 1}: unload to {self.f_low:.0f} N")
            return Command(self.speed, "tension",
                           message=f"cycle {self.n + 1} -> {self.target:.0f} N")
        # ---- unloading ----
        if s.load <= self.f_low + lead:
            self._cyc.update({"trough_load": s.load, "trough_pos": s.pos,
                              "trough_strain": s.strain, "t_trough": s.t})
            self.log.append(self._cyc)
            self._pend = ("low", s.load, lead, self.f_low)
            self.n += 1
            if self.n >= self.max_cycles:
                return Command(0, "hold", done=True,
                               message=f"{self.n} cycles without fracture (cap)")
            self.target += self.step_N
            self._peak, self._armed = 0.0, False
            self.dir = "tension"
            return Command(self.speed, "tension",
                           message=f"cycle {self.n + 1} -> {self.target:.0f} N")
        return Command(self.speed, "compression",
                       message=f"cycle {self.n + 1}: unload to {self.f_low:.0f} N")

    def start_message(self) -> str:
        return (f"Progressive cyclic to FRACTURE: peaks {self.start_N:.0f} N +{self.step_N:.0f} N, "
                f"unload to {self.f_low:.0f} N @ {self.speed:.3f} mm/s")
