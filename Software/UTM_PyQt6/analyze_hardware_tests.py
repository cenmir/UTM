"""
Phase 8.6 Hardware Test Analyzer (stationary-specimen variant).

Runs three checks on a single CSV exported from the UTM GUI:
  * 8.6.5  GUI stability        - frame rate, interval jitter, drops
  * 8.6.10 DIC-LoadCell sync    - stall rows get unique DIC timestamps
  * Noise floor / drift         - DIC strain std dev and linear drift

Usage:
    python analyze_hardware_tests.py <path-to-csv>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


STALE_THRESHOLD_MS = 100.0
NOISE_FLOOR_STD_LIMIT = 1e-3        # strain std dev should be < this
DRIFT_LIMIT_PER_MIN = 5e-4          # monotonic drift should be < this / min
MCU_INTERVAL_TARGET_MS = 88.0       # firmware loop ~88 ms (11.4 Hz)
MCU_INTERVAL_LIMIT_MS = 200.0       # any interval > this is a drop / stall


def load_csv(path: Path) -> pd.DataFrame:
    with path.open() as f:
        header_row = 0
        for i, line in enumerate(f):
            if not line.startswith("#"):
                header_row = i
                break
    df = pd.read_csv(path, comment="#", header=0, skiprows=header_row)
    df.columns = [c.strip() for c in df.columns]
    return df


def test_gui_stability(df: pd.DataFrame) -> dict:
    """8.6.5 — verify MCU interval jitter and detect GUI stalls."""
    mcu = df["MCU_Time_s"].to_numpy() * 1000.0  # ms
    intervals = np.diff(mcu)
    intervals = intervals[intervals > 0]

    stalls = intervals[intervals > MCU_INTERVAL_LIMIT_MS]
    return {
        "samples": len(df),
        "duration_s": float(mcu[-1] - mcu[0]) / 1000.0,
        "mcu_interval_mean_ms": float(np.mean(intervals)),
        "mcu_interval_std_ms": float(np.std(intervals)),
        "mcu_interval_max_ms": float(np.max(intervals)),
        "effective_rate_hz": 1000.0 / float(np.mean(intervals)),
        "stall_count": int(len(stalls)),
        "stall_max_ms": float(np.max(stalls)) if len(stalls) else 0.0,
    }


def test_timestamp_sync(df: pd.DataFrame) -> dict:
    """8.6.10 — stall rows (same PC Time_s) must get distinct DIC_Time_s."""
    pc_time = df["Time_s"].to_numpy()
    dic_time = df["DIC_Time_s"].to_numpy()
    lag = df["Lag_ms"].to_numpy()

    # Group by PC time; any group of 2+ is a stall burst.
    _, inverse, counts = np.unique(pc_time, return_inverse=True, return_counts=True)
    stall_groups = np.where(counts >= 2)[0]

    recovered = 0
    collapsed = 0
    for g in stall_groups:
        rows = np.where(inverse == g)[0]
        unique_dic = len(np.unique(dic_time[rows]))
        if unique_dic == len(rows):
            recovered += 1
        elif unique_dic == 1:
            collapsed += 1

    stale_rows = int(np.sum(lag > STALE_THRESHOLD_MS))
    fresh_rows = int(np.sum((lag >= 0) & (lag <= STALE_THRESHOLD_MS)))

    return {
        "stall_bursts_total": int(len(stall_groups)),
        "stall_bursts_recovered": recovered,
        "stall_bursts_collapsed": collapsed,
        "lag_mean_ms": float(np.mean(lag)),
        "lag_median_ms": float(np.median(lag)),
        "lag_max_ms": float(np.max(lag)),
        "fresh_rows": fresh_rows,
        "stale_rows": stale_rows,
    }


def test_noise_floor(df: pd.DataFrame) -> dict:
    """Stationary markers → ε should stay ≈ 0. Measure std dev and drift."""
    mcu_min = df["MCU_Time_s"].to_numpy() / 60.0
    mcu_min = mcu_min - mcu_min[0]

    results = {}
    for col in ("DIC_Cauchy", "DIC_True"):
        y = df[col].to_numpy()
        # Linear fit against MCU time (min) → slope = strain drift / min.
        slope, intercept = np.polyfit(mcu_min, y, 1)
        results[f"{col}_mean"] = float(np.mean(y))
        results[f"{col}_std"] = float(np.std(y))
        results[f"{col}_max_abs"] = float(np.max(np.abs(y)))
        results[f"{col}_drift_per_min"] = float(slope)
    return results


def fmt(v, unit=""):
    if isinstance(v, float):
        if abs(v) < 1e-3 and v != 0:
            return f"{v:.3e}{unit}"
        return f"{v:.4f}{unit}"
    return f"{v}{unit}"


def verdict(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def report(df: pd.DataFrame) -> None:
    print("=" * 68)
    print("PHASE 8.6 HARDWARE TEST REPORT (stationary specimen)")
    print("=" * 68)

    s = test_gui_stability(df)
    pass_rate = abs(s["mcu_interval_mean_ms"] - MCU_INTERVAL_TARGET_MS) < 30.0
    pass_stalls = s["stall_count"] <= 1
    print(f"\n[8.6.5] GUI Stability")
    print(f"  Samples:             {s['samples']}")
    print(f"  Duration:            {fmt(s['duration_s'], ' s')}")
    print(f"  MCU interval:        {fmt(s['mcu_interval_mean_ms'], ' ms')} "
          f"+/- {fmt(s['mcu_interval_std_ms'], ' ms')} "
          f"(max {fmt(s['mcu_interval_max_ms'], ' ms')})")
    print(f"  Effective rate:      {fmt(s['effective_rate_hz'], ' Hz')}")
    print(f"  Stalls (>200ms):     {s['stall_count']} "
          f"(worst {fmt(s['stall_max_ms'], ' ms')})")
    print(f"  Verdict:             rate {verdict(pass_rate)}, stalls {verdict(pass_stalls)}")

    t = test_timestamp_sync(df)
    pass_recovered = t["stall_bursts_collapsed"] == 0
    print(f"\n[8.6.10] DIC <-> Load Cell Timestamp Sync")
    print(f"  Stall bursts total:      {t['stall_bursts_total']}")
    print(f"   - recovered (unique DIC): {t['stall_bursts_recovered']}")
    print(f"   - collapsed (same DIC):   {t['stall_bursts_collapsed']}")
    print(f"  Lag:  mean {fmt(t['lag_mean_ms'], ' ms')}, "
          f"median {fmt(t['lag_median_ms'], ' ms')}, "
          f"max {fmt(t['lag_max_ms'], ' ms')}")
    print(f"  Fresh rows (lag<=100ms): {t['fresh_rows']}")
    print(f"  Stale rows (lag>100ms):  {t['stale_rows']}")
    print(f"  Verdict:             {verdict(pass_recovered)}")

    n = test_noise_floor(df)
    pass_std = (n["DIC_Cauchy_std"] < NOISE_FLOOR_STD_LIMIT
                and n["DIC_True_std"] < NOISE_FLOOR_STD_LIMIT)
    pass_drift = (abs(n["DIC_Cauchy_drift_per_min"]) < DRIFT_LIMIT_PER_MIN
                  and abs(n["DIC_True_drift_per_min"]) < DRIFT_LIMIT_PER_MIN)
    print(f"\n[Noise Floor] Stationary-marker DIC drift")
    for col in ("DIC_Cauchy", "DIC_True"):
        print(f"  {col}:")
        print(f"    mean:           {fmt(n[f'{col}_mean'])}")
        print(f"    std dev:        {fmt(n[f'{col}_std'])}")
        print(f"    max |eps|:      {fmt(n[f'{col}_max_abs'])}")
        print(f"    drift per min:  {fmt(n[f'{col}_drift_per_min'])}")
    print(f"  Verdict:             std {verdict(pass_std)}, drift {verdict(pass_drift)}")

    print("\n" + "=" * 68)
    all_pass = pass_rate and pass_stalls and pass_recovered and pass_std and pass_drift
    print(f"OVERALL: {verdict(all_pass)}")
    print("=" * 68)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"CSV not found: {path}")
        sys.exit(1)
    df = load_csv(path)
    report(df)


if __name__ == "__main__":
    main()
