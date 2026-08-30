"""SF13 — the guided checklist. What order to do things in, derived from state the app already has.

The app has accumulated a real procedure: Px₀ must be frozen after the preload but before Prepare
test (which tares the force out from under it); the specimen mode has to be picked before capture
is armed or the speckle video records the wrong polarity; the data has to be saved before a report
means anything. Every one of those has its own dialog or tooltip, added the day it caught somebody
out. This is where they stop being separate warnings and become one visible order.

DELIBERATELY OPTIONAL, and off by default. An operator who knows the procedure does not need a
panel telling them, and a checklist that cannot be dismissed is just a wider warning. It lives
behind View ▸ Guided wizard.

No new measurement and no new state machine: `steps()` is a pure read of flags that already exist,
so the panel cannot disagree with the app or get stuck out of sync. It is a view, not a controller
— nothing here can start a test, and a step that reads TODO never blocks anything.
"""

DONE, NEXT, TODO, INFO = "done", "next", "todo", "info"

# Enough load to call a preload "applied". Well above noise, well below any real preload target.
# A CEILING, not the threshold itself: see preload_floor().
PRELOAD_MIN_N = 50.0

# The load cell reads 0.27 N sd with 0.75 N quantisation, so 2 N is unmistakably "loaded" while
# still being reachable by an elastomer that is barely being held.
PRELOAD_NOISE_N = 2.0


def preload_floor(app):
    """How much load counts as "preloaded" FOR THIS PROFILE.

    A flat 50 N was wrong the moment a material arrived whose whole preload is 20 N. TPU is
    preloaded to 20 N deliberately - at PLA's 300 N it would already be pulled through a large
    part of its elastic range before the tare - so a fixed 50 N floor declared every correctly
    prepared TPU specimen un-preloaded, and then warned that Px0 had been frozen unloaded when
    it had been frozen exactly where the operator was told to freeze it.

    Half the target, capped at the old 50 N so nothing changes for a 300 N preload, and floored
    just above the load cell noise.
    """
    try:
        target = float(app.preloadTargetSpinBox.value())
    except Exception:
        return PRELOAD_MIN_N
    return max(PRELOAD_NOISE_N, min(PRELOAD_MIN_N, 0.5 * target))


def _stop_mm(f):
    """Crosshead travel at which the moving marker reaches the frame edge.

    room px of marker travel -> room/drift px of SEPARATION growth -> /Px0 = strain ->
    x gauge / share = crosshead mm, since only ~65 % of the travel reaches the gauge.
    """
    growth = f["room"] / max(1e-6, f.get("drift") or 1.264)
    strain = growth / max(1e-6, f.get("px0") or 1.0)
    return strain * (f.get("gauge") or 80.0) / max(1e-6, f.get("share") or 0.65)


def _blobs(app):
    fn = getattr(app, "_live_blob_count", None)
    try:
        return int(fn()) if callable(fn) else 0
    except Exception:
        return 0


def _camera_live(app):
    cam = getattr(getattr(app, "camera_manager", None), "camera", None)
    try:
        return cam is not None and cam.IsOpen()
    except Exception:
        return False


def steps(app):
    """[(key, label, state, detail)] in the order they should be done.

    state: DONE (satisfied) · NEXT (the first thing outstanding) · TODO (not yet) · INFO (optional,
    never blocks). The caller renders; nothing here touches the UI.
    """
    cm = getattr(app, "camera_manager", None)
    px0 = getattr(cm, "initial_distance", None) if cm else None
    px0_load = getattr(app, "_px0_load_N", None)
    saved = getattr(app, "_last_saved_csv", None)
    n_samples = len(getattr(app, "load_plot_times", []) or [])
    moved = max((abs(p) for p in (getattr(app, "load_plot_positions", []) or [])), default=0.0)
    after_preload = bool(app.px0_after_preload()) if hasattr(app, "px0_after_preload") else True

    out = []

    def add(key, label, ok, detail="", kind=None):
        out.append([key, label, DONE if ok else (kind or TODO), detail])

    add("connect", "Connect to the rig", bool(getattr(app, "connected", False)),
        "serial link open" if getattr(app, "connected", False) else "Connect button, top left")

    motors = bool(getattr(app, "motorsSwitch", None) and app.motorsSwitch.isChecked())
    add("motors", "Enable motors", motors,
        "enabled" if motors else "nothing will move until this is on")

    live = _camera_live(app)
    nb = _blobs(app)
    add("camera", "Start camera, DIC tracking 2/2", live and nb == 2,
        f"{nb}/2 markers" if live else "camera off — no strain will be recorded")

    # Force and position are what a test IS; velocity is a convenience channel, so it is reported
    # but not required. A run with the load-cell stream off records nothing worth analysing.
    streams = {n: bool(getattr(app, n + "Switch", None) and getattr(app, n + "Switch").isChecked())
               for n in ("loadCell", "position", "velocity")}
    essential = streams["loadCell"] and streams["position"]
    on = [n for n, v in streams.items() if v]
    add("streams", "Enable data streams", essential,
        ("on: " + ", ".join(on)) if essential else
        "load cell + position must be streaming or the run records nothing")

    mode = app.specimenModeCombo.currentText() if hasattr(app, "specimenModeCombo") else "?"
    out.append(["mode", "Choose specimen mode", INFO,
                f"currently {mode} — pick this BEFORE arming capture, the speckle video "
                f"follows it. White = dark dots on light PLA, Black = the reverse."])

    # Auto-calibrate. OPTIONAL, and placed here because it needs the camera live and the specimen
    # mode already chosen, but nothing later depends on it. It is worth offering rather than
    # leaving in a menu: exposure and threshold carry over from whatever ran last, and a value
    # measured on a different specimen looks exactly like one measured on this one.
    exp = getattr(cm, "EXPOSURE_TIME", None)
    thr = getattr(cm, "THRESHOLD", None)
    otsu = False
    try:
        import cv2 as _cv2
        otsu = bool(getattr(cm, "THRESHOLD_TYPE", 0) & _cv2.THRESH_OTSU)
    except Exception:
        pass
    now = f"{exp/1000:.0f} ms, thr {'auto (Otsu)' if otsu else thr}" if exp else "camera off"
    if getattr(app, "_autocal_t", None) is not None:
        detail = f"run for this specimen — now {now}"
    else:
        detail = (f"optional · Settings ▸ DIC camera setup ▸ Auto-calibrate. Currently {now}, "
                  f"carried over from the last run — worth a sweep on a new material or after the "
                  f"lighting changes")
    out.append(["autocal", "Auto-calibrate DIC", INFO, detail])

    # Preload. After Prepare test the reading is tared to ~0, so the durable evidence that a
    # preload was applied is the load Px₀ was captured at, not the live reading.
    load_now = abs(getattr(app, "current_load", 0.0) or 0.0)
    floor = preload_floor(app)
    preloaded = load_now >= floor or (px0_load or 0.0) >= floor
    add("preload", "Apply preload", preloaded,
        f"{load_now:.0f} N now" if load_now >= floor else
        (f"Px₀ was taken at {px0_load:.0f} N" if (px0_load or 0) >= floor
         else "Preload tension — seat the specimen first"))

    # Px₀. Under the after-preload convention, freezing it unloaded is the mistake worth naming.
    # Calibrate Px₀, NOT Tare DIC. Tare DIC clears the console and the live diagnostics and leaves
    # the reference alone — the two are different operations. This step stays HERE, after the
    # preload, because under the after-preload convention the freeze defines the strain zero, and
    # Prepare test (below) tares the FORCE immediately after, at which point the load it was
    # captured at is gone.
    px0_ok = px0 is not None
    if px0_ok and after_preload and (px0_load or 0.0) < floor:
        out.append(["px0", "Calibrate Px₀ — freeze the strain reference", NEXT,
                    f"⚠ frozen at {px0_load or 0:.0f} N — the convention is AFTER preload; "
                    f"press Calibrate Px₀ again"])
    else:
        add("px0", "Calibrate Px₀ — freeze the strain reference", px0_ok,
            f"{px0:.1f} px @ {px0_load or 0:.0f} N  (nothing else moves it)"
            if px0_ok else
            "strain has no reference until this is set — Tare DIC does NOT set it")

    # FRAMING. Whether the markers can physically stay in frame for the planned pull. This
    # lives here, in the panel the operator actually watches, because it existed only as a
    # console line before and S36 was lost at 15.8 mm to a warning that had been printed and
    # never seen.
    f = getattr(app, "_framing", None)
    if f:
        room, need = f.get("room", 0.0), f.get("need", 0.0)
        short_mm = (need - room) / max(1e-6, f.get("pxmm") or 1.0)
        if f.get("mover") is None:
            out.append(["framing", "Marker travel room", INFO,
                        "apply the preload, then Calibrate Px₀ again — which marker moves "
                        "cannot be told until something has"])
        elif room >= need:
            out.append(["framing", "Marker travel room", DONE,
                        f"{room:.0f} px ahead of the moving marker, {need:.0f} needed for the "
                        f"{f['target']:.0f} mm pull"])
        else:
            out.append(["framing", "Marker travel room", NEXT,
                        f"⚠ ONLY {room:.0f} px ahead of the moving marker, {need:.0f} needed — "
                        f"tracking will stop at about {_stop_mm(f):.0f} mm. "
                        f"Shift the CAMERA ~{short_mm:.0f} mm, then Calibrate Px₀ again"])

    prepared = getattr(app, "_prepared_t", None) is not None
    add("prepare", "Prepare test (tares DIC readouts, position, force)", prepared,
        "done" if prepared else "clears the plots and zeroes the axes")

    armed = False
    cap = getattr(app, "capture", None)
    if cap is not None:
        armed = bool(getattr(cap, "png_enabled", False) or getattr(cap, "video_enabled", False)
                     or getattr(cap, "recording", False))
    out.append(["capture", "Arm frame capture", INFO,
                "armed" if armed else
                "optional — Settings ▸ Capture settings, only if this run needs a video"])

    ran = n_samples > 0 and moved > 0.05
    add("run", "Run the test", ran, f"{n_samples} samples" if ran else
        "Fracture test, a manual pull, or an advanced test mode "
        "(cyclic · staircase · relaxation · creep · →fracture)")

    add("save", "Save data", bool(saved), f"{saved.split(chr(92))[-1]}" if saved else
        "save into the specimen folder — the report follows it there")

    # The report has no GUI button any more (2026-08-30): computing E, sigma_y and UTS from
    # the curve is the exercise, so the app stops at the saved CSV. Kept as a wizard row so the
    # operator knows where the run ENDS, and where the analysis picks it up.
    out.append(["report", "Analyse the CSV", INFO,
                "the app stops here — properties are computed from the saved file "
                "(python utm_report.py <csv> --area 80 --gauge 60)"])

    # Exactly one NEXT, always. The Px₀ row can already have claimed it by flagging a wrong-state
    # calibration, and a checklist showing two "do this next" arrows tells the operator nothing —
    # so only promote a TODO when nothing has claimed it.
    if not any(r[2] == NEXT for r in out):
        for row in out:
            if row[2] == TODO:
                row[2] = NEXT
                break
    return [tuple(r) for r in out]


def summary(app):
    """(done, blocking_total) — for a one-line header."""
    rows = steps(app)
    blocking = [r for r in rows if r[2] != INFO]
    return sum(1 for r in blocking if r[2] == DONE), len(blocking)
