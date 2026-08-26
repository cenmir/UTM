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
    """The video frame, with the two tracking boxes drawn on it and placed by clicking."""
    clicked = pyqtSignal(float, float)          # in FRAME pixel coordinates

    def __init__(self):
        super().__init__()
        self.setMinimumSize(260, 320)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#101317; border:1px solid #2b3138;")
        self.setText("Load a video to begin")
        self._gray = None
        self._boxes = [None, None]
        self._half = 24
        self._scale = 1.0
        self._ox = self._oy = 0

    def set_frame(self, gray):
        self._gray = gray
        self._redraw()

    def set_boxes(self, a, b, half):
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
        cols = (QColor("#2ecc71"), QColor("#e8590c"))
        pts = []
        for i, bx in enumerate(self._boxes):
            if bx is None:
                continue
            cx, cy = bx[0] * self._scale, bx[1] * self._scale
            r = self._half * self._scale
            pts.append((cx, cy))
            p.setPen(QPen(cols[i], 2))
            p.drawRect(int(cx - r), int(cy - r), int(2 * r), int(2 * r))
            p.drawText(int(cx - r), int(cy - r) - 4, "AB"[i])
        if len(pts) == 2:
            p.setPen(QPen(QColor("#4dabf7"), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(pts[0][0]), int(pts[0][1]), int(pts[1][0]), int(pts[1][1]))
        p.end()
        self.setPixmap(pm)

    def mousePressEvent(self, e):
        if self._gray is None or self._scale <= 0:
            return
        x = (e.position().x() - self._ox) / self._scale
        y = (e.position().y() - self._oy) / self._scale
        h, w = self._gray.shape
        if 0 <= x < w and 0 <= y < h:
            self.clicked.emit(float(x), float(y))


class Worker(QThread):
    """Runs the analysis off the GUI thread and streams results back a frame at a time."""
    row = pyqtSignal(object)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, path, a, b, cfg):
        super().__init__()
        self.path, self.a, self.b, self.cfg = path, a, b, cfg
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            gen = PP.analyse(self.path, self.a, self.b, self.cfg,
                             progress=lambda d, t: self.progress.emit(d, t),
                             should_stop=lambda: self._stop)
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = None
        self.info = None
        self.boxes = [None, None]
        self._next_box = 0
        self.worker = None
        self.summary = None
        self._t, self._e = [], []
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

    def _reset_plot(self):
        self.ax.clear()
        self.ax.set_xlabel("time (s)")
        self.ax.set_ylabel("DIC strain (%)")
        self.ax.set_title("DIC strain vs time")
        self.ax.grid(alpha=0.3)
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
        self._refresh_boxes()

    def on_ref_frame(self, v):
        self.frameLbl.setText(str(v))
        if self.path:
            self._show_frame(v)

    def on_click(self, x, y):
        self.boxes[self._next_box] = (x, y)
        self._next_box = 1 - self._next_box
        self._refresh_boxes()

    def on_clear(self):
        self.boxes = [None, None]
        self._next_box = 0
        self._refresh_boxes()

    def on_auto(self):
        """Find two markers the way the rig does — both polarities, so it works on either specimen."""
        if not self.path:
            return
        import cv2
        g = PP.read_frame(self.path, self.frameSlider.value())
        best = None
        for mode, name in ((cv2.THRESH_BINARY_INV, "dark dots on a light specimen"),
                           (cv2.THRESH_BINARY, "bright dots on a dark specimen")):
            for thr in (110, 130, 150, 170, 190):
                _, b = cv2.threshold(g, thr, 255, mode)
                cs, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                pts = []
                for c in cs:
                    a = cv2.contourArea(c)
                    per = cv2.arcLength(c, True)
                    circ = 4 * np.pi * a / per ** 2 if per > 0 else 0
                    M = cv2.moments(c)
                    if 500 < a < 200000 and circ > 0.45 and M["m00"] > 0:
                        pts.append((M["m10"] / M["m00"], M["m01"] / M["m00"], circ))
                if len(pts) == 2:
                    score = min(p[2] for p in pts)
                    if best is None or score > best[0]:
                        best = (score, pts, thr, name)
        if not best:
            QMessageBox.information(
                self, "No marker pair found",
                "Could not find exactly two round markers in this frame.\n\n"
                "That is expected on a speckle pattern, which has no discrete dots — click the "
                "frame twice to place the boxes by hand instead.")
            return
        _, pts, thr, name = best
        pts = sorted(pts, key=lambda p: p[1])
        self.boxes = [(pts[0][0], pts[0][1]), (pts[1][0], pts[1][1])]
        self._next_box = 0
        self._refresh_boxes()
        self.log.emit("[PostProc] auto-detected 2 markers (%s, threshold %d)" % (name, thr))

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
                             PP.Box(b[0], b[1], cfg.box_half), cfg)
        self.worker.row.connect(self.on_row)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.progress.connect(lambda d, t: self.bar.setValue(int(100 * d / max(1, t))))
        self.worker.start()
        self.log.emit("[PostProc] analysing %s from frame %d at %.4f fps"
                      % (self.info["name"], cfg.ref_frame, cfg.fps))

    def on_stop(self):
        if self.worker:
            self.worker.stop()

    def on_row(self, r):
        if r.ok:
            self._t.append(r.t); self._e.append(r.cauchy); self._tr.append(r.true)
        self.status.setText(
            "frame %d   t %.2f s   L %s px   ε %s   corr %.2f%s"
            % (r.idx, r.t,
               "—" if r.l_px != r.l_px else "%.2f" % r.l_px,
               "—" if r.cauchy != r.cauchy else "%.4f %%" % (r.cauchy * 100),
               r.corr, ("   " + r.note) if r.note else ""))
        if len(self._t) % 10 == 0:
            self._redraw_plot()

    def _redraw_plot(self):
        self.ax.clear()
        self.ax.set_xlabel("time (s)"); self.ax.set_ylabel("DIC strain (%)")
        self.ax.set_title("DIC strain vs time")
        self.ax.grid(alpha=0.3)
        if self._t:
            self.ax.plot(self._t, [v * 100 for v in self._e], color="#e8590c", lw=1.5,
                         label="engineering (Cauchy)")
            if self.showTrue.isChecked():
                self.ax.plot(self._t, [v * 100 for v in self._tr], color="#1f6fb4", lw=1.2,
                             ls="--", label="true (log)")
            self.ax.legend(frameon=False, fontsize=9)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def on_done(self, summary):
        self.summary = summary
        self._redraw_plot()
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
