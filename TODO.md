# UTM — TODO

**App 0.5.4 · Firmware 1.3.1 · updated 2026-08-27**

Three documents, three jobs — do not merge them:

| doc | job |
|---|---|
| **this file** | what must happen next, in order. Deployment first, then open validation. **Software.** |
| **`MECHANICAL_TODO.md`** | the mechanical counterpart — alignment, compliance, backlash, load train. Development to date has been almost entirely software; this is the gap. |
| `Software/UTM_PyQt6/docs/ROADMAP.md` | living status of every feature (SF1–SF19) and the research campaign. **The detail lives there.** |
| `Software/UTM_PyQt6/docs/TEST_FAILURES.md` | runs that did not complete, with root cause. Read before blaming the software. |

---

## 🔴 P0 — Student deployment (guide ready Monday 2026-08-31; campaign runs 7 weeks)

~40 student groups generate tensile data over **seven weeks**, unsupervised for most of it. The app
is currently configured as a **research instrument for one expert operator**. Everything here is
about closing that gap and keeping it closed for seven weeks of forty different pairs of hands.

### Decisions to make before writing the guide

- [ ] **Resolve the Px₀ convention and write down the one you teach.** `README.md` states
      "Px₀ is frozen AFTER the preload"; SF18 added a **Calibrate Px₀** button explicitly so it
      could be frozen BEFORE preload, and the wizard warns on an unloaded Px₀. Both are defensible;
      an ambiguous procedure taught to 40 groups is not. Pick one, make the wizard agree, fix the
      README. **Blocks the guide.**
- [ ] **Mandate white markers, not black.** Black-mode runs show an unexplained DIC delivery
      collapse — S13 lost **51 %** of coverage, S29 **21 %**, while white S26 held **99.9 %**
      (ROADMAP §3a item 6, still open, n = 3). Do not put a seven-week campaign on the untriaged path.
- [ ] **Infill is a free variable — there is no force ceiling.** The "2.6 kN motor ceiling" was
      a mechanical misalignment, resolved 2026-08-12 (loose load holders + binding screws), and the
      rig is rated to **~15 kN**. 100 % infill has fractured 11 times at 3586–3826 N. Let the groups
      choose infill; just make them **log it**, since it is the most interesting variable they have.

### App changes (small, low risk, high leverage)

- [ ] **Ship a `Student` settings profile** in `utm_recipes.py` beside `Default` and `TPU`.
      The single biggest lever: one dropdown entry moves preload, speed, strain cap, auto-stop, ROI
      and material together. Adi's own note applies exactly — *"two set and one forgotten is a
      wasted specimen."* Seeded by `ensure_default()`, so it appears on first launch on any machine.
- [ ] **Default the Guided wizard ON** — `main.py:5221`, `_recall_bool("ui/wizard_open", False)`
      → `True`. Turned off at the expert operator's request; students are the opposite case. Pure
      VIEW, AST-checked to reach no control path, so there is no risk in this.
- [ ] **Decide the registry policy.** `registry.json` auto-appends on Save. Over 40 runs this either
      becomes a genuinely good class dataset or it pollutes the research register. Decide before
      week 1, not week 4.

### Surviving seven weeks — the items a one-day session would not need

- [ ] **Weekly mechanical check, and put it in writing.** Loose load holders letting the crossheads
      go out of alignment is **the** documented failure mode on this rig (S15), and mounting and
      unmounting 40 specimens is exactly what loosens them. Weekly: **check load-holder torque,
      crosshead alignment, and screw lubrication.** A stall is now a maintenance signal, not a
      software one — if the stall guard ever fires, this is the first thing to check.
- [ ] **DIC auto-calibration is SESSION-ONLY — decide how that is handled.** `utm_autocal.py`
      never writes back to the preset in `camera_manager.py`, so every restart returns to the
      hand-set exposure and threshold chosen once under one set of LEDs. Over seven weeks the
      lighting *will* drift, and the first symptom is a ruined test. Either persist the result to
      the `Student` profile, or make **Settings ▸ Auto-calibrate DIC…** a mandatory step in the
      student procedure rather than the optional wizard row it is now.
- [ ] **Load-cell calibration check at least once mid-campaign.** Seven weeks and 40 mountings is
      long enough for the two-point calibration to drift; a known reference weight takes minutes.
- [ ] **Consumables and spares.** Marker spray, specimen stock, and a spare ESP32 / USB cable.
      A dead cable in week 3 with no spare costs a week of slots.

### Guide (written + recorded)

- [ ] **Written guide** — one page the students actually follow at the rig. Must cover the three
      things that will otherwise generate 40 identical questions:
      **force reads negative** after tare-at-preload on an unloaded or fractured specimen;
      the preload is not optional; Px₀ has exactly one owner (see decision above).
- [ ] **Recorded walkthrough** — one full run end to end: mount → preload → Calibrate Px₀ →
      Prepare specimen → Fracture test → auto-stop → Save → Generate report.
- [ ] **A one-page WHAT-WENT-WRONG sheet** beside the machine. Over seven weeks you will not be
      there for most runs. Cover: stall guard fired → call the supervisor, do not re-run;
      DIC shows 0/2 markers → re-run auto-calibrate; specimen did not fracture; force negative.
- [ ] **Dry-run the guide yourself on one specimen before recording**, following only what is
      written. Anything you reach for that is not in the guide is a gap.

## 🟡 P1 — Open validation (needs rig time, does not block Monday)

### HIGH — Quantify machine compliance

**Only 19–29 % of crosshead travel reaches the gauge.** This is a *validation* item, not a
mechanical-repair one: until it is quantified, every crosshead-derived number carries an unknown
machine term, and `Motor_Strain` is unusable as anything but a rough sanity check.

The frame is 80×80 aluminium and effectively rigid at 3.8 kN, so it is not the source. The
**specimen form-holder is printed 100 % PLA**, and bulk stiffness does not account for the loss —
the dominant term is **local contact crushing**, which also explains the rising-stiffness toe region.

- [ ] **Bearing-stress calculation** — 3800 N divided by the actual bearing area at each PLA contact
      face. PLA yields at ~50–60 MPa, so below ~70 mm² the holder crushes plastically on every test
      and the machine drifts softer across the campaign. **No rig time, no disassembly** — the
      holder drawing and a calculator. Do this one first.
- [ ] **Rigid-dummy compliance curve** — steel bar of the same grip geometry, pulled the same way.
      Isolates *frame + drivetrain + holder + contact*, i.e. everything that is not the specimen.
      Gives a force-by-force correction curve for crosshead strain.
- [ ] **Holder-creep check** — a relaxation run against the rigid dummy. Any force decay with no
      specimen present is holder creep, and it contaminates the creep / relaxation / staircase-dwell
      results until it is bounded.

Full mechanical context in `MECHANICAL_TODO.md` §3.

### Carried over from Phase 8.6

75 of 83 items complete.

- [ ] **8.6.3** Known-displacement test — Motor vs DIC Cauchy strain on a real specimen.
- [ ] **8.6.4** Strain sign test — tension (+) / compression (−) under real loading.
- [ ] **8.6.15** Printed-marker calibration — tare on 50 mm dot spacing, swap to 55 mm,
      confirm DIC Cauchy ≈ 0.1000. Validates the DIC maths end-to-end, independent of the UTM.
- [ ] **8.6.17** Motor encoder accuracy — command 1 / 5 / 10 mm, compare to `Position_mm`.
      Validates the `Motor_Strain` denominator.
- [ ] **8.6.18** Multi-session tare consistency — reconnect the camera between sessions,
      verify `px_per_mm` holds.
- [ ] **8.6.19** Elastic modulus characterisation — 0.05 mm/s ramp to ~0.5 mm compression,
      hold 30 s, return. Pass: R² > 0.99, E within 1–4 GPa, hold drift < 5 %.
- [ ] **DIC↔load-cell match** — hardware-verify that stall rows carry unique DIC values.
- [ ] Remove the temporary 8.4.6 validation log from `main.py` once the above pass.

---

## UI / UX — before the students arrive (highest value per hour)

The panel grew feature by feature and the grouping now reflects **build order, not operator order**.
The original author could not find the motor enable switch; 40 students will not do better.
Raised 2026-08-27. All of this is layout — no measurement path is touched.

### Safety — do this one first

- [x] **DONE 2026-08-27 — The Emergency STOP scrolled out of view.** Moved out of
      `motorControlGroup` into `verticalLayout_outer`, outside `mainScrollArea`. It was also the
      insertion anchor for four runtime-built sections (`indexOf(self.emergencyStopButton)`), so
      those were rewritten to explicit appends. Verified by constructing the real window offscreen:
      parent chain is now `centralwidget → MainWindow`, panel order unchanged.
      ⚠️ **Still to check visually:** it now spans the FULL WINDOW width, not just the control
      column. Probably correct for an E-STOP — confirm, or wrap it in an HBox with a left stretch.

<details><summary>original report</summary>

- **The Emergency STOP scrolls out of view.** `mainScrollArea` (`ui/utm_mainwindow.ui:37`) wraps
      the whole control panel, and the E-STOP sits at **line 1270 — with `positionGroup` (1278) and
      `incrementalMoveGroup` (1304) below it**. It is not even the last widget, so it can be
      scrolled off in either direction. **Pin it outside the scroll area**, docked to the bottom of
      the panel, always visible.

</details>

### Reorder to match the operator sequence

The wizard already encodes the right order. The panel should mirror it: connect → enable motors →
data streams → preload → prepare → run → save.

- [ ] **Motor Control moves above Speed Control.** You enable motors before you set a speed.
- [ ] **`Motors` → `Enable Motors`**, moved to the **first row of Motor Control**, above Direction.
- [ ] **Put every switch immediately next to its label.** `Enable Motors`, `Connection` and the three
      Data Streams toggles all sit at the far right of a wide row with a gap between, so label and
      state have to be paired across empty space. Label → control → stretch, not
      label → stretch → control.

### Split Motor Control — it currently holds four unrelated things

Preload, specimen preparation, the strain-rate test and Advanced test modes are all inside a group
called *Motor Control*. Proposed grouping:

| Group | Contents |
|---|---|
| **Connection** | scan / port / connect (unchanged) |
| **Motor Control** | **Enable Motors** · Direction · jog speed |
| **Data Streams** | load cell · position · velocity (unchanged) |
| **Specimen** | settings profile · infill % · preload · release to preload / fully · Prepare test |
| **Run Test** | auto-stop · Fracture test · strain-rate test · Advanced test modes |
| **Save & Report** | Comment · File ID · Save Data · Generate report |
| **Emergency STOP** | pinned, outside the scroll area |

- [ ] **Name the data group `Save & Report`**, not `Data`. Comment and File ID are *inputs to* those
      two actions — File ID goes into the filename, the comment into the CSV header — so the group
      is named for what you came to it to do. `Data` is a category label; `Save & Report` is a verb.
- [ ] **Check whether the save controls are duplicated per tab** — there is both a `stressDataGroup`
      and a `loadDataGroup`. If both carry Save, consolidate to one place.
- [ ] **Decide where Speed Control lands.** Either its own group directly under Motor Control, or
      folded into it as the manual-jog speed — the strain-rate test and the advanced modes already
      carry their own speed fields, so the top-level one is only for jogging. The circular gauge is a
      *readout*, not a control, and could move to the live-readout area either way.

### Narrow screens — the panel must survive a 13–14" laptop

Today, narrowing the control column **hides elements and makes them unselectable**. Raised
2026-08-27. Set a concrete target and test against it, rather than "looks fine on my monitor":

> **Design target: the control column works down to ~320 px, on a 1366×768 screen at 150 % Windows
> scaling.** That is the real constraint a 13–14" student laptop imposes.

- [ ] **Root cause — 69 hard size constraints in `ui/utm_mainwindow.ui`** (`minimumSize`,
      `maximumSize`, explicit `<width>`). These are what stop the panel shrinking gracefully: a
      layout cannot compress below the sum of its children's minimums, so it clips instead. **Audit
      all 69**; most should become size *policies*, not fixed pixels.
- [ ] **Move labels ABOVE their controls, left-aligned.** This is the single biggest win for narrow
      widths — a label beside a field doubles the row's minimum width. Qt does it natively:
      `QFormLayout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)`. Note only **6**
      QFormLayouts exist across the `.ui` and `main.py` today — nearly every row is a QHBoxLayout
      with the label welded beside the control, which is exactly why they squish.
- [ ] **Specimen first row holds too much** — `Settings:` + profile combo + `Load` + `Save…` +
      `Infill %` + spinner, all on one line. Split: profile and its two buttons on one row, infill on
      its own.
- [ ] **`Auto-stop at fracture` loses visibility** wedged between `Prepare test` and `Fracture test`.
      **Move it above the two buttons**, on its own row. It is a mode that governs both, not a peer
      of either — the position should say so.
- [ ] **Advanced test modes: `Low` and `High` side by side** squish together. Same fix — label above
      control, and let the pair stack when there is no room.
- [ ] **Never let a control become unreachable.** If a group genuinely cannot fit, it must wrap or
      the panel must scroll — clipping a control so it cannot be clicked is the one outcome to
      design out. Check every group at the target width.
- [ ] **Test at 125 % and 150 % Windows DPI scaling**, not just 100 %. Fixed pixel sizes are exactly
      what breaks under scaling, and student laptops are rarely at 100 %.

### Working on the UI with no machine attached — yes, and here is the setup

**You do not need the rig.** Confirmed: the app starts with no serial link and no camera, and
**disabled widgets still occupy their full geometry** — so every layout, truncation and clipping bug
is visible while disconnected. Layout work is fully doable on a laptop at midnight.

**Qt Designer is NOT the workflow** (operator's call, 2026-08-27) — changes are verified by
running the app end-to-end. That is the right call anyway: the panel is built two ways, with some
widgets created in `main.py` and inserted at runtime relative to others, so Designer only ever
showed part of the truth.

- [ ] **Edits go straight to the `.ui` XML and `main.py`, verified by launching.** For a structural
      change, an offscreen build is a fast pre-check before a visual one —
      `QT_QPA_PLATFORM=offscreen` plus constructing `UTMApplication` exercises every runtime layout
      builder without a rig, a camera or a window. That is how the E-STOP move was verified.
- [x] **DONE 2026-08-28 — `--demo` flag.** `python main.py --demo` renders every control in
      its enabled state with no rig. Verified offscreen: **9/9 gated controls disabled without
      the flag, 9/9 enabled with it**; `send_command` is replaced so a demo session cannot
      reach a port (returns False, logs `[DEMO] not sent: ...`); title reads `DEMO MODE (no
      hardware)`. It ORs into the gate rather than forcing `self.connected`, because the
      connection monitor rewrites that flag on a timer and would undo it.

<details><summary>original request</summary>

- **Add a `--demo` flag so the panel renders in its ENABLED state.** Twelve controls gate on
      `connected`, so a disconnected app shows half the panel greyed out and you cannot judge it.
      **There are currently no CLI flags at all** — `main.py:7487` is a bare
      `QApplication(sys.argv)` — so this is a clean, self-contained addition: parse one argument,
      force the connected state true, refuse to send serial. Cheap, and it is what makes a weekend
      of UI work actually productive.

</details>
- [ ] **Load an existing CSV** to populate the plots, cropping and data groups without hardware —
      CSV import already restores DIC data and calibration.
- [ ] **The DIC post-processing tab runs fully offline** against recorded video, so that whole tab
      can be designed and tested with no rig at all.

### ✅ DONE 2026-08-28 — Connection UX: autoconnect, and three real bugs

**Autoconnect.** The app now finds and opens the rig at launch with no scanning and no
picking. Two stages, and only the second proves anything: USB **VID/PID narrows** the
candidates, the firmware **handshake confirms** (`Welcome to Mirzas...`, which
`serial_manager` already tested for). `--no-autoconnect` opts out; it falls back silently to
the manual controls when nothing is found.

**Three bugs fixed along the way:**

1. **Connect could be clicked with no port selected**, and the resulting
   `Error: No COM port selected` went to the Console — invisible from any other tab, so it
   read as "the button does nothing". The switch is now **disabled** unless a port exists,
   with a tooltip saying to scan.
2. **An in-flight attempt could not be stopped.** The toggle-off branch only acted
   `if self.connected or port_open`, so an attempt against a dead port left the worker thread
   and the handshake timer running with the switch stuck on. Added
   `SerialManager.cancel_connect()`, and the toggle now calls it.
3. **Connecting did not show the Console**, where the entire connection story is written.
   It now switches tabs on connect and on the no-port error.

**Field note — the rig board is a CH340, not a CP2104.** Live scan: `COM3` reports
`0x1A86:0x7523`. **CH340 chips have no USB serial number** (`serial=None` on this board), so
the "pin the serial number to survive COM renumbering" idea in the original plan **does not
work here**. VID/PID plus the handshake is what identifies the rig. Worth re-checking after
the USB hub arrives, since renumbering is exactly what a hub causes.

- [ ] **Try it against the real rig.** Verified offscreen with the connect call stubbed, so no
      port was opened and the ESP32 was never DTR-reset. The identification is proven on live
      hardware (`COM3` correctly picked out of three ports); the actual open is not.
- [ ] **Decide whether autoconnect should retry** if the rig is plugged in *after* launch.
      Currently it runs once at startup. A student who forgets the cable has to press Scan.


---

## Deployment — one file, no install (for discussion)

Goal: a student downloads one `.exe` and runs it. `tools/build_exe.py` (PyInstaller) already exists
but has never been used in anger. Raised 2026-08-27.

### ✅ DONE 2026-08-27 — `deploy/` and a working `build_exe.py`

A double-clickable icon now exists, and the PyInstaller script actually runs.

| file | what |
|---|---|
| `deploy/install.ps1` | Windows. venv + deps + Desktop and Start-Menu shortcuts, `pythonw.exe` so there is no console window. `-Rig` (with pypylon) or default analysis profile. |
| `deploy/install.sh` | macOS `.command` / Linux `.desktop`. Same two profiles. Lower priority, as agreed. |
| `deploy/make_icon.py` | generates `utm.ico` + `utm.png` — a stress-strain curve to fracture, drawn per size so it reads at 16 px. There was no icon in the repo at all before. |

**`tools/build_exe.py` was BROKEN and is now fixed.** It still assumed it sat beside `main.py`, but
it moved into `tools/` in the 2026-08-25 reorganisation — so `MAIN_PY` resolved to
`tools/main.py` and `get_version()` raised `FileNotFoundError` at import. Fixed, plus: it now
bundles `ui/help/` (without which every `?` diagram is silently blank), sets the icon, and takes
`--analysis` to exclude pypylon for the student build.

- [ ] **Run `install.ps1` end-to-end on the rig PC** — parse-checked and the shortcut mechanism is
      verified, but the full venv-and-install path has not been executed.
- [ ] **Actually build an exe and test it on a clean Windows machine** with no Python and no Pylon.
      Still the only test that counts, and `__file__` paths under a frozen build remain unproven.

### ⭐ Installer — built, NOT yet run end-to-end

Files exist and are parse-checked; **none of it has been executed against a real install.**

- [ ] **Run `deploy\install.ps1` on the rig PC.** Creates `.venv`, installs deps, puts a
      Desktop + Start Menu icon. Parse-checked and the `.lnk` mechanism is verified, but the
      venv-and-pip path has never been executed.
- [ ] **Run `deploy\install.ps1 -Rig` vs the default analysis profile** and confirm the
      analysis one really does start with no pypylon. *(The import guard is done and tested —
      see below — so this should now work.)*
- [ ] **Test `deploy/bootstrap.ps1`** — the `irm ... | iex` one-liner. **Blocked until the
      merge is pushed**: it clones `cenmir/UTM`, which is still at the old head, so the raw
      URL 404s today.
- [ ] **Build an actual exe** with `tools/build_exe.py --analysis` and test it on a clean
      Windows machine with no Python and no Pylon. Still the only test that counts.
- [ ] **Fix `__file__` under PyInstaller BEFORE building** — see below. The exe will appear to
      work and then fail silently without it.
- [ ] **`install.sh` (macOS/Linux) is untested.** Low priority, as agreed.

**✅ Prerequisite done 2026-08-28: pypylon import is now optional.** `camera_manager.py` did
`from pypylon import pylon` at module level and `main.py` imports `CameraManager` at module
level, so a machine without pypylon **could not start the app at all** — the `--analysis`
build would have compiled and then crashed on launch. All four `pylon.*` uses sit behind
`connect_camera()`, so the import is now soft (`PYLON_AVAILABLE`) and that one entry point
refuses cleanly with a message pointing at the post-processing tab. Verified by blocking
pypylon with a `find_spec` hook: app imports, window builds, `connect_camera()` returns False.

### The framing decision: this is TWO builds, not one

- [ ] **Decide the target before building anything.** They need different things:

| Build | For | pypylon | Notes |
|---|---|---|---|
| **Rig build** | the lab PC that drives the machine | **yes** | One machine, one setup. An installed venv is arguably better than an exe here — easier to patch mid-campaign. |
| **Analysis build** | the ~40 student laptops | **no** | Post-processing tab, CSV load, plots, Generate report. **This is the one worth shipping as a single exe** — and dropping pypylon removes the hardest dependency by far. |

`utm_analysis.py`, `utm_registry.py`, `utm_dic.py`, `control_policies.py` and `utm_recipes.py` are
**deliberately stdlib-only**, so the entire offline path already runs with no camera stack. The
analysis build is a much smaller problem than the rig build.

### The trap that will break the first exe you make

- [ ] **`__file__`-derived paths do not survive PyInstaller.** `CAPTURE_ROOT`, `UI_FILE`, the
      `ui/help` lookup and `utm_recipes.RECIPES_DIR` are all built from `__file__`, which under a
      frozen one-file build points into a **temporary extraction directory** that is deleted on exit.
      Per the module README these paths **fail silently** — no exception, just a capture that never
      appears or a blank help image. Route all four through a `sys._MEIPASS`-aware helper for
      read-only assets, and an explicit user-data directory for anything written.

### The rest

- [ ] **Windows SmartScreen will flag an unsigned exe** downloaded by 40 students, and PyInstaller
      one-file builds draw antivirus false positives. Either get it signed, or write the
      click-through into the guide and warn the students before they panic.
- [ ] **One-file vs one-folder.** One-file re-extracts on every launch — expect 5–15 s of startup
      with PyQt6 + matplotlib bundled. One-folder starts fast but is a folder, not "a single file".
      A zipped one-folder build is the usual compromise; decide which promise matters more.
- [ ] **Pin the version in the filename** (`build_exe.py` already reads `__version__` from
      `main.py`). Over seven weeks you will ship more than one build, and you need to know which one
      a student is reporting a bug against.
- [ ] **Test on a clean Windows machine** with no Python and no Pylon. That is the only test that
      counts, and it is the one everybody skips.
- [ ] **Decide how students get their data off the rig PC** — the analysis build is only useful if
      they can take a CSV home. USB stick, network share, or the report PDF alone.

---

## ⚙️ Firmware — next revision

No firmware work is currently scheduled; version sits at **1.3.1**. These are the items for the
next revision, whenever it happens. Neither blocks the student campaign.

### Read the second AS5600 — crosshead skew detection  ⭐ the one worth doing

**The encoder is already fitted, wired through the TCA9548A and initialised — and never read.**

- `D32_Firmware/src/main.cpp:35` — `#define SENS_IDX 0`, and `ProcessSensors()` only ever reads
  that one channel, so the reported position is **one side's opinion**.
- `D32_Firmware/src/main.cpp:23-24` — **one** `STEP_PIN 14` / `DIR_PIN 27` and **one**
  `MoToStepper`; both TMC2160 drivers take the same pulse train in parallel. There is no
  independent control of the two sides and no correction if they diverge.
- `Sensors` already exposes `readTotalPosition(int)` and carries `amsOffsets[2]`. The capability is
  built and paid for; nothing new has to be wired.

If one side binds and skips steps the crosshead **racks**, and today nothing detects it. That is
precisely the S15 fault mode (`docs/TEST_FAILURES.md`), and the instrument that would have caught
it in seconds is already bolted to the machine.

- [ ] **Read channel 1 alongside channel 0** and expose the difference over serial as its own field.
- [ ] **Log skew as a CSV column** — it then becomes a health trace on every test from then on, and
      a slow drift across the 7-week campaign is exactly the signal §1 of `MECHANICAL_TODO.md` is
      trying to catch by hand.
- [ ] **Add a skew threshold**: warn, then halt. Strictly better than the software stall guard,
      which sees the symptom (crosshead frozen) rather than the cause (sides diverging).
- [ ] **Testing plan — this needs deliberate validation, not just a code change:**
      - Bench test first, motors free, no specimen: confirm both channels track and that the
        difference sits at a stable near-zero with a known noise band. **Establish that band before
        setting any threshold**, or the threshold is a guess.
      - Confirm the multiplexer channel select is correct for both — `tcaselect()` must run before
        every read, and a wrong channel returns the *other* encoder's angle, which looks like
        perfect agreement rather than an error.
      - Verify the cumulative-position offsets (`amsOffsets[2]`) behave independently across a
        power cycle for both channels; only channel 0's path has ever been exercised.
      - Then induce a known skew deliberately (one side hand-cranked, machine disabled) and confirm
        both the reading and the halt fire at the expected magnitude.
- [ ] **Watch the I2C budget.** `ProcessSensors()` runs on a 50 ms cadence and the load-cell loop
      shares the bus; a second `tcaselect` + read per cycle roughly doubles the encoder I2C traffic.
      Measure the loop time after, not before — the `# DIC Loop` header line already reports it.

### Also

- [ ] **Consider exposing loop timing over serial** as a first-class field rather than a header
      comment, so a slow loop is visible live rather than found afterwards in a CSV.

---

## 🔵 P2 — Research (see ROADMAP for the full detail)

- [ ] **Why did DIC delivery slow?** ROADMAP §3a item 6. Narrowed to downstream-of-detection and
      correlated with Black mode; n = 3. **Confirm on the next Black run.** Gates the P0 marker
      decision above for any future campaign.
- [ ] **Ask MOT for their load or crosshead-displacement channel.** Turns the extensometer
      comparison into a real scale check by cancelling the compliance term. Cheap, and the only
      thing left on that thread.
- [ ] **T6.6 damage curve** — fresh 50 % specimen, 400→1100 N, 12 sine cycles, one uninterrupted
      run. The only route to D = 1 − Eᵢ/E₀. ~40 min.
- [ ] **Deck slides for SF11/12/13/18/19** — two overview slides first, then per-feature slides as
      screenshots arrive. SF18 is blocked on the lighting problem.
- [ ] **Multi-marker Poisson / true Cauchy** — maths ready in `utm_dic.py`; needs a 4-marker
      specimen preset and camera wiring.

---

## Housekeeping

- [ ] `README.md` points at `Software/UTM_PyQt6/dic_replay.py`; the file is at
      `Software/UTM_PyQt6/tools/dic_replay.py`. Stale since the 2026-08-25 reorganisation.
- [ ] Registry integrity check — must print `0 unresolved`, run **from the repository root**:
      ```
      python -c "import json,os; r=json.load(open('Software/UTM_PyQt6/registry.json')); print(sum(1 for x in r if not os.path.isfile(x['csv'])),'unresolved of',len(r))"
      ```
