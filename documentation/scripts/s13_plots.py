"""Figures for the S13 black-specimen slides."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402

import s13_data as S                                               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, GRID = "#1A1A1A", "#666666", "#DDDDDD"
RED, GREEN, AMBER = "#C0392B", "#2F9E44", "#D29922"


def _frame(ax):
    ax.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.9)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_color(INK)


def _save(fig, path, dpi=190):
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return path


# ---------------------------------------------------------------- S13 on its own
def solo(path=None, *, figsize=(11.4, 6.4)):
    """The black specimen's own four views — the run as it happened."""
    d, r, s = S.run("S13"), S.run("S13")["r"], S.summary("S13")
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    fig.subplots_adjust(hspace=0.42, wspace=0.26, left=0.075, right=0.975, top=0.90, bottom=0.10)

    ax = axes[0, 0]
    x, y = S.curve("S13")
    ax.plot(x, y, lw=2.1, color=INK, zorder=5)
    for lbl, e, sg, c in (("yield", r["sy_ec"], r["sy"], GREEN),
                          ("UTS", r["uts_ec"], r["uts"], AMBER),
                          ("fracture", r["ef"] * 100, r["sigf"], RED)):
        ax.scatter([e], [sg], s=70, facecolor="white", edgecolor=c, lw=2, zorder=6, label=lbl)
    ax.set_title("Stress vs DIC strain", fontsize=10, color=INK)
    ax.set_xlabel("ε (%)", fontsize=9, color=INK)
    ax.set_ylabel("σ (MPa)", fontsize=9, color=INK)
    ax.set_xlim(0, None)
    ax.set_ylim(0, None)
    _frame(ax)
    ax.legend(loc="lower right", fontsize=8, frameon=True, edgecolor=GRID)

    ax = axes[0, 1]
    ax.plot(d["t"], d["F"], lw=1.5, color=INK, zorder=5)
    ax.axvline(d["t"][r["fr_i"]], color=RED, ls="--", lw=1.3)
    ax.text(d["t"][r["fr_i"]] - 2, np.nanmax(d["F"]) * 0.55, "fracture", fontsize=8.5,
            color=RED, ha="right", rotation=90)
    ax.set_title("Load vs time — the load cell, unaffected by DIC", fontsize=10, color=INK)
    ax.set_xlabel("t (s)", fontsize=9, color=INK)
    ax.set_ylabel("tared force (N)", fontsize=9, color=INK)
    _frame(ax)

    ax = axes[1, 0]
    v = d["valid"]
    ax.plot(d["t"], d["pos"] / S.GAUGE_MM * 100, lw=1.4, color=MUTED, zorder=4,
            label="crosshead / gauge")
    ax.plot(d["t"][v], d["ec"][v] * 100, lw=1.6, color=INK, zorder=5, label="DIC gauge strain")
    ax.set_title("DIC strain vs crosshead strain", fontsize=10, color=INK)
    ax.set_xlabel("t (s)", fontsize=9, color=INK)
    ax.set_ylabel("strain (%)", fontsize=9, color=INK)
    ax.set_ylim(0, 12)
    _frame(ax)
    ax.legend(loc="upper left", fontsize=8, frameon=True, edgecolor=GRID)

    ax = axes[1, 1]
    t, e = S.hold("S13")
    keep = t >= t[-1] - S.NOISE_WINDOW_S
    ax.plot(t[keep] - t[keep][0], e[keep] - e[keep].mean(), lw=1.2, color=INK, zorder=5)
    ax.axhline(0, color=MUTED, lw=0.8)
    for k in (1, -1):
        ax.axhline(k * s["rms"], color=GREEN, ls="--", lw=1.1)
    ax.text(0.2, s["rms"] * 1.25, f"±1 RMS = {s['rms']:.1f} µε", fontsize=8.5, color=GREEN)
    ax.set_title(f"DIC noise, specimen stationary (last {S.NOISE_WINDOW_S} s)",
                 fontsize=10, color=INK)
    ax.set_xlabel("time in hold (s)", fontsize=9, color=INK)
    ax.set_ylabel("strain, mean removed (µε)", fontsize=9, color=INK)
    _frame(ax)

    fig.suptitle(f"S13 · BLACK specimen, white spray dots · 100 % infill · "
                 f"UTS {s['UTS']:.2f} MPa · ε_f {s['ef']:.2f} %",
                 fontsize=12, color=INK, y=0.975)
    return _save(fig, path) if path else fig


# ---------------------------------------------------------------- S13 vs S26
def vs_s26(path=None, *, figsize=(12.8, 4.15)):
    """Head to head with the closest white run, same material."""
    fig, axes = plt.subplots(1, 2, figsize=figsize,
                             gridspec_kw=dict(width_ratios=[1.35, 1.0]))
    fig.subplots_adjust(wspace=0.20, left=0.062, right=0.978, top=0.84, bottom=0.155)

    ax = axes[0]
    for tag in ("S13", "S26"):
        x, y = S.curve(tag)
        s = S.summary(tag)
        ax.plot(x, y, lw=2.2, color=s["colour"], zorder=5,
                label=f"{s['label']} · {s['marker']}   UTS {s['UTS']:.2f} · E {s['E']:.2f} · "
                      f"ε_f {s['ef']:.2f} %")
        r = S.run(tag)["r"]
        ax.scatter([r["uts_ec"]], [r["uts"]], s=70, facecolor="white",
                   edgecolor=s["colour"], lw=2, zorder=6)
    ax.set_title("Stress vs strain — black against the closest white run", fontsize=10.5,
                 color=INK)
    ax.set_xlabel("DIC gauge strain ε (%)", fontsize=9.5, color=INK)
    ax.set_ylabel("Engineering stress σ (MPa)", fontsize=9.5, color=INK)
    ax.set_xlim(0, None)
    ax.set_ylim(0, None)
    _frame(ax)
    ax.legend(loc="lower right", fontsize=8.5, frameon=True, edgecolor=GRID)

    ax = axes[1]
    ins = [("UTS", "UTS"), ("σ_y", "sy"), ("E", "E"), ("ε_f", "ef")]
    x = np.arange(len(ins))
    black = [100 * (S.summary("S13")[k] / S.white_mean(k) - 1) for _, k in ins]
    spread = [S.white_spread(k) for _, k in ins]
    ax.bar(x - 0.2, black, 0.4, color=INK, zorder=5, label="S13 black vs white MEAN")
    ax.bar(x + 0.2, spread, 0.4, color="#BBBBBB", zorder=4,
           label="the two WHITE runs vs each other")
    ax.axhline(0, color=MUTED, lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels([n for n, _ in ins], fontsize=9.5)
    ax.set_ylabel("difference (%)", fontsize=9.5, color=INK)
    ax.set_title("Black-vs-white is SMALLER than white-vs-white", fontsize=10.5, color=INK)
    _frame(ax)
    ax.legend(loc="upper left", fontsize=8.5, frameon=True, edgecolor=GRID)

    fig.suptitle("S13 (BLACK) vs S26 (white) — same material, same protocol, 100 % infill",
                 fontsize=12, color=INK, y=0.965)
    return _save(fig, path) if path else fig


# ---------------------------------------------------------------- noise
def noise_fig(path=None, *, figsize=(11.4, 4.6)):
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    fig.subplots_adjust(wspace=0.24, left=0.07, right=0.975, top=0.86, bottom=0.15)

    ax = axes[0]
    for tag in S.ORDER:
        t, e = S.hold(tag)
        s = S.summary(tag)
        keep = t >= t[-1] - S.NOISE_WINDOW_S
        ax.plot(t[keep] - t[keep][0], e[keep] - e[keep].mean(), lw=1.2, color=s["colour"],
                label=f"{tag} {s['marker']}  RMS {s['rms']:.1f} µε")
    ax.set_title(f"Stationary hold, last {S.NOISE_WINDOW_S} s — every reading here is noise",
                 fontsize=10.5, color=INK)
    ax.set_xlabel("time in hold (s)", fontsize=9.5, color=INK)
    ax.set_ylabel("strain, mean removed (µε)", fontsize=9.5, color=INK)
    _frame(ax)
    ax.legend(loc="upper right", fontsize=8.5, frameon=True, edgecolor=GRID)

    ax = axes[1]
    for tag in S.ORDER:
        w, rms = S.noise_sweep(tag)
        s = S.summary(tag)
        ax.plot(w, rms, "o-", ms=4.5, lw=1.7, color=s["colour"], label=f"{tag} {s['marker']}")
    ax.axvline(S.NOISE_WINDOW_S, color=RED, ls="--", lw=1.2)
    ax.text(S.NOISE_WINDOW_S + 0.6, 4, "common window", fontsize=8.5, color=RED, rotation=90)
    ax.set_title("Why the window must be equal: RMS moves with it", fontsize=10.5, color=INK)
    ax.set_xlabel("window length (s)", fontsize=9.5, color=INK)
    ax.set_ylabel("RMS noise (µε)", fontsize=9.5, color=INK)
    ax.set_ylim(0, 22)
    _frame(ax)
    ax.legend(loc="lower right", fontsize=8.5, frameon=True, edgecolor=GRID)

    fig.suptitle("DIC noise — the BLACK specimen is the quietest of the three",
                 fontsize=12, color=INK, y=0.965)
    return _save(fig, path) if path else fig


# ---------------------------------------------------------------- coverage
def coverage_fig(path=None, *, figsize=(11.4, 4.6)):
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    fig.subplots_adjust(wspace=0.26, left=0.07, right=0.965, top=0.86, bottom=0.15)

    ax = axes[0]
    for tag in S.ORDER:
        s = S.summary(tag)
        g = S.run(tag)["gaps_ms"]
        g = g[g < 420]
        ax.hist(g, bins=42, alpha=0.6, color=s["colour"], zorder=4,
                label=f"{tag} {s['marker']} — median {s['gap_median']:.0f} ms")
    ax.axvline(S.STALE_MS, color=RED, lw=2.2, zorder=6)
    ax.text(S.STALE_MS + 8, ax.get_ylim()[1] * 0.8, f"matching window\n{S.STALE_MS} ms",
            fontsize=8.5, color=RED)
    ax.set_title("Gap between consecutive DIC readings", fontsize=10.5, color=INK)
    ax.set_xlabel("gap (ms)", fontsize=9.5, color=INK)
    ax.set_ylabel("count", fontsize=9.5, color=INK)
    _frame(ax)
    ax.legend(loc="upper right", fontsize=8, frameon=True, edgecolor=GRID)

    ax = axes[1]
    labs = [f"{t}\n{S.summary(t)['marker']}" for t in S.ORDER]
    x = np.arange(len(labs))
    cov = [S.summary(t)["coverage"] for t in S.ORDER]
    two = [S.summary(t)["two_blob"] for t in S.ORDER]
    ax.bar(x - 0.2, two, 0.4, color=GREEN, zorder=5, label="frames where 2 markers were FOUND")
    ax.bar(x + 0.2, cov, 0.4, color="#7FA8D0", zorder=5, label="load rows that GOT a strain value")
    for xi, (a, b) in enumerate(zip(two, cov)):
        ax.text(xi - 0.2, a + 2, f"{a:.0f}", ha="center", fontsize=8.5, color=INK)
        ax.text(xi + 0.2, b + 2, f"{b:.0f}", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=9)
    ax.set_ylabel("%", fontsize=9.5, color=INK)
    ax.set_ylim(0, 118)
    ax.set_title("Detection was perfect on all three — the loss is downstream",
                 fontsize=10.5, color=INK)
    _frame(ax)
    ax.legend(loc="lower left", fontsize=8, frameon=True, edgecolor=GRID)

    fig.suptitle("S13's 47 % coverage: a matching-window problem, not a marker-colour one",
                 fontsize=12, color=INK, y=0.965)
    return _save(fig, path) if path else fig


FIGURES = {"s13_solo.png": solo, "s13_vs_s26.png": vs_s26,
           "s13_noise.png": noise_fig, "s13_coverage.png": coverage_fig}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn(os.path.join(HERE, "..", "figures", name)))
