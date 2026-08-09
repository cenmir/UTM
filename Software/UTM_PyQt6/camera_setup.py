"""
Camera + specimen setup checker.

Single-shot diagnostic to run after every camera/specimen change, before
starting a real acquisition. Verifies:

  1. Camera connects at the configured ROI
  2. Both markers are inside the active ROI
  3. Exactly 2 blobs detected consistently across N frames
  4. Blob positions are stable (sub-pixel)
  5. Blobs sit away from ROI edges (no clipping risk)

Usage:
    python camera_setup.py                 # interactive mode prompt
    python camera_setup.py --mode white    # dark markers on light specimen
    python camera_setup.py --mode black    # light markers on dark specimen
    python camera_setup.py --mode black --frames 60
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from camera_manager import CameraManager


OUTPUT_DIR = Path("setup_output")
N_FRAMES_DEFAULT = 30
MIN_OK_FRACTION = 0.95
DISTANCE_STD_LIMIT_PX = 0.5
EDGE_MARGIN_PX = 30             # warn if blob center closer than this to ROI edge
ACQUISITION_TIMEOUT_MS = 20000  # safety timeout


def prompt_mode() -> str:
    while True:
        print("\nSpecimen mode:")
        print("  [w] White specimen — DARK markers on LIGHT background")
        print("  [b] Black specimen — LIGHT markers on DARK background")
        choice = input("Choose (w/b): ").strip().lower()
        if choice in ("w", "white"):
            return "White"
        if choice in ("b", "black"):
            return "Black"
        print("Invalid — enter 'w' or 'b'.")


class SetupChecker:
    def __init__(self, cm: CameraManager, n_frames: int):
        self.cm = cm
        self.n_frames = n_frames
        self.records = []  # list of (n_blobs, centroids, frame)

    def on_frame(self, frame):
        centroids = self.cm.detect_blobs(frame)
        self.records.append((len(centroids), centroids, frame))
        if len(self.records) >= self.n_frames:
            QApplication.instance().quit()

    def summary(self, mode: str) -> bool:
        n = len(self.records)
        if n == 0:
            print("\n[FAIL] No frames captured - camera may have errored.")
            return False

        roi_h, roi_w = self.records[-1][2].shape[:2]
        counts = [r[0] for r in self.records]
        two_blob = [r for r in self.records if r[0] == 2]
        ok_fraction = len(two_blob) / n

        bar = "=" * 64
        print(f"\n{bar}")
        print(f" CAMERA SETUP CHECK   mode={mode}   frames={n}")
        print(bar)
        print(f" ROI (post-rotation): {roi_w} x {roi_h} px")
        print(f" Detection distribution:")
        print(f"   exactly 2 blobs:  {len(two_blob):>3} ({ok_fraction*100:5.1f}%)")
        print(f"   0 blobs:          {sum(1 for c in counts if c == 0):>3}")
        print(f"   1 blob:           {sum(1 for c in counts if c == 1):>3}")
        print(f"   3+ blobs:         {sum(1 for c in counts if c >= 3):>3}")

        checks = []  # (name, passed, criterion_text)
        checks.append(
            ("Detection rate", ok_fraction >= MIN_OK_FRACTION,
             f">= {MIN_OK_FRACTION*100:.0f}%")
        )

        if two_blob:
            distances = np.array([
                abs(r[1][1][1] - r[1][0][1]) for r in two_blob
            ])
            print(f"\n Blob vertical distance (px):")
            print(f"   mean: {distances.mean():.2f}")
            print(f"   std:  {distances.std():.3f}")
            print(f"   min:  {distances.min():.2f}")
            print(f"   max:  {distances.max():.2f}")
            checks.append(
                ("Distance stability", distances.std() < DISTANCE_STD_LIMIT_PX,
                 f"std < {DISTANCE_STD_LIMIT_PX} px")
            )

            _, centroids, frame = two_blob[-1]
            h, w = frame.shape[:2]
            print(f"\n Blob positions in ROI (latest frame):")
            min_margin = float("inf")
            for i, (x, y) in enumerate(centroids, start=1):
                mx = min(x, w - x)
                my = min(y, h - y)
                min_margin = min(min_margin, mx, my)
                print(f"   blob {i}: ({x:7.1f}, {y:7.1f})  "
                      f"edge margin ({mx:.0f}, {my:.0f}) px")
            checks.append(
                ("Edge margin", min_margin >= EDGE_MARGIN_PX,
                 f">= {EDGE_MARGIN_PX} px from ROI edge")
            )

            out_path = self._save_annotated(two_blob[-1])
            print(f"\n Annotated frame saved to: {out_path}")

        print(f"\n{bar}")
        print(" VERDICT:")
        all_pass = True
        for name, ok, crit in checks:
            tag = "PASS" if ok else "FAIL"
            all_pass = all_pass and ok
            print(f"   [{tag}] {name:<22s} ({crit})")
        print(bar)

        if all_pass:
            print(" >> SETUP OK - ready to tare DIC and start acquisition.")
        else:
            print(" >> SETUP NOT READY - suggestions:")
            self._print_suggestions(counts, mode, checks)
        print(bar)
        return all_pass

    def _print_suggestions(self, counts, mode, checks):
        n = len(counts)
        zero = sum(1 for c in counts if c == 0)
        one = sum(1 for c in counts if c == 1)
        three_plus = sum(1 for c in counts if c >= 3)
        other_mode = "Black" if mode == "White" else "White"

        if zero > n * 0.5:
            print(f"   - 0 blobs in most frames:")
            print(f"     * Wrong specimen mode? (currently '{mode}'; try '{other_mode}')")
            print(f"     * Markers outside ROI? Run grab_full_frame.py to see full sensor")
            print(f"     * Lighting or threshold mismatch")
        if one > 0:
            print(f"   - 1 blob in {one} frame(s):")
            print(f"     * A marker is at/beyond the ROI edge - widen ROI")
            print(f"     * Or one marker is occluded/damaged - re-check specimen")
        if three_plus > 0:
            print(f"   - 3+ blobs in {three_plus} frame(s):")
            print(f"     * Background artifacts pass the filter")
            print(f"     * Raise MIN_AREA or MIN_CIRCULARITY in camera_manager.py")
        for name, ok, _ in checks:
            if name == "Edge margin" and not ok:
                print(f"   - Blob too close to ROI edge:")
                print(f"     * Camera/specimen drift will clip markers mid-test")
                print(f"     * Widen ROI, or re-center the specimen before tare")
            if name == "Distance stability" and not ok:
                print(f"   - Marker distance is jittery:")
                print(f"     * Camera or specimen vibration")
                print(f"     * Lighting flicker (try steady LED, not fluorescent)")

    def _save_annotated(self, record):
        _, centroids, frame = record
        vis = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) if frame.ndim == 2 else frame.copy()
        h, w = vis.shape[:2]
        # ROI edge frame
        cv2.rectangle(vis, (0, 0), (w - 1, h - 1), (100, 100, 100), 1)
        for i, (x, y) in enumerate(centroids, start=1):
            cv2.circle(vis, (int(x), int(y)), 40, (0, 0, 255), 3)
            cv2.circle(vis, (int(x), int(y)), 5, (0, 255, 0), -1)
            cv2.putText(vis, f"B{i}", (int(x) + 50, int(y) + 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        if len(centroids) == 2:
            p1 = (int(centroids[0][0]), int(centroids[0][1]))
            p2 = (int(centroids[1][0]), int(centroids[1][1]))
            cv2.line(vis, p1, p2, (255, 0, 0), 2)
            dist = abs(centroids[1][1] - centroids[0][1])
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            cv2.putText(vis, f"{dist:.0f} px", (mid[0] + 10, mid[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / "camera_setup.png"
        cv2.imwrite(str(out_path), vis)
        return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Camera + specimen setup checker."
    )
    parser.add_argument(
        "--mode", choices=["white", "black"],
        help="Specimen mode (omit for interactive prompt)",
    )
    parser.add_argument(
        "--frames", type=int, default=N_FRAMES_DEFAULT,
        help=f"Number of frames to analyze (default {N_FRAMES_DEFAULT})",
    )
    args = parser.parse_args()

    mode = args.mode.capitalize() if args.mode else prompt_mode()

    app = QApplication(sys.argv)
    cm = CameraManager()
    cm.set_specimen_mode(mode)

    checker = SetupChecker(cm, args.frames)
    cm.frame_ready.connect(checker.on_frame)
    cm.error_occurred.connect(lambda msg: None)  # suppress per-frame noise

    print(f"\nConnecting camera (mode={mode}, ROI={cm.ROI})...")
    if not cm.connect_camera():
        print("[FAIL] Could not connect to camera.")
        sys.exit(1)

    cm.start_acquisition()
    print(f"Collecting {args.frames} frames...")

    safety = QTimer()
    safety.setSingleShot(True)
    safety.timeout.connect(app.quit)
    safety.start(ACQUISITION_TIMEOUT_MS)

    app.exec()

    cm.stop_acquisition()
    cm.disconnect_camera()

    ok = checker.summary(mode)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
