"""Evidence figures for SF19 (capture) — real frames and real video, from S26.

  sf_capture_strip.png   five stills across the pull, each labelled with the load and strain
                         that the LOAD CSV holds at that same instant
  sf_capture_views.png   the three recorded video views at ONE instant: raw, boosted, speckle

S26 is used because it carries all three video streams and a clean fracture.

The frame -> load-sample link is the point of the figure, so it is done properly rather than by
assuming the two recordings start together. They do not: the capture folder's index.csv puts frame 0
at 11:15:25.8 and the CSV header puts test t=0 at 11:15:15, so the frames cover t = 10.8 - 95.2 s of
a 125.3 s test. Interpolating "frame fraction -> row fraction" therefore reads the last frames
against post-fracture rows and labels them 0 MPa / 19 % strain. Every still here is matched to the
load row nearest IN TIME instead.

The stills are 2348 x 419 after rotation (5.6:1), so they are stacked as rows rather than laid out
side by side — in a row of five each still would be letterboxed into a sliver.
"""
import csv
import datetime
import os
import sys

import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIGS = os.path.join(HERE, "..", "figures")
sys.path.insert(0, os.path.abspath(os.path.join(ROOT, "Software", "UTM_PyQt6")))
from utm_analysis import read_csv, analyze                            # noqa: E402

SPEC = os.path.join(ROOT, "Software", "UTM_PyQt6", "Test data", "8.6.20 - Tensile test to Failure",
                    "Specimen_S26_V2_Spray_Video3")
RUN = os.path.join(SPEC, "20260817_111525")
FRAMES = os.path.join(RUN, "frames")
MUTED, INK = "#666666", "#212529"
AREA = 80.0


def _csv():
    for f in os.listdir(SPEC):
        if f.lower().endswith(".csv"):
            return os.path.join(SPEC, f)
    return None


def _test_t0(csv_path):
    """Test t=0 as a wall clock, from the CSV header the app wrote."""
    with open(csv_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("# Test Date:"):
                return datetime.datetime.strptime(line.split(":", 1)[1].strip(),
                                                  "%Y-%m-%d %H:%M:%S")
            if not line.startswith("#"):
                break
    return None


def _frame_times(t0):
    """[(frame index, filename, test-relative seconds)] from the capture folder's own index."""
    out = []
    with open(os.path.join(FRAMES, "index.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = (datetime.datetime.fromisoformat(r["pc_time_iso"]) - t0).total_seconds()
            out.append((int(r["frame"]), r["file"], t))
    return out


def _still(fname):
    im = cv2.imread(os.path.join(FRAMES, fname), cv2.IMREAD_GRAYSCALE)
    return cv2.rotate(im, cv2.ROTATE_90_CLOCKWISE)


def fig_strip(out="sf_capture_strip.png"):
    """Five stills across the pull, each carrying the load and strain recorded at that instant.

    The point is that the capture runs unattended for the whole test and still holds the fracture
    frame — the one frame that cannot be recaptured."""
    csv_path = _csv()
    a = analyze(csv_path, AREA, 80)
    rows = read_csv(csv_path)
    force = [r["F"] + a["anchor"] for r in rows]
    i_peak = int(np.argmax(force))
    ft = _frame_times(_test_t0(csv_path))

    def nearest_row(t):
        return min(range(len(rows)), key=lambda k: abs(rows[k]["t"] - t))

    def nearest_frame(t):
        return min(ft, key=lambda f: abs(f[2] - t))

    # the last frame recorded while the specimen was still whole
    t_break = next((rows[i]["t"] for i in range(i_peak, len(rows))
                    if force[i] < 0.3 * force[i_peak]), rows[-1]["t"])
    picks = [(ft[0][2], "capture starts"),
             (0.5 * (ft[0][2] + rows[i_peak]["t"]), "mid-pull"),
             (rows[i_peak]["t"], "PEAK LOAD"),
             (t_break - 1.0, "last whole frame"),
             (ft[-1][2], "after fracture")]

    fig, axes = plt.subplots(len(picks), 1, figsize=(6.6, 5.6))
    for ax, (t, tag) in zip(axes, picks):
        idx, fname, ft_t = nearest_frame(t)
        ax.imshow(_still(fname), cmap="gray", vmin=0, vmax=255)
        j = nearest_row(ft_t)
        if tag == "after fracture":
            lab = (f"frame {idx} · t = {ft_t:.1f} s · {tag.upper()} — "
                   f"{abs(force[j]) / AREA:.1f} MPa, the specimen is in two pieces")
            col = "#c92a2a"
        else:
            lab = (f"frame {idx} · t = {ft_t:.1f} s · {force[j] / AREA:.1f} MPa · "
                   f"ε {rows[j]['ec'] * 100:.2f} %   ({tag})")
            col = INK if tag != "PEAK LOAD" else "#1f6fb4"
        ax.set_title(lab, fontsize=9.2, color=col,
                     weight="bold" if tag in ("PEAK LOAD", "after fracture") else "normal", pad=3)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color("#AAB2BD")
    fig.suptitle(f"S26 — {len(ft)} stills recorded unattended across the pull, 0 dropped\n"
                 f"each frame matched to the load sample at the same instant",
                 fontsize=10.5, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    p = os.path.join(FIGS, out)
    fig.savefig(p, dpi=170)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


def fig_views(out="sf_capture_views.png"):
    """The three video streams at one instant. Raw is the archival record; the other two are
    derived views recorded alongside it so the operator can SEE the speckle during the run."""
    vids = [("video.avi", "RAW — the archival record", "#1f6fb4"),
            ("video_boost.avi", "BOOSTED CONTRAST — for watching live", "#7048e8"),
            ("video_speckle.avi", "ADAPTIVE SPECKLE — what the detector sees", "#2f9e44")]
    fig, axes = plt.subplots(3, 1, figsize=(6.6, 3.5))
    for ax, (name, label, col) in zip(axes, vids):
        path = os.path.join(RUN, name)
        cap = cv2.VideoCapture(path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * 0.6))
        okf, frame = cap.read()
        cap.release()
        if okf:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
            ax.imshow(cv2.rotate(g, cv2.ROTATE_90_CLOCKWISE), cmap="gray", vmin=0, vmax=255)
        else:
            ax.text(0.5, 0.5, "not readable", ha="center", va="center", transform=ax.transAxes)
        mb = os.path.getsize(path) / 1e6 if os.path.exists(path) else 0
        ax.set_title(f"{label}   ·   {name} · {total} frames · {mb:.0f} MB",
                     fontsize=8.8, color=col, weight="bold", pad=3)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color(col)
            sp.set_linewidth(1.4)
    fig.suptitle("All three views, same pull, frame-for-frame — S26 at 60 % of the run",
                 fontsize=10.5, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    p = os.path.join(FIGS, out)
    fig.savefig(p, dpi=170)
    plt.close(fig)
    print("wrote", os.path.basename(p))
    return p


def facts():
    csv_path = _csv()
    files = [f for f in os.listdir(FRAMES) if f.endswith(".png")]
    ft = _frame_times(_test_t0(csv_path))
    rows = read_csv(csv_path)
    out = {"stills": len(files), "run": os.path.basename(RUN),
           "t_first": ft[0][2], "t_last": ft[-1][2], "t_test": rows[-1]["t"],
           "fps": (len(ft) - 1) / max(1e-6, ft[-1][2] - ft[0][2])}
    for name in ("video.avi", "video_boost.avi", "video_speckle.avi"):
        p = os.path.join(RUN, name)
        if os.path.exists(p):
            cap = cv2.VideoCapture(p)
            out[name] = (int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                         os.path.getsize(p) / 1e6)
            cap.release()
    out["still_mb"] = sum(os.path.getsize(os.path.join(FRAMES, f)) for f in files) / 1e6
    return out


def all_figs():
    return [fig_strip(), fig_views()]


if __name__ == "__main__":
    all_figs()
    for k, v in facts().items():
        print(f"  {k}: {v}")
