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
PRELOAD_MIN_N = 50.0


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

    # Preload. After Prepare test the reading is tared to ~0, so the durable evidence that a
    # preload was applied is the load Px₀ was captured at, not the live reading.
    load_now = abs(getattr(app, "current_load", 0.0) or 0.0)
    preloaded = load_now >= PRELOAD_MIN_N or (px0_load or 0.0) >= PRELOAD_MIN_N
    add("preload", "Apply preload", preloaded,
        f"{load_now:.0f} N now" if load_now >= PRELOAD_MIN_N else
        (f"Px₀ was taken at {px0_load:.0f} N" if (px0_load or 0) >= PRELOAD_MIN_N
         else "Preload tension — seat the specimen first"))

    # Px₀. Under the after-preload convention, freezing it unloaded is the mistake worth naming.
    # Named "Tare DIC" first because that is the button now — one click, no dialog. It stays HERE,
    # after the preload, and not up with the camera steps: under the after-preload convention this
    # freeze defines the strain zero, and Prepare test (below) tares the FORCE, after which the
    # reading is ~0 N and the load it was captured at is lost.
    px0_ok = px0 is not None
    if px0_ok and after_preload and (px0_load or 0.0) < PRELOAD_MIN_N:
        out.append(["px0", "Tare DIC — freeze Px₀", NEXT,
                    f"⚠ frozen at {px0_load or 0:.0f} N — the convention is AFTER preload; re-tare"])
    else:
        add("px0", "Tare DIC — freeze Px₀", px0_ok,
            f"{px0:.1f} px @ {px0_load or 0:.0f} N  (or Calibrate Px₀, which asks first)"
            if px0_ok else "strain has no reference until this is set")

    prepared = getattr(app, "_prepared_t", None) is not None
    add("prepare", "Prepare test (tares Px₀, position, force)", prepared,
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

    out.append(["report", "Generate report", INFO,
                "builds from the saved CSV, into the same folder"])

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
