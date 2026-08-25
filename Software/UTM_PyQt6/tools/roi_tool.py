"""
roi_tool.py - interactively set the DIC camera ROI by clicking the two markers.

Why this exists: deriving the ROI from the rotated full_frame grid is error-prone
(rotation transform + display stretching). This tool sidesteps all of that:

  1. Grabs the FULL sensor WITHOUT rotation, so a click maps straight to pylon
     OffsetX/OffsetY - zero coordinate math.
  2. You click the two marker centres (approx is fine - each click snaps to the
     nearest dark blob and measures its radius).
  3. It computes a band that brackets both markers (small margin across the
     specimen, generous margin along the loading axis for strain headroom),
     snapped to the camera's ROI increments and clamped to the sensor.
  4. It APPLIES that ROI to the real camera, grabs again, rotates exactly like
     CameraManager.capture_frame, and runs the SAME blob detection - so the
     "2 blobs detected" result is ground truth, not a simulation.

Camera must be free: CLOSE the UTM app first (only one process can hold the camera).

Usage:
    python roi_tool.py                 # defaults: cross-margin 60, gauge-margin 250
    python roi_tool.py --gauge 350     # more stretch headroom along the loading axis
    python roi_tool.py --cross 90
"""
import argparse
from pathlib import Path

from pypylon import pylon
import cv2
import numpy as np

EXPOSURE = 50000
GAMMA = 0.5
THRESHOLD = 100          # dark dots on light specimen (White mode)
MIN_AREA, MAX_AREA, MIN_CIRC = 2000, 200000, 0.5
OUT = Path("full_frame_output"); OUT.mkdir(exist_ok=True)


def detect_blobs(gray):
    """Same logic as CameraManager.detect_blobs (White preset)."""
    _, b = cv2.threshold(gray, THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if MIN_AREA < a < MAX_AREA:
            p = cv2.arcLength(c, True)
            if p > 0 and 4 * np.pi * a / (p * p) > MIN_CIRC:
                M = cv2.moments(c)
                out.append((M["m10"] / M["m00"], M["m01"] / M["m00"], (a / np.pi) ** 0.5))
    return out


def refine_click(gray, x, y, win=140):
    """Snap an approximate click to the nearest dark blob centre; return (cx, cy, r)."""
    x0, y0 = max(0, x - win), max(0, y - win)
    sub = gray[y0:y + win, x0:x + win]
    blobs = detect_blobs(sub)
    if not blobs:
        return float(x), float(y), 65.0
    cx, cy, r = min(blobs, key=lambda b: (b[0] + x0 - x) ** 2 + (b[1] + y0 - y) ** 2)
    return cx + x0, cy + y0, r


def grab(cam, roi=None, rotate=False):
    if cam.IsGrabbing():
        cam.StopGrabbing()
    cam.OffsetX.Value = 0; cam.OffsetY.Value = 0
    if roi is None:
        cam.Width.Value = cam.Width.Max; cam.Height.Value = cam.Height.Max
    else:
        ox, oy, w, h = roi
        cam.Width.Value = w; cam.Height.Value = h
        cam.OffsetX.Value = ox; cam.OffsetY.Value = oy
    cam.ExposureTime.Value = EXPOSURE
    try: cam.Gamma.Value = GAMMA
    except Exception: pass
    cam.PixelFormat.Value = "Mono8"
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    g = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    img = g.Array.copy(); g.Release(); cam.StopGrabbing()
    return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE) if rotate else img


def snap(v, inc):
    return int(round(v / inc)) * inc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cross", type=int, default=140, help="margin (px) across the specimen (tolerance for shift/tilt)")
    ap.add_argument("--gauge", type=int, default=280, help="margin (px) each side along the loading axis")
    args = ap.parse_args()

    cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    cam.Open()
    print("Connected. Grabbing full sensor (un-rotated)...")
    full = grab(cam, roi=None, rotate=False)
    H, W = full.shape
    print(f"Full sensor: Width(X)={W}  Height(Y)={H}  | inc: "
          f"W={int(cam.Width.Inc)} H={int(cam.Height.Inc)} OX={int(cam.OffsetX.Inc)} OY={int(cam.OffsetY.Inc)}")
    cv2.imwrite(str(OUT / "sensor_full.png"), full)

    scale = min(1.0, 1100.0 / max(H, W))
    disp = cv2.resize(cv2.cvtColor(full, cv2.COLOR_GRAY2BGR), None, fx=scale, fy=scale)
    clicks = []
    title = "Click the TWO markers (approx is fine), then press any key"

    def cb(ev, x, y, flags, param):
        if ev == cv2.EVENT_LBUTTONDOWN and len(clicks) < 2:
            cx, cy, r = refine_click(full, int(x / scale), int(y / scale))
            clicks.append((cx, cy, r))
            cv2.circle(disp, (int(cx * scale), int(cy * scale)), int(r * scale), (0, 0, 255), 2)
            cv2.imshow(title, disp)
            print(f"  marker {len(clicks)} -> sensor ({cx:.0f}, {cy:.0f})  r={r:.0f}")

    cv2.imshow(title, disp); cv2.setMouseCallback(title, cb)
    print("Click the two marker centres, then press any key.")
    cv2.waitKey(0); cv2.destroyAllWindows()

    if len(clicks) < 2:
        print("Need 2 markers. Aborting."); cam.Close(); return

    (x1, y1, r1), (x2, y2, r2) = clicks[:2]
    r = max(r1, r2)
    minx, maxx = min(x1, x2), max(x1, x2)
    miny, maxy = min(y1, y2), max(y1, y2)
    gauge_is_x = abs(x2 - x1) >= abs(y2 - y1)
    mx = args.gauge if gauge_is_x else args.cross
    my = args.cross if gauge_is_x else args.gauge

    ox = minx - r - mx; w = (maxx - minx) + 2 * (r + mx)
    oy = miny - r - my; h = (maxy - miny) + 2 * (r + my)

    oxi, oyi, wi, hi = int(cam.OffsetX.Inc), int(cam.OffsetY.Inc), int(cam.Width.Inc), int(cam.Height.Inc)
    ox = max(0, snap(ox, oxi)); oy = max(0, snap(oy, oyi))
    w = min(snap(w, wi), cam.Width.Max - ox); h = min(snap(h, hi), cam.Height.Max - oy)
    w = snap(w, wi); h = snap(h, hi)
    roi = [int(ox), int(oy), int(w), int(h)]
    print(f"\nGauge axis: {'X' if gauge_is_x else 'Y'}  | margins: cross={args.cross} gauge={args.gauge}")
    print(f"Computed ROI [OffsetX, OffsetY, Width, Height] = {roi}")

    # Close the loop: apply on the real camera, rotate like the live pipeline, detect.
    res = grab(cam, roi=roi, rotate=True)
    cv2.imwrite(str(OUT / "roi_preview.png"), res)
    found = detect_blobs(res)
    print(f"\n--- LIVE-EQUIVALENT CHECK ---")
    print(f"Blobs detected in applied ROI (rotated, same as live DIC): {len(found)}  (want 2)")
    for i, (bx, by, br) in enumerate(sorted(found, key=lambda b: b[1])):
        print(f"   blob{i}: ({bx:.0f},{by:.0f}) r={br:.0f}")
    print(f"Preview saved -> {OUT / 'roi_preview.png'}")
    if len(found) == 2:
        print("\nOK - both markers framed. Paste this into camera_manager.py White preset 'roi':")
        print(f"    \"roi\": {roi},")
        print("Then FULLY RESTART the app (python main.py) so the new preset loads.")
    else:
        print("\nNOT 2 blobs - rerun and click more precisely, or adjust --cross/--gauge.")

    pv = cv2.resize(cv2.cvtColor(res, cv2.COLOR_GRAY2BGR), None, fx=0.5, fy=0.5)
    cv2.imshow("ROI preview (live orientation) - press any key", pv)
    cv2.waitKey(0); cv2.destroyAllWindows()
    cam.Close()


if __name__ == "__main__":
    main()
