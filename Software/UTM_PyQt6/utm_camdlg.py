"""Manual camera-parameter dialog for the DIC camera, with live trackability feedback.

    from utm_camdlg import CameraParamsDialog
    CameraParamsDialog(camera_manager, parent).exec()

The counterpart to auto-calibration: sometimes the operator knows what they want, or wants to
explore around what the sweep proposed. The point of doing it HERE rather than by editing the
preset is the live readout — every field change is immediately re-scored against the current frame
by utm_autocal, so you can see whether a value tracks before you commit to it.

That feedback is the whole reason this exists. Typing numbers blind is exactly how the preset's
exposure and threshold came to be wrong under the current lighting: they were right once, nothing
said when they stopped being right.

CANCEL RESTORES EVERYTHING. Exposure is pushed to the camera live so the feed reacts as you drag,
which means leaving the dialog by any route other than Apply has to put the sensor back.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton, QGroupBox,
                             QDialogButtonBox)
import cv2

import utm_autocal as AC


class CameraParamsDialog(QDialog):
    PREVIEW_MS = 300           # live re-score cadence; the camera runs at 35 fps, the eye does not

    def __init__(self, cm, parent=None):
        super().__init__(parent)
        self.cm = cm
        self.setWindowTitle("DIC camera parameters")
        self.setMinimumWidth(430)

        # Snapshot for Cancel. Exposure is live-applied, so this is not optional.
        self._orig = {
            "exposure": getattr(cm, "EXPOSURE_TIME", None),
            "threshold": cm.THRESHOLD, "thresh_type": cm.THRESHOLD_TYPE,
            "min_area": cm.MIN_AREA, "max_area": cm.MAX_AREA, "min_circ": cm.MIN_CIRCULARITY,
        }
        self._applied = False

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Values apply to this session only — the preset in camera_manager.py is untouched."))

        # ---- sensor -------------------------------------------------------------------------
        sensor = QGroupBox("Sensor")
        g = QGridLayout(sensor)
        self.exposure = QDoubleSpinBox()
        self.exposure.setRange(0.05, 500.0); self.exposure.setDecimals(2)
        self.exposure.setSuffix(" ms"); self.exposure.setSingleStep(1.0)
        self.exposure.setToolTip("Longer exposure = brighter frame, but motion blur and clipping.")
        exp = self._orig["exposure"]
        self.exposure.setValue((exp or 50000) / 1000.0)
        self.exposure.setEnabled(getattr(cm, "camera", None) is not None)
        g.addWidget(QLabel("Exposure"), 0, 0); g.addWidget(self.exposure, 0, 1)
        if not self.exposure.isEnabled():
            g.addWidget(QLabel("(camera not running)"), 0, 2)
        lay.addWidget(sensor)

        # ---- detection ----------------------------------------------------------------------
        det = QGroupBox("Marker detection")
        d = QGridLayout(det)
        self.otsu = QCheckBox("Threshold automatically (Otsu, per frame)")
        self.otsu.setToolTip("Recompute the cut level from each frame's own histogram. Follows the "
                             "lighting; ignores the fixed value below.")
        self.otsu.setChecked(bool(cm.THRESHOLD_TYPE & cv2.THRESH_OTSU))
        d.addWidget(self.otsu, 0, 0, 1, 2)

        self.threshold = QSpinBox(); self.threshold.setRange(0, 255)
        self.threshold.setValue(int(cm.THRESHOLD))
        self.threshold.setToolTip("Grey level separating marker from background.")
        d.addWidget(QLabel("Threshold"), 1, 0); d.addWidget(self.threshold, 1, 1)

        self.min_area = QSpinBox(); self.min_area.setRange(1, 2_000_000)
        self.min_area.setValue(int(cm.MIN_AREA)); self.min_area.setSuffix(" px²")
        self.max_area = QSpinBox(); self.max_area.setRange(1, 5_000_000)
        self.max_area.setValue(int(cm.MAX_AREA)); self.max_area.setSuffix(" px²")
        self.min_circ = QDoubleSpinBox(); self.min_circ.setRange(0.0, 1.0)
        self.min_circ.setSingleStep(0.05); self.min_circ.setDecimals(2)
        self.min_circ.setValue(float(cm.MIN_CIRCULARITY))
        self.min_circ.setToolTip("1.0 is a perfect circle. This is what rejects the grip bands.")
        d.addWidget(QLabel("Min blob area"), 2, 0); d.addWidget(self.min_area, 2, 1)
        d.addWidget(QLabel("Max blob area"), 3, 0); d.addWidget(self.max_area, 3, 1)
        d.addWidget(QLabel("Min circularity"), 4, 0); d.addWidget(self.min_circ, 4, 1)
        lay.addWidget(det)

        # ---- live feedback -------------------------------------------------------------------
        self.readout = QLabel("—")
        self.readout.setTextFormat(Qt.TextFormat.RichText)
        self.readout.setWordWrap(True)
        self.readout.setMinimumHeight(56)
        live = QGroupBox("Live check (current frame)")
        QVBoxLayout(live).addWidget(self.readout)
        lay.addWidget(live)

        row = QHBoxLayout()
        reset = QPushButton("Restore preset defaults")
        reset.setToolTip("Back to the values camera_manager.py ships for this specimen mode.")
        reset.clicked.connect(self._restore_preset)
        row.addWidget(reset); row.addStretch(1)
        lay.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.exposure.valueChanged.connect(self._exposure_changed)
        for wdg in (self.threshold, self.min_area, self.max_area, self.min_circ):
            wdg.valueChanged.connect(self._refresh)
        self.otsu.toggled.connect(self._refresh)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self.PREVIEW_MS)
        self._refresh()

    # -----------------------------------------------------------------------------------------
    def _thresh_type(self):
        base = self._orig["thresh_type"] & ~cv2.THRESH_OTSU
        return base | cv2.THRESH_OTSU if self.otsu.isChecked() else base

    def values(self):
        return {"exposure": self.exposure.value() * 1000.0,
                "threshold": float(self.threshold.value()),
                "thresh_type": self._thresh_type(),
                "min_area": int(self.min_area.value()),
                "max_area": int(self.max_area.value()),
                "min_circ": float(self.min_circ.value())}

    def _exposure_changed(self, ms):
        """Push exposure to the sensor as it changes, so the feed shows the effect immediately."""
        if getattr(self.cm, "camera", None) is not None:
            self.cm.set_exposure(ms * 1000.0)
        self._refresh()

    def _refresh(self):
        v = self.values()
        self.threshold.setEnabled(not self.otsu.isChecked())
        frame = getattr(self.cm, "latest_frame", None)
        if frame is None:
            self.readout.setText("<i>No frame — start the camera to see the live check.</i>")
            return
        m = AC.frame_score(frame, v["threshold"], v["thresh_type"],
                           min_area=v["min_area"], max_area=v["max_area"],
                           min_circ=v["min_circ"])
        n = m["n_blobs"]
        if n != 2:
            self.readout.setText(
                f"<b style='color:#c0392b'>{n} marker(s) found — need exactly 2.</b><br>"
                f"<span style='color:#666'>Mean grey {m['mean']:.0f} · "
                f"clipped {m['clipped_pct']:.1f} %"
                + (f" · cut at {m['threshold']:.0f}" if self.otsu.isChecked() else "")
                + "</span><br><span style='color:#666'>Nothing is measured until this reads 2.</span>")
            return
        col = "#2f9e44" if m["score"] > 0.7 else ("#d29922" if m["score"] > 0.4 else "#c0392b")
        verdict = ("good" if m["score"] > 0.7 else
                   "usable, but close to the edge" if m["score"] > 0.4 else "fragile")
        self.readout.setText(
            f"<b style='color:{col}'>2 markers · score {m['score']:.2f} — {verdict}</b><br>"
            f"<span style='color:#666'>contrast {m['contrast']:.2f} "
            f"(margin {m.get('margin', 0):.0f} grey levels) · "
            f"headroom {m['headroom']:.2f} (clipped {m['clipped_pct']:.1f} %) · "
            f"separation {m['sep_px']:.0f} px"
            + (f" · Otsu cut {m['threshold']:.0f}" if self.otsu.isChecked() else "")
            + "</span><br><span style='color:#666'>Contrast margin is the one that predicts "
              "whether tracking survives a flicker.</span>")

    def _restore_preset(self):
        p = self.cm.SPECIMEN_PRESETS.get(self.cm.specimen_mode)
        if not p:
            return
        self.exposure.setValue(p["exposure"] / 1000.0)
        self.otsu.setChecked(bool(p["threshold_type"] & cv2.THRESH_OTSU))
        self.threshold.setValue(int(p["threshold"]))
        self.min_area.setValue(int(p["min_area"]))
        self.max_area.setValue(int(p["max_area"]))
        self.min_circ.setValue(float(p["min_circularity"]))
        self._refresh()

    def _apply(self):
        v = self.values()
        if getattr(self.cm, "camera", None) is not None:
            self.cm.set_exposure(v["exposure"])
        self.cm.THRESHOLD = v["threshold"]
        self.cm.THRESHOLD_TYPE = v["thresh_type"]
        self.cm.MIN_AREA = v["min_area"]
        self.cm.MAX_AREA = v["max_area"]
        self.cm.MIN_CIRCULARITY = v["min_circ"]
        self._applied = True
        self.accept()

    def reject(self):
        """Cancel — put the sensor back, since exposure was applied live."""
        if not self._applied and self._orig["exposure"] is not None:
            if getattr(self.cm, "camera", None) is not None:
                self.cm.set_exposure(self._orig["exposure"])
        super().reject()

    def done(self, r):
        self._timer.stop()
        super().done(r)
