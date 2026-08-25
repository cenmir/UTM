"""
Pre-flight blob detectability check.

Grabs 30 live frames, runs blob detection on each, reports how reliably
two blobs are found. Saves an annotated snapshot (check_blobs.png) for
visual confirmation.

Pass criteria for the hardware test run:
  * >=95 percent of frames return exactly 2 blobs
  * Distance between blobs is stable (std dev < 0.5 px across frames)

Usage:
    python check_blobs.py
"""
# Run from the APP directory (Software/UTM_PyQt6), which is also where this script's data and
# output paths are resolved from:  python tools/check_blobs.py
# The app modules live one level up, so put that on the path before importing them.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from camera_manager import CameraManager


OUTPUT_DIR = Path("../output/setup_output")
N_FRAMES = 30
MIN_OK_FRACTION = 0.95
DISTANCE_STD_LIMIT_PX = 0.5


class BlobChecker:
    def __init__(self, cm: CameraManager):
        self.cm = cm
        self.records = []          # list of (n_blobs, centroids, frame)

    def on_frame(self, frame):
        centroids = self.cm.detect_blobs(frame)
        self.records.append((len(centroids), centroids, frame))
        if len(self.records) >= N_FRAMES:
            QApplication.instance().quit()

    def summary(self):
        n = len(self.records)
        if n == 0:
            print("No frames processed — camera may have failed.")
            return False

        counts = [r[0] for r in self.records]
        two_blob = [r for r in self.records if r[0] == 2]
        ok_fraction = len(two_blob) / n

        print(f"\nFrames analyzed:        {n}")
        print(f"Frames with 2 blobs:    {len(two_blob)} ({ok_fraction * 100:.1f}%)")
        print(f"Frames with 0 blobs:    {sum(1 for c in counts if c == 0)}")
        print(f"Frames with 1 blob:     {sum(1 for c in counts if c == 1)}")
        print(f"Frames with 3+ blobs:   {sum(1 for c in counts if c >= 3)}")

        if not two_blob:
            print("\nFAIL: No frame produced exactly 2 blobs.")
            print("Check: specimen placement, lighting, threshold, marker contrast.")
            return False

        distances = []
        for _, centroids, _ in two_blob:
            (x1, y1), (x2, y2) = centroids[0], centroids[1]
            distances.append(abs(y2 - y1))
        distances = np.array(distances)

        print(f"\nBlob vertical distance (px):")
        print(f"  mean:   {distances.mean():.2f}")
        print(f"  std:    {distances.std():.3f}")
        print(f"  min:    {distances.min():.2f}")
        print(f"  max:    {distances.max():.2f}")

        self._save_annotated(two_blob[-1])

        pass_frac = ok_fraction >= MIN_OK_FRACTION
        pass_stable = distances.std() < DISTANCE_STD_LIMIT_PX

        print(f"\nDetection rate:   {'PASS' if pass_frac else 'FAIL'} "
              f"(need >= {MIN_OK_FRACTION * 100:.0f}%)")
        print(f"Distance stable:  {'PASS' if pass_stable else 'FAIL'} "
              f"(need std < {DISTANCE_STD_LIMIT_PX} px)")
        print(f"\nSaved annotated frame -> {OUTPUT_DIR / 'Software/UTM_PyQt6/output/diagnostics/check_blobs.png'}")
        return pass_frac and pass_stable

    def _save_annotated(self, record):
        _, centroids, frame = record
        if frame is None:
            return
        vis = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) if frame.ndim == 2 else frame.copy()
        for (x, y) in centroids:
            cv2.circle(vis, (int(x), int(y)), 40, (0, 0, 255), 3)
            cv2.circle(vis, (int(x), int(y)), 5, (0, 255, 0), -1)
        if len(centroids) == 2:
            p1 = (int(centroids[0][0]), int(centroids[0][1]))
            p2 = (int(centroids[1][0]), int(centroids[1][1]))
            cv2.line(vis, p1, p2, (255, 0, 0), 2)
        OUTPUT_DIR.mkdir(exist_ok=True)
        cv2.imwrite(str(OUTPUT_DIR / "Software/UTM_PyQt6/output/diagnostics/check_blobs.png"), vis)


def main():
    app = QApplication(sys.argv)
    cm = CameraManager()
    checker = BlobChecker(cm)

    cm.frame_ready.connect(checker.on_frame)
    # Silence the per-frame "Expected 2 blobs, found N" noise from the signal.
    cm.error_occurred.connect(lambda msg: None)

    if not cm.connect_camera():
        print("Failed to connect to camera.")
        sys.exit(1)

    cm.start_acquisition()
    print(f"Collecting {N_FRAMES} frames...")

    # Safety timeout: give up after 20 s
    safety = QTimer()
    safety.setSingleShot(True)
    safety.timeout.connect(app.quit)
    safety.start(20000)

    app.exec()

    cm.stop_acquisition()
    cm.disconnect_camera()

    ok = checker.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
