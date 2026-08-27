"""The DIC Post-Processing tab: load a recorded video, place a virtual extensometer, get strain.

Left half is the video and everything that decides the measurement; right half is the strain-vs-time
plot, drawn live as the analysis runs. The split is deliberate — the operator sets up on the left
and watches the answer appear on the right, without either half moving.

The measurement itself is utm_postproc; nothing here computes strain. That module in turn calls
utm_dic.dic_strain, the same function the live rig calls, so a video replayed here and the pull
that produced it cannot disagree about what strain means.

Placing the extensometer:
    Click the frame to drop box A, click again for box B, or press Auto-detect for sprayed dots.
    The gauge length in mm is the physical distance BETWEEN THE BOXES — it sets px/mm and nothing
    else. Strain is a pixel ratio, so an unknown or wrong gauge cannot corrupt the strain trace;
    it only makes the px/mm readout meaningless.
"""
import os
import time

import numpy as np
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                             QFileDialog, QDoubleSpinBox, QSpinBox, QGroupBox, QSplitter,
                             QProgressBar, QMessageBox, QSlider, QCheckBox)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import utm_postproc as PP


class FrameView(QLabel):
    """The video frame, the two tracking boxes, and everything needed to place them precisely.

    Three ways to position a box, because clicking alone is not enough on every specimen:
      * click       — places the next box, snapping to a marker centre when one is near
      * drag        — grab an existing box and move it freely, no snapping, for a speckle pattern
                      or a marker the detector will not find
      * arrow keys  — nudge the selected box one frame-pixel at a time (ten with Shift)

    The centre is drawn as a crosshair, not just a box outline. The box is usually much smaller
    than the dot it sits on, so an outline alone gives the eye nothing to judge centring against —
    which is exactly the complaint that prompted the drag and the crosshair.
    """
    clicked = pyqtSignal(float, float)          # in FRAME pixel coordinates
    moved = pyqtSignal(int, float, float)       # box index dragged to a new frame position
    selected = pyqtSignal(int)

    GRAB_SLACK_PX = 14.0                        # extra grab radius, in WIDGET pixels

    def __init__(self):
        super().__init__()
        self.setMinimumSize(260, 320)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#101317; border:1px solid #2b3138;")
        self.setText("Load a video to begin")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)   # so the arrow keys reach us
        self.setMouseTracking(True)
        self._gray = None
        self._boxes = [None, None]
        self._half = 24
        self._scale = 1.0
        self._ox = self._oy = 0
        self._drag = None            # index of the box being dragged
        self._sel = None             # index of the selected box, for the arrow keys
        self._markers = []           # drawn as faint rings, so the operator sees what will snap

    def set_frame(self, gray):
        self._gray = gray
        self._redraw()

    def set_boxes(self, a, b, half):
        self._boxes = [a, b]
        self._half = half
        self._redraw()

    def play(self, gray, a, b, half):
        """One repaint for a frame AND its box positions — used while the analysis runs.

        set_frame() followed by set_boxes() would redraw twice per frame, which at 25 Hz on a
        2348 px frame is enough scaling work to make the GUI feel heavy for no benefit.
        """
        self._gray = gray
        self._boxes = [a, b]
        self._half = half
        self._redraw()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._redraw()

    def _redraw(self):
        if self._gray is None:
            return
        h, w = self._gray.shape
        buf = np.ascontiguousarray(self._gray)
        img = QImage(buf.data, w, h, w, QImage.Format.Format_Grayscale8)
        pm = QPixmap.fromImage(img).scaled(self.width(), self.height(),
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        self._scale = pm.width() / w if w else 1.0
        self._ox = (self.width() - pm.width()) // 2
        self._oy = (self.height() - pm.height()) // 2
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Every marker the snap knows about, as a faint ring. Without this the operator cannot
        # tell whether a click will snap or land free — the detector's opinion is invisible.
        p.setPen(QPen(QColor(77, 171, 247, 130), 1, Qt.PenStyle.DotLine))
        for m in self._markers:
            mx, my, mr = m[0] * self._scale, m[1] * self._scale, m[2] * self._scale
            p.drawEllipse(int(mx - mr), int(my - mr), int(2 * mr), int(2 * mr))

        cols = (QColor("#2ecc71"), QColor("#e8590c"))
        pts = []
        for i, bx in enumerate(self._boxes):
            if bx is None:
                continue
            cx, cy = bx[0] * self._scale, bx[1] * self._scale
            r = max(3.0, self._half * self._scale)
            pts.append((cx, cy))
            sel = (i == self._sel)
            p.setPen(QPen(cols[i], 3 if sel else 2))
            p.drawRect(int(cx - r), int(cy - r), int(2 * r), int(2 * r))
            # The crosshair IS the placement: it marks the exact pixel that becomes L0's endpoint.
            p.setPen(QPen(cols[i], 1))
            p.drawLine(int(cx - r - 6), int(cy), int(cx + r + 6), int(cy))
            p.drawLine(int(cx), int(cy - r - 6), int(cx), int(cy + r + 6))
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.drawPoint(int(cx), int(cy))
            p.setPen(QPen(cols[i], 2))
            p.drawText(int(cx + r + 4), int(cy - r - 4), "AB"[i] + (" ◄" if sel else ""))
        if len(pts) == 2:
            p.setPen(QPen(QColor("#4dabf7"), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(pts[0][0]), int(pts[0][1]), int(pts[1][0]), int(pts[1][1]))
        p.end()
        self.setPixmap(pm)

    def set_markers(self, markers):
        self._markers = list(markers or [])
        self._redraw()

    def select(self, i):
        self._sel = i
        self._redraw()

    def _to_frame(self, pos):
        if self._gray is None or self._scale <= 0:
            return None
        x = (pos.x() - self._ox) / self._scale
        y = (pos.y() - self._oy) / self._scale
        h, w = self._gray.shape
        return (float(min(max(x, 0), w - 1)), float(min(max(y, 0), h - 1)))

    def _box_under(self, pos):
        """Which box is under the cursor, in WIDGET pixels — so the grab feels the same at any zoom."""
        for i, bx in enumerate(self._boxes):
            if bx is None:
                continue
            cx = bx[0] * self._scale + self._ox
            cy = bx[1] * self._scale + self._oy
            reach = max(8.0, self._half * self._scale) + self.GRAB_SLACK_PX
            if abs(pos.x() - cx) <= reach and abs(pos.y() - cy) <= reach:
                return i
        return None

    def mousePressEvent(self, e):
        p = self._to_frame(e.position())
        if p is None:
            return
        self.setFocus()
        hit = self._box_under(e.position())
        if hit is not None:
            # Grabbing an existing box MOVES it, and never snaps: this is the manual override for
            # a speckle pattern, or a marker the detector will not find.
            self._drag = hit
            self._sel = hit
            self.selected.emit(hit)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._redraw()
            return
        self.clicked.emit(*p)

    def mouseMoveEvent(self, e):
        if self._drag is None:
            if self._gray is not None:
                over = self._box_under(e.position())
                self.setCursor(Qt.CursorShape.OpenHandCursor if over is not None
                               else Qt.CursorShape.CrossCursor)
            return
        p = self._to_frame(e.position())
        if p is None:
            return
        self._boxes[self._drag] = p
        self.moved.emit(self._drag, p[0], p[1])
        self._redraw()

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def keyPressEvent(self, e):
        """Arrow keys nudge the selected box by one FRAME pixel — ten with Shift.

        The mouse cannot address a single frame pixel once the frame is scaled down to fit the
        pane: one widget pixel is several frame pixels. This is how a placement is finished.
        """
        if self._sel is None or self._boxes[self._sel] is None:
            super().keyPressEvent(e); return
        step = 10.0 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
        dx = dy = 0.0
        k = e.key()
        if k == Qt.Key.Key_Left:
            dx = -step
        elif k == Qt.Key.Key_Right:
            dx = step
        elif k == Qt.Key.Key_Up:
            dy = -step
        elif k == Qt.Key.Key_Down:
            dy = step
        elif k in (Qt.Key.Key_Tab, Qt.Key.Key_Space):
            other = 1 - self._sel
            if self._boxes[other] is not None:
                self._sel = other
                self.selected.emit(other)
                self._redraw()
            return
        else:
            super().keyPressEvent(e); return
        x, y = self._boxes[self._sel]
        h, w = self._gray.shape
        x = float(min(max(x + dx, 0), w - 1)); y = float(min(max(y + dy, 0), h - 1))
        self._boxes[self._sel] = (x, y)
        self.moved.emit(self._sel, x, y)
        self._redraw()


class Worker(QThread):
    """Runs the analysis off the GUI thread and streams results back a frame at a time."""
    row = pyqtSignal(object)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    frame = pyqtSignal(object, object, object, float)   # gray, box A now, box B now, half-size

    # The analysis runs several times faster than the recording (S26: ~126 fps against a 19.9 fps
    # capture), so every frame must NOT be shipped to the GUI thread. Two brakes: a time throttle
    # for a steady display rate, and a pending flag so a slow repaint applies back-pressure
    # instead of letting a queue of 1 MB frames build up behind it.
    PREVIEW_HZ = 25.0
    # Downscale BEFORE crossing the thread. The preview pane is a few hundred pixels tall, so
    # shipping a full 2348 px frame 25 times a second copies ~1 MB and then throws most of it
    # away in the scaler — measured at a 4x slowdown of the analysis itself. Shrinking here costs
    # one resize and keeps the displayed detail the pane can actually show. Box coordinates are
    # scaled with it, so the view still draws them in frame coordinates.
    PREVIEW_MAX_PX = 720

    def __init__(self, path, a, b, cfg, preview=True):
        super().__init__()
        self.path, self.a, self.b, self.cfg = path, a, b, cfg
        self._stop = False
        self._preview = preview
        self._last_emit = 0.0
        self._pending = False

    def stop(self):
        self._stop = True

    def frame_shown(self):
        """Called from the GUI thread once a preview frame has actually been painted."""
        self._pending = False

    def _on_frame(self, gray, a_xy, b_xy):
        if not self._preview or self._pending:
            return
        now = time.monotonic()
        if now - self._last_emit < 1.0 / self.PREVIEW_HZ:
            return
        self._last_emit = now
        self._pending = True
        import cv2
        h, w = gray.shape
        k = min(1.0, self.PREVIEW_MAX_PX / float(max(h, w)))
        if k < 1.0:
            small = cv2.resize(gray, (max(1, int(w * k)), max(1, int(h * k))),
                               interpolation=cv2.INTER_AREA)
            a_xy = (a_xy[0] * k, a_xy[1] * k)
            b_xy = (b_xy[0] * k, b_xy[1] * k)
        else:
            small, k = gray, 1.0
        # cv2.resize returns a fresh array; the full-size path still needs a copy because the
        # decoder reuses its buffer and this crosses a thread.
        # The drawn box must shrink with the frame, or it would be drawn at full-frame size
        # over a downscaled image and stop matching the patch that is actually being correlated.
        self.frame.emit(np.ascontiguousarray(small) if k < 1.0
                        else np.ascontiguousarray(gray).copy(),
                        a_xy, b_xy, self.cfg.box_half * k)

    def run(self):
        try:
            gen = PP.analyse(self.path, self.a, self.b, self.cfg,
                             progress=lambda d, t: self.progress.emit(d, t),
                             should_stop=lambda: self._stop,
                             preview=self._on_frame)
            while True:
                try:
                    self.row.emit(next(gen))
                except StopIteration as stop:
                    self.done.emit(stop.value)
                    return
        except Exception as e:                       # a bad file must not take the app down
            self.failed.emit(str(e))


class PostProcTab(QWidget):
    log = pyqtSignal(str)
    PLOT_HZ = 8.0            # live plot refresh; the data is kept in full regardless

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None
        self.info = None
        self.boxes = [None, None]
        self._next_box = 0
        self.worker = None
        self.summary = None
        self._t, self._e, self._tr = [], [], []
        self._line_c = self._line_t = None
        self._last_plot = 0.0
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self):
        split = QSplitter(Qt.Orientation.Horizontal)

        # ---- LEFT: the video and the measurement setup
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(6, 6, 6, 6)

        row = QHBoxLayout()
        self.loadBtn = QPushButton("Load video…")
        self.loadBtn.clicked.connect(self.on_load)
        self.fileLbl = QLabel("no video loaded"); self.fileLbl.setStyleSheet("color:#8a8f98;")
        row.addWidget(self.loadBtn); row.addWidget(self.fileLbl, 1)
        lv.addLayout(row)

        self.view = FrameView()
        self.view.clicked.connect(self.on_click)
        self.view.moved.connect(self.on_box_moved)
        self.view.selected.connect(lambda i: self._refresh_l0())
        lv.addWidget(self.view, 1)

        fr = QHBoxLayout()
        fr.addWidget(QLabel("Reference frame"))
        self.frameSlider = QSlider(Qt.Orientation.Horizontal)
        self.frameSlider.setEnabled(False)
        self.frameSlider.valueChanged.connect(self.on_ref_frame)
        self.frameLbl = QLabel("0")
        fr.addWidget(self.frameSlider, 1); fr.addWidget(self.frameLbl)
        lv.addLayout(fr)

        g = QGroupBox("Virtual extensometer"); gl = QGridLayout(g)
        self.autoBtn = QPushButton("Auto-detect markers")
        self.autoBtn.setToolTip("Find two sprayed dots the way the rig does. For a speckle pattern, "
                                "click the frame twice instead.")
        self.autoBtn.clicked.connect(self.on_auto)
        self.clearBtn = QPushButton("Clear boxes"); self.clearBtn.clicked.connect(self.on_clear)
        gl.addWidget(self.autoBtn, 0, 0); gl.addWidget(self.clearBtn, 0, 1)

        self.gauge = QDoubleSpinBox(); self.gauge.setRange(0.1, 1000); self.gauge.setValue(80.0)
        self.gauge.setSuffix(" mm"); self.gauge.setDecimals(2)
        self.gauge.setToolTip("Physical distance BETWEEN THE BOXES. Sets px/mm only — strain is a "
                              "pixel ratio and does not depend on it.")
        self.gauge.valueChanged.connect(self._refresh_l0)
        self.boxHalf = QSpinBox(); self.boxHalf.setRange(6, 200); self.boxHalf.setValue(24)
        self.boxHalf.setSuffix(" px"); self.boxHalf.valueChanged.connect(self._refresh_boxes)
        self.boxHalf.setToolTip("Half-size of each tracked patch. Bigger is steadier but blurs "
                                "local deformation; it must comfortably contain the speckle or dot.")
        self.search = QSpinBox(); self.search.setRange(4, 500); self.search.setValue(40)
        self.search.setSuffix(" px")
        self.search.setToolTip("How far a box may travel from the reference frame. Must exceed the "
                               "largest expected movement, or the match will hit the window edge.")
        self.minCorr = QDoubleSpinBox(); self.minCorr.setRange(0.05, 0.99)
        self.minCorr.setSingleStep(0.05); self.minCorr.setValue(0.55)
        self.minCorr.setToolTip("Below this peak correlation the frame is not trusted: the tracker "
                                "re-seeds and flags it rather than reporting a confident wrong value.")
        for r, (lab, wdg) in enumerate((("Gauge (A→B)", self.gauge), ("Box half-size", self.boxHalf),
                                        ("Search window", self.search),
                                        ("Min correlation", self.minCorr)), start=1):
            gl.addWidget(QLabel(lab), r, 0); gl.addWidget(wdg, r, 1)
        self.l0Lbl = QLabel("place two boxes to set Px₀")
        self.l0Lbl.setStyleSheet("color:#4dabf7; font-weight:bold;")
        gl.addWidget(self.l0Lbl, 5, 0, 1, 2)
        lv.addWidget(g)

        g2 = QGroupBox("Timebase"); g2l = QGridLayout(g2)
        self.fps = QDoubleSpinBox(); self.fps.setRange(0.01, 10000); self.fps.setDecimals(4)
        self.fps.setValue(30.0); self.fps.setSuffix(" fps")
        self.fps.setToolTip("The file's own value is only a default. Containers frequently declare "
                            "a frame rate the recording never had.")
        self.step = QSpinBox(); self.step.setRange(1, 100); self.step.setValue(1)
        self.step.setPrefix("every "); self.step.setSuffix(" frame(s)")
        g2l.addWidget(QLabel("Frame rate"), 0, 0); g2l.addWidget(self.fps, 0, 1)
        g2l.addWidget(QLabel("Analyse"), 1, 0); g2l.addWidget(self.step, 1, 1)
        self.fpsWarn = QLabel(""); self.fpsWarn.setWordWrap(True)
        self.fpsWarn.setStyleSheet("color:#f39c12;")
        g2l.addWidget(self.fpsWarn, 2, 0, 1, 2)
        lv.addWidget(g2)

        self.playChk = QCheckBox("Play the video while analysing")
        self.playChk.setChecked(True)
        self.playChk.setToolTip("Show each frame with the tracking boxes following the markers, so "
                                "the pull can be watched as it is measured. Turn it off for a "
                                "slightly faster run on a long video.")
        lv.addWidget(self.playChk)

        rr = QHBoxLayout()
        self.runBtn = QPushButton("Run analysis"); self.runBtn.setEnabled(False)
        self.runBtn.clicked.connect(self.on_run)
        self.stopBtn = QPushButton("Stop"); self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self.on_stop)
        self.expBtn = QPushButton("Export CSV"); self.expBtn.setEnabled(False)
        self.expBtn.clicked.connect(self.on_export)
        rr.addWidget(self.runBtn); rr.addWidget(self.stopBtn); rr.addWidget(self.expBtn)
        lv.addLayout(rr)
        self.bar = QProgressBar(); self.bar.setValue(0)
        lv.addWidget(self.bar)
        self.status = QLabel("—"); self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#c9d1d9;")
        lv.addWidget(self.status)

        # ---- RIGHT: the answer
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(6, 6, 6, 6)
        self.fig = Figure(figsize=(6, 5))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._reset_plot()
        rv.addWidget(self.canvas, 1)
        self.showTrue = QCheckBox("also plot true (log) strain")
        self.showTrue.stateChanged.connect(lambda *_: self._redraw_plot())
        rv.addWidget(self.showTrue)

        split.addWidget(left); split.addWidget(right)
        split.setStretchFactor(0, 3); split.setStretchFactor(1, 4)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(split)

    def _want_true(self):
        """The checkbox is built after the axes, so this must survive not existing yet."""
        c = getattr(self, "showTrue", None)
        return bool(c and c.isChecked())

    def _reset_plot(self):
        """Rebuild the axes once. During a run the LINES are updated, never the whole figure.

        Clearing and re-plotting on every update redraws the axes, ticks, grid and legend as well
        as the data; measured on a 561-frame run that cost more time than decoding and correlating
        the video did. Keeping the Line2D objects and calling set_data() is the difference between
        a plot that keeps up and one that throttles the analysis behind it.
        """
        self.ax.clear()
        self.ax.set_xlabel("time (s)")
        self.ax.set_ylabel("DIC strain (%)")
        self.ax.set_title("DIC strain vs time")
        self.ax.grid(alpha=0.3)
        self._line_c, = self.ax.plot([], [], color="#e8590c", lw=1.5,
                                     label="engineering (Cauchy)")
        self._line_t, = self.ax.plot([], [], color="#1f6fb4", lw=1.2, ls="--",
                                     label="true (log)")
        self._line_t.set_visible(self._want_true())
        self.ax.legend(frameon=False, fontsize=9)
        self._last_plot = 0.0
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ actions
    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open a recorded video", "",
            "Video (*.avi *.mp4 *.mkv *.mov *.wmv *.m4v *.mpg *.mpeg);;All files (*)")
        if not path:
            return
        try:
            self.info = PP.probe(path)
        except Exception as e:
            QMessageBox.warning(self, "Cannot open video", str(e)); return
        self.path = path
        self.fileLbl.setText("%s — %d frames, %dx%d"
                             % (self.info["name"], self.info["frames"],
                                self.info["w"], self.info["h"]))
        self.frameSlider.setEnabled(True)
        self.frameSlider.setRange(0, max(0, self.info["frames"] - 1))
        self.frameSlider.setValue(0)
        # The container's fps is only a fallback. If this video came out of one of our own
        # captures, the folder beside it records what the camera ACTUALLY did — prefer that, and
        # say so, rather than letting a wrong declared rate quietly stretch the time axis.
        if self.info["fps"] > 0:
            self.fps.setValue(self.info["fps"])
        true = PP.true_fps_from_sidecar(path)
        if true:
            fps_true, src, _n = true
            self.fps.setValue(round(fps_true, 4))
            if self.info["fps"] > 0 and abs(fps_true - self.info["fps"]) / self.info["fps"] > 0.02:
                self.fpsWarn.setText(
                    "Using %.4f fps measured from %s. The file itself declares %.2f fps — "
                    "believing it would scale time by %.2f×."
                    % (fps_true, src, self.info["fps"], self.info["fps"] / fps_true))
            else:
                self.fpsWarn.setText("Frame rate %.4f fps confirmed from %s." % (fps_true, src))
        else:
            self.fpsWarn.setText(PP.fps_warning(self.info)
                                 or "No capture sidecar beside this video — the frame rate is the "
                                    "file's own claim. Check it before trusting the time axis.")
        self.on_clear()
        self._show_frame(0)
        self.log.emit("[PostProc] loaded %s (%d frames, %.2f fps declared)"
                      % (self.info["name"], self.info["frames"], self.info["fps"]))

    def _show_frame(self, idx):
        g = PP.read_frame(self.path, idx)
        if g is None:
            return
        self.view.set_frame(g)
        # Found once per displayed frame, not once per click: the sweep is the expensive part and
        # the frame does not change between clicks.
        self._markers = PP.find_markers(g)
        self._markers_frame = idx
        self.view.set_markers(self._markers)
        self._refresh_boxes()

    def on_ref_frame(self, v):
        self.frameLbl.setText(str(v))
        if self.path:
            self._show_frame(v)

    def on_click(self, x, y):
        """Place a box — on the nearest marker's CENTRE when there is one near the click.

        The centre is what sets L0, and hitting it by eye is guesswork. A click near a dot
        therefore means that dot's computed centroid. On a speckle pattern there are no discrete
        markers, nothing is close enough, and the click stands exactly where it was made.
        """
        if getattr(self, "_markers_frame", None) != self.frameSlider.value():
            # The view is showing the last analysed frame after a run, or the markers are stale.
            # Boxes are always placed on the REFERENCE frame, so put that back before placing —
            # otherwise the click would be measured against a picture it does not belong to.
            self._show_frame(self.frameSlider.value())
            self.log.emit("[PostProc] back to the reference frame (%d) to place a box"
                          % self.frameSlider.value())
        snapped = PP.snap_to_marker(getattr(self, "_markers", []), x, y)
        if snapped:
            cx, cy, moved, m = snapped
            self.boxes[self._next_box] = (cx, cy)
            self.log.emit("[PostProc] box %s snapped to a marker centre — moved %.1f px "
                          "(r %.0f px, circularity %.2f)"
                          % ("AB"[self._next_box], moved, m[2], m[3]))
            self._suggest_box_size(m[2])
        else:
            self.boxes[self._next_box] = (x, y)
            if getattr(self, "_markers", None):
                self.log.emit("[PostProc] box %s placed as clicked — no marker within snapping "
                              "range" % "AB"[self._next_box])
        self._next_box = 1 - self._next_box
        self._refresh_boxes()

    def on_box_moved(self, i, x, y):
        """A drag or an arrow-key nudge — free placement, deliberately without snapping."""
        self.boxes[i] = (x, y)
        self._refresh_l0()

    def on_clear(self):
        self.boxes = [None, None]
        self._next_box = 0
        self._refresh_boxes()

    def on_auto(self):
        """Find the two markers with the shared finder, so it agrees with click-to-snap."""
        if not self.path:
            return
        g = PP.read_frame(self.path, self.frameSlider.value())
        markers = PP.find_markers(g)
        self._markers = markers
        # Drop specks: a marker pair is made of the BIG round things. Without this a 13 px
        # artefact at the frame edge competes with a 60 px sprayed dot on circularity alone.
        if markers:
            rmax = max(m[2] for m in markers)
            markers = [m for m in markers if m[2] >= 0.35 * rmax]
        if len(markers) < 2:
            QMessageBox.information(
                self, "No marker pair found",
                "Could not find two round markers in this frame.\n\n"
                "That is expected on a speckle pattern, which has no discrete dots — click the "
                "frame twice to place the boxes by hand instead. Clicks snap to a marker centre "
                "when there is one, and stay where you put them when there is not.")
            return
        pair = sorted(markers[:2], key=lambda m: m[1])
        self.boxes = [(pair[0][0], pair[0][1]), (pair[1][0], pair[1][1])]
        self._next_box = 0
        # Size the patch to the marker it is tracking. The 24 px default is a fraction of a 60 px
        # sprayed dot, which both correlates on less of the pattern than it could AND draws a box
        # far smaller than the dot, leaving nothing to judge centring by. 1.25x the radius keeps
        # the whole dot plus a little of its surround.
        self._suggest_box_size(max(pair[0][2], pair[1][2]))
        self._refresh_boxes()
        self.log.emit("[PostProc] auto-detected 2 markers — r %.0f/%.0f px, circularity %.2f/%.2f"
                      % (pair[0][2], pair[1][2], pair[0][3], pair[1][3]))

    def _suggest_box_size(self, marker_radius):
        """Size the patch to the marker. This is the single biggest lever on noise.

        A box smaller than the dot sees only its flat interior — no gradient, nothing to localise
        on, because the information is at the EDGE. Measured on S25 over a matched strain window:
        24 px half-size gives 313 microstrain of noise, 40 gives 150, and 1.25x the marker radius
        (75 px here) gives 22 — against 28 for the live rig. A 14x difference from one number
        nobody would think to change.
        """
        want = int(round(1.25 * marker_radius))
        want = max(self.boxHalf.minimum(), min(self.boxHalf.maximum(), want))
        if want > self.boxHalf.value():
            old = self.boxHalf.value()
            self.boxHalf.setValue(want)
            self.log.emit("[PostProc] box half-size %d -> %d px to cover a %.0f px marker. A box "
                          "smaller than the dot sees only flat interior and tracks it poorly."
                          % (old, want, marker_radius))

    def _refresh_boxes(self):
        self.view.set_boxes(self.boxes[0], self.boxes[1], self.boxHalf.value())
        self._refresh_l0()

    def _refresh_l0(self):
        a, b = self.boxes
        if a and b:
            l0 = float(np.hypot(b[0] - a[0], b[1] - a[1]))
            ppm = l0 / self.gauge.value() if self.gauge.value() > 0 else 0
            self.l0Lbl.setText("Px₀ = %.2f px    →    %.4f px/mm at %.2f mm"
                               % (l0, ppm, self.gauge.value()))
            self.runBtn.setEnabled(self.path is not None and not (self.worker and self.worker.isRunning()))
        else:
            self.l0Lbl.setText("place two boxes to set Px₀")
            self.runBtn.setEnabled(False)

    def _cfg(self):
        return PP.Settings(gauge_mm=self.gauge.value(), box_half=self.boxHalf.value(),
                           search=self.search.value(), min_corr=self.minCorr.value(),
                           ref_frame=self.frameSlider.value(), fps=self.fps.value(),
                           step=self.step.value())

    def on_run(self):
        a, b = self.boxes
        if not (a and b and self.path):
            return
        self._t, self._e, self._tr = [], [], []
        self.summary = None
        self._reset_plot()
        self.runBtn.setEnabled(False); self.stopBtn.setEnabled(True); self.expBtn.setEnabled(False)
        cfg = self._cfg()
        self.worker = Worker(self.path, PP.Box(a[0], a[1], cfg.box_half),
                             PP.Box(b[0], b[1], cfg.box_half), cfg,
                             preview=self.playChk.isChecked())
        self.worker.row.connect(self.on_row)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.frame.connect(self.on_frame)
        self.worker.progress.connect(lambda d, t: self.bar.setValue(int(100 * d / max(1, t))))
        self.worker.start()
        self.log.emit("[PostProc] analysing %s from frame %d at %.4f fps"
                      % (self.info["name"], cfg.ref_frame, cfg.fps))

    def on_stop(self):
        if self.worker:
            self.worker.stop()

    def on_frame(self, gray, a, b, half):
        """Paint one frame of the pull, then tell the worker it may send the next."""
        self.view.play(gray, a, b, half)
        if self.worker:
            self.worker.frame_shown()

    def on_row(self, r):
        if r.ok:
            self._t.append(r.t); self._e.append(r.cauchy); self._tr.append(r.true)
        self.status.setText(
            "frame %d   t %.2f s   L %s px   ε %s   corr %.2f%s"
            % (r.idx, r.t,
               "—" if r.l_px != r.l_px else "%.2f" % r.l_px,
               "—" if r.cauchy != r.cauchy else "%.4f %%" % (r.cauchy * 100),
               r.corr, ("   " + r.note) if r.note else ""))
        self._redraw_plot(force=False)

    def _redraw_plot(self, force=True):
        """Update the two lines in place. force=False obeys a time throttle, for live updates."""
        if getattr(self, "_line_c", None) is None:
            return
        if not force:
            now = time.monotonic()
            if now - getattr(self, "_last_plot", 0.0) < 1.0 / self.PLOT_HZ:
                return
            self._last_plot = now
        self._line_c.set_data(self._t, [v * 100 for v in self._e])
        self._line_t.set_data(self._t, [v * 100 for v in self._tr])
        self._line_t.set_visible(self._want_true())
        if self._t:
            self.ax.relim()
            self.ax.autoscale_view()
        self.canvas.draw_idle()

    def on_done(self, summary):
        self.summary = summary
        self._redraw_plot()
        # Stop on the LAST frame, with the boxes where they finished. The preview is throttled,
        # so the last frame PAINTED is not necessarily the last frame ANALYSED — read that final
        # frame explicitly rather than leaving whichever one the throttle happened to allow.
        # The FRAME is the last one analysed — on a fracture run that is the broken specimen, and
        # it is the picture worth ending on. The BOXES are from the last frame that actually
        # tracked, because after a fracture there is no honest position to draw.
        if summary.rows and self.path:
            end = summary.rows[-1]
            pos = next((r for r in reversed(summary.rows) if r.ok), end)
            g = PP.read_frame(self.path, end.idx)
            if g is not None:
                self.view.play(g, pos.a, pos.b, self.boxHalf.value())
                self._markers = []      # these are tracked positions, not detections to snap to
                self._markers_frame = None
                self.view.set_markers([])
                if pos is not end:
                    self.log.emit("[PostProc] showing the final frame (%d); the boxes are from "
                                  "frame %d, the last one that tracked."
                                  % (end.idx, pos.idx))
        self.runBtn.setEnabled(True); self.stopBtn.setEnabled(False)
        self.expBtn.setEnabled(bool(summary and summary.rows))
        peak = max((v for v in self._e), default=0.0) * 100
        msg = ("Done — %d frames, %d tracked (%.1f %%), %d re-seed(s). Px₀ %.2f px, peak strain "
               "%.3f %%." % (summary.n, summary.tracked, summary.coverage, summary.reseeds,
                             summary.l0_px, peak))
        self.status.setText(msg)
        self.log.emit("[PostProc] " + msg)
        if summary.coverage < 90:
            self.log.emit("[PostProc] coverage below 90 % — try a larger box, a wider search "
                          "window, or a lower minimum correlation.")

    def on_failed(self, err):
        self.runBtn.setEnabled(True); self.stopBtn.setEnabled(False)
        self.status.setText("failed: " + err)
        self.log.emit("[PostProc] FAILED: " + err)
        QMessageBox.warning(self, "Analysis failed", err)

    def on_export(self):
        if not self.summary:
            return
        base = os.path.splitext(os.path.basename(self.path))[0] + "_dic_postproc.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save the analysis", base, "CSV (*.csv)")
        if not path:
            return
        try:
            PP.to_csv(self.summary, path, source_video=self.path, cfg=self._cfg())
            self.log.emit("[PostProc] wrote " + path)
        except Exception as e:
            QMessageBox.warning(self, "Could not write the CSV", str(e))
