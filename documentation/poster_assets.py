"""Proof assets that had no generator — SF2 (Prepare specimen) and SF8 (Release load).

Both are WORKFLOW features, not measurements, so these are drawn as schematics rather than plots and
are labelled as such on the poster. Every number in them comes from the rig-test record in
`Software/UTM_PyQt6/docs/TESTING_TODO.md` (SF2 = checklist item #2, SF8 = the "bonus" item confirmed
2026-07-27 and retuned at line 139); nothing here is invented.

    python documentation/poster_assets.py
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, RED, GREEN, GREY, ORANGE = "#1f6fb2", "#c0392b", "#1e8449", "#7f8c8d", "#e67e22"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "figure.facecolor": "white"})
    return plt


def _save(fig, name):
    p = os.path.join(_HERE, name)
    fig.savefig(p, dpi=150, bbox_inches="tight", facecolor="white")
    return p


def _box(ax, x, y, w, h, text, *, fc="white", ec=GREY, fs=9, bold=False, tc="black", lw=1.6):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor=fc, edgecolor=ec, linewidth=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=tc, linespacing=1.35)


def _arrow(ax, x0, y0, x1, y1, colour=GREY):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=colour, lw=2.0))


def fig_prepare_specimen():
    """SF2 — three separate tares plus a manual blob check collapse into one button."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.4, 3.1))
    ax.set_xlim(0, 10); ax.set_ylim(0, 4.3); ax.axis("off")

    ax.text(0.1, 4.05, "BEFORE — 4 separate actions, easy to skip one", fontsize=10,
            fontweight="bold", color=RED, va="top")
    for i, t in enumerate(["Tare\nposition", "Tare\nforce", "Tare\nDIC", "Eyeball the\nblob count"]):
        _box(ax, 0.1 + i * 2.45, 2.55, 2.15, 1.05, t, ec=RED, fs=9)
        if i < 3:
            _arrow(ax, 0.1 + i * 2.45 + 2.20, 3.07, 0.1 + (i + 1) * 2.45 - 0.04, 3.07, RED)

    ax.text(0.1, 2.15, "AFTER — one button", fontsize=10, fontweight="bold", color=GREEN, va="top")
    _box(ax, 0.1, 0.55, 3.05, 1.15, "“Prepare specimen”", fc="#eaf6ee", ec=GREEN, fs=12, bold=True,
         tc=GREEN, lw=2.4)
    _arrow(ax, 3.30, 1.12, 3.75, 1.12, GREEN)
    _box(ax, 3.85, 0.55, 6.05, 1.15,
         "position + force + DIC tared together · consoles and stress–strain plot cleared\n"
         "DIC tares ONLY at a green 2/2 marker lock — so a bad mount cannot be tared away",
         fc="white", ec=GREEN, fs=8.6)
    fig.tight_layout()
    return _save(fig, "feat_prepare_specimen.png")


def fig_release_load():
    """SF8 — the unload is driven past the TARED zero to the true zero, because taring at preload
    hides the real load. Schematic; the annotated values are the rig-test record."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.4, 3.1))
    t = [0, 1.0, 1.6, 3.2, 4.4, 5.2]
    F = [300, 300, 240, 60, 0, 0]                       # true load, N (illustrative shape)
    ax.plot(t, F, color=BLUE, lw=2.6, solid_capstyle="round")
    ax.axhline(0, color="black", lw=1.2)
    ax.axhline(300, color=GREY, ls=":", lw=1.5)
    ax.text(0.05, 312, "preload 300 N — the load cell was TARED here, so the readout says “0 N”",
            fontsize=8.5, color=GREY)
    ax.text(5.22, 10, "TRUE zero", fontsize=8.5, color=GREY, ha="right")
    ax.annotate("Stopping at the TARED zero would leave\n300 N still on the specimen.\n"
                "Release load drives PAST it, to the TRUE zero.",
                xy=(1.05, 296), xytext=(1.55, 175), fontsize=9, color=RED, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.8))
    ax.annotate("lands ≤ 5 N", xy=(4.4, 4), xytext=(4.0, 78), fontsize=9.5, color=GREEN,
                fontweight="bold", arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.8))
    ax.set_xlabel("Time"); ax.set_ylabel("TRUE load on the specimen (N)")
    ax.set_xticks([]); ax.set_ylim(-30, 360); ax.set_xlim(0, 5.3)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.set_title("SF8 · Release load — schematic (validated 2026-07-27)", fontsize=10)
    ax.text(5.22, -22, "0.20 mm/s · halts if the load RISES · cancel by button, manual direction or E-Stop",
            fontsize=8.2, color=GREY, ha="right", va="bottom")
    fig.tight_layout()
    return _save(fig, "feat_release_load.png")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for p in (fig_prepare_specimen(), fig_release_load()):
        print("  " + os.path.basename(p))
