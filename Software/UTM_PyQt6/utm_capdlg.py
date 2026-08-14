"""Capture setup dialog — what to record, in what views, where, and what it will cost.

    from utm_capdlg import CaptureSetupDialog
    CaptureSetupDialog(capture_manager, make_style, parent).exec()

Replaces four scattered menu entries (two enable ticks and two view submenus) with one panel. The
menu version could not answer the question that actually matters — "how much disk is this going to
eat" — because the answer depends on which of six checkboxes are set across two different submenus,
and nothing added them up. Here the total is live, colour-coded, and stated per minute of test.

Stills and video are BOTH multi-select and shown side by side, because they are the same choice
made twice and separating them into different menus implied a distinction that does not exist. The
asymmetry that IS real — a second stills view costs ~1.9 GB/min against ~0.3 for video — is shown
as a number next to each tick rather than enforced by hiding the option.
"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QCheckBox,
                             QGroupBox, QPushButton, QDialogButtonBox, QFileDialog, QLineEdit)

KEYS = ("raw", "speckle", "boost")
WARN_GB_PER_MIN = 2.5      # amber past this
BAD_GB_PER_MIN = 4.5       # red past this


class CaptureSetupDialog(QDialog):
    def __init__(self, cap, make_style, parent=None, armed=(False, False)):
        """`cap` is the CaptureManager; `make_style(key)` builds a Style bound to the live preset."""
        super().__init__(parent)
        self.cap = cap
        self.make_style = make_style
        self.setWindowTitle("Capture setup")
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Recording starts automatically with a test when its box below is ticked, or at any "
            "time from the CAP / REC buttons on the camera feed."))

        cols = QHBoxLayout()
        self.png_on, self.png_views = self._sink_box(
            cols, "PNG stills", armed[0],
            [s.key for s in cap.png_styles], png=True,
            note="Lossless. The archival record — every other view can be derived from Raw offline.")
        self.avi_on, self.avi_views = self._sink_box(
            cols, "AVI video", armed[1],
            [s.key for s in cap.video_styles], png=False,
            note="MJPG, intra-frame, so extensometer software can seek it.")
        lay.addLayout(cols)

        # ---- where -----------------------------------------------------------------------------
        where = QGroupBox("Where to save")
        wl = QHBoxLayout(where)
        self.folder = QLineEdit(cap.root)
        self.folder.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        wl.addWidget(self.folder, 1); wl.addWidget(browse)
        lay.addWidget(where)
        self.warn_onedrive = QLabel("")
        self.warn_onedrive.setWordWrap(True)
        lay.addWidget(self.warn_onedrive)

        # ---- the number that was missing ------------------------------------------------------
        self.total = QLabel("")
        self.total.setTextFormat(Qt.TextFormat.RichText)
        self.total.setWordWrap(True)
        tot = QGroupBox("Disk cost")
        QVBoxLayout(tot).addWidget(self.total)
        lay.addWidget(tot)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._refresh()

    def _sink_box(self, parent_layout, title, on, active_keys, *, png, note):
        box = QGroupBox(title)
        g = QGridLayout(box)
        enable = QCheckBox(f"Auto-start {title.split()[0]} with each test")
        enable.setChecked(on)
        enable.toggled.connect(self._refresh)
        g.addWidget(enable, 0, 0, 1, 2)
        lbl = QLabel(note); lbl.setWordWrap(True); lbl.setStyleSheet("color:#888;")
        g.addWidget(lbl, 1, 0, 1, 2)
        views = {}
        for i, key in enumerate(KEYS):
            st = self.make_style(key)
            cb = QCheckBox(st.label.split(" (")[0].split(" —")[0])
            cb.setToolTip(st.note)
            cb.setChecked(key in active_keys)
            cb.toggled.connect(self._refresh)
            g.addWidget(cb, 2 + i, 0)
            rate = QLabel(f"~{st.gb_per_min(png=png):.2f} GB/min")
            rate.setStyleSheet("color:#888;")
            g.addWidget(rate, 2 + i, 1)
            views[key] = cb
        parent_layout.addWidget(box)
        return enable, views

    # -----------------------------------------------------------------------------------------
    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Capture folder", self.folder.text()
                                             or os.path.expanduser("~"))
        if d:
            self.folder.setText(d)
            self._refresh()

    def selected(self, views):
        keys = [k for k in KEYS if views[k].isChecked()]
        return keys or ["raw"]           # never leave a sink with nothing to write

    def _refresh(self):
        png_keys = self.selected(self.png_views)
        avi_keys = self.selected(self.avi_views)
        png_gb = sum(self.make_style(k).gb_per_min(png=True) for k in png_keys) \
            if self.png_on.isChecked() else 0.0
        avi_gb = sum(self.make_style(k).gb_per_min() for k in avi_keys) \
            if self.avi_on.isChecked() else 0.0
        total = png_gb + avi_gb
        col = "#2f9e44" if total < WARN_GB_PER_MIN else (
            "#d29922" if total < BAD_GB_PER_MIN else "#c0392b")
        parts = []
        if png_gb:
            parts.append(f"stills {png_gb:.2f}")
        if avi_gb:
            parts.append(f"video {avi_gb:.2f}")
        detail = "  +  ".join(parts) if parts else "nothing armed"
        self.total.setText(
            f"<b style='color:{col}; font-size:15px'>~{total:.2f} GB per minute of test</b>"
            f"<br><span style='color:#888'>{detail}"
            + (f" &nbsp;·&nbsp; a 2-minute fracture pull ≈ <b>{total*2:.1f} GB</b>"
               if total else "") + "</span>")

        d = self.folder.text()
        if d and "onedrive" in d.lower():
            self.warn_onedrive.setText(
                "<b style='color:#c0392b'>⚠ This folder is inside OneDrive.</b> "
                "<span style='color:#888'>OneDrive will try to sync every frame as it is written — "
                "that can slow the writes enough to drop frames during the pull, and will upload "
                "gigabytes. Pick a folder outside OneDrive.</span>")
        else:
            self.warn_onedrive.setText("")

    def apply_to(self, cap):
        """Write the choices back. Returns (png_armed, avi_armed)."""
        cap.png_styles = [self.make_style(k) for k in self.selected(self.png_views)]
        cap.video_styles = [self.make_style(k) for k in self.selected(self.avi_views)]
        if self.folder.text():
            cap.root = self.folder.text()
        return self.png_on.isChecked(), self.avi_on.isChecked()
