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
import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QCheckBox,
                             QGroupBox, QPushButton, QDialogButtonBox, QFileDialog, QLineEdit,
                             QComboBox)

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
        # Still FORMAT lives here rather than in a settings menu, because it changes what the run
        # writes and belongs beside the size estimate it moves. All choices are LOSSLESS - this
        # picks bytes and CPU, never quality.
        # _sink_box runs TWICE — stills then video — so the video pass must not wipe the combo
        # and the labels the stills pass created.
        self.fmt_combo = getattr(self, "fmt_combo", None)
        self.codec_combo = getattr(self, "codec_combo", None)
        self.rate_lbls = getattr(self, "rate_lbls", {})
        self.avi_rate_lbls = getattr(self, "avi_rate_lbls", {})
        row0 = 2
        if png:
            from utm_capture import STILL_FORMATS
            g.addWidget(QLabel("File format"), 2, 0)
            self.fmt_combo = QComboBox()
            for k, spec in STILL_FORMATS.items():
                self.fmt_combo.addItem(spec["label"], k)
            cur = getattr(self.cap, "still_format", "tiff")
            i0 = self.fmt_combo.findData(cur)
            self.fmt_combo.setCurrentIndex(i0 if i0 >= 0 else 0)
            self.fmt_combo.setToolTip(
                "All three keep every pixel. TIFF uncompressed costs a fifth of PNG's CPU for the "
                "same size on disk; TIFF LZW is the same pixels in about a third of the space.")
            self.fmt_combo.currentIndexChanged.connect(self._refresh)
            g.addWidget(self.fmt_combo, 2, 1)
            row0 = 3
        else:
            from utm_capture import VIDEO_CODECS
            g.addWidget(QLabel("Codec"), 2, 0)
            self.codec_combo = QComboBox()
            for k, spec in VIDEO_CODECS.items():
                self.codec_combo.addItem(spec["label"], k)
            cur = getattr(self.cap, "video_codec", "ffv1")
            i0 = self.codec_combo.findData(cur)
            self.codec_combo.setCurrentIndex(i0 if i0 >= 0 else 0)
            self.codec_combo.setToolTip(
                "FFV1 and Y800 are LOSSLESS — verified pixel-identical on this machine. MJPG is "
                "lossy: only about half the pixels survive it, so use it for review, never for "
                "re-analysis.")
            self.codec_combo.currentIndexChanged.connect(self._refresh)
            g.addWidget(self.codec_combo, 2, 1)
            row0 = 3
        for i, key in enumerate(KEYS):
            st = self.make_style(key)
            cb = QCheckBox(st.label.split(" (")[0].split(" —")[0])
            cb.setToolTip(st.note)
            cb.setChecked(key in active_keys)
            cb.toggled.connect(self._refresh)
            g.addWidget(cb, row0 + i, 0)
            rate = QLabel(f"~{st.gb_per_min(png=png):.2f} GB/min")
            rate.setStyleSheet("color:#888;")
            g.addWidget(rate, row0 + i, 1)
            (self.rate_lbls if png else self.avi_rate_lbls)[key] = rate
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

    def _still_factor(self):
        """Size of the chosen still format relative to PNG, so the estimate follows the dropdown.

        Without this the dialog would promise PNG's 1.9 GB/min while writing TIFF-LZW's 0.7, and a
        size warning that does not track the setting sitting next to it is worse than none at all.
        """
        from utm_capture import STILL_FORMATS, STILL_FORMAT
        key = self.fmt_combo.currentData() if self.fmt_combo is not None else STILL_FORMAT
        return STILL_FORMATS.get(key, STILL_FORMATS[STILL_FORMAT])["kb"] / STILL_FORMATS["png"]["kb"]

    def _codec_factor(self):
        """Chosen codec's size relative to MJPG, whose bytes the Style estimates were built on."""
        from utm_capture import VIDEO_CODECS, VIDEO_CODEC
        key = self.codec_combo.currentData() if self.codec_combo is not None else VIDEO_CODEC
        return VIDEO_CODECS.get(key, VIDEO_CODECS[VIDEO_CODEC])["kb"] / VIDEO_CODECS["mjpg"]["kb"]

    def _refresh(self):
        png_keys = self.selected(self.png_views)
        avi_keys = self.selected(self.avi_views)
        _f = self._still_factor()
        for _k, _lbl in getattr(self, "rate_lbls", {}).items():
            _lbl.setText(f"~{self.make_style(_k).gb_per_min(png=True) * _f:.2f} GB/min")
        png_gb = sum(self.make_style(k).gb_per_min(png=True) * _f for k in png_keys) \
            if self.png_on.isChecked() else 0.0
        _v = self._codec_factor()
        for _k, _lbl in getattr(self, "avi_rate_lbls", {}).items():
            _lbl.setText(f"~{self.make_style(_k).gb_per_min() * _v:.2f} GB/min")
        avi_gb = sum(self.make_style(k).gb_per_min() * _v for k in avi_keys) \
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
        # Quoted for a FULL HOUR as well as a minute. The long-running protocols — creep,
        # relaxation, cyclic — run for an hour or more, and at these rates that is the number that
        # decides whether the run fits on the disk at all. A 3-minute fracture pull never was the
        # binding case.
        hour = total * 60.0
        free_gb = 0.0
        try:
            d = self.folder.text() or os.path.expanduser("~")
            drive = os.path.splitdrive(os.path.abspath(d))[0] + os.sep
            free_gb = shutil.disk_usage(drive).free / 1e9
        except Exception:
            pass
        over = free_gb and hour > free_gb
        self.total.setText(
            f"<b style='color:{col}; font-size:15px'>~{total:.2f} GB per minute</b>"
            + (f" &nbsp;&nbsp;<b style='color:{'#c0392b' if over else col}; font-size:15px'>"
               f"~{hour:,.0f} GB per hour</b>" if total else "")
            + f"<br><span style='color:#888'>{detail}"
            + (f" &nbsp;·&nbsp; 3-minute fracture pull ≈ <b>{total*3:.1f} GB</b>"
               f" &nbsp;·&nbsp; 15-minute run ≈ <b>{total*15:.0f} GB</b>" if total else "")
            + (f"<br><span style='color:{'#c0392b' if over else '#888'}'>"
               f"{'⚠ ' if over else ''}{free_gb:,.0f} GB free on this drive"
               f"{' — an hour at this setting would not fit' if over else ''}"
               f"{f' (about {free_gb/total/60:.1f} hours of recording)' if not over and total else ''}"
               "</span>" if free_gb else "")
            + "</span>")

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
        if self.fmt_combo is not None:
            cap.still_format = self.fmt_combo.currentData()
        if self.codec_combo is not None:
            cap.video_codec = self.codec_combo.currentData()
        cap.video_styles = [self.make_style(k) for k in self.selected(self.avi_views)]
        if self.folder.text():
            cap.root = self.folder.text()
        return self.png_on.isChecked(), self.avi_on.isChecked()
