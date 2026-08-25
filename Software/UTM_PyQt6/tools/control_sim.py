"""Simulation harness for the UTM control policies (control_policies.py).

Runs each policy against a simple spring PLANT so its SpeedCommands actually move a
simulated specimen — a closed loop with NO hardware. Use this to validate control logic
(does force-ramp stop at target? does cyclic do N cycles? does strain-rate converge?
does staircase dwell? do relax/creep hold?) BEFORE ever wiring a policy to the motor.

Also exposes replay_csv(): feed a recorded test's (t, load, pos, strain) through a policy
to check its stop conditions against real data.

    python control_sim.py            # runs the validation suite, prints PASS/FAIL per mode
"""
# Run from the APP directory (Software/UTM_PyQt6), which is also where this script's data and
# output paths are resolved from:  python tools/control_sim.py
# The app modules live one level up, so put that on the path before importing them.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from control_policies import (Signals, ForceRampPolicy, StrainRatePolicy, CyclicPolicy,
                              StaircasePolicy, RelaxationPolicy, CreepPolicy)

_SGN = {"tension": 1.0, "compression": -1.0, "hold": 0.0}


class SpringPlant:
    """Elastic specimen+rig with a force plateau. Crosshead position integrates the commanded
    speed; force = k·pos (capped at f_cap); DIC strain = pos·gauge_share / gauge_length.
    Enough to exercise every policy's LOGIC (transitions, counts, stops, rate tracking).
    Real stress-relaxation/creep dynamics are NOT modelled — those need the rig."""

    def __init__(self, k=900.0, gauge_share=0.55, gauge_mm=80.0, f_cap=3700.0):
        self.k, self.gs, self.gauge, self.f_cap = k, gauge_share, gauge_mm, f_cap
        self.pos = 0.0

    def load(self):
        return min(self.k * self.pos, self.f_cap)

    def strain(self):
        return self.pos * self.gs / self.gauge

    def advance(self, cmd, dt):
        self.pos = max(0.0, self.pos + _SGN[cmd.direction] * cmd.speed * dt)


def run_plant(policy, plant=None, dt=0.09, max_t=400.0):
    """Closed-loop: policy <-> plant. Returns a trajectory dict + the final Command."""
    plant = plant or SpringPlant()
    t = 0.0
    traj = {"t": [], "load": [], "strain": [], "pos": [], "speed": [], "dir": []}
    last = None
    while t < max_t:
        s = Signals(t=t, load=plant.load(), pos=plant.pos, strain=plant.strain())
        cmd = policy.step(s)
        traj["t"].append(t); traj["load"].append(s.load); traj["strain"].append(s.strain)
        traj["pos"].append(s.pos); traj["speed"].append(cmd.speed); traj["dir"].append(cmd.direction)
        last = cmd
        if cmd.done:
            break
        plant.advance(cmd, dt)
        t += dt
    return traj, last


def replay_csv(policy, csv_path, anchor=0.0, ec0=0.0):
    """Feed a recorded test through a policy (does NOT close the loop — the trajectory is fixed).
    Validates stop-detection / schedule against real data. Returns (fired_index, command)."""
    from utm_analysis import read_csv
    data = read_csv(csv_path)
    for i, d in enumerate(data):
        cmd = policy.step(Signals(t=d["t"], load=d["F"] + anchor, pos=d["pos"],
                                  strain=(d["ec"] - ec0)))
        if cmd.done:
            return i, cmd
    return None, cmd


# ----------------------------------------------------------------------------------------
def _pk(x):        # peak of a list
    return max(x) if x else 0.0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    results = []

    def check(name, cond, detail):
        results.append((name, cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}: {detail}")

    print("=== F2 · ForceRampPolicy (auto-preload, target 470 N, stop 1.03x) ===")
    tr, last = run_plant(ForceRampPolicy(470))
    check("force-ramp stops at ~1.03x target", last.done and 470 <= _pk(tr["load"]) <= 500,
          f"final load {tr['load'][-1]:.1f} N, done={last.done} ({last.message})")
    # speed schedule: fast early, gentle near target
    early = tr["speed"][2] if len(tr["speed"]) > 2 else 0
    check("speed schedule ramps fast->gentle", early >= 0.19 and tr["speed"][-1] <= 0.03,
          f"early {early:.3f} mm/s -> final {tr['speed'][-1]:.3f} mm/s")

    print("=== Phase B · StrainRatePolicy (target 1e-3 /s, stop ε 0.03) ===")
    tr, last = run_plant(StrainRatePolicy(1e-3, gauge_mm=80.0, stop_strain=0.03))
    # measured rate over the middle of the run
    mid = len(tr["t"]) // 2
    win = [(tr["t"][k], tr["strain"][k]) for k in range(mid, min(mid + 8, len(tr["t"])))]
    rate = (win[-1][1] - win[0][1]) / (win[-1][0] - win[0][0]) if len(win) > 1 else 0
    check("strain rate converges to target", 0.7e-3 <= rate <= 1.3e-3, f"measured {rate:.2e} /s (target 1.0e-3)")
    check("stops at target strain", last.done and abs(tr["strain"][-1] - 0.03) < 0.003,
          f"final ε {tr['strain'][-1]:.4f}, done={last.done}")

    print("=== Phase B · CyclicPolicy (500-2500 N x3) ===")
    tr, last = run_plant(CyclicPolicy(500, 2500, 3))
    reversals = sum(1 for k in range(1, len(tr["dir"])) if tr["dir"][k] != tr["dir"][k - 1])
    check("completes 3 cycles then stops", last.done and "3 cycles" in last.message,
          f"done={last.done} ({last.message}); {reversals} direction reversals")
    check("load stayed within bounds", 450 <= _pk(tr["load"]) <= 2600, f"peak load {_pk(tr['load']):.0f} N")

    print("=== Phase B · StaircasePolicy ([1000,2000,3000] N, dwell 15 s) ===")
    tr, last = run_plant(StaircasePolicy([1000, 2000, 3000], dwell_s=15.0))
    holds = sum(1 for k in range(1, len(tr["dir"])) if tr["dir"][k] == "hold" and tr["dir"][k - 1] != "hold")
    check("visits 3 levels with dwells, then stops", last.done and holds >= 3,
          f"done={last.done}; {holds} hold phases; peak {_pk(tr['load']):.0f} N")

    print("=== Phase B · RelaxationPolicy (hold ε 0.02 for 20 s) ===")
    tr, last = run_plant(RelaxationPolicy(target_strain=0.02, duration_s=20.0))
    held = sum(1 for d in tr["dir"] if d == "hold")
    check("reaches strain then holds to completion", last.done and tr["strain"][-1] >= 0.019 and held > 100,
          f"final ε {tr['strain'][-1]:.4f}, {held} hold samples, done={last.done}")

    print("=== Phase B · CreepPolicy (hold 2000 N for 20 s) ===")
    tr, last = run_plant(CreepPolicy(target_load=2000, duration_s=20.0))
    check("reaches load then holds to completion", last.done and abs(tr["load"][-1] - 2000) < 60,
          f"final load {tr['load'][-1]:.0f} N, done={last.done} ({last.message})")

    n_pass = sum(1 for _, c in results if c)
    print(f"\n=== {n_pass}/{len(results)} checks passed ===")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
