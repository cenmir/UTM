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
    """Load–unload between two FORCE bounds for N cycles (hysteresis / stiffness degradation).

    `waveform`:
      • 'triangle' — constant-speed ramps up and down (sharp velocity reversal at each peak).
      • 'sine'     — the speed is eased by the load fraction, spd = speed·sin(π·frac), so it slows to
                     a crawl approaching each bound and is fastest at mid-load. This rounds the peaks
                     (no velocity kink) → smooth, sine-shaped cycles, better for viscoelastic
                     hysteresis loops. LOW frequency only — the rig can't do fatigue-rate cycling.
    Both respect the Low/High bounds EXACTLY (same reversal logic); the period is emergent (set by
    speed + specimen stiffness), as with the triangle."""
    name = "cyclic"

    def __init__(self, f_low: float, f_high: float, cycles: int, speed: float = 0.1,
                 waveform: str = "triangle"):
        self.f_low, self.f_high, self.cycles, self.speed = f_low, f_high, cycles, speed
        self.waveform = waveform
        self.dir = "tension"
        self.done_cycles = 0

    def step(self, s: Signals) -> Command:
        if self.dir == "tension" and s.load >= self.f_high:
            self.dir = "compression"
        elif self.dir == "compression" and s.load <= self.f_low:
            self.dir = "tension"
            self.done_cycles += 1
            if self.done_cycles >= self.cycles:
                return Command(0, "hold", done=True, message=f"{self.cycles} cycles complete")
        spd = self.speed
        if self.waveform == "sine":
            frac = (s.load - self.f_low) / max(1e-6, self.f_high - self.f_low)
            frac = min(1.0, max(0.0, frac))
            spd = max(0.01, self.speed * math.sin(math.pi * frac))   # ease to a crawl at each bound
        return Command(spd, self.dir, message=f"cycle {self.done_cycles + 1}/{self.cycles}")

    def start_message(self) -> str:
        return f"Cyclic {self.waveform} {self.f_low:.0f}-{self.f_high:.0f} N x{self.cycles} @ {self.speed:.3f} mm/s"


class StaircasePolicy(ControlPolicy):
    """Step the load up through `levels` (N); at each level HOLD for `dwell_s` (records the
    stress-relaxation at that step) before advancing. Automates the manual V4b/V4c staircases."""
    name = "staircase"

    def __init__(self, levels: List[float], dwell_s: float, speed: float = 0.1,
                 ramp_shape: str = "linear"):
        self.levels = list(levels)
        self.dwell = dwell_s
        self.speed = speed
        self.ramp_shape = ramp_shape
        self.i = 0
        self.holding = False
        self.hold_start = 0.0

    def _ramp_speed(self, load: float) -> float:
        """Constant speed for 'linear'; for 'smooth' ease to a crawl as the load nears the target
        level (spd = speed·sin(π·frac) between the previous and target level) so each level is
        approached gently — less overshoot past the target and a cleaner start-of-hold."""
        if self.ramp_shape != "smooth":
            return self.speed
        target = self.levels[self.i]
        prev = self.levels[self.i - 1] if self.i > 0 else 0.0
        span = target - prev
        if span <= 1e-6:
            return self.speed
        frac = min(1.0, max(0.0, (load - prev) / span))
        return max(0.01, self.speed * math.sin(math.pi * frac))

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
                 hold_speed: float = 0.01, tol_N: float = 5.0):
        self.target_load = target_load
        self.duration = duration_s
        self.ramp_speed = ramp_speed
        self.hold_speed = hold_speed
        self.tol = tol_N
        self.phase = "ramp"
        self.hold_start = 0.0

    def step(self, s: Signals) -> Command:
        if self.phase == "ramp":
            if s.load >= self.target_load:
                self.phase = "hold"
                self.hold_start = s.t
            else:
                return Command(self.ramp_speed, "tension", message="ramp to creep load")
        if s.t - self.hold_start >= self.duration:
            return Command(0, "hold", done=True, message="creep complete")
        if s.load < self.target_load - self.tol:
            return Command(self.hold_speed, "tension", message="creep: hold load (+)")
        if s.load > self.target_load + self.tol:
            return Command(self.hold_speed, "compression", message="creep: hold load (−)")
        return Command(0, "hold", message=f"creep {s.t - self.hold_start:.0f}/{self.duration:.0f} s")

    def start_message(self) -> str:
        return f"Creep: hold {self.target_load:.0f} N for {self.duration:.0f} s"
