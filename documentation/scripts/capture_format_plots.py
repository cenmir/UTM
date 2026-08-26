"""Figures for the capture-format slides (deck p255-251).

  cap_still_formats.png   what the three still formats cost, and that all three are identical
  cap_video_codecs.png    where MJPG actually loses the image, next to what the codecs cost

The video figure is the one that earns its place. "MJPG is lossy" is a claim; an error map made
from the rig's own frames is a measurement, and it shows WHERE the loss lands — on the marker
edges, which is precisely what the blob detector measures.

Sizes and timings come from utm_capture's format tables, so the slides cannot drift from the code.
"""
import glob
import os
import sys

import cv2
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP = os.path.abspath(os.path.join(REPO, "Software", "UTM_PyQt6"))
sys.path.insert(0, APP)
import utm_capture as CAP                                              # noqa: E402

RUN = os.path.join(APP, "Test data", "8.6.20 - Tensile test to Failure",
                   "Specimen_S26_V2_Spray_Video3", "20260817_111525")
GRID, INK, MUTED = "#DDDDDD", "#1A1A1A", "#666666"
C_GOOD, C_BAD, C_MID = "#2f9e44", "#d62728", "#1f77b4"


def _style(ax):
    ax.grid(True, axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _frame(n=800):
    f = sorted(glob.glob(os.path.join(RUN, "frames", "*.png")))
    return cv2.imread(f[n], cv2.IMREAD_GRAYSCALE) if f else None


def fig_stills(out="cap_still_formats.png"):
    keys = ["tiff", "tiff_lzw", "png"]
    T = CAP.STILL_FORMATS
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 3.25))
    x = np.arange(len(keys))
    lab = ["TIFF\nuncompressed", "TIFF\nLZW", "PNG\n(was default)"]
    col = [C_GOOD, C_MID, MUTED]

    b = a1.bar(x, [T[k]["kb"] / 1024 for k in keys], width=0.55, color=col)
    for r, k in zip(b, keys):
        a1.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.02,
                "%.2f MB" % (T[k]["kb"] / 1024), ha="center", fontsize=10, weight="bold")
    a1.set_xticks(x); a1.set_xticklabels(lab, fontsize=9)
    a1.set_ylabel("file size per frame (MB)")
    a1.set_ylim(0, max(T[k]["kb"] for k in keys) / 1024 * 1.25)
    a1.set_title("Size — LZW is the same pixels in a third of the space", fontsize=11)
    _style(a1)

    b = a2.bar(x, [T[k]["ms"] for k in keys], width=0.55, color=col)
    for r, k in zip(b, keys):
        a2.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.15,
                "%.1f ms" % T[k]["ms"], ha="center", fontsize=10, weight="bold")
    a2.axhline(50, color=C_BAD, ls=":", lw=1.3)
    a2.text(0.99, 50, " budget at 20 fps ", transform=a2.get_yaxis_transform(),
            ha="right", va="bottom", fontsize=8, color=C_BAD)
    a2.set_xticks(x); a2.set_xticklabels(lab, fontsize=9)
    a2.set_ylabel("CPU to write one frame (ms)")
    a2.set_ylim(0, 55)
    a2.set_title("CPU — uncompressed TIFF costs a fifth of PNG", fontsize=11)
    _style(a2)

    fig.tight_layout()
    p = os.path.join(HERE, "..", "figures", out); fig.savefig(p, dpi=170); plt.close(fig)
    return p


def fig_video(out="cap_video_codecs.png"):
    """Left: where MJPG loses the image. Right: what each codec costs."""
    png = _frame()
    fig = plt.figure(figsize=(13.6, 3.25))
    gs = fig.add_gridspec(1, 4, width_ratios=[1, 1, 1.1, 1.9], wspace=0.42)

    if png is not None:
        cap = cv2.VideoCapture(os.path.join(RUN, "video.avi"))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 800)
        okr, fr = cap.read(); cap.release()
        mj = (cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY) if fr.ndim == 3 else fr) if okr else None
    else:
        mj = None

    if png is not None and mj is not None:
        w = min(png.shape[1], mj.shape[1])
        # a crop centred on the lower marker — the thing the detector actually measures
        # a nearly square crop centred on the lower marker, so the blob is not stretched
        ys, ye, xs, xe = 1880, 2050, 120, min(300, w)
        a, b = png[ys:ye, xs:xe], mj[ys:ye, xs:xe]
        d = np.abs(a.astype(int) - b.astype(int))
        for i, (img, ttl, kw) in enumerate((
                (a, "The still (TIFF/PNG)\nevery pixel as the sensor saw it", dict(cmap="gray", vmin=0, vmax=255)),
                (b, "The same frame via MJPG", dict(cmap="gray", vmin=0, vmax=255)),
                (d, "|difference| — where MJPG lost it\nmax %d levels, %.0f %% of pixels changed"
                    % (d.max(), 100 * (d > 0).mean()), dict(cmap="inferno", vmin=0, vmax=12)))):
            ax = fig.add_subplot(gs[0, i])
            im = ax.imshow(img, aspect="equal", **kw)
            ax.set_title(ttl, fontsize=8.6)
            ax.set_xticks([]); ax.set_yticks([])
            if i == 2:
                # horizontal, under the panel: a vertical bar here collided with the
                # neighbouring chart's y-axis label
                cb = fig.colorbar(im, ax=ax, orientation="horizontal",
                                  fraction=0.055, pad=0.04)
                cb.ax.tick_params(labelsize=6.5)
                cb.set_label("grey levels of error", fontsize=7)

    ax = fig.add_subplot(gs[0, 3])
    keys = ["ffv1", "y800", "mjpg"]
    V = CAP.VIDEO_CODECS
    x = np.arange(len(keys))
    col = [C_GOOD, C_MID, C_BAD]
    bars = ax.bar(x, [V[k]["kb"] / 1024 for k in keys], width=0.55, color=col)
    for r, k in zip(bars, keys):
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.02,
                "%.2f MB\n%.1f ms\n%.1f %% kept" % (V[k]["kb"] / 1024, V[k]["ms"],
                                                    V[k]["identical"]),
                ha="center", fontsize=8, weight="bold",
                color=INK if V[k]["lossless"] else C_BAD)
    ax.set_xticks(x)
    ax.set_xticklabels(["FFV1\nDEFAULT", "Raw\nY800", "MJPG\n(was default)"], fontsize=9)
    ax.set_ylabel("size per frame (MB)")
    ax.set_ylim(0, max(V[k]["kb"] for k in keys) / 1024 * 1.45)
    ax.set_title("What each codec costs", fontsize=11)
    _style(ax)

    p = os.path.join(HERE, "..", "figures", out)
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p


if __name__ == "__main__":
    for f in (fig_stills(), fig_video()):
        print("wrote", os.path.basename(f))
