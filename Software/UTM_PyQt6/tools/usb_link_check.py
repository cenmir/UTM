#!/usr/bin/env python3
"""Why is the camera delivering ~0 fps? Report what the USB link actually negotiated.

Run with the app's camera STOPPED (press Stop Camera first) - only one process may open it.

    cd Software/UTM_PyQt6
    python tools/usb_link_check.py

The question this answers: did the camera come up on SuperSpeed (USB 3, ~5 Gbps) or fall back
to USB 2 (480 Mbps)? A USB3 Vision camera on a USB 2 path enumerates perfectly, previews, and
then delivers a small fraction of the configured frame rate - which looks exactly like a
"broken camera" and is actually a cable, a port, or a hub that never brought SuperSpeed up.
"""
import sys
import time

try:
    from pypylon import pylon
except ImportError:
    sys.exit("pypylon is not installed in this interpreter.")


def get(cam, name):
    """Read a node if the camera has it; None otherwise. Model-dependent."""
    try:
        node = getattr(cam, name)
        return node.GetValue()
    except Exception:
        return None


def main():
    tlf = pylon.TlFactory.GetInstance()
    devs = tlf.EnumerateDevices()
    if not devs:
        sys.exit("No Basler device found. Check the cable and that the app is not holding it.")

    print("Devices found: %d" % len(devs))
    for d in devs:
        print("  %s  %s  (SN %s)" % (d.GetModelName(), d.GetDeviceClass(), d.GetSerialNumber()))

    cam = pylon.InstantCamera(tlf.CreateFirstDevice())
    cam.Open()
    print()

    # ---- what the link negotiated -------------------------------------------------
    speed = get(cam, "BslUSBSpeedMode") or get(cam, "DeviceLinkSpeed")
    link_bps = get(cam, "DeviceLinkSpeed")
    print("=== USB link ===")
    print("  speed mode              : %s" % speed)
    if link_bps:
        print("  DeviceLinkSpeed         : %s B/s  (%.2f Gbit/s)" % (
            f"{link_bps:,}", link_bps * 8 / 1e9))
        if link_bps * 8 < 1.0e9:
            print("  >> This is USB 2 territory. A SuperSpeed link reports ~5 Gbit/s.")

    lim_mode = get(cam, "DeviceLinkThroughputLimitMode")
    lim = get(cam, "DeviceLinkThroughputLimit")
    cur = get(cam, "DeviceLinkCurrentThroughput")
    print("  throughput limit mode   : %s" % lim_mode)
    if lim:
        print("  throughput limit        : %s B/s  (%.0f MB/s)" % (f"{lim:,}", lim / 1e6))
    if cur:
        print("  current throughput      : %s B/s  (%.0f MB/s)" % (f"{cur:,}", cur / 1e6))

    # ---- what the camera thinks it can do -----------------------------------------
    print()
    print("=== frame rate ===")
    for n in ("AcquisitionFrameRate", "AcquisitionFrameRateAbs",
              "ResultingFrameRate", "ResultingFrameRateAbs"):
        v = get(cam, n)
        if v is not None:
            print("  %-24s: %.2f fps" % (n, v))
    w, h = get(cam, "Width"), get(cam, "Height")
    pf = get(cam, "PixelFormat")
    if w and h:
        need = w * h * 20 / 1e6
        print("  ROI                     : %d x %d  (%s)" % (w, h, pf))
        print("  needs about             : %.1f MB/s at 20 fps" % need)

    # ---- measure it ---------------------------------------------------------------
    print()
    print("=== measured (grabbing 3 s) ===")
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    n, bad, t0 = 0, 0, time.monotonic()
    while time.monotonic() - t0 < 3.0:
        try:
            r = cam.RetrieveResult(500, pylon.TimeoutHandling_Return)
            if r and r.GrabSucceeded():
                n += 1
            elif r:
                bad += 1
            if r:
                r.Release()
        except Exception as e:
            print("  grab error: %s" % e)
            break
    dt = time.monotonic() - t0
    cam.StopGrabbing()
    print("  grabbed %d frames in %.1f s  =  %.1f fps   (%d failed)" % (n, dt, n / dt, bad))

    cfg = get(cam, "ResultingFrameRate") or get(cam, "AcquisitionFrameRate") or 0
    if cfg and n / dt < cfg * 0.5:
        print()
        print("  >> Delivering under half the configured rate. In order of likelihood:")
        print("     1. The link is USB 2, not SuperSpeed - see the speed above. Try the camera")
        print("        DIRECTLY in a blue USB 3 port on the PC, bypassing the hub entirely. If")
        print("        that fixes it, the hub or its upstream cable is not carrying SuperSpeed.")
        print("     2. The hub's SuperSpeed path is shared or unpowered - use its own supply.")
        print("     3. DeviceLinkThroughputLimit is capping it (see above).")

    cam.Close()
    print()
    print("done")


if __name__ == "__main__":
    main()
