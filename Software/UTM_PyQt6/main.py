"""
UTM Control Application - PyQt6
Universal Testing Machine Control Software

Main application file that initializes the GUI and manages the application lifecycle.

============================================
APPLICATION VERSION - UPDATE ON EVERY COMMIT!
============================================
"""

__version__ = "0.5.4"


import sys
import time            # module-level: _live_blob_count/_on_dic_blobs need it at signal time
import math            # DIC overlay geometry (dashed line / marker travel)
import os              # capture folder paths
from utm_autocal import MIN_MARGIN as _AC_MIN_MARGIN   # "fragile" line for the DIC health badge
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressDialog, QVBoxLayout, QFileDialog
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6 import uic
from serial_manager import SerialManager
from widgets import FluentSwitch, SpeedGauge, RangeSlider
from datetime import datetime, timedelta

# Matplotlib imports for embedding plots
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.dates as mdates
# Camera and DIC imports
from camera_manager import CameraManager
import numpy as np
import cv2
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QGroupBox, QHBoxLayout, QVBoxLayout,
                              QPushButton, QLabel, QSizePolicy,
                              QScrollArea, QWidget)

# Path to the UI file
UI_FILE = Path(__file__).parent / "ui" / "utm_mainwindow.ui"


class UTMApplication(QMainWindow):
    """Main application window for UTM control"""

    def __init__(self):
        super().__init__()

        # Load the UI file
        uic.loadUi(UI_FILE, self)

        # Set window title with version
        self.setWindowTitle(f"UTM Control v{__version__}")

        # Apply custom styles
        self.apply_styles()

        # Connect signals to slots
        self.connect_signals()

        # Initialize application state
        self.init_state()

        # Appearance LAST: the plots, toolbars and DIC badges must all exist before the theme walks
        # them. Dark is the default; a previous choice is restored.
        self._build_view_menu()
        self._build_settings_menu()
        import theme as _theme
        self.apply_theme(self._recall("ui/theme", _theme.DEFAULT), announce=False)

        print("UTM Application initialized")

    def apply_styles(self):
        """Apply custom styles and replace widgets"""
        # Replace the connection checkbox with a custom FluentSwitch widget
        self.connectionSwitch = FluentSwitch()
        self.connectionSwitch.setFixedSize(44, 22)

        # The checkbox is in horizontalLayout_connection - access it directly
        layout = self.horizontalLayout_connection

        # Find the checkbox in the layout and replace it
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() == self.connectionCheckBox:
                layout.removeWidget(self.connectionCheckBox)
                self.connectionCheckBox.hide()
                self.connectionCheckBox.deleteLater()
                layout.insertWidget(i, self.connectionSwitch)
                break

        # Replace the motors checkbox with custom FluentSwitch
        self.motorsSwitch = FluentSwitch()
        self.motorsSwitch.setFixedSize(44, 22)

        layout = self.horizontalLayout_motorsEnable
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() == self.motorsCheckBox:
                layout.removeWidget(self.motorsCheckBox)
                self.motorsCheckBox.hide()
                self.motorsCheckBox.deleteLater()
                layout.insertWidget(i, self.motorsSwitch)
                break

        # Replace Data Stream checkboxes with FluentSwitch toggles
        # These control whether data is displayed to console (polling is automatic)
        self._replace_checkbox_with_switch_horizontal('loadCellCheckBox', 'loadCellSwitch', 'horizontalLayout_dataStreams')
        self._replace_checkbox_with_switch_horizontal('positionCheckBox', 'positionSwitch', 'horizontalLayout_dataStreams')
        self._replace_checkbox_with_switch_horizontal('velocityCheckBox', 'velocitySwitch', 'horizontalLayout_dataStreams')

        # Replace speed unit checkbox with radio buttons
        self._setup_speed_unit_controls()

        # Replace speed gauge placeholder with actual SpeedGauge widget
        self._setup_speed_gauge()

        # ...then put that gauge BESIDE the speed controls rather than above them
        self._compact_speed_control()

    def _replace_checkbox_with_switch_horizontal(self, checkbox_name, switch_name, layout_name):
        """Helper to replace a checkbox with FluentSwitch in a horizontal layout"""
        checkbox = getattr(self, checkbox_name, None)
        layout = getattr(self, layout_name, None)

        if checkbox and layout:
            switch = FluentSwitch()
            switch.setFixedSize(44, 22)
            setattr(self, switch_name, switch)

            # Find the checkbox in the layout and replace it
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == checkbox:
                    layout.removeWidget(checkbox)
                    checkbox.hide()
                    checkbox.deleteLater()
                    layout.insertWidget(i, switch)
                    break

    def _setup_speed_unit_controls(self):
        """Replace speed unit checkbox with radio buttons and reorganize speed controls"""
        from PyQt6.QtWidgets import QRadioButton, QLabel, QButtonGroup

        # Get the speed unit layout
        layout = self.horizontalLayout_speedUnit

        # Clear existing widgets
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Create "Speed unit:" label

        # Create radio buttons for mm/s and RPM
        self.speedUnitMmRadio = QRadioButton("mm/s")
        self.speedUnitRpmRadio = QRadioButton("RPM")

        # Create button group for mutual exclusivity
        self.speedUnitGroup = QButtonGroup(self)
        self.speedUnitGroup.addButton(self.speedUnitMmRadio)
        self.speedUnitGroup.addButton(self.speedUnitRpmRadio)

        # Default to mm/s
        self.speedUnitMmRadio.setChecked(True)

        layout.addWidget(self.speedUnitMmRadio)
        layout.addWidget(self.speedUnitRpmRadio)
        layout.addStretch()

        # Update the "Set RPM:" label to "Set speed:"
        self.label_3.setText("Set:")

        # Add unit label after spinbox
        self.speedUnitValueLabel = QLabel("mm/s")
        self.horizontalLayout_setSpeed.addWidget(self.speedUnitValueLabel)

    def _compact_speed_control(self):
        """Put the gauge beside the controls instead of above them.

        The .ui stacks four rows vertically — gauge, unit radios, live speed, set speed — which cost
        ~260 px of a control column that has to fit a laptop screen. The gauge is square and the
        three control rows are short and wide, so side by side they fit in the height of the gauge
        alone: ~140 px, a saving of ~120 px for free.

        Rebuilt here in code rather than in the .ui because Qt Designer output is regenerated from
        the tool and hand-edits to it get lost; every other layout change in this file is made the
        same way.
        """
        from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QSpacerItem
        gauge = getattr(self, "speedGauge", None)
        old = self.speedControlGroup.layout()
        if gauge is None or old is None:
            return

        # The .ui rows carry spacers that CENTRED them across the full group width, and the unit row
        # got an addStretch() on top. In a narrow left column those are pure waste — they pushed the
        # "Set speed" row's natural width to 382 px inside a 288 px group, which is what clipped the
        # gauge. Strip them; the rows are left-aligned in the new column anyway.
        for lay in (self.horizontalLayout_speedUnit, self.horizontalLayout_setSpeed):
            for i in range(lay.count() - 1, -1, -1):
                if isinstance(lay.itemAt(i), QSpacerItem) or lay.itemAt(i).spacerItem() is not None:
                    lay.takeAt(i)

        # Detach the three control rows from the old vertical layout, keeping their order.
        rows = [self.horizontalLayout_speedUnit,
                self.speedDisplayLabel,
                self.horizontalLayout_setSpeed]
        for r in rows:
            old.removeItem(r) if not isinstance(r, QWidget) else old.removeWidget(r)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0); left.setSpacing(6)
        left.addStretch(1)
        for r in rows:
            left.addWidget(r) if isinstance(r, QWidget) else left.addLayout(r)
        left.addStretch(1)

        outer = QHBoxLayout()
        outer.setContentsMargins(4, 2, 4, 4); outer.setSpacing(6)
        outer.addLayout(left, 1)
        outer.addWidget(gauge, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        QWidget().setLayout(old)              # re-parent the dead layout so Qt destroys it
        self.speedControlGroup.setLayout(outer)
        # Width budget for the group is ~288 px: left rows + gauge + margins must fit inside it.
        # Dropping the "mm/s" suffix after the spin box frees 48 px (the unit is already on the
        # radio right above it and in the live readout), which is spent on BOTH a wider entry box
        # and a bigger dial.
        unit_suffix = getattr(self, "speedUnitValueLabel", None)
        if unit_suffix is not None:
            unit_suffix.hide()
        self.setSpeedSpinBox.setFixedWidth(110)       # 68 was too narrow to read a 3-decimal speed

        # NOT a fixed size. SpeedGauge paints from side = min(width, height) and scales, so it stays
        # circular at whatever it is given — letting it EXPAND means it takes all the width the left
        # column does not need, and grows further if the panel is ever dragged wider, instead of
        # being frozen at whatever looked right in one column width.
        from PyQt6.QtWidgets import QSizePolicy as _SP
        gauge.setMinimumSize(104, 104)
        gauge.setMaximumSize(16777215, 16777215)
        gauge.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Expanding)

    def _setup_speed_gauge(self):
        """Replace the speed gauge placeholder with actual SpeedGauge widget"""
        # The placeholder is now inside horizontalLayout_speedGaugeCenter (for centering)
        layout = self.horizontalLayout_speedGaugeCenter

        # Find and replace the placeholder
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() == self.speedGaugePlaceholder:
                # Create the speed gauge
                self.speedGauge = SpeedGauge()
                self.speedGauge.setFixedSize(104, 104)
                self.speedGauge.setMaxValue(self.MAX_RPM)
                self.speedGauge.setUnit("RPM")

                # Remove placeholder and insert gauge
                layout.removeWidget(self.speedGaugePlaceholder)
                self.speedGaugePlaceholder.hide()
                self.speedGaugePlaceholder.deleteLater()
                layout.insertWidget(i, self.speedGauge)
                break

    def _setup_load_plot(self):
        """Setup the matplotlib canvas for the load plot"""
        # Create the matplotlib figure and canvas
        self.load_figure = Figure(figsize=(8, 4), dpi=100)
        self.load_figure.set_facecolor('#f0f0f0')
        self.load_canvas = FigureCanvas(self.load_figure)

        # Create the axes
        self.load_ax = self.load_figure.add_subplot(111)
        self.load_ax.set_xlabel('Time')
        self.load_ax.set_ylabel('Force (N)')
        self.load_ax.set_title('Load vs Time')
        self.load_ax.grid(True, alpha=0.3)

        # Create the line object (empty initially)
        self.load_line, = self.load_ax.plot([], [], 'b-', linewidth=1)
        self.load_markers, = self.load_ax.plot([], [], 'b.', markersize=3)

        # Hover annotation for showing time/force values
        self.load_annotation = self.load_ax.annotate(
            '', xy=(0, 0), xytext=(15, 15), textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.4', fc='white', ec='gray', alpha=0.9),
            fontsize=8, visible=False
        )
        self.load_crosshair_h = self.load_ax.axhline(y=0, color='gray', linewidth=0.5, linestyle=':', visible=False)
        self.load_crosshair_v = self.load_ax.axvline(x=0, color='gray', linewidth=0.5, linestyle=':', visible=False)

        # Create crop selection markers (vertical lines and shaded region)
        self.crop_line_low = self.load_ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5, visible=False)
        self.crop_line_high = self.load_ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5, visible=False)
        self.crop_span = self.load_ax.axvspan(0, 1, alpha=0.2, color='yellow', visible=False)

        # Format x-axis for time
        self.load_ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.load_figure.autofmt_xdate()

        # Replace the placeholder with the canvas
        # The placeholder is inside loadPlotFrame which has a layout
        layout = self.loadPlotFrame.layout()
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            # Remove the placeholder
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self.loadPlotPlaceholder:
                    layout.removeWidget(self.loadPlotPlaceholder)
                    self.loadPlotPlaceholder.hide() 
                    self.loadPlotPlaceholder.deleteLater()
                    break
            # Add the toolbar and canvas
            self.load_toolbar = NavigationToolbar(self.load_canvas, self.loadPlotFrame)
            self.load_toolbar.setFixedHeight(24)
            self.load_toolbar.setIconSize(QSize(16, 16))
            self.load_toolbar.setStyleSheet("background-color: #f0f0f0;")
            layout.addWidget(self.load_toolbar)
            layout.addWidget(self.load_canvas)
        else:
            # Create a layout if none exists
            layout = QVBoxLayout(self.loadPlotFrame)
            layout.setContentsMargins(0, 0, 0, 0)
            self.loadPlotPlaceholder.hide()
            self.loadPlotPlaceholder.deleteLater()
            self.load_toolbar = NavigationToolbar(self.load_canvas, self.loadPlotFrame)
            self.load_toolbar.setFixedHeight(24)
            self.load_toolbar.setIconSize(QSize(16, 16))
            self.load_toolbar.setStyleSheet("background-color: #f0f0f0;")
            layout.addWidget(self.load_toolbar)
            layout.addWidget(self.load_canvas)

        self.load_figure.tight_layout()

        # Reparent load tab widgets into a proper layout (like stress/strain tab).
        # The existing load-plot content goes in a top widget; a vertical splitter
        # puts a DIC camera monitor below it so the feed can be watched from this tab too.
        from PyQt6.QtWidgets import QSplitter, QWidget
        tab = self.loadPlotTab

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(4, 0, 4, 4)
        top_layout.setSpacing(2)

        self.loadPlotFrame.setParent(top_widget)
        top_layout.addWidget(self.loadPlotFrame)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(4)
        for group in [self.loadDataGroup, self.loadPlotControlsGroup, self.calibrationGroup]:
            group.setParent(top_widget)
            group.setFixedHeight(190)
            controls_row.addWidget(group)
        self._add_cross_readout("load")      # stress + DIC strain, inside the Load Data box
        top_layout.addLayout(controls_row)

        self.dataCroppingGroup.setParent(top_widget)
        self.dataCroppingGroup.setFixedHeight(90)
        top_layout.addWidget(self.dataCroppingGroup)

        # DIC camera monitor (mirrors the live feed from the Stress/Strain tab)
        cam_monitor = self._build_load_plot_camera_monitor()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(cam_monitor)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 240])

        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(splitter)

        # Connect mouse motion for hover cursor
        self.load_canvas.mpl_connect('motion_notify_event', self._on_load_mouse_move)
        self.load_canvas.mpl_connect('axes_leave_event', self._on_load_mouse_leave)

    def _on_load_mouse_move(self, event):
        """Show time/force values on hover"""
        if event.inaxes != self.load_ax or event.xdata is None:
            return
        from matplotlib import dates as mdates_conv
        time_str = mdates_conv.num2date(event.xdata).strftime('%H:%M:%S')
        self.load_annotation.xy = (event.xdata, event.ydata)
        self.load_annotation.set_text(f't = {time_str}\nF = {event.ydata:.2f} N')
        self.load_annotation.set_visible(True)
        self.load_crosshair_h.set_ydata([event.ydata])
        self.load_crosshair_h.set_visible(True)
        self.load_crosshair_v.set_xdata([event.xdata])
        self.load_crosshair_v.set_visible(True)
        self.load_canvas.draw_idle()

    def _on_load_mouse_leave(self, event):
        """Hide annotation when mouse leaves the plot"""
        self.load_annotation.set_visible(False)
        self.load_crosshair_h.set_visible(False)
        self.load_crosshair_v.set_visible(False)
        self.load_canvas.draw_idle()

    def _setup_range_slider(self):
        """Setup the range slider for data cropping"""
        # Create the range slider widget
        self.cropRangeSlider = RangeSlider()
        self.cropRangeSlider.setRange(0, 100)

        # Replace the placeholder with the range slider
        parent = self.rangeSliderPlaceholder.parent()
        geometry = self.rangeSliderPlaceholder.geometry()

        self.rangeSliderPlaceholder.hide()
        self.rangeSliderPlaceholder.deleteLater()

        self.cropRangeSlider.setParent(parent)
        self.cropRangeSlider.setGeometry(geometry)
        self.cropRangeSlider.show()

        # Connect the range changed signal
        self.cropRangeSlider.rangeChanged.connect(self._on_crop_range_changed)

    def _setup_stress_strain_plot(self):
        """Setup the matplotlib canvas for the stress-strain plot"""
        # Create the matplotlib figure and canvas
        self.ss_figure = Figure(figsize=(8, 3), dpi=100)
        self.ss_figure.set_facecolor('#f0f0f0')
        self.ss_canvas = FigureCanvas(self.ss_figure)

        # Create the axes
        self.ss_ax = self.ss_figure.add_subplot(111)
        self.ss_ax.set_xlabel('Engineering strain, DIC (%)')
        self.ss_ax.set_ylabel('Stress (MPa)')
        self.ss_ax.set_title('Stress vs Strain')
        self.ss_ax.grid(True, alpha=0.3)

        # Create the line objects (empty initially)
        self.ss_line, = self.ss_ax.plot([], [], 'b-', linewidth=1, label='Motor')
        self.ss_markers, = self.ss_ax.plot([], [], 'b.', markersize=3)
        # Second line for DIC overlay (hidden by default)
        self.ss_dic_line, = self.ss_ax.plot([], [], 'r-', linewidth=1, label='DIC engineering')
        self.ss_dic_markers, = self.ss_ax.plot([], [], 'r.', markersize=3)
        self.ss_dic_line.set_visible(False)
        self.ss_dic_markers.set_visible(False)

        # Hover annotation for showing strain/stress values
        self.ss_annotation = self.ss_ax.annotate(
            '', xy=(0, 0), xytext=(15, 15), textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.4', fc='white', ec='gray', alpha=0.9),
            fontsize=8, visible=False
        )
        self.ss_crosshair_h = self.ss_ax.axhline(y=0, color='gray', linewidth=0.5, linestyle=':', visible=False)
        self.ss_crosshair_v = self.ss_ax.axvline(x=0, color='gray', linewidth=0.5, linestyle=':', visible=False)

        # Create crop selection markers (vertical lines and shaded region)
        self.ss_crop_line_low = self.ss_ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5, visible=False)
        self.ss_crop_line_high = self.ss_ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5, visible=False)
        self.ss_crop_span = self.ss_ax.axvspan(0, 1, alpha=0.2, color='yellow', visible=False)

        # Replace the placeholder with the canvas
        layout = self.stressStrainPlotFrame.layout()
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            # Remove the placeholder
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self.stressStrainPlotPlaceholder:
                    layout.removeWidget(self.stressStrainPlotPlaceholder)
                    self.stressStrainPlotPlaceholder.hide()
                    self.stressStrainPlotPlaceholder.deleteLater()
                    break
            # Add the toolbar and canvas
            self.ss_toolbar = NavigationToolbar(self.ss_canvas, self.stressStrainPlotFrame)
            self.ss_toolbar.setFixedHeight(24)
            self.ss_toolbar.setIconSize(QSize(16, 16))
            self.ss_toolbar.setStyleSheet("background-color: #f0f0f0;")
            layout.addWidget(self.ss_toolbar)
            layout.addWidget(self.ss_canvas)
        else:
            # Create a layout if none exists
            layout = QVBoxLayout(self.stressStrainPlotFrame)
            layout.setContentsMargins(0, 0, 0, 0)
            self.stressStrainPlotPlaceholder.hide()
            self.stressStrainPlotPlaceholder.deleteLater()
            self.ss_toolbar = NavigationToolbar(self.ss_canvas, self.stressStrainPlotFrame)
            self.ss_toolbar.setFixedHeight(24)
            self.ss_toolbar.setIconSize(QSize(16, 16))
            self.ss_toolbar.setStyleSheet("background-color: #f0f0f0;")
            layout.addWidget(self.ss_toolbar)
            layout.addWidget(self.ss_canvas)

        self.ss_figure.tight_layout()

        # Connect mouse motion for hover cursor
        self.ss_canvas.mpl_connect('motion_notify_event', self._on_ss_mouse_move)
        self.ss_canvas.mpl_connect('axes_leave_event', self._on_ss_mouse_leave)

    def _on_ss_mouse_move(self, event):
        """Show strain/stress values on hover"""
        if event.inaxes != self.ss_ax or event.xdata is None:
            return
        self.ss_annotation.xy = (event.xdata, event.ydata)
        # x is now in PERCENT (see STRAIN_TO_PCT) — show both so the readout is unambiguous.
        self.ss_annotation.set_text(
            f'ε = {event.xdata:.3f} %  ({event.xdata / 100.0:.5f})\nσ = {event.ydata:.3f} MPa')
        self.ss_annotation.set_visible(True)
        self.ss_crosshair_h.set_ydata([event.ydata])
        self.ss_crosshair_h.set_visible(True)
        self.ss_crosshair_v.set_xdata([event.xdata])
        self.ss_crosshair_v.set_visible(True)
        self.ss_canvas.draw_idle()

    def _on_ss_mouse_leave(self, event):
        """Hide annotation when mouse leaves the plot"""
        self.ss_annotation.set_visible(False)
        self.ss_crosshair_h.set_visible(False)
        self.ss_crosshair_v.set_visible(False)
        self.ss_canvas.draw_idle()

    def _setup_ss_range_slider(self):
        """Setup the range slider for stress-strain data cropping"""
        # Create the range slider widget
        self.ssCropRangeSlider = RangeSlider()
        self.ssCropRangeSlider.setRange(0, 100)

        # Replace the placeholder with the range slider
        parent = self.ssRangeSliderPlaceholder.parent()
        layout = parent.layout()

        if layout is not None:
            # Find and replace the placeholder in the layout
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self.ssRangeSliderPlaceholder:
                    layout.removeWidget(self.ssRangeSliderPlaceholder)
                    self.ssRangeSliderPlaceholder.hide()
                    self.ssRangeSliderPlaceholder.deleteLater()
                    layout.insertWidget(i, self.ssCropRangeSlider)
                    break
        else:
            # Fallback to geometry-based replacement
            geometry = self.ssRangeSliderPlaceholder.geometry()
            self.ssRangeSliderPlaceholder.hide()
            self.ssRangeSliderPlaceholder.deleteLater()
            self.ssCropRangeSlider.setParent(parent)
            self.ssCropRangeSlider.setGeometry(geometry)
            self.ssCropRangeSlider.show()

        # Connect the range changed signal
        self.ssCropRangeSlider.rangeChanged.connect(self._on_ss_crop_range_changed)

    def _setup_main_splitter(self):
        """Replace the HBoxLayout between tabs and right panel with a draggable QSplitter"""
        from PyQt6.QtWidgets import QSplitter
        parent_layout = self.scrollAreaWidgetContents.layout()
        # The horizontalLayout_main holds tabWidget and controlPanelFrame
        # Remove them from the layout, wrap in a splitter
        self.tabWidget.setParent(None)
        self.controlPanelFrame.setParent(None)

        # The right-hand control column stacks Connection · Data streams · Speed · Motor control ·
        # Crosshead · Incremental move, and MEASURES 1192 px of minimum height. A 15" laptop offers
        # about 650 px of viewport, so that single column was forcing the OUTER mainScrollArea to
        # scroll — and because the camera sits at the bottom of the LEFT column, the specimen ended
        # up below the fold. Giving the control column its own scroll area caps what it can demand
        # of the window: the left side (plot + camera) now always fits, and only the controls scroll.
        from PyQt6.QtWidgets import QScrollArea, QFrame
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel_scroll.setWidget(self.controlPanelFrame)
        panel_scroll.setMinimumWidth(self.controlPanelFrame.minimumWidth() + 20)  # + scrollbar
        self.controlPanelScroll = panel_scroll

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tabWidget)
        splitter.addWidget(panel_scroll)
        # Remove the max width constraint so the right panel is resizable
        self.controlPanelFrame.setMaximumWidth(16777215)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([800, 320])
        splitter.setChildrenCollapsible(False)

        parent_layout.insertWidget(0, splitter)

    def _update_load_plot(self):
        """Update the load plot (called by timer at 5 Hz)"""
        if not self.load_plot_needs_update:
            return
        # A matplotlib redraw costs ~22 ms on this figure and Qt charges it in FULL for a canvas
        # sitting on a hidden tab — where nobody can see the result. Only one of the two plot tabs
        # is ever on screen, so half the plotting the app used to do was invisible by construction.
        # The dirty flag deliberately stays SET, so the tab redraws the moment it is shown.
        if not self.load_canvas.isVisible():
            return

        self.load_plot_needs_update = False

        n_points = len(self.load_plot_times)
        if n_points == 0:
            return

        # Downsample for display if we have too many points
        if n_points > self.LOAD_PLOT_DOWNSAMPLE_THRESHOLD:
            # Calculate step size to get approximately DISPLAY_POINTS
            step = max(1, n_points // self.LOAD_PLOT_DISPLAY_POINTS)
            times = self.load_plot_times[::step]
            forces = self.load_plot_forces[::step]
            # Always include the last point for real-time feel
            if self.load_plot_times[-1] not in times:
                times = times + [self.load_plot_times[-1]]
                forces = forces + [self.load_plot_forces[-1]]
        else:
            times = list(self.load_plot_times)
            forces = list(self.load_plot_forces)

        # Update the line data
        self.load_line.set_data(times, forces)

        # Update markers if enabled (only show on downsampled data)
        if hasattr(self, 'loadShowMarkersCheckBox') and self.loadShowMarkersCheckBox.isChecked():
            self.load_markers.set_data(times, forces)
            self.load_markers.set_visible(True)
        else:
            self.load_markers.set_visible(False)

        # Auto-scale if enabled - use explicit axis limits for datetime x-axis
        if hasattr(self, 'loadAutoScaleCheckBox') and self.loadAutoScaleCheckBox.isChecked():
            # Set x-axis limits explicitly for datetime data (need at least 2 different times)
            if len(times) > 1:
                self.load_ax.set_xlim(times[0], times[-1])
            # Recalculate y-axis limits
            self.load_ax.relim()
            self.load_ax.autoscale_view(scalex=False, scaley=True)

        # Redraw the canvas
        self.load_canvas.draw_idle()

    # ---- stress-strain series construction -----------------------------------------------------
    # These four helpers exist so the live plot puts a curve on screen on the SAME basis as
    # utm_report / utm_analysis. They previously disagreed on four separate counts, which stacked
    # into a curve that looked like a different test:
    #
    #   1. DROPOUT ROWS. When the DIC loses a marker the strain column reads 0.0 for that sample.
    #      The live plot drew those, so the trace snapped back to zero strain and back out again —
    #      the horizontal streaks across the curve. `utm_analysis` has always gated on lpx > 100;
    #      the same gate is applied here. A sample with no strain reading is not a data point.
    #   2. THE ANCHOR. Force is tared at the preload, so the plotted stress was short by the whole
    #      tared-away load (300 N ≈ 3.8 MPa ≈ 8 % on S25/S26; it was 470 N ≈ 15 % on the V6
    #      quintet, which is where this was first noticed). Added back here.
    #   3. UNITS. The report plots strain in %, the GUI plotted a bare fraction — a factor of 100
    #      between two axes that are supposed to show the same quantity.
    #   4. A PAIRING BUG in the downsampler (see _ss_thin).
    #
    # What is NOT corrected: the live plot still shows the pre-test hold and the post-fracture tail,
    # which the report windows out. That is correct for a LIVE plot — it must show what is happening
    # now, not a retrospective analysis window — but it is why a finished test still looks busier
    # here than in the report.
    DIC_VALID_LPX = 100.0        # same gate as utm_analysis: below this the markers were not found
    STRAIN_TO_PCT = 100.0

    def _ss_source_array(self, key):
        """(strain array, is_dic) for a strain-source key."""
        if key in ("eng", "both_motor", "both_true"):
            return self.load_plot_dic_cauchy, True      # CSV col DIC_Cauchy = ΔL/L₀
        if key == "true":
            return self.load_plot_dic_true, True
        return self.stress_strain_strains, False

    def _ss_anchor_MPa(self):
        """Stress to add back so the axis is TRUE engineering stress, not tared stress.

        The report derives this from the post-fracture hold, which does not exist yet during a live
        test. `_tare_load_N` — the load that was tared away — is the same quantity measured a
        different way, and it is known the moment the tare happens. On the V6d specimen it lands
        within ~5 % of the post-fracture anchor (494 N vs 470 N), against 15 % if omitted entirely.
        Zero before any tare, which is correct: nothing has been tared away yet.
        """
        a = max(0.0, getattr(self, '_tare_load_N', 0.0))
        return a / self.cross_sectional_area if self.cross_sectional_area > 0 else 0.0

    def _ss_pairs(self, arr, is_dic, n):
        """(strain %, stress MPa) for every sample that HAS a strain reading."""
        off = self._ss_anchor_MPa()
        lpx = self.load_plot_dic_L_px
        xs, ys = [], []
        for i in range(min(n, len(arr), len(self.stress_strain_stresses))):
            if is_dic and (i >= len(lpx) or lpx[i] <= self.DIC_VALID_LPX):
                continue                                # marker lost — no strain for this sample
            xs.append(arr[i] * self.STRAIN_TO_PCT)
            ys.append(self.stress_strain_stresses[i] + off)
        return xs, ys

    def _ss_thin(self, xs, ys):
        """Downsample for display, keeping the newest point so the trace stays live.

        The old version appended `strains[-1]` (the last DOWNSAMPLED strain) next to `stresses[-1]`
        (the true last stress), pairing a stale x with a fresh y and drawing a spurious horizontal
        run-out at the end of the curve. x and y are only ever appended together here.
        """
        n = len(xs)
        if n <= self.LOAD_PLOT_DOWNSAMPLE_THRESHOLD:
            return xs, ys
        step = max(1, n // self.LOAD_PLOT_DISPLAY_POINTS)
        tx, ty = xs[::step], ys[::step]
        if (n - 1) % step:                              # last sample missed by the stride
            tx, ty = tx + [xs[-1]], ty + [ys[-1]]
        return tx, ty

    def _ss_xlabel(self, source):
        return {"motor": "Crosshead strain (%)",
                "true":  "True / log strain, DIC (%)"}.get(source, "Engineering strain, DIC (%)")

    def _update_stress_strain_plot(self):
        """Update the stress-strain plot (called by timer)"""
        if not self.stress_strain_plot_needs_update:
            return
        if not self.ss_canvas.isVisible():        # see _update_load_plot — flag stays set
            return

        self.stress_strain_plot_needs_update = False

        n_points = len(self.stress_strain_stresses)
        if n_points == 0:
            return

        # Determine strain source from combo box
        # Stable key from userData, NOT the display text — renaming a combo entry must never be able
        # to silently change which array gets plotted.
        source = (self.strainSourceCombo.currentData()
                  if hasattr(self, 'strainSourceCombo') else "motor") or "motor"

        arr, is_dic = self._ss_source_array(source)
        strains, stresses = self._ss_thin(*self._ss_pairs(arr, is_dic, n_points))

        # Update primary line
        self.ss_line.set_data(strains, stresses)
        self.ss_line.set_visible(True)
        self.ss_ax.set_xlabel(self._ss_xlabel(source))
        self.ss_ax.set_ylabel("Engineering stress (MPa)" if self._ss_anchor_MPa()
                              else "Stress, tared (MPa)")
        # Samples with no marker lock are dropped, so a DIC source with the camera off yields an
        # EMPTY curve while load data streams in. Say so on the plot: a blank panel with a live
        # load plot on the next tab reads as a crash, not as "there is no DIC strain to draw".
        if is_dic and not strains:
            self.ss_ax.set_title("Stress vs Strain — no DIC strain yet "
                                 "(camera off, or markers not locked)")
        else:
            self.ss_ax.set_title("Stress vs Strain")

        # "Both" modes — primary line is DIC engineering, secondary is Motor or DIC true/log
        if source in ("both_motor", "both_true"):
            self.ss_line.set_label("DIC engineering")
            sec_key = "true" if source == "both_true" else "motor"
            self.ss_dic_line.set_label("DIC true / log" if sec_key == "true" else "Motor")
            sec_arr, sec_is_dic = self._ss_source_array(sec_key)
            secondary_strains, secondary_stresses = self._ss_thin(
                *self._ss_pairs(sec_arr, sec_is_dic, n_points))
            self.ss_dic_line.set_data(secondary_strains, secondary_stresses)
            self.ss_dic_line.set_visible(True)
            show_markers = hasattr(self, 'ssShowMarkersCheckBox') and self.ssShowMarkersCheckBox.isChecked()
            self.ss_dic_markers.set_data(secondary_strains, secondary_stresses)
            self.ss_dic_markers.set_visible(show_markers)
            # Show legend only in Both mode
            self.ss_ax.legend(loc='upper left', fontsize=8)
        else:
            self.ss_dic_line.set_visible(False)
            self.ss_dic_markers.set_visible(False)
            legend = self.ss_ax.get_legend()
            if legend:
                legend.remove()

        # Update markers if enabled
        if hasattr(self, 'ssShowMarkersCheckBox') and self.ssShowMarkersCheckBox.isChecked():
            self.ss_markers.set_data(strains, stresses)
            self.ss_markers.set_visible(True)
        else:
            self.ss_markers.set_visible(False)

        # Auto-scale if enabled — only consider visible lines
        if hasattr(self, 'ssAutoScaleCheckBox') and self.ssAutoScaleCheckBox.isChecked():
            all_x = []
            all_y = []
            for line in [self.ss_line, self.ss_dic_line]:
                if line.get_visible() and len(line.get_xdata()) > 0:
                    all_x.extend(line.get_xdata())
                    all_y.extend(line.get_ydata())
            if all_x and all_y:
                x_min, x_max = min(all_x), max(all_x)
                y_min, y_max = min(all_y), max(all_y)
                x_margin = max((x_max - x_min) * 0.05, 1e-6)
                y_margin = max((y_max - y_min) * 0.05, 1e-6)
                self.ss_ax.set_xlim(x_min - x_margin, x_max + x_margin)
                self.ss_ax.set_ylim(y_min - y_margin, y_max + y_margin)

        # Redraw the canvas
        self.ss_canvas.draw_idle()

    def connect_signals(self):
        """Connect UI signals to their respective slot functions"""
        # Console controls
        self.sendButton.clicked.connect(self.on_send_command)
        self.clearConsoleButton.clicked.connect(self.on_clear_console)
        self.commandLineEdit.returnPressed.connect(self.on_send_command)

        # Stress/Strain tab controls
        self.clearStressStrainButton.clicked.connect(self.on_clear_load_plot)  # Shared clear (clears both)
        self.areaSpinBox.valueChanged.connect(self.on_specimen_dimensions_changed)
        self.gaugeLengthSpinBox.valueChanged.connect(self.on_specimen_dimensions_changed)
        self.ssCropDataButton.clicked.connect(self.on_crop_data)  # Shared crop
        # Note: ssCropRangeSlider.rangeChanged is connected in _setup_ss_range_slider()

        # Stress/Strain plot toggle sync with Load Plot toggle
        self.ssTogglePlotCheckBox.stateChanged.connect(self._sync_plot_toggles)
        self.loadTogglePlotCheckBox.stateChanged.connect(self._sync_plot_toggles)

        # Show Markers checkboxes - trigger plot redraw when toggled
        self.ssShowMarkersCheckBox.stateChanged.connect(self._update_stress_strain_plot)
        self.loadShowMarkersCheckBox.stateChanged.connect(self._update_load_plot)

        # Load Plot tab controls
        self.clearLoadPlotButton.clicked.connect(self.on_clear_load_plot)
        self.tareButton.clicked.connect(self.on_tare)
        self.calibrateButton.clicked.connect(self.on_calibrate)
        self.offsetSpinBox.valueChanged.connect(self.on_calibration_values_changed)
        self.scaleSpinBox.valueChanged.connect(self.on_calibration_values_changed)
        self.displayRateSpinBox.valueChanged.connect(self._on_display_rate_changed)
        self.cropDataButton.clicked.connect(self.on_crop_data)

        # Stress/Strain tab duplicates - connect to same handlers and sync values
        self.tareButton_2.clicked.connect(self.on_tare_stress_strain)
        self.displayRateSpinBox_2.valueChanged.connect(self._on_display_rate_2_changed)
        self.cropDataButton_2.clicked.connect(self.on_crop_data)

        # Right panel - Connection controls
        self.scanPortsButton.clicked.connect(self.on_scan_ports)
        self.connectionSwitch.clicked.connect(self.on_connection_toggle)

        # Right panel - Data stream toggles (control console display, not polling)
        # Polling is automatic - these control whether data is printed to console
        self.loadCellSwitch.clicked.connect(lambda: self.on_load_cell_toggle(self.loadCellSwitch.isChecked()))
        self.positionSwitch.clicked.connect(lambda: self.on_position_toggle(self.positionSwitch.isChecked()))
        self.velocitySwitch.clicked.connect(lambda: self.on_velocity_toggle(self.velocitySwitch.isChecked()))

        # Right panel - Speed unit radio buttons
        self.speedUnitMmRadio.toggled.connect(self.on_speed_unit_changed)
        self.speedUnitRpmRadio.toggled.connect(self.on_speed_unit_changed)
        # Use editingFinished instead of valueChanged to only update on Enter or focus lost
        self.setSpeedSpinBox.editingFinished.connect(self.on_speed_editing_finished)

        # Right panel - Motor controls
        self.upRadioButton.toggled.connect(self.on_direction_changed)
        self.stopRadioButton.toggled.connect(self.on_direction_changed)
        self.downRadioButton.toggled.connect(self.on_direction_changed)
        self.motorsSwitch.clicked.connect(lambda: self.on_motors_toggle(self.motorsSwitch.isChecked()))
        self.emergencyStopButton.clicked.connect(self.on_emergency_stop)

        # Right panel - Position and incremental move
        self.tareLocationButton.clicked.connect(self.on_tare_location)
        self._add_return_zero_button()
        self.moveUpButton.clicked.connect(self.on_move_up)
        self.moveDownButton.clicked.connect(self.on_move_down)

        # Right panel - Data export/import
        self.saveDataButton.clicked.connect(self.on_save_data)
        self.openDataButton.clicked.connect(self.on_open_data)

        # One-click per-specimen PDF report (uses the shared analysis library utm_analysis)
        #
        # The "save the CSV first" rule was only ever conveyed in two weak places: a tooltip that
        # said "last-saved test CSV" without saying to go and save it, and the unsaved-data dialog,
        # which by definition only appears AFTER the operator has already pressed the button. Both
        # are recoveries, not instructions. The tooltip now leads with the rule, and a "?" beside
        # the button spells the whole workflow out — matching modeHelpButton, which is how every
        # other explain-this affordance in this app already looks.
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QToolButton
        self.generateReportButton = QPushButton("Generate report")
        self.generateReportButton.setToolTip(
            "SAVE THE TEST DATA FIRST — the report is built from the saved CSV, not from\n"
            "what is on screen. If the run is unsaved you will be offered the save dialog.\n\n"
            "Builds a one-page PDF (+ the individual graphs) using the UI settings (specimen\n"
            "mode, preload, speed, area, gauge), asks where to put it — defaulting to the\n"
            "specimen folder beside the CSV — and opens the PDF.")
        self.generateReportButton.clicked.connect(self.on_generate_report)
        self.reportHelpButton = QToolButton()
        self.reportHelpButton.setText("?")
        self.reportHelpButton.setFixedSize(24, 24)
        self.reportHelpButton.setToolTip("How saving and reporting fit together")
        self.reportHelpButton.clicked.connect(self.on_report_help)
        if hasattr(self, "dataButtonsLayout"):
            row = QHBoxLayout()
            row.addWidget(self.generateReportButton, 1)
            row.addWidget(self.reportHelpButton, 0)
            # Its OWN row, not a third seat in dataButtonsLayout. That row is a QHBoxLayout holding
            # Open Data and Save Data inside a ~308 px panel; a third button already squeezed
            # "Generate report" (sizeHint 202 px) down to about 92, and adding the "?" took it to
            # 62 — the label was being truncated to fit. On its own line it gets the full width.
            parent = self.dataButtonsLayout.parentWidget()
            outer = parent.layout() if parent is not None else None
            idx = -1
            if outer is not None:
                idx = next((i for i in range(outer.count())
                            if outer.itemAt(i).layout() is self.dataButtonsLayout), -1)
            if idx >= 0:
                outer.insertLayout(idx + 1, row)          # directly under Open / Save Data
            else:
                self.dataButtonsLayout.addLayout(row)     # fallback: keep the old placement

    def on_report_help(self):
        """Spell out the save -> report order in plain language.

        Deliberately not a restatement of the tooltip: it names the ORDER, says why the order
        exists (the analysis reads the file, not the live buffer), and shows what a finished
        specimen folder looks like — which is the thing that makes the rule stick.
        """
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Save, then report")
        box.setText("Save the test data BEFORE you generate the report.")
        box.setInformativeText(
            "The report is built from the saved CSV file, not from what is on screen — so there "
            "has to be a file first.\n\n"
            "1.  Run the test.\n"
            "2.  Save data  →  choose the specimen folder. The CSV is written.\n"
            "3.  Generate report  →  it asks where to put it, already pointing at that same "
            "folder. Press Enter.\n\n"
            "You get 10 files: the one-page PDF summary and the four graphs, each as PDF and PNG. "
            "The PDF opens by itself.\n\n"
            "If you press Generate report before saving, it stops and offers to save first — it "
            "will not quietly report on your previous test.\n\n"
            "Shortcut: turn on “On save: generate the report” and step 3 happens automatically "
            "every time you save.")
        box.exec()

    def init_state(self):
        """Initialize application state variables"""
        from PyQt6.QtCore import QTimer

        # Serial communication
        self.serial_manager = SerialManager()
        self.connected = False
        self.firmware_version = "Unknown"

        # Connect serial manager signals
        self.serial_manager.connection_changed.connect(self.on_connection_state_changed)
        self.serial_manager.data_received.connect(self.on_serial_data_received)
        self.serial_manager.load_cell_data.connect(self.on_load_cell_data)
        self.serial_manager.position_data.connect(self.on_motor_position_data)
        self.serial_manager.velocity_data.connect(self.on_motor_velocity_data)
        self.serial_manager.firmware_version.connect(self.on_firmware_version)
        self.serial_manager.error_occurred.connect(self.on_serial_error)

        # Data storage
        self.current_load = 0.0
        self.max_load = 0.0  # Maximum load recorded during test
        self.cross_sectional_area = 80.0  # mm²
        self.gauge_length = 80.0  # mm

        # Load plot data - store ALL points for complete test visualization
        self.load_plot_times = []  # All timestamps
        self.load_plot_forces = []  # All force values (calibrated)
        self.load_plot_raw_forces = []  # Raw ADC values for export
        self.load_plot_positions = []  # Crosshead position (mm) for export
        self.load_plot_speeds = []  # Crosshead speed (mm/s) for export
        self.load_plot_dic_cauchy = []  # DIC Cauchy strain per load cell tick
        self.load_plot_dic_true = []  # DIC true strain per load cell tick
        self.load_plot_dic_timestamps = []  # datetime when DIC value was computed by camera
        self.load_plot_dic_L_px = []  # DIC current pixel distance between blobs (gauge axis)
        self.load_plot_dic_dx_px = []  # DIC perpendicular-axis pixel distance (diagnostic)
        self.load_plot_dic_blobs = []  # DIC health: blob count (markers found) per load sample
        self.load_plot_mcu_timestamps = []  # MCU millis() timestamp from firmware (true sample time)

        # Time anchor for MCU↔PC clock bridge (set on first load cell sample)
        self._time_anchor_pc = None      # datetime of first sample (PC clock)
        self._time_anchor_mcu_ms = None  # millis() of first sample (MCU clock)
        self.DIC_STALE_THRESHOLD_MS = 100  # Max age (ms) before DIC reading is considered stale
        self.load_plot_needs_update = False  # Flag to trigger plot redraw
        self.data_unsaved = False  # Flag to track if data needs saving

        # Downsampling for display performance (plot every Nth point when > threshold)
        self.LOAD_PLOT_DOWNSAMPLE_THRESHOLD = 1000  # Start downsampling after this many points
        self.LOAD_PLOT_DISPLAY_POINTS = 500  # Target points to display when downsampling

        # Stress-strain plot data (calculated from load plot data)
        self.stress_strain_strains = []  # Strain values (dimensionless)
        self.stress_strain_stresses = []  # Stress values (MPa)
        self.stress_strain_plot_needs_update = False  # Flag to trigger plot redraw

        # Max values tracking for stress-strain
        self.max_stress = 0.0  # MPa
        self.max_strain = 0.0  # dimensionless

        # Initialize the load plot and range slider
        self._setup_load_plot()
        self._setup_range_slider()

        # Initialize the stress-strain plot and range slider
        self._setup_stress_strain_plot()
        self._setup_ss_range_slider()

        # Setup camera display AFTER stress-strain plot is ready
        self._setup_camera_display()

        # Auto-preload controls (target-force jog) in the Motor Control group
        self._setup_preload_controls()
        self._setup_testmode_controls()
        self._setup_control_modes_segment()
        self._setup_recipe_controls()

        # Replace HBoxLayout between tabs and right panel with a draggable splitter
        self._setup_main_splitter()

        # Connect camera buttons (must be after _setup_camera_display creates them)
        self.startCameraButton.clicked.connect(self.on_start_camera)
        self.stopCameraButton.clicked.connect(self.on_stop_camera)
        self.tareDICButton.clicked.connect(self.on_calibrate_px0)
        self.tareDICAliasButton.clicked.connect(self.on_calibrate_px0)
        self.specimenModeCombo.currentTextChanged.connect(self.on_specimen_mode_changed)
        # Load Plot tab's duplicate controls drive the same handlers (state kept in sync)
        self.startCameraButtonLP.clicked.connect(self.on_start_camera)
        self.stopCameraButtonLP.clicked.connect(self.on_stop_camera)
        self.tareDICButtonLP.clicked.connect(self.on_calibrate_px0)
        self.tareDICAliasButtonLP.clicked.connect(self.on_calibrate_px0)
        self.specimenModeComboLP.currentTextChanged.connect(self.on_specimen_mode_changed)

        # Added camera state variables 

        # DIC Camera state
        self.camera_manager = CameraManager()
        from utm_capture import CaptureManager
        self.capture = CaptureManager(root=self.CAPTURE_ROOT,
                                      fps=getattr(CameraManager, "FRAME_RATE", 35))
        self._capture_runs = []          # [{dir, start, end}] — matched to a CSV by time overlap
        self._cam_err_last, self._cam_err_t, self._cam_err_n = None, 0.0, 0   # see on_camera_error
        self._last_feed_paint = 0.0                                          # feed throttle
        self.dic_recording_enabled = False
        self.latest_dic_strain = 0.0
        self.latest_dic_cauchy = 0.0
        self.latest_dic_true_strain = 0.0
        self.camera_active = False

        # Connect camera signals
        self.camera_manager.frame_ready.connect(self.update_camera_feed)
        self.camera_manager.dic_strain_updated.connect(self.update_dic_strain_label)
        self.camera_manager.error_occurred.connect(self.on_camera_error)
        # --- Live DIC health badge (Phase C) ---
        self.camera_manager.blobs_detected.connect(self._on_dic_blobs)
        self.camera_manager.error_occurred.connect(self._on_dic_error_count)
        self._dic_blob_count = 0
        self._dic_blob_t = 0.0                            # when _dic_blob_count last CHANGED hands
        self.DIC_BLOB_STALE_S = 1.0                       # older than this = the camera has stopped
        self._dic_blob_history = []                       # recent per-frame blob counts
        self._expected_markers = 2                        # 4 when a multi-marker preset is selected
        self._dic_health_timer = QTimer(self)
        self._dic_health_timer.timeout.connect(self._update_dic_health)
        self._dic_health_timer.start(500)
        self.camera_manager.connection_changed.connect(self.on_camera_connection_changed)

        # Calibration values (synced with UI spinboxes)
        self.force_scale = self.scaleSpinBox.value()
        self.force_offset = self.offsetSpinBox.value()

        # Calibration workflow state
        self.calibration_active = False
        self.calibration_step = 0  # 0=idle, 1=collecting force0, 2=collecting force1
        self.calibration_raw_buffer = []  # Buffer for raw force values during calibration
        self.calibration_timer = None  # Timer for data collection countdown
        self.calibration_weight_kg = 0.0  # Weight in kg for calibration
        self.calibration_force0 = 0.0  # Mean raw force with no weight
        self.calibration_force1 = 0.0  # Mean raw force with known weight
        self.calibration_progress = None  # Progress dialog

        # Motor position tracking (from encoder)
        # Note: This is motor/encoder-based displacement. DIC strain will be separate.
        self.motor_position_zero = 0.0  # Tare offset for motor position
        self.motor_position_raw = 0  # Raw encoder value
        self.motor_displacement_mm = 0.0  # Calculated displacement in mm
        self.motor_velocity_rpm = 0.0  # Current motor velocity
        self.motor_velocity_avg_rpm = 0.0  # Averaged motor velocity

        # Console display toggles (data is always polled, these control console output)
        self.display_position_to_console = False
        self.display_velocity_to_console = False

        # Stall detection (only for continuous movement, not incremental moves)
        self.stall_detection_enabled = True
        self.stall_velocity_threshold = 0.5  # RPM below this is considered stalled
        self.stall_count = 0  # Counter for consecutive stall readings
        self.stall_count_threshold = 3  # Number of consecutive readings before triggering stall
        self.incremental_move_active = False  # True during MoveSteps command
        self.incremental_move_grace_period = False  # True briefly after starting incremental move
        self.movement_start_grace_period = False  # True briefly after starting movement

        # Auto-preload: move in tension until the load reaches a target, then stop
        self.preload_active = False
        self.preload_target = 0.0
        self._release_active = False
        # Closed-loop test-mode (Phase B) — active policy from control_policies, or None when idle
        self.active_policy = None
        self._policy_last_speed = 0.0
        self._policy_last_speed_t = 0.0
        self._policy_start_t = 0.0
        self._policy_button = None
        self._policy_start_label = "Start mode"
        self._policy_dic_watch = (0.0, 0.0)
        self._autostop_detector = None       # live fracture detector for manual-pull auto-stop
        self._stall_hist = []                # (t, pos) samples for the stall guard
        self._preload_last_speed = 0.0   # last commanded approach speed (mm/s) for throttling
        self._preload_last_speed_t = 0.0
        self.preload_timeout_timer = QTimer()
        self.preload_timeout_timer.setSingleShot(True)
        self.preload_timeout_timer.setInterval(int(self.PRELOAD_TIMEOUT_S * 1000))
        self.preload_timeout_timer.timeout.connect(self._on_preload_timeout)

        # Polling timers for motor data
        # Timer for position polling (always when connected)
        self.motor_position_timer = QTimer()
        self.motor_position_timer.setInterval(100)  # 10 Hz polling
        self.motor_position_timer.timeout.connect(self._poll_motor_position)

        # Timer for velocity polling (when motors enabled)
        self.motor_velocity_timer = QTimer()
        self.motor_velocity_timer.setInterval(200)  # 5 Hz polling
        self.motor_velocity_timer.timeout.connect(self._poll_motor_velocity)

        # Timer for movement start grace period (1 second to allow motor acceleration)
        self.grace_period_timer = QTimer()
        self.grace_period_timer.setSingleShot(True)
        self.grace_period_timer.setInterval(1000)  # 1 second grace period
        self.grace_period_timer.timeout.connect(self._end_grace_period)

        # Timer for incremental move grace period (1 second to allow motor to start)
        self.incremental_grace_timer = QTimer()
        self.incremental_grace_timer.setSingleShot(True)
        self.incremental_grace_timer.setInterval(1000)  # 1 second grace period
        self.incremental_grace_timer.timeout.connect(self._end_incremental_grace_period)

        # Timer for plot updates (rate controlled by displayRateSpinBox)
        # Synced between Load Plot and Stress-Strain tabs
        self.load_plot_timer = QTimer()
        self._update_display_rate()  # Set initial interval from spinbox
        self.load_plot_timer.timeout.connect(self._update_load_plot)
        self.load_plot_timer.timeout.connect(self._update_stress_strain_plot)
        self.load_plot_timer.start()  # Always running, but only redraws when needed

        # A canvas on a hidden tab skips its redraws (see _update_load_plot), so the tab the
        # operator switches TO has to catch up at once rather than looking frozen until the next
        # load-cell sample. Both are called: only the visible one will actually do any work.
        self.tabWidget.currentChanged.connect(self._on_plot_tab_changed)

        # Split console into main + camera panels
        self._setup_console_split()

        # Console initialization
        self.append_to_console("UTM Control Application Started")

        # Auto-scan for COM ports on startup
        self.auto_scan_ports()

        self.append_to_console("Ready to connect to device")

        # Initialize speed control for mm/s mode (default)
        self._init_speed_controls()

        # Update UI with initial values
        self.update_load_display()

        # Set initial UI state (disconnected)
        self.update_controls_enabled_state()
    
    def auto_scan_ports(self):
        """Automatically scan for COM ports on startup and select if only one available"""
        self.append_to_console("Auto-scanning for COM ports...")
        ports = SerialManager.scan_ports()
        
        self.comPortComboBox.clear()
        
        if ports:
            self.comPortComboBox.addItems(ports)
            self.append_to_console(f"Found {len(ports)} COM port(s): {', '.join(ports)}")
            
            # Auto-select if only one port is available
            if len(ports) == 1:
                self.comPortComboBox.setCurrentIndex(0)
                self.append_to_console(f"→ Auto-selected {ports[0]}")
        else:
            self.append_to_console("No COM ports found. Click 'Scan for COM ports' to retry.")

    # ========== Console Functions ==========

    def _setup_console_split(self):
        """Split the console tab into main console (left) and camera console (right)"""
        from PyQt6.QtWidgets import QSplitter, QTextEdit

        # Create camera console widget
        self.cameraConsoleTextEdit = QTextEdit()
        self.cameraConsoleTextEdit.setReadOnly(True)
        self.cameraConsoleTextEdit.setFont(self.consoleTextEdit.font())
        self.cameraConsoleTextEdit.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #cccccc; }"
        )

        # Wrap both consoles in a labelled layout
        main_group = QGroupBox("System Console")
        main_layout = QVBoxLayout(main_group)
        main_layout.setContentsMargins(2, 2, 2, 2)

        cam_group = QGroupBox("Camera / DIC Console")
        cam_layout = QVBoxLayout(cam_group)
        cam_layout.setContentsMargins(2, 2, 2, 2)

        # Buttons at top, then text edit below
        main_btn_row = QHBoxLayout()
        clear_main_btn = QPushButton("Clear")
        clear_main_btn.setFixedWidth(60)
        clear_main_btn.clicked.connect(lambda: (self.consoleTextEdit.clear(), self.append_to_console("Console cleared")))
        self.pauseMainConsoleBtn = QPushButton("Pause")
        self.pauseMainConsoleBtn.setFixedWidth(60)
        self.pauseMainConsoleBtn.setCheckable(True)
        self.pauseMainConsoleBtn.toggled.connect(lambda checked: self.pauseMainConsoleBtn.setText("Resume" if checked else "Pause"))
        main_btn_row.addWidget(clear_main_btn)
        main_btn_row.addWidget(self.pauseMainConsoleBtn)
        main_btn_row.addStretch()
        main_layout.addLayout(main_btn_row)
        main_layout.addWidget(self.consoleTextEdit)

        cam_btn_row = QHBoxLayout()
        clear_cam_btn = QPushButton("Clear")
        clear_cam_btn.setFixedWidth(60)
        clear_cam_btn.clicked.connect(self.cameraConsoleTextEdit.clear)
        self.pauseCamConsoleBtn = QPushButton("Pause")
        self.pauseCamConsoleBtn.setFixedWidth(60)
        self.pauseCamConsoleBtn.setCheckable(True)
        self.pauseCamConsoleBtn.toggled.connect(lambda checked: self.pauseCamConsoleBtn.setText("Resume" if checked else "Pause"))
        cam_btn_row.addWidget(clear_cam_btn)
        cam_btn_row.addWidget(self.pauseCamConsoleBtn)
        cam_btn_row.addStretch()
        cam_layout.addLayout(cam_btn_row)
        cam_layout.addWidget(self.cameraConsoleTextEdit)

        # Create splitter and add both groups — 50/50 split
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(main_group)
        splitter.addWidget(cam_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Insert splitter into the console tab layout (position 0, before command row)
        console_layout = self.consoleTab.layout()
        # Remove the original consoleTextEdit from position 0 (it's now inside main_group)
        console_layout.insertWidget(0, splitter)
        # Ensure splitter doesn't push command/button rows off screen
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Set stretch: splitter gets all available space, other rows stay fixed
        console_layout.setStretchFactor(splitter, 1)
        for i in range(1, console_layout.count()):
            item = console_layout.itemAt(i)
            if item:
                console_layout.setStretch(i, 0)

    def append_to_console(self, message):
        """Append a message to the appropriate console with optional timestamp"""
        from datetime import datetime

        if self.timestampCheckBox.isChecked():
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            message = f"{timestamp} -> {message}"

        # Route camera/DIC messages to camera console
        is_camera_msg = any(tag in message for tag in ["[Camera", "[DIC]"])
        if is_camera_msg and hasattr(self, 'cameraConsoleTextEdit'):
            if hasattr(self, 'pauseCamConsoleBtn') and self.pauseCamConsoleBtn.isChecked():
                return
            self.cameraConsoleTextEdit.append(message)
            if self.autoScrollCheckBox.isChecked():
                scrollbar = self.cameraConsoleTextEdit.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        else:
            if hasattr(self, 'pauseMainConsoleBtn') and self.pauseMainConsoleBtn.isChecked():
                return
            self.consoleTextEdit.append(message)
            if self.autoScrollCheckBox.isChecked():
                scrollbar = self.consoleTextEdit.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())

    def set_status(self, message, is_warning=False):
        """Set the status bar message

        Args:
            message: The status message to display
            is_warning: If True, display in warning style (orange/red)
        """
        self.statusLineEdit.setText(message)
        if is_warning:
            self.statusLineEdit.setStyleSheet(
                "QLineEdit { background-color: #4a3000; color: #ffaa00; border: 1px solid #ff6600; padding-left: 8px; }"
            )
        else:
            self.statusLineEdit.setStyleSheet(
                "QLineEdit { background-color: #2b2b2b; color: #cccccc; border: 1px solid #555; padding-left: 8px; }"
            )

    def on_send_command(self):
        """Handle send button click or Enter key in command field"""
        command = self.commandLineEdit.text().strip()

        if not command:
            return

        # Display the command in console
        self.append_to_console(f">> {command}")

        # Send command to serial device
        if not self.connected:
            self.append_to_console("Error: Not connected to device")
        else:
            self.serial_manager.send_command(command)

        # Clear the command field
        self.commandLineEdit.clear()

    def on_clear_console(self):
        """Clear both console panels"""
        self.consoleTextEdit.clear()
        if hasattr(self, 'cameraConsoleTextEdit'):
            self.cameraConsoleTextEdit.clear()
        self.append_to_console("Console cleared")

    # ========== Stress/Strain Functions ==========

    def on_clear_stress_strain_plot(self):
        """Clear the stress-strain plot (display + data), leaving the load plot intact."""
        self.stress_strain_strains.clear()
        self.stress_strain_stresses.clear()
        self.max_stress = 0.0
        self.max_strain = 0.0
        if hasattr(self, 'maxStressValue'):
            self.maxStressValue.setText("0.0000")
        if hasattr(self, 'maxStrainValue'):
            self.maxStrainValue.setText("0.000000")
        if hasattr(self, 'ssCurrentPointsValue'):
            self.ssCurrentPointsValue.setText("0")
        if hasattr(self, 'ssCropRangeSlider'):
            self.ssCropRangeSlider.blockSignals(True)
            self.ssCropRangeSlider.setRange(0, 100)
            self.ssCropRangeSlider.blockSignals(False)
        for _m in ('ss_crop_line_low', 'ss_crop_line_high', 'ss_crop_span'):
            if hasattr(self, _m):
                getattr(self, _m).set_visible(False)
        self.ss_line.set_data([], [])
        self.ss_markers.set_data([], [])
        self.ss_ax.relim()
        self.ss_ax.autoscale_view()
        self.ss_canvas.draw_idle()
        self.append_to_console("Stress-Strain plot cleared")

    def on_specimen_dimensions_changed(self):
        """Handle changes to specimen dimensions"""
        self.cross_sectional_area = self.areaSpinBox.value()
        self.gauge_length = self.gaugeLengthSpinBox.value()
        self.append_to_console(
            f"Specimen dimensions updated: Area={self.cross_sectional_area} mm², "
            f"L₀={self.gauge_length} mm"
        )

    # ========== Load Plot Functions ==========

    def _update_plot_title(self):
        """Update plot title to show unsaved indicator"""
        base_title = "Load vs Time"
        if self.data_unsaved:
            self.load_ax.set_title(f"{base_title} *")
        else:
            self.load_ax.set_title(base_title)
        self.load_canvas.draw_idle()

    def on_clear_load_plot(self):
        """Clear the load plot data (also clears stress-strain data since they are synced)"""
        # Clear all load plot stored data
        self.load_plot_times.clear()
        self.load_plot_forces.clear()
        self.load_plot_raw_forces.clear()
        self.load_plot_positions.clear()
        self.load_plot_speeds.clear()

        # Clear DIC data
        self.load_plot_dic_cauchy.clear()
        self.load_plot_dic_true.clear()
        self.load_plot_dic_timestamps.clear()
        self.load_plot_dic_L_px.clear()
        self.load_plot_dic_dx_px.clear()
        self.load_plot_dic_blobs.clear()
        self.load_plot_mcu_timestamps.clear()

        # Reset time anchor for MCU↔PC clock bridge
        self._time_anchor_pc = None
        self._time_anchor_mcu_ms = None

        # Clear stress-strain data
        self.stress_strain_strains.clear()
        self.stress_strain_stresses.clear()

        # Reset max load
        self.max_load = 0.0
        self.maxLoadValue.setText("0.00")

        # Reset max stress/strain
        self.max_stress = 0.0
        self.max_strain = 0.0
        self.maxStressValue.setText("0.0000")
        self.maxStrainValue.setText("0.000000")

        # Reset current points count (both tabs)
        self.currentPointsValue.setText("0")
        self.ssCurrentPointsValue.setText("0")

        # Reset unsaved flag and update title
        self.data_unsaved = False
        self._update_plot_title()

        # Reset the load plot range slider to full range
        self.cropRangeSlider.blockSignals(True)
        self.cropRangeSlider.setRange(0, 100)
        self.cropRangeSlider.blockSignals(False)

        # Reset the stress-strain range slider to full range
        self.ssCropRangeSlider.blockSignals(True)
        self.ssCropRangeSlider.setRange(0, 100)
        self.ssCropRangeSlider.blockSignals(False)

        # Hide load plot crop markers
        self.crop_line_low.set_visible(False)
        self.crop_line_high.set_visible(False)
        self.crop_span.set_visible(False)

        # Hide stress-strain crop markers
        self.ss_crop_line_low.set_visible(False)
        self.ss_crop_line_high.set_visible(False)
        self.ss_crop_span.set_visible(False)

        # Clear the load plot display
        self.load_line.set_data([], [])
        self.load_markers.set_data([], [])
        self.load_ax.relim()
        self.load_ax.autoscale_view()
        self.load_canvas.draw_idle()

        # Clear the stress-strain plot display
        self.ss_line.set_data([], [])
        self.ss_markers.set_data([], [])
        self.ss_ax.relim()
        self.ss_ax.autoscale_view()
        self.ss_canvas.draw_idle()

        self.append_to_console("Plots cleared")

    def _on_plot_tab_changed(self, _index):
        """Repaint whichever plot just came into view.

        Deferred by one event-loop turn: on the tab-changed signal Qt has not finished showing the
        new page yet, so isVisible() is still False and the redraw would be skipped again.
        """
        QTimer.singleShot(0, self._update_load_plot)
        QTimer.singleShot(0, self._update_stress_strain_plot)

    def _update_display_rate(self):
        """Update the load plot timer interval from the current display rate"""
        rate_seconds = self.displayRateSpinBox.value()
        interval_ms = int(rate_seconds * 1000)
        self.load_plot_timer.setInterval(interval_ms)

    def _on_display_rate_changed(self):
        """Handle display rate change from Load Plot tab - sync to Stress/Strain tab"""
        value = self.displayRateSpinBox.value()
        self.displayRateSpinBox_2.blockSignals(True)
        self.displayRateSpinBox_2.setValue(value)
        self.displayRateSpinBox_2.blockSignals(False)
        self._update_display_rate()

    def _on_display_rate_2_changed(self):
        """Handle display rate change from Stress/Strain tab - sync to Load Plot tab"""
        value = self.displayRateSpinBox_2.value()
        self.displayRateSpinBox.blockSignals(True)
        self.displayRateSpinBox.setValue(value)
        self.displayRateSpinBox.blockSignals(False)
        self._update_display_rate()

    def _on_crop_range_changed(self, low, high):
        """Handle range slider value changes - update crop markers on plot"""
        n_points = len(self.load_plot_times)
        if n_points == 0:
            # No data - hide markers
            self.crop_line_low.set_visible(False)
            self.crop_line_high.set_visible(False)
            self.crop_span.set_visible(False)
            self.load_canvas.draw_idle()
            return

        # If at full range (0-100), hide markers
        if low == 0 and high == 100:
            self.crop_line_low.set_visible(False)
            self.crop_line_high.set_visible(False)
            self.crop_span.set_visible(False)
            self.load_canvas.draw_idle()
            return

        # Calculate indices from percentages
        low_idx = int((low / 100.0) * (n_points - 1))
        high_idx = int((high / 100.0) * (n_points - 1))

        # Get x positions (time values) for the markers
        low_time = mdates.date2num(self.load_plot_times[low_idx])
        high_time = mdates.date2num(self.load_plot_times[high_idx])

        # Update vertical line positions
        self.crop_line_low.set_xdata([low_time, low_time])
        self.crop_line_high.set_xdata([high_time, high_time])

        # Update the span (shaded region)
        # Need to remove old span and create new one since axvspan doesn't have set_xy
        self.crop_span.remove()
        self.crop_span = self.load_ax.axvspan(low_time, high_time, alpha=0.2, color='yellow', visible=True)

        # Show the markers
        self.crop_line_low.set_visible(True)
        self.crop_line_high.set_visible(True)

        self.load_canvas.draw_idle()

    def _on_strain_source_changed(self, index):
        """Handle strain source combo box change — force plot redraw"""
        self.stress_strain_plot_needs_update = True
        self._update_stress_strain_plot()

    def _on_ss_crop_range_changed(self, low, high):
        """Handle stress-strain range slider value changes - update crop markers on plot"""
        n_points = len(self.stress_strain_strains)
        if n_points == 0:
            # No data - hide markers
            self.ss_crop_line_low.set_visible(False)
            self.ss_crop_line_high.set_visible(False)
            self.ss_crop_span.set_visible(False)
            self.ss_canvas.draw_idle()
            return

        # If at full range (0-100), hide markers
        if low == 0 and high == 100:
            self.ss_crop_line_low.set_visible(False)
            self.ss_crop_line_high.set_visible(False)
            self.ss_crop_span.set_visible(False)
            self.ss_canvas.draw_idle()
            return

        # Calculate indices from percentages
        low_idx = int((low / 100.0) * (n_points - 1))
        high_idx = int((high / 100.0) * (n_points - 1))

        # Get x positions for the markers — from the strain source the plot is ACTUALLY drawing,
        # in the same % units. This used to read stress_strain_strains (crosshead) unconditionally
        # while the curve defaulted to DIC, so the crop markers stood at unrelated x positions.
        src = (self.strainSourceCombo.currentData()
               if hasattr(self, 'strainSourceCombo') else "motor") or "motor"
        arr, _ = self._ss_source_array(src)
        low_idx = min(low_idx, len(arr) - 1)
        high_idx = min(high_idx, len(arr) - 1)
        low_strain = arr[low_idx] * self.STRAIN_TO_PCT
        high_strain = arr[high_idx] * self.STRAIN_TO_PCT

        # Update vertical line positions
        self.ss_crop_line_low.set_xdata([low_strain, low_strain])
        self.ss_crop_line_high.set_xdata([high_strain, high_strain])

        # Update the span (shaded region)
        self.ss_crop_span.remove()
        self.ss_crop_span = self.ss_ax.axvspan(low_strain, high_strain, alpha=0.2, color='yellow', visible=True)

        # Show the markers
        self.ss_crop_line_low.set_visible(True)
        self.ss_crop_line_high.set_visible(True)

        self.ss_canvas.draw_idle()

        # Keep both range sliders in sync
        self.cropRangeSlider.blockSignals(True)
        self.cropRangeSlider.setLow(low)
        self.cropRangeSlider.setHigh(high)
        self.cropRangeSlider.blockSignals(False)
        # Update load plot crop markers
        self._on_crop_range_changed(low, high)

    def _sync_plot_toggles(self):
        """Keep both plot toggle checkboxes in sync"""
        sender = self.sender()
        if sender == self.loadTogglePlotCheckBox:
            self.ssTogglePlotCheckBox.blockSignals(True)
            self.ssTogglePlotCheckBox.setChecked(self.loadTogglePlotCheckBox.isChecked())
            self.ssTogglePlotCheckBox.blockSignals(False)
        elif sender == self.ssTogglePlotCheckBox:
            self.loadTogglePlotCheckBox.blockSignals(True)
            self.loadTogglePlotCheckBox.setChecked(self.ssTogglePlotCheckBox.isChecked())
            self.loadTogglePlotCheckBox.blockSignals(False)

    def on_crop_data(self):
        """Crop the data to the selected range (affects both plots since data is synced)"""
        n_points = len(self.load_plot_times)
        if n_points == 0:
            self.append_to_console("No data to crop")
            return

        # Use whichever range slider has been adjusted (both should be in sync)
        low = self.cropRangeSlider.low()
        high = self.cropRangeSlider.high()

        # If at full range, nothing to crop
        if low == 0 and high == 100:
            self.append_to_console("No cropping needed (full range selected)")
            return

        # Calculate indices
        low_idx = int((low / 100.0) * (n_points - 1))
        high_idx = int((high / 100.0) * (n_points - 1))

        # Crop the load plot data
        self.load_plot_times = self.load_plot_times[low_idx:high_idx + 1]
        self.load_plot_forces = self.load_plot_forces[low_idx:high_idx + 1]
        self.load_plot_raw_forces = self.load_plot_raw_forces[low_idx:high_idx + 1]
        self.load_plot_positions = self.load_plot_positions[low_idx:high_idx + 1]
        self.load_plot_speeds = self.load_plot_speeds[low_idx:high_idx + 1]
        self.load_plot_dic_cauchy = self.load_plot_dic_cauchy[low_idx:high_idx + 1]
        self.load_plot_dic_true = self.load_plot_dic_true[low_idx:high_idx + 1]
        self.load_plot_dic_timestamps = self.load_plot_dic_timestamps[low_idx:high_idx + 1]
        self.load_plot_dic_L_px = self.load_plot_dic_L_px[low_idx:high_idx + 1]
        self.load_plot_dic_dx_px = self.load_plot_dic_dx_px[low_idx:high_idx + 1]
        self.load_plot_dic_blobs = self.load_plot_dic_blobs[low_idx:high_idx + 1]
        self.load_plot_mcu_timestamps = self.load_plot_mcu_timestamps[low_idx:high_idx + 1]

        # Crop the stress-strain data
        self.stress_strain_strains = self.stress_strain_strains[low_idx:high_idx + 1]
        self.stress_strain_stresses = self.stress_strain_stresses[low_idx:high_idx + 1]

        # Recalculate max load from cropped data (by absolute value, preserving sign)
        if self.load_plot_forces:
            self.max_load = max(self.load_plot_forces, key=abs)
            self.maxLoadValue.setText(f"{self.max_load:.2f}")
        else:
            self.max_load = 0.0
            self.maxLoadValue.setText("0.00")

        # Recalculate max stress/strain from cropped data
        if self.stress_strain_stresses:
            self.max_stress = max(self.stress_strain_stresses, key=abs)
            self.maxStressValue.setText(f"{self.max_stress:.4f}")
        else:
            self.max_stress = 0.0
            self.maxStressValue.setText("0.0000")

        if self.stress_strain_strains:
            self.max_strain = max(self.stress_strain_strains, key=abs)
            self.maxStrainValue.setText(f"{self.max_strain:.6f}")
        else:
            self.max_strain = 0.0
            self.maxStrainValue.setText("0.000000")

        # Update current points count (both tabs)
        self.currentPointsValue.setText(str(len(self.load_plot_forces)))
        self.ssCurrentPointsValue.setText(str(len(self.stress_strain_stresses)))

        # Reset both range sliders to full range
        self.cropRangeSlider.blockSignals(True)
        self.cropRangeSlider.setRange(0, 100)
        self.cropRangeSlider.blockSignals(False)

        self.ssCropRangeSlider.blockSignals(True)
        self.ssCropRangeSlider.setRange(0, 100)
        self.ssCropRangeSlider.blockSignals(False)

        # Hide the load plot crop markers
        self.crop_line_low.set_visible(False)
        self.crop_line_high.set_visible(False)
        self.crop_span.set_visible(False)

        # Hide the stress-strain crop markers
        self.ss_crop_line_low.set_visible(False)
        self.ss_crop_line_high.set_visible(False)
        self.ss_crop_span.set_visible(False)

        # Force both plots to update
        self.load_plot_needs_update = True
        self.stress_strain_plot_needs_update = True
        self._update_load_plot()
        self._update_stress_strain_plot()

        self.append_to_console(f"Data cropped: {n_points} -> {len(self.load_plot_times)} points")

    def on_tare(self):
        """Zero the load cell (tare function) - adjusts offset based on recent readings"""
        # TODO: Implement with data storage - average last 50 force readings
        self.append_to_console("Tare: Adjusting force offset...")
        # For now, just use current load as offset adjustment
        # Remember HOW MUCH load was zeroed away — "Release load" drives to -this so the specimen
        # ends at TRUE zero absolute force (tared 0 N still holds the preload, e.g. 300 N).
        self._tare_load_N = self.current_load
        self.force_offset = self.force_offset + self.current_load
        self.offsetSpinBox.blockSignals(True)
        self.offsetSpinBox.setValue(self.force_offset)
        self.offsetSpinBox.blockSignals(False)
        self.append_to_console(f"Force offset adjusted to {self.force_offset:.4f}")

    def on_tare_stress_strain(self):
        """Zero both force and position so the stress-strain curve restarts from (0, 0)"""
        self.on_tare()
        self.on_tare_location()
        self.append_to_console("Stress/Strain tare complete — curve origin reset to (0, 0)")

    def on_calibration_values_changed(self):
        """Handle manual changes to offset/scale spinboxes"""
        self.force_offset = self.offsetSpinBox.value()
        self.force_scale = self.scaleSpinBox.value()

    def on_calibrate(self):
        """Start the two-point calibration workflow"""
        if not self.connected:
            QMessageBox.warning(self, "Not Connected",
                "Please connect to the UTM before calibrating.")
            return

        if not self.loadCellSwitch.isChecked():
            QMessageBox.warning(self, "Load Cell Off",
                "Please turn on the Load Cell data stream before calibrating.")
            return

        # Get the weight value
        weight = self.weightSpinBox.value()
        if weight <= 0:
            QMessageBox.warning(self, "Invalid Weight",
                "Please enter a valid calibration weight (in kg).")
            return

        self.calibration_weight_kg = weight

        # Step 1: Confirm and instruct user to remove weight
        reply = QMessageBox.information(self, "Calibration - Step 1",
            f"Calibration will use a {weight:.3f} kg weight.\n\n"
            "STEP 1: Remove any weight from the load cell.\n\n"
            "Press OK when ready to collect zero-load data (10 seconds).",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Cancel:
            self.append_to_console("Calibration cancelled")
            return

        # Start collecting force0 data
        self._start_calibration_data_collection(1)

    def _start_calibration_data_collection(self, step):
        """Start collecting calibration data for the specified step"""
        self.calibration_step = step
        self.calibration_active = True
        self.calibration_raw_buffer = []

        step_name = "zero-load" if step == 1 else "loaded"
        self.append_to_console(f"Collecting {step_name} data for 10 seconds...")

        # Create progress dialog
        self.calibration_progress = QProgressDialog(
            f"Collecting {step_name} data...", "Cancel", 0, 100, self)
        self.calibration_progress.setWindowTitle("Calibration")
        self.calibration_progress.setMinimumDuration(0)
        self.calibration_progress.setValue(0)
        self.calibration_progress.canceled.connect(self._cancel_calibration)
        self.calibration_progress.show()

        # Start timer for 10-second countdown (update every 100ms)
        self.calibration_elapsed = 0
        self.calibration_timer = QTimer()
        self.calibration_timer.setInterval(100)  # 100ms updates
        self.calibration_timer.timeout.connect(self._calibration_timer_tick)
        self.calibration_timer.start()

    def _calibration_timer_tick(self):
        """Timer tick during calibration data collection"""
        self.calibration_elapsed += 100
        progress = int((self.calibration_elapsed / 10000) * 100)  # 10 seconds = 10000ms

        if self.calibration_progress:
            self.calibration_progress.setValue(progress)

        if self.calibration_elapsed >= 10000:
            # 10 seconds elapsed - stop collection
            self.calibration_timer.stop()
            self._finish_calibration_step()

    def _finish_calibration_step(self):
        """Finish current calibration step and calculate mean"""
        if self.calibration_progress:
            self.calibration_progress.close()
            self.calibration_progress = None

        if not self.calibration_raw_buffer:
            QMessageBox.warning(self, "Calibration Error",
                "No data collected. Make sure Load Cell is streaming data.")
            self._cancel_calibration()
            return

        # Calculate mean of collected raw values
        mean_value = sum(self.calibration_raw_buffer) / len(self.calibration_raw_buffer)
        n_samples = len(self.calibration_raw_buffer)

        if self.calibration_step == 1:
            # Step 1 complete - store force0
            self.calibration_force0 = mean_value
            self.append_to_console(f"Zero-load mean: {mean_value:.2f} ({n_samples} samples)")

            # Prompt for step 2
            reply = QMessageBox.information(self, "Calibration - Step 2",
                f"Zero-load data collected: {mean_value:.2f}\n\n"
                f"STEP 2: Place the {self.calibration_weight_kg:.3f} kg weight on the load cell.\n\n"
                "Press OK when ready to collect loaded data (10 seconds).",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Cancel:
                self._cancel_calibration()
                return

            # Start collecting force1 data
            self._start_calibration_data_collection(2)

        elif self.calibration_step == 2:
            # Step 2 complete - store force1 and calculate calibration
            self.calibration_force1 = mean_value
            self.append_to_console(f"Loaded mean: {mean_value:.2f} ({n_samples} samples)")

            # Calculate calibration values
            self._calculate_calibration()

    def _calculate_calibration(self):
        """Calculate and apply calibration values from collected data"""
        force0 = self.calibration_force0
        force1 = self.calibration_force1
        weight_kg = self.calibration_weight_kg

        delta_force = force1 - force0

        if abs(delta_force) < 1:
            QMessageBox.warning(self, "Calibration Error",
                f"Delta force too small ({delta_force:.2f}).\n"
                "Check that the weight was properly placed on the load cell.")
            self._cancel_calibration()
            return

        # Calculate scale and offset
        # Formula: scale = (weight_kg * g) / deltaForce
        # offset = force0 * scale
        new_scale = (weight_kg * 9.82) / delta_force
        new_offset = force0 * new_scale

        self.append_to_console(f"Calibration complete:")
        self.append_to_console(f"  Force0 (no weight): {force0:.2f}")
        self.append_to_console(f"  Force1 (with weight): {force1:.2f}")
        self.append_to_console(f"  Delta: {delta_force:.2f}")
        self.append_to_console(f"  New Scale: {new_scale:.6f}")
        self.append_to_console(f"  New Offset: {new_offset:.4f}")

        # Update spinboxes (this will trigger on_calibration_values_changed)
        self.scaleSpinBox.setValue(new_scale)
        self.offsetSpinBox.setValue(new_offset)

        # Reset calibration state
        self.calibration_active = False
        self.calibration_step = 0

        self.set_status("Load cell calibrated successfully")
        QMessageBox.information(self, "Calibration Complete",
            f"Load cell calibration complete!\n\n"
            f"Scale: {new_scale:.6f}\n"
            f"Offset: {new_offset:.4f}")

    def _cancel_calibration(self):
        """Cancel the calibration process"""
        if self.calibration_timer:
            self.calibration_timer.stop()
            self.calibration_timer = None
        if self.calibration_progress:
            self.calibration_progress.close()
            self.calibration_progress = None
        self.calibration_active = False
        self.calibration_step = 0
        self.calibration_raw_buffer = []
        self.append_to_console("Calibration cancelled")

    def update_load_display(self):
        """Update the load value display"""
        self.currentLoadValue.setText(f"{self.current_load:.2f}")

    # ========== Connection Functions ==========

    def on_scan_ports(self):
        """Scan for available COM ports"""
        self.append_to_console("Scanning for COM ports...")
        ports = SerialManager.scan_ports()
        
        self.comPortComboBox.clear()
        
        if ports:
            self.comPortComboBox.addItems(ports)
            self.append_to_console(f"Found {len(ports)} COM port(s): {', '.join(ports)}")
        else:
            self.append_to_console("No COM ports found")

    def on_connection_toggle(self, checked):
        """Handle connection switch toggle"""
        if checked:
            port = self.comPortComboBox.currentText()
            if not port:
                self.append_to_console("Error: No COM port selected")
                # Reset switch without triggering signal
                self.connectionSwitch.blockSignals(True)
                self.connectionSwitch.setChecked(False)
                self.connectionSwitch.blockSignals(False)
                return

            # TODO: Get baud rate from UI (for now using default 9600)
            baud_rate = 9600

            self.append_to_console(f"Connecting to {port} at {baud_rate} baud...")
            self.set_status(f"Connecting to {port}...")

            # SAFETY: Block signals during connection to prevent accidental motor commands
            self.upRadioButton.blockSignals(True)
            self.downRadioButton.blockSignals(True)
            self.stopRadioButton.blockSignals(True)
            self.motorsSwitch.blockSignals(True)

            # Reset UI to safe state
            self.stopRadioButton.setChecked(True)
            self.motorsSwitch.setChecked(False)

            # Restore signals
            self.upRadioButton.blockSignals(False)
            self.downRadioButton.blockSignals(False)
            self.stopRadioButton.blockSignals(False)
            self.motorsSwitch.blockSignals(False)

            # Start connection attempt (non-blocking - result comes via signals)
            self.serial_manager.connect(port, baud_rate)
            # Note: Switch stays on during connection attempt
            # It will be reset by on_connection_state_changed if connection fails
        else:
            # Only disconnect if we're actually connected or port is open
            if self.connected or self.serial_manager.port_open:
                self.append_to_console("Disconnecting...")
                self.serial_manager.disconnect()

    def update_status_lamp(self, connected):
        """Update the status lamp color"""
        if connected:
            self.statusLamp.setStyleSheet(
                "QLabel { background-color: #00ff00; border-radius: 15px; border: 2px solid #00aa00; }"
            )
        else:
            self.statusLamp.setStyleSheet(
                "QLabel { background-color: black; border-radius: 15px; border: 2px solid #555; }"
            )

    def update_controls_enabled_state(self):
        """Update enabled/disabled state of all controls based on connection and motor state"""
        connected = self.connected
        motors_enabled = self.motorsSwitch.isChecked()

        # Data Streams group - toggles enabled when connected
        self.loadCellSwitch.setEnabled(connected)
        self.positionSwitch.setEnabled(connected)
        self.velocitySwitch.setEnabled(connected)

        # Speed Control group - enabled only when connected
        self.speedGauge.setEnabled(connected)
        self.setSpeedSpinBox.setEnabled(connected)
        self.speedUnitMmRadio.setEnabled(connected)
        self.speedUnitRpmRadio.setEnabled(connected)

        # Motor Control group - Motors toggle enabled when connected
        self.motorsSwitch.setEnabled(connected)

        # Direction controls - enabled when connected AND motors enabled
        direction_enabled = connected and motors_enabled
        self.upRadioButton.setEnabled(direction_enabled)
        self.stopRadioButton.setEnabled(direction_enabled)
        self.downRadioButton.setEnabled(direction_enabled)
        if getattr(self, 'preloadButton', None) is not None:
            self.preloadButton.setEnabled(direction_enabled)
            self.preloadTargetSpinBox.setEnabled(direction_enabled and not self.preload_active)
        for b in (getattr(self, 'releaseToPreloadButton', None), getattr(self, 'releaseButton', None)):
            if b is not None:
                # Mid-release, only the button that started it stays live (it is the cancel).
                b.setEnabled(direction_enabled and
                             (not getattr(self, '_release_active', False)
                              or b.text() == "Cancel release"))
        if getattr(self, 'strainRateButton', None) is not None:
            self.strainRateButton.setEnabled(direction_enabled)
        if getattr(self, 'modeStartButton', None) is not None:
            self._testmode_direction_ok = direction_enabled
            self._update_control_mode_enabled()

        # Emergency stop - always enabled when connected (safety!)
        self.emergencyStopButton.setEnabled(connected)

        # Position group - enabled only when connected
        self.displacementLabel.setEnabled(connected)
        self.tareLocationButton.setEnabled(connected)
        if getattr(self, 'returnZeroButton', None) is not None:
            self.returnZeroButton.setEnabled(connected)

        # Incremental Move group - enabled when connected AND motors enabled
        self.moveUpButton.setEnabled(direction_enabled)
        self.moveDownButton.setEnabled(direction_enabled)
        self.moveDistanceSpinBox.setEnabled(direction_enabled)

        # Save Data button - always enabled (can save data even when disconnected)

    # ========== Data Stream Functions ==========

    def on_load_cell_toggle(self, state):
        """Toggle load cell data streaming to firmware"""
        if state:
            self.append_to_console("Load cell data ON")
            if self.connected:
                self.serial_manager.send_command("LoadCellOn")
        else:
            self.append_to_console("Load cell data OFF")
            if self.connected:
                self.serial_manager.send_command("LoadCellOff")

    def on_position_toggle(self, state):
        """Toggle position data display in console"""
        self.display_position_to_console = state
        if state:
            self.append_to_console("Position display ON")
        else:
            self.append_to_console("Position display OFF")

    def on_velocity_toggle(self, state):
        """Toggle velocity data display in console"""
        self.display_velocity_to_console = state
        if state:
            self.append_to_console("Velocity display ON")
        else:
            self.append_to_console("Velocity display OFF")

    # ========== Motor Data Polling ==========

    def _start_motor_polling(self):
        """Start polling motor position (called when connected)"""
        self.motor_position_timer.start()
        self.append_to_console("Motor position polling started")

    def _stop_motor_polling(self):
        """Stop all motor polling (called when disconnected)"""
        self.motor_position_timer.stop()
        self.motor_velocity_timer.stop()

    def _start_velocity_polling(self):
        """Start polling motor velocity (called when motors enabled)"""
        if not self.motor_velocity_timer.isActive():
            self.motor_velocity_timer.start()

    def _stop_velocity_polling(self):
        """Stop polling motor velocity (called when motors disabled)"""
        self.motor_velocity_timer.stop()

    def _poll_motor_position(self):
        """Timer callback to poll motor position"""
        if self.connected:
            self.serial_manager.send_command("GetTotalAngle")

    def _poll_motor_velocity(self):
        """Timer callback to poll motor velocity"""
        if self.connected:
            self.serial_manager.send_command("GetVelocity")

    def _start_movement_grace_period(self):
        """Start a grace period after beginning movement (allows motor to accelerate)"""
        self.movement_start_grace_period = True
        self.stall_count = 0  # Reset stall counter
        self.grace_period_timer.start()

    def _end_grace_period(self):
        """Called when grace period ends - stall detection can now activate"""
        self.movement_start_grace_period = False

    def _start_incremental_grace_period(self):
        """Start a grace period for incremental move (allows motor to start)"""
        self.incremental_move_grace_period = True
        self.incremental_grace_timer.start()

    def _end_incremental_grace_period(self):
        """Called when incremental grace period ends - completion detection can now activate"""
        self.incremental_move_grace_period = False

    # ========== Speed Control Functions ==========

    # Conversion constants
    # Lead screw: 5mm pitch, 20:1 gear ratio
    # 1 RPM = 5mm / 20 / 60 = 0.004167 mm/s
    MM_PER_S_PER_RPM = 5.0 / 20.0 / 60.0  # ~0.004167

    # Safety limits
    MAX_RPM = 450  # Maximum allowed RPM (hardware limit)
    MAX_MM_PER_S = MAX_RPM * MM_PER_S_PER_RPM  # ~1.875 mm/s
    # auto-preload speed ramp knots: (load fraction of target, speed mm/s), interpolated for a
    # smooth slow-down — hold 0.2 to 10 %, ramp to 0.1 by 15 %, hold to 50 %, then a long gentle
    # deceleration to a 0.02 mm/s creep by 90 % so it eases onto the target with minimal overshoot.
    PRELOAD_SPEED_KNOTS = [(0.0, 0.20), (0.10, 0.20), (0.15, 0.10),
                           (0.50, 0.10), (0.90, 0.02), (1.0, 0.02)]
    PRELOAD_TARGET_FACTOR = 1.03  # stop at this x target: offsets PLA stress relaxation (held load
                                  # decays ~2 % after the motor stops) so the held load lands >= target
    PRELOAD_OVERSHOOT_CAP = 1.25  # hard safety: force-halt if load exceeds this multiple of target
    PRELOAD_TIMEOUT_S = 180       # runaway safety: abort auto-preload after this long without reaching target
    RELEASE_SPEED_MM_S = 0.20     # release: constant gentle back-off speed (mm/s) - 0.30 felt too fast
    RELEASE_TARGET_N = 5.0        # release: stop once load drops to/below this (~zero tension)
    RELEASE_MIN_LOAD_N = -50.0    # release safety: hard stop if load goes this far into compression
    RELEASE_RISE_CAP_N = 50.0     # release safety: halt if load RISES this far (wrong direction / snag)
    RELEASE_TIMEOUT_S = 180       # release runaway safety (s)
    STALL_WINDOW_S = 6.0          # stall guard: crosshead must advance within this window while pulling
    STALL_MIN_ADVANCE_MM = 0.05   # ...by at least this much, else it is stalled (near-zero movement only)
    STALL_SHORTFALL_FRAC = 0.35   # ...or this fraction of the travel actually COMMANDED, whichever is
                                  # smaller. A flat 0.05 mm assumed every mode runs near 0.1 mm/s
                                  # (0.6 mm expected = an 8% bar); a tapered approach floors at
                                  # 0.01-0.02 mm/s = 0.06-0.12 mm expected, where 0.05 mm demands
                                  # 42-83% of commanded and a healthy motor trips on rounding alone.
    STALL_MIN_LOAD_N = 200.0      # ...only guard under load (avoids slack / start-up false trips)

    # Closed-loop test-mode (Phase B) safety net — independent of any policy
    # Load cell = ANYLOAD 3 t = 29.4 kN rated. Specimens peak <= ~4.8 kN, so this protects the cell
    # (and the 3D-printed grips) while leaving 2x headroom over a normal fracture -> never false-halts.
    # Raise toward ~25 kN only if you test much stronger materials; MUST stay below 29.4 kN.
    POLICY_MAX_FORCE_N = 10000    # hard Stop+EStop if load exceeds this (N)
    # End-stop backstop for the test modes ONLY (the preload has no travel limit — it stops on force /
    # overshoot / timeout). Must be ABOVE any real fracture travel (V6 fractured ~7-9 mm) yet below the
    # rig's usable stroke so a post-fracture runaway can't drive into the mechanical end-stop.
    # TODO: set to (rig usable stroke - a few mm) once confirmed; 45 mm is a safe non-false-halting placeholder.
    POLICY_MAX_TRAVEL_MM = 30.0   # hard Stop+EStop if crosshead travel exceeds this (mm); ~2x a PLA fracture test's ~8-15 mm
    POLICY_TIMEOUT_S = 900        # runaway backstop for long holds (relaxation/creep)
    POLICY_STALE_FREEZE_S = 0.2   # strain-rate: HOLD speed (no blind ramp-up) once DIC strain is stale this long
                                  #   (0.2 s ~= 2 DIC frames — freezes before the controller can ramp a high command)
    POLICY_DEAD_DIC_S = 1.0       # strain-rate: hard-HALT if strain stays frozen this long (camera lost)

    def _init_speed_controls(self):
        """Initialize speed controls with mm/s defaults"""
        # Set spinbox for mm/s mode with safety limit
        self.setSpeedSpinBox.setMaximum(self.MAX_MM_PER_S)  # Limited by MAX_RPM
        self.setSpeedSpinBox.setDecimals(3)
        self.setSpeedSpinBox.setSingleStep(0.1)
        self.setSpeedSpinBox.setValue(0.1)  # Default 0.1 mm/s (~24 RPM)

        # Initialize speed display to 0 (no measured speed yet)
        self.speedDisplayLabel.setText("Now: 0.00 mm/s")

    def on_speed_unit_changed(self, checked):
        """Handle speed unit radio button change"""
        if not checked:
            return

        is_mm = self.speedUnitMmRadio.isChecked()
        unit = "mm/s" if is_mm else "RPM"

        # Get current value BEFORE changing spinbox settings
        current_value = self.setSpeedSpinBox.value()

        # Block signals to prevent sending commands during conversion
        self.setSpeedSpinBox.blockSignals(True)

        # Convert current spinbox value to new unit
        if is_mm:
            # Switching TO mm/s FROM RPM - convert RPM to mm/s
            new_value = current_value * self.MM_PER_S_PER_RPM
            self.setSpeedSpinBox.setMaximum(self.MAX_MM_PER_S)  # Limited by MAX_RPM
            self.setSpeedSpinBox.setDecimals(3)
            self.setSpeedSpinBox.setSingleStep(0.1)
        else:
            # Switching TO RPM FROM mm/s - convert mm/s to RPM
            new_value = current_value / self.MM_PER_S_PER_RPM if self.MM_PER_S_PER_RPM > 0 else 0
            self.setSpeedSpinBox.setMaximum(self.MAX_RPM)  # Safety limit
            self.setSpeedSpinBox.setDecimals(1)
            self.setSpeedSpinBox.setSingleStep(1.0)

        # Clamp new value to max (in case of rounding errors)
        new_value = min(new_value, self.setSpeedSpinBox.maximum())

        self.setSpeedSpinBox.setValue(new_value)
        self.setSpeedSpinBox.blockSignals(False)

        # Update unit label next to spinbox
        self.speedUnitValueLabel.setText(unit)

        # Update the speed display label
        self._update_speed_display()

        # Update speed gauge unit and max
        if is_mm:
            self.speedGauge.setMaxValue(self.MAX_MM_PER_S)
            self.speedGauge.setUnit("mm/s")
        else:
            self.speedGauge.setMaxValue(self.MAX_RPM)
            self.speedGauge.setUnit("RPM")

        self.append_to_console(f"Speed unit changed to {unit} ({new_value:.2f} {unit})")

    def on_speed_editing_finished(self):
        """Handle speed spinbox editing finished (Enter pressed or focus lost)"""
        self._update_speed_display()

        # If motors are running and moving (not STOP), update speed
        if self.connected and self.motorsSwitch.isChecked():
            if not self.stopRadioButton.isChecked():
                firmware_speed = self.get_firmware_speed()
                speed_rpm = self.get_speed_rpm()
                self.append_to_console(f"Speed updated to {speed_rpm:.1f} RPM")
                self.serial_manager.send_command(f"SetSpeed {firmware_speed}")

    def _update_speed_display(self):
        """Update the speed display label with SET speed (when motors are off)"""
        is_mm = self.speedUnitMmRadio.isChecked()
        value = self.setSpeedSpinBox.value()
        unit = "mm/s" if is_mm else "RPM"
        self.speedDisplayLabel.setText(f"Set: {value:.2f} {unit}")

    def _update_measured_speed_display(self):
        """Update the speed display label and gauge with MEASURED velocity (when motors are running)"""
        is_mm = self.speedUnitMmRadio.isChecked()
        if is_mm:
            # Convert RPM to mm/s
            value = self.motor_velocity_rpm * self.MM_PER_S_PER_RPM
            unit = "mm/s"
            max_value = self.MAX_MM_PER_S
        else:
            value = self.motor_velocity_rpm
            unit = "RPM"
            max_value = self.MAX_RPM
        self.speedDisplayLabel.setText(f"Now: {value:.2f} {unit}")

        # Update the speed gauge
        self.speedGauge.setMaxValue(max_value)
        self.speedGauge.setUnit(unit)
        self.speedGauge.setValue(value)

    def get_speed_rpm(self):
        """Get the current speed setting in RPM (for firmware commands)"""
        value = self.setSpeedSpinBox.value()
        if self.speedUnitMmRadio.isChecked():
            # Convert mm/s to RPM
            rpm = value / self.MM_PER_S_PER_RPM if self.MM_PER_S_PER_RPM > 0 else 0
        else:
            rpm = value
        # Safety clamp (should be caught by spinbox limits, but just in case)
        return min(rpm, self.MAX_RPM)

    def get_firmware_speed(self):
        """Get speed in firmware units (RPM × 10), clamped to MAX_RPM for safety"""
        rpm = self.get_speed_rpm()
        # SAFETY: Clamp to maximum RPM to prevent dangerous speeds
        if rpm > self.MAX_RPM:
            self.append_to_console(f"WARNING: Speed {rpm:.1f} RPM clamped to {self.MAX_RPM} RPM (max)")
            rpm = self.MAX_RPM
        return int(rpm * 10)

    # ========== Motor Control Functions ==========

    def on_direction_changed(self, checked):
        """Handle direction radio button changes"""
        # Only process when button is being checked (not unchecked)
        # Radio buttons emit toggled(False) for old button and toggled(True) for new button
        if not checked:
            return

        # a manual direction change cancels an in-progress auto-preload / release / test mode
        if self.preload_active:
            self._reset_preload_ui()
        if getattr(self, '_release_active', False):
            self._release_active = False
            self._restore_release_buttons()
        if getattr(self, '_return_active', False):
            self._return_active = False
            if getattr(self, 'returnZeroButton', None) is not None:
                self.returnZeroButton.setText("Return to 0 mm")
        if getattr(self, 'active_policy', None) is not None:
            self.active_policy = None                       # manual takeover ends any test-mode policy
            if getattr(self, '_policy_button', None) is not None:
                self._policy_button.setText(getattr(self, '_policy_start_label', 'Start mode'))
        self._autostop_detector = None                      # reset the fracture detector on any direction change
        self._stall_hist = []                               # reset the stall guard on any direction change

        if not self.connected:
            return

        # Get speed from the speed selector
        firmware_speed = self.get_firmware_speed()
        speed_rpm = self.get_speed_rpm()

        if self.upRadioButton.isChecked():
            self.append_to_console(f"Direction: UP at {speed_rpm:.1f} RPM")
            # Show speed in selected unit
            if self.speedUnitMmRadio.isChecked():
                speed_display = speed_rpm * self.MM_PER_S_PER_RPM
                self.set_status(f"Moving UP at {speed_display:.3f} mm/s")
            else:
                self.set_status(f"Moving UP at {speed_rpm:.1f} RPM")
            self.serial_manager.send_command(f"SetSpeed {firmware_speed}")
            # NOTE: firmware Up/Down are inverted vs physical motion on this rig, so the
            # "Up" control sends "Down" — the label now matches the real gripper direction.
            self.serial_manager.send_command("Down")
            # Start grace period for stall detection
            self._start_movement_grace_period()
        elif self.downRadioButton.isChecked():
            self.append_to_console(f"Direction: DOWN at {speed_rpm:.1f} RPM")
            # Show speed in selected unit
            if self.speedUnitMmRadio.isChecked():
                speed_display = speed_rpm * self.MM_PER_S_PER_RPM
                self.set_status(f"Moving DOWN at {speed_display:.3f} mm/s")
            else:
                self.set_status(f"Moving DOWN at {speed_rpm:.1f} RPM")
            self.serial_manager.send_command(f"SetSpeed {firmware_speed}")
            self.serial_manager.send_command("Up")  # inverted mapping (see Up branch)
            # Start grace period for stall detection
            self._start_movement_grace_period()
        else:
            self.append_to_console("Direction: STOP")
            self.set_status("Motors enabled - Stopped")
            self.serial_manager.send_command("Stop")
            # Cancel grace period if stopping
            self.grace_period_timer.stop()
            self.movement_start_grace_period = False

    def on_motors_toggle(self, state):
        """Toggle motor enable/disable"""
        if state:
            # SAFETY: Set direction to STOP before enabling motors
            self.stopRadioButton.blockSignals(True)
            self.stopRadioButton.setChecked(True)
            self.stopRadioButton.blockSignals(False)

            self.append_to_console("Motors ENABLED (direction set to STOP)")
            self.set_status("Motors enabled - Select direction to move")
            if self.connected:
                self.serial_manager.send_command("Enable")
                # Start velocity polling when motors are enabled
                self._start_velocity_polling()
        else:
            # SAFETY: Stop motor rotation and set direction to STOP before disabling
            self.stopRadioButton.blockSignals(True)
            self.stopRadioButton.setChecked(True)
            self.stopRadioButton.blockSignals(False)

            self.append_to_console("Motors DISABLED (stopped)")
            self._reset_preload_ui()
            self.set_status("Motors disabled")
            if self.connected:
                self.serial_manager.send_command("Stop")
                self.serial_manager.send_command("Disable")
            # Stop velocity polling when motors are disabled
            self._stop_velocity_polling()
            # Switch speed display back to showing SET speed
            self._update_speed_display()
            # Reset speed gauge to 0
            self.speedGauge.setValue(0)

        # Update direction and incremental move controls based on motor state
        self.update_controls_enabled_state()

    # ========== Auto-preload (move in tension until load reaches a target) ==========

    def _setup_preload_controls(self):
        """Add a target-force input + Preload button to the Motor Control group (right panel)."""
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton
        row = QHBoxLayout()
        row.addWidget(QLabel("Preload to:"))
        self.preloadTargetSpinBox = QDoubleSpinBox()
        self.preloadTargetSpinBox.setRange(0, 2000)
        self.preloadTargetSpinBox.setDecimals(0)
        self.preloadTargetSpinBox.setSingleStep(10)
        # 300 N, matching what the rig has actually been run at since S22 (anchors 280-308 N on
        # S24/S25/S26) and matching recipes/Default.json, which already said 300. The old 470 came
        # from the V6 quintet and had drifted into being an outlier that every run overwrote by hand.
        self.preloadTargetSpinBox.setValue(300)
        self.preloadTargetSpinBox.setSuffix(" N")
        self.preloadTargetSpinBox.setToolTip(
            "Target load. The gripper moves in tension until the load cell reaches this value, then stops.")
        self.preloadButton = QPushButton("Preload tension")
        self.preloadButton.setToolTip(
            "Auto-move the gripper in tension until Current Load reaches the target, then stop. Click again to cancel.")
        # TWO release depths, as two buttons rather than one button plus a mode. The reading is
        # tared at the preload, so tared 0 N and true 0 N are ~300 N apart on this rig — a release
        # that overshoots drives the specimen toward compression. Naming each end point on its own
        # button means the motor can never travel further than the label the operator just pressed;
        # a tickbox would have made the depth depend on state set minutes earlier.
        self.releaseToPreloadButton = QPushButton("Release to preload")
        self.releaseToPreloadButton.setToolTip(
            "Back off the TEST load only, stopping at tared ~0 N — which still holds the preload.\n"
            "Use this between runs: the specimen stays mounted and tensioned, ready to pull again.\n"
            "Click again to cancel.")
        self.releaseButton = QPushButton("Release fully")
        self.releaseButton.setToolTip(
            "Release ALL load: back off until the specimen reaches TRUE zero force.\n"
            "The reading is tared at the preload, so tared 0 N still holds it — this drives on to\n"
            "-(tared-away load), e.g. -300 N, leaving the specimen free to unclamp. Click again to cancel.")
        row.addWidget(self.preloadTargetSpinBox)
        row.addWidget(self.preloadButton)
        rel_row = QHBoxLayout()
        rel_row.addWidget(self.releaseToPreloadButton)
        rel_row.addWidget(self.releaseButton)
        lay = self.motorControlGroup.layout()
        idx = lay.indexOf(self.emergencyStopButton)
        if idx >= 0:
            lay.insertLayout(idx, row)
            lay.insertLayout(idx + 1, rel_row)
        else:
            lay.addLayout(row)
            lay.addLayout(rel_row)
        self.preloadButton.clicked.connect(self.on_preload_start)
        self.preloadButton.setEnabled(False)
        self.preloadTargetSpinBox.setEnabled(False)
        self.releaseToPreloadButton.clicked.connect(self.on_release_to_preload)
        self.releaseButton.clicked.connect(self.on_release_preload_start)
        for b in (self.releaseToPreloadButton, self.releaseButton):
            b.setEnabled(False)

    def on_preload_start(self):
        """Start (or, if already running, cancel) an automatic preload to the target force."""
        if self.preload_active:
            self._stop_preload("cancelled by user")
            return
        target = self.preloadTargetSpinBox.value()
        if not self.connected:
            self.append_to_console("[Preload] Not connected — cannot move."); return
        if not self.motorsSwitch.isChecked():
            self.append_to_console("[Preload] Enable motors first."); return
        if target <= 0:
            self.append_to_console("[Preload] Set a positive target load."); return
        if self.current_load >= target:
            self.append_to_console(
                f"[Preload] Load is already {self.current_load:.1f} N >= target {target:.0f} N."); return
        # gentle tension approach
        self.preload_target = float(target)
        self._preload_last_speed = self.PRELOAD_SPEED_KNOTS[0][1]
        self._preload_last_speed_t = 0.0
        self.preload_active = True
        # show "Up" (tension) selected without re-triggering the direction handler
        self.upRadioButton.blockSignals(True)
        self.upRadioButton.setChecked(True)
        self.upRadioButton.blockSignals(False)
        self.serial_manager.send_command(f"SetSpeed {self._fw_speed(self.PRELOAD_SPEED_KNOTS[0][1])}")
        self.serial_manager.send_command("Down")   # firmware "Down" = physical tension
        self._start_movement_grace_period()
        self.preload_timeout_timer.start()
        self.preloadButton.setText("Cancel preload")
        self.preloadTargetSpinBox.setEnabled(False)
        self.append_to_console(
            f"[Preload] Approaching {target:.0f} N (tension) — speed ramps 0.20 → 0.10 → 0.05 mm/s "
            f"(smooth, around 10 % / 75 %)...")
        self.set_status(f"Preloading to {target:.0f} N ...")

    def _stall_threshold_mm(self, cmd_speed_mm_s):
        """How far the crosshead must advance within STALL_WINDOW_S before we call it stalled.
        Scales with what was actually commanded so a legitimate tapered crawl is not mistaken for a
        stall, and never exceeds the original fixed bar (so behaviour at normal speeds is unchanged).
        Returns 0 when nothing was commanded -> the guard cannot fire."""
        expected = max(0.0, cmd_speed_mm_s) * self.STALL_WINDOW_S
        return min(self.STALL_MIN_ADVANCE_MM, self.STALL_SHORTFALL_FRAC * expected)

    def _fw_speed(self, mm_s):
        """Convert mm/s to the firmware SetSpeed value (RPM x 10), clamped to MAX_RPM."""
        rpm = min(mm_s / self.MM_PER_S_PER_RPM, self.MAX_RPM)
        return int(rpm * 10)

    def _preload_check(self):
        """Smooth-ramped approach; stop when the live load reaches the target.
        The approach speed is interpolated vs load fraction (no abrupt drops), and there is
        NO early anticipation — it stops AT the target, landing within +5 % (never short)."""
        # HARD safety net: force-halt if the load ever runs well past the target.
        if self.current_load >= self.PRELOAD_OVERSHOOT_CAP * self.preload_target:
            if self.connected:
                self.serial_manager.send_command("Stop")
                self.serial_manager.send_command("EStop")
            self._reset_preload_ui()
            self.stopRadioButton.blockSignals(True)
            self.stopRadioButton.setChecked(True)
            self.stopRadioButton.blockSignals(False)
            self.append_to_console(
                f"[Preload] OVERSHOOT SAFETY — halted at {self.current_load:.1f} N "
                f"(target {self.preload_target:.0f} N)")
            self.set_status("⚠ Preload overshoot — motor halted", is_warning=True)
            return
        # smooth speed ramp: interpolate the approach speed vs load fraction, then throttle the
        # SetSpeed sends (by value + time) so the slow-down is smooth without spamming the firmware.
        # LIVE SetSpeed only — re-issuing "Down" mid-move re-latches motion and fights the stop.
        import time
        now = time.monotonic()
        target = self.preload_target
        frac = self.current_load / target if target > 0 else 1.0
        spd = self._preload_speed(frac)
        if (abs(spd - self._preload_last_speed) >= 0.01
                and now - self._preload_last_speed_t >= 0.15):
            self._preload_last_speed = spd
            self._preload_last_speed_t = now
            self.serial_manager.send_command(f"SetSpeed {self._fw_speed(spd)}")
        # throttled progress log
        if now - getattr(self, '_preload_last_log', 0.0) >= 1.0:
            self._preload_last_log = now
            self.append_to_console(
                f"[Preload] current {self.current_load:.1f} N  ({frac*100:.0f} %, {spd:.3f} mm/s)  /  "
                f"target {target:.0f} N")
        # stop at factor x target so the HELD load lands >= target after PLA stress relaxation
        if self.current_load >= self.PRELOAD_TARGET_FACTOR * target:
            self._stop_preload(
                f"reached {self.current_load:.1f} N "
                f"(target {target:.0f} N x{self.PRELOAD_TARGET_FACTOR:.2f}, offsets relaxation)")

    def _preload_speed(self, frac):
        """Interpolated approach speed (mm/s) for a load fraction — smooth ramps between knots."""
        knots = self.PRELOAD_SPEED_KNOTS
        if frac <= knots[0][0]:
            return knots[0][1]
        for (f0, s0), (f1, s1) in zip(knots, knots[1:]):
            if frac <= f1:
                return s0 + (s1 - s0) * (frac - f0) / (f1 - f0) if f1 > f0 else s1
        return knots[-1][1]

    def _stop_preload(self, message, warn=False):
        """Stop the motor and end the auto-preload, with a console/status message."""
        self._reset_preload_ui()
        self.stopRadioButton.blockSignals(True)
        self.stopRadioButton.setChecked(True)
        self.stopRadioButton.blockSignals(False)
        self.movement_start_grace_period = False
        self.grace_period_timer.stop()
        if self.connected:
            self.serial_manager.send_command("Stop")
        self.append_to_console(f"[Preload] {message}")
        self.set_status(f"Preload: {message}", is_warning=warn)

    def _on_preload_timeout(self):
        self._stop_preload("timed out — target not reached", warn=True)

    def _reset_preload_ui(self):
        """Clear auto-preload state and restore the button/input (does NOT command the motor)."""
        self.preload_active = False
        if getattr(self, 'preload_timeout_timer', None) is not None:
            self.preload_timeout_timer.stop()
        if getattr(self, 'preloadButton', None) is not None:
            self.preloadButton.setText("Preload tension")
        if getattr(self, 'preloadTargetSpinBox', None) is not None:
            self.preloadTargetSpinBox.setEnabled(True)

    # ---- Return the crosshead to the tared zero, ready for the next specimen ----------------
    #
    # After a fracture the crosshead sits wherever the pull ended (~9-10 mm), and getting back to
    # the mounting position meant nudging it by hand with the incremental controls. This drives it
    # to δ = 0 and stops there.
    #
    # It is a REPOSITIONING move, not a measurement, so it runs faster than a test — but it is
    # still a motor command with a specimen possibly in the grips, so it carries the same shape of
    # safety net as preload and release: a load ceiling that both gates the start and aborts mid-
    # move, a timeout, and a taper so it does not overshoot the target it is driving at.
    RETURN_SPEED_MM_S = 0.50        # brisk approach
    RETURN_SLOW_MM = 0.60           # taper inside this distance from zero
    RETURN_SLOW_SPEED_MM_S = 0.10
    RETURN_TOL_MM = 0.05            # "arrived"
    # SIGNED tension ceiling: refuse to start, and abort, above this. It is deliberately NOT abs().
    # The force reading is tared at the preload, so a specimen carrying nothing at all reads
    # -(tared_away) — typically -280 to -480 N after a fracture or a full release. Testing abs()
    # blocked precisely the case this button exists for, while a genuinely gripped specimen (which
    # reads POSITIVE tension) is what has to be refused.
    RETURN_MAX_LOAD_N = 50.0
    # ...but dropping abs() would also drop the only guard against driving into an obstruction,
    # which shows up as load moving hard in EITHER direction. Watch the change from where the move
    # started instead: that works wherever the tare happens to sit, which an absolute limit cannot.
    RETURN_MAX_DELTA_N = 250.0
    RETURN_TIMEOUT_S = 240

    def _add_return_zero_button(self):
        """Put 'Return to 0 mm' directly under Tare Location, inside the Crosshead position box.

        It belongs beside the δ readout it acts on, not in the motor-control column: the two
        buttons are the pair of things you do to that number — redefine zero, or go back to it.
        """
        from PyQt6.QtWidgets import QPushButton
        self.returnZeroButton = QPushButton("Return to 0 mm")
        self.returnZeroButton.setToolTip(
            "Drive the crosshead back to δ = 0 — the mounting position for the next specimen.\n"
            "Slows near the target and stops within 0.05 mm.\n"
            f"Refuses to start, and aborts, above {self.RETURN_MAX_LOAD_N:.0f} N of TENSION, so it "
            "cannot drive against a specimen that is still gripped. Negative (compressive) and "
            "near-zero readings are fine — that is the normal post-fracture state.\n"
            "Press again to cancel.")
        self.returnZeroButton.clicked.connect(self.on_return_to_zero)
        self.returnZeroButton.setEnabled(False)
        lay = self.positionGroup.layout()
        if lay is not None:
            lay.addWidget(self.returnZeroButton)
        else:                                   # .ui uses absolute geometry in this group
            g = self.tareLocationButton.geometry()
            self.returnZeroButton.setParent(self.positionGroup)
            self.returnZeroButton.setGeometry(g.x(), g.y() + g.height() + 4, g.width(), g.height())
            self.positionGroup.setMinimumHeight(g.y() + 2 * g.height() + 14)
            self.returnZeroButton.show()

    def on_return_to_zero(self):
        """Drive the crosshead back to δ = 0. Cancels if pressed again while running."""
        from PyQt6.QtWidgets import QMessageBox
        if getattr(self, "_return_active", False):
            self._stop_return("cancelled by user"); return
        if not self.connected:
            self.append_to_console("[Return] Not connected — cannot move."); return
        if not self.motorsSwitch.isChecked():
            self.append_to_console("[Return] Enable motors first."); return
        if self.preload_active or getattr(self, "_release_active", False) \
                or getattr(self, "active_policy", None) is not None:
            self.append_to_console("[Return] Finish the preload / release / test mode first."); return

        d = self.motor_displacement_mm
        if abs(d) <= self.RETURN_TOL_MM:
            self.append_to_console(f"[Return] Already at δ = {d:+.3f} mm — nothing to do."); return

        # A specimen still carrying TENSION is the case this must not blunder into: driving toward
        # zero would compress or snap it. Refuse, and say which button fixes it.
        #
        # Signed, not abs(). A fractured or fully released specimen reads NEGATIVE — the preload
        # was tared away, so nothing in the grips shows as -(tared_away) — and that is the state
        # this button is normally pressed in.
        load = self.current_load or 0.0
        if load > self.RETURN_MAX_LOAD_N:
            self.append_to_console(
                f"[Return] Tension is {load:+.0f} N — release it first (Release fully), otherwise "
                "driving back to zero would push against a specimen that is still gripped.")
            QMessageBox.warning(self, "Return to zero",
                                f"Tension is {load:+.0f} N.\n\nRelease the load first — returning "
                                "to zero now would drive the crosshead against a loaded specimen.")
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Return to zero")
        msg.setText(f"Drive the crosshead from δ = {d:+.3f} mm back to 0?")
        msg.setInformativeText(
            f"It will move {abs(d):.2f} mm at {self.RETURN_SPEED_MM_S:.2f} mm/s, slowing near the "
            f"end, and stop within {self.RETURN_TOL_MM:.2f} mm.\n\n"
            f"Load now: {load:+.0f} N.\n"
            f"Aborts on its own if tension exceeds {self.RETURN_MAX_LOAD_N:.0f} N, or if the load "
            f"moves more than {self.RETURN_MAX_DELTA_N:.0f} N from here in either direction. "
            "Press Stop / E-Stop at any time.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            self.append_to_console("[Return] cancelled."); return

        import time
        self._return_active = True
        self._return_start_t = time.monotonic()
        self._return_start_d = d
        self._return_start_load = load          # baseline for the obstruction guard
        self._return_last_log = 0.0
        self._return_speed = None
        # Positive δ means the crosshead travelled in TENSION, so coming back is the release
        # direction — the same latch the release loop uses. Negative δ is the mirror.
        btn = self.downRadioButton if d > 0 else self.upRadioButton
        cmd = "Up" if d > 0 else "Down"
        btn.blockSignals(True); btn.setChecked(True); btn.blockSignals(False)
        self._return_cmd = cmd
        self._set_return_speed(self.RETURN_SPEED_MM_S)
        self.serial_manager.send_command(cmd)
        self._start_movement_grace_period()
        self.returnZeroButton.setText("Cancel return")
        self.append_to_console(f"[Return] driving from δ = {d:+.3f} mm to 0 "
                               f"at {self.RETURN_SPEED_MM_S:.2f} mm/s ...")
        self.set_status("Returning crosshead to zero ...")

    def _set_return_speed(self, mm_s):
        """Only re-send SetSpeed when it actually changes — the taper would otherwise spam it."""
        if self._return_speed is not None and abs(self._return_speed - mm_s) < 1e-6:
            return
        self._return_speed = mm_s
        self.serial_manager.send_command(f"SetSpeed {self._fw_speed(mm_s)}")

    def _return_check(self):
        """Live loop: taper near zero, stop on arrival, and bail out on load / timeout."""
        import time
        d = self.motor_displacement_mm
        load = self.current_load or 0.0

        # Two separate failures, and they need two separate tests. Tension climbing past the
        # ceiling means a specimen is still gripped; a big swing EITHER way from where the move
        # started means the crosshead has run into something. Only the first can be judged against
        # a fixed number, because only the second is independent of where the tare sits.
        if load > self.RETURN_MAX_LOAD_N:
            if self.connected:
                self.serial_manager.send_command("Stop")
            self._stop_return(f"SAFETY — tension reached {load:+.0f} N; something is in the grips",
                              warn=True)
            return
        swing = load - getattr(self, "_return_start_load", load)
        if abs(swing) > self.RETURN_MAX_DELTA_N:
            if self.connected:
                self.serial_manager.send_command("Stop")
            self._stop_return(f"SAFETY — load moved {swing:+.0f} N since the move began "
                              f"(now {load:+.0f} N); the crosshead is pushing against something",
                              warn=True)
            return
        if time.monotonic() - self._return_start_t > self.RETURN_TIMEOUT_S:
            self._stop_return("timed out", warn=True); return
        # Overshoot past zero counts as arrived: the sign of δ flipped, so continuing would drive
        # away from the target rather than toward it.
        if abs(d) <= self.RETURN_TOL_MM or (d * self._return_start_d) < 0:
            self._stop_return(f"at δ = {d:+.3f} mm — ready for the next specimen")
            return
        self._set_return_speed(self.RETURN_SLOW_SPEED_MM_S if abs(d) <= self.RETURN_SLOW_MM
                               else self.RETURN_SPEED_MM_S)
        now = time.monotonic()
        if now - self._return_last_log >= 1.0:
            self._return_last_log = now
            self.append_to_console(f"[Return] δ = {d:+.3f} mm  ->  0")

    def _stop_return(self, message, warn=False):
        self._return_active = False
        self.stopRadioButton.blockSignals(True); self.stopRadioButton.setChecked(True)
        self.stopRadioButton.blockSignals(False)
        self.movement_start_grace_period = False
        if getattr(self, "grace_period_timer", None) is not None:
            self.grace_period_timer.stop()
        if self.connected:
            self.serial_manager.send_command("Stop")
        if getattr(self, "returnZeroButton", None) is not None:
            self.returnZeroButton.setText("Return to 0 mm")
        self.append_to_console(f"[Return] {message}")
        self.set_status(f"Return to zero: {message}", is_warning=warn)

    # ---- Release preload: back off the tension so you can preload again ----
    def on_release_to_preload(self):
        """PARTIAL release: shed the test load, stop with the preload still on the specimen."""
        self._start_release(full=False)

    def on_release_preload_start(self):
        """FULL release: all the way to true zero, so the specimen can be unclamped."""
        self._start_release(full=True)

    def _start_release(self, full):
        """Start (or, if running, cancel) a controlled release.

        Two depths, and the difference is the whole point of having two buttons. The force reading
        is TARED at the preload, so tared 0 N still holds that preload (e.g. 300 N of real tension):

          full=False  stop at tared ~0 N          -> test load gone, PRELOAD STILL APPLIED
          full=True   stop at tared -(tared_away) -> TRUE zero absolute force, specimen free

        `_tare_load_N` is captured by the tare itself; if the user never tared we fall back to the
        preload target box.
        """
        if getattr(self, '_release_active', False):
            self._stop_release("cancelled by user"); return
        if not self.connected:
            self.append_to_console("[Release] Not connected — cannot move."); return
        if not self.motorsSwitch.isChecked():
            self.append_to_console("[Release] Enable motors first."); return
        if self.preload_active or getattr(self, 'active_policy', None) is not None:
            self.append_to_console("[Release] Cancel the preload / test mode first."); return
        tared_away = getattr(self, '_tare_load_N', 0.0)
        if tared_away <= 0.0:
            tared_away = max(0.0, self.preloadTargetSpinBox.value())
        # stop RELEASE_TARGET_N above the chosen zero, same margin the old ~0 N release used
        self._release_full = bool(full)
        self._release_target_N = self.RELEASE_TARGET_N - (tared_away if full else 0.0)
        self._release_floor_N = self._release_target_N + self.RELEASE_MIN_LOAD_N   # relative safety floor
        if self.current_load <= self._release_target_N:
            self.append_to_console(
                f"[Release] Load already {self.current_load:.1f} N "
                f"(target ≤ {self._release_target_N:.0f} N) — nothing to release."); return
        import time
        self._release_active = True
        self._release_start_load = self.current_load
        self._release_start_t = time.monotonic()
        self._release_last_log = 0.0
        # release direction = downRadioButton = firmware "Up" = physical release (reduces tension)
        self.downRadioButton.blockSignals(True)
        self.downRadioButton.setChecked(True)
        self.downRadioButton.blockSignals(False)
        self.serial_manager.send_command(f"SetSpeed {self._fw_speed(self.RELEASE_SPEED_MM_S)}")
        self.serial_manager.send_command("Up")   # firmware "Up" = physical release on this rig
        self._start_movement_grace_period()
        # Only the button that was pressed becomes the cancel; the other greys out, so there is
        # never a second live motion button competing with it mid-release.
        active, other = ((self.releaseButton, self.releaseToPreloadButton) if full else
                         (self.releaseToPreloadButton, self.releaseButton))
        active.setText("Cancel release")
        other.setEnabled(False)
        where = (f"= true zero, {tared_away:.0f} N was tared away" if full
                 else f"= preload still applied, {tared_away:.0f} N stays on the specimen")
        self.append_to_console(
            f"[Release] Releasing from {self.current_load:.1f} N to <= {self._release_target_N:.0f} N "
            f"({where}) at {self.RELEASE_SPEED_MM_S:.2f} mm/s ...")
        self.set_status("Releasing to true zero ..." if full else "Releasing to preload ...")

    def _release_check(self):
        """Live-load loop for the release: gentle back-off until load ~0, with safety nets. The direction
        is latched ONCE at start (preload discipline); here we only watch the load and stop."""
        import time
        # SAFETY: load must be DROPPING — if it climbs, we're moving the wrong way / snagged.
        if self.current_load > self._release_start_load + self.RELEASE_RISE_CAP_N:
            if self.connected:
                self.serial_manager.send_command("Stop"); self.serial_manager.send_command("EStop")
            self._stop_release(f"SAFETY — load ROSE to {self.current_load:.1f} N during release; halted", warn=True)
            return
        # SAFETY: do not drive past true zero into real compression. The floor is RELATIVE to the
        # target (target - 50 N), otherwise the old fixed -50 N would abort a release that has to
        # travel to e.g. -300 N tared just to reach true zero.
        floor = getattr(self, '_release_floor_N', self.RELEASE_MIN_LOAD_N)
        if self.current_load <= floor:
            self._stop_release(f"reached {self.current_load:.1f} N (compression limit)", warn=True)
            return
        if time.monotonic() - self._release_start_t > self.RELEASE_TIMEOUT_S:
            self._stop_release("timed out", warn=True)
            return
        target = getattr(self, '_release_target_N', self.RELEASE_TARGET_N)
        # DONE: all load released (tared reading is now -preload => true zero absolute force)
        if self.current_load <= target:
            done = ("~0 N true — specimen free to unclamp" if getattr(self, '_release_full', True)
                    else "the preload is STILL APPLIED — specimen stays mounted and tensioned")
            self._stop_release(f"released to {self.current_load:.1f} N tared = {done}")
            return
        now = time.monotonic()
        if now - getattr(self, '_release_last_log', 0.0) >= 1.0:
            self._release_last_log = now
            self.append_to_console(
                f"[Release] current {self.current_load:.1f} N  ->  target <= {target:.0f} N")

    def _stop_release(self, message, warn=False):
        """Stop the motor and end the release, restoring the button."""
        self._release_active = False
        self.stopRadioButton.blockSignals(True)
        self.stopRadioButton.setChecked(True)
        self.stopRadioButton.blockSignals(False)
        self.movement_start_grace_period = False
        if getattr(self, 'grace_period_timer', None) is not None:
            self.grace_period_timer.stop()
        if self.connected:
            self.serial_manager.send_command("Stop")
        self._restore_release_buttons()
        self.append_to_console(f"[Release] {message}")
        self.set_status(f"Release: {message}", is_warning=warn)

    def _restore_release_buttons(self):
        """Both release buttons back to their resting labels and enabled state.

        Called from every exit path — normal finish, safety halt, cancel, and a manual direction
        change — because the pressed button is left reading "Cancel release" and the other is left
        disabled, and either one stuck that way strands the operator.
        """
        for b, label in ((getattr(self, 'releaseToPreloadButton', None), "Release to preload"),
                         (getattr(self, 'releaseButton', None), "Release fully")):
            if b is not None:
                b.setText(label)
        # Re-enable through the single authority rather than setEnabled(True) here: a release that
        # ended on a safety halt may have left the motors off, and these must not come back armed.
        self.update_controls_enabled_state()

    # ========== Closed-loop test modes (Phase B, BETA) — reuse the safe preload discipline ==========
    def _setup_testmode_controls(self):
        """Add a strain-rate control (BETA) to the Motor Control group. Closed-loop on the DIC gauge
        strain rate — same live-SetSpeed-only discipline as auto-preload, so it is the safe first
        Phase-B mode. Cyclic/staircase/relaxation/creep exist in control_policies.py but are NOT wired
        here yet (they need rig checks of hold / direction-reversal firmware behaviour)."""
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton
        row = QHBoxLayout()
        row.addWidget(QLabel("Strain rate:"))
        self.strainRateSpinBox = QDoubleSpinBox()
        self.strainRateSpinBox.setRange(0.0001, 0.0100); self.strainRateSpinBox.setDecimals(4)
        self.strainRateSpinBox.setSingleStep(0.0005); self.strainRateSpinBox.setValue(0.0005)
        self.strainRateSpinBox.setSuffix(" /s")
        self.strainRateSpinBox.setToolTip("Target DIC gauge strain rate (compliance-free). Needs the DIC camera running.\n"
                                          "Lower = slower crosshead demand = more motor force headroom (steppers lose "
                                          "force at speed). On a stiff specimen it may become speed-limited rather than stall.")
        self.strainRateButton = QPushButton("Start strain-rate fracture test")
        self.strainRateButton.setToolTip("BETA closed-loop DIC strain-rate pull to FRACTURE. Crosshead capped low so the "
                                         "motor keeps its pulling force. Keep Emergency Stop in reach and use a fresh "
                                         "specimen; needs the DIC camera running (green 2/2).")
        row.addWidget(self.strainRateSpinBox); row.addWidget(self.strainRateButton)
        lay = self.motorControlGroup.layout()
        idx = lay.indexOf(self.emergencyStopButton)
        lay.insertLayout(idx, row) if idx >= 0 else lay.addLayout(row)
        self.strainRateButton.clicked.connect(self.on_strain_rate_start)
        self.strainRateButton.setEnabled(False)

    def on_strain_rate_start(self):
        """Start (or, if running, cancel) the closed-loop strain-rate mode."""
        if getattr(self, "active_policy", None) is not None:
            self._stop_policy("cancelled by user"); return
        if not self.connected or not self.motorsSwitch.isChecked():
            self.append_to_console("[Mode] Connect and enable motors first."); return
        if self.preload_active:
            self.append_to_console("[Mode] Finish or cancel the preload first."); return
        from control_policies import StrainRatePolicy
        gauge = self.gauge_length if self.gauge_length > 0 else 80.0
        policy = StrainRatePolicy(self.strainRateSpinBox.value(), gauge_mm=gauge, stop_strain=None,
                                  speed_limits=(0.005, 0.2))   # moderate cap: enough to TRACK the target rate on a
                                  # stiff specimen, low enough to limit blind-ramp overshoot if DIC drops. (Speed is
                                  # NOT the stall cause — that is the motor's variable torque ceiling; see memory.)
        self._start_policy(policy, self.strainRateButton, "Start strain-rate fracture test")

    def _setup_control_modes_segment(self):
        """SEPARATE segment to pick an advanced closed-loop test type (cyclic / staircase / relaxation /
        creep) and set its parameters. Each maps to a control_policies policy and runs through the SAME
        _policy_step loop + safety net (stall guard · force/travel backstop · timeout) as strain-rate.
        A QStackedWidget shows only the chosen mode's fields."""
        from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDoubleSpinBox,
                                     QSpinBox, QPushButton, QStackedWidget, QWidget, QFrame, QToolButton,
                                     QCheckBox)

        def dsb(lo, hi, dec, step, val, suf=""):
            b = QDoubleSpinBox(); b.setRange(lo, hi); b.setDecimals(dec); b.setSingleStep(step); b.setValue(val)
            if suf:
                b.setSuffix(suf)
            return b

        def isb(lo, hi, val):
            b = QSpinBox(); b.setRange(lo, hi); b.setValue(val); return b

        def page(pairs):
            """Two label/field pairs per ROW, not one long line.

            The control column is ~300 px wide and cyclic alone has five parameters; packed into a
            single QHBoxLayout every spin box was crushed to a few pixels and its value clipped. A
            2-column grid wraps them instead, and the fields get a usable minimum width."""
            from PyQt6.QtWidgets import QGridLayout
            w = QWidget(); g = QGridLayout(w)
            g.setContentsMargins(0, 0, 0, 0); g.setHorizontalSpacing(6); g.setVerticalSpacing(4)
            for i, (lab, widget) in enumerate(pairs):
                widget.setMinimumWidth(84)
                r, c = divmod(i, 2)
                g.addWidget(QLabel(lab), r, c * 2)
                g.addWidget(widget, r, c * 2 + 1)
            g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)
            return w

        seg = QVBoxLayout()
        self.modeEnableCheck = QCheckBox("Enable — choose type + settings")
        self.modeEnableCheck.setStyleSheet("font-weight:bold")
        self.modeEnableCheck.setToolTip("Tick to arm the advanced closed-loop modes. Left off, the type/settings "
                                        "stay greyed so they can't be changed by accident.")
        self.modeEnableCheck.toggled.connect(self._update_control_mode_enabled)
        seg.addWidget(self.modeEnableCheck)
        crow = QHBoxLayout(); crow.addWidget(QLabel("Test type:"))
        self.modeCombo = QComboBox()
        self.modeCombo.addItems(["Cyclic", "Staircase", "Relaxation", "Creep",
                                 "Staircase → FRACTURE", "Progressive cyclic → FRACTURE"])
        crow.addWidget(self.modeCombo)
        self.modeHelpButton = QToolButton(); self.modeHelpButton.setText("?")
        self.modeHelpButton.setFixedSize(24, 24)
        self.modeHelpButton.setToolTip("Show a diagram of the selected test type and what each setting means")
        self.modeHelpButton.clicked.connect(self.on_mode_help)
        crow.addWidget(self.modeHelpButton); crow.addStretch(1); seg.addLayout(crow)

        self.modeStack = QStackedWidget()
        # Cyclic — load/unload between two FORCE bounds, N cycles
        self.cyc_lo = dsb(0, 5000, 0, 10, 50, " N"); self.cyc_hi = dsb(0, 5000, 0, 10, 500, " N")
        self.cyc_n = isb(1, 1000, 5); self.cyc_spd = dsb(0.005, 0.5, 3, 0.01, 0.1, " mm/s")
        # Sine FIRST because it is measurably better, not by preference: peak error on the rig was
        # 71.2 N with Triangle (T5) against 15.3 N with Sine (T6.3) and 3.4 N once the load window
        # was raised (T6.5). Triangle drives at constant speed into each bound and overshoots on the
        # reversal; Sine eases to a crawl there.
        self.cyc_wave = QComboBox(); self.cyc_wave.addItems(["Sine", "Triangle"])
        self.cyc_wave.setToolTip("Sine (default) eases to a crawl at each bound → smooth, rounded "
                                 "cycles and far less reversal overshoot: peak error 15.3 N vs "
                                 "71.2 N for Triangle on the same rig.\n"
                                 "Triangle = constant-speed ramps; use it only if you need a "
                                 "constant strain rate within each stroke.")
        self.modeStack.addWidget(page([("Low", self.cyc_lo), ("High", self.cyc_hi),
                                       ("Cycles", self.cyc_n), ("Speed", self.cyc_spd),
                                       ("Waveform", self.cyc_wave)]))
        # Staircase — step load up (start + i·step), hold each level for dwell
        self.stc_start = dsb(0, 5000, 0, 10, 200, " N"); self.stc_step = dsb(10, 2000, 0, 10, 200, " N")
        self.stc_n = isb(1, 20, 4); self.stc_dwell = dsb(1, 600, 0, 5, 30, " s")
        self.stc_spd = dsb(0.005, 0.5, 3, 0.01, 0.1, " mm/s")
        # Smooth FIRST, for the same reason and with a bigger margin: arrival overshoot per level was
        # +45.5 / +46.8 / +52.6 N with Linear (T3) against +6.0 / +4.8 / +7.8 N with Smooth (T4) —
        # about 8x better. It also matches Staircase → FRACTURE, which already defaulted to Smooth.
        self.stc_shape = QComboBox(); self.stc_shape.addItems(["Smooth", "Linear"])
        self.stc_shape.setToolTip("Smooth (default) eases to a crawl approaching each level, so it "
                                  "lands on target instead of sailing past: overshoot ~5-8 N vs "
                                  "~46-53 N for Linear on the same rig.\n"
                                  "Linear = constant-speed ramp to each level.")
        self.modeStack.addWidget(page([("Start", self.stc_start), ("Step", self.stc_step),
                                       ("Levels", self.stc_n), ("Dwell", self.stc_dwell),
                                       ("Speed", self.stc_spd), ("Ramp", self.stc_shape)]))
        # Relaxation — ramp to a target STRAIN, then hold still and log force decay
        self.rlx_strain = dsb(0.001, 0.2, 4, 0.005, 0.02); self.rlx_dur = dsb(1, 3600, 0, 10, 120, " s")
        self.rlx_spd = dsb(0.005, 0.5, 3, 0.01, 0.1, " mm/s")
        self.modeStack.addWidget(page([("Hold strain", self.rlx_strain), ("Duration", self.rlx_dur),
                                       ("Speed", self.rlx_spd)]))
        # Creep — ramp to a target LOAD, then hold force ~constant and log strain creep
        self.crp_load = dsb(10, 5000, 0, 10, 500, " N"); self.crp_dur = dsb(1, 3600, 0, 10, 120, " s")
        self.crp_spd = dsb(0.005, 0.5, 3, 0.01, 0.1, " mm/s")
        self.modeStack.addWidget(page([("Load", self.crp_load), ("Duration", self.crp_dur),
                                       ("Speed", self.crp_spd)]))
        # --- DESTRUCTIVE protocols: keep stepping/cycling until the specimen breaks ---
        # Staircase → fracture: modulus + a mini relaxation at EVERY level, and a sharp yield onset
        # (the dwell drop stays small while elastic, then grows abruptly past yield).
        self.sfr_start = dsb(0, 5000, 0, 10, 400, " N"); self.sfr_step = dsb(10, 2000, 0, 10, 400, " N")
        self.sfr_dwell = dsb(1, 600, 0, 5, 15, " s"); self.sfr_spd = dsb(0.005, 0.5, 3, 0.01, 0.1, " mm/s")
        self.sfr_shape = QComboBox(); self.sfr_shape.addItems(["Smooth", "Linear"])
        self.sfr_shape.setToolTip("Smooth eases into each level (less overshoot). Past yield the specimen is "
                                  "much softer, so the eased approach gets slow — Linear is faster there.")
        self.modeStack.addWidget(page([("Start", self.sfr_start), ("Step", self.sfr_step),
                                       ("Dwell", self.sfr_dwell), ("Speed", self.sfr_spd),
                                       ("Ramp", self.sfr_shape)]))
        # Progressive cyclic → fracture: every unload measures the modulus at that damage state.
        self.pcy_start = dsb(0, 5000, 0, 10, 600, " N"); self.pcy_step = dsb(10, 2000, 0, 10, 400, " N")
        self.pcy_low = dsb(20, 2000, 0, 10, 150, " N"); self.pcy_spd = dsb(0.005, 0.5, 3, 0.01, 0.1, " mm/s")
        self.pcy_low.setToolTip("Unload floor — kept well above 0 N so the specimen never goes slack "
                                "or into compression between cycles.")
        self.modeStack.addWidget(page([("1st peak", self.pcy_start), ("Peak step", self.pcy_step),
                                       ("Unload to", self.pcy_low), ("Speed", self.pcy_spd)]))
        seg.addWidget(self.modeStack)
        self.modeCombo.currentIndexChanged.connect(self.modeStack.setCurrentIndex)

        self.modeStartButton = QPushButton("Start test")
        self.modeStartButton.setToolTip("Run the chosen closed-loop mode. Use a SCRAP specimen first and keep a hand near "
                                        "Emergency Stop.\nRelaxation/creep just HOLD; cyclic REVERSES load↔unload. Same "
                                        "stall / force-travel safety net as the strain-rate mode.")
        self.modeStartButton.clicked.connect(self.on_control_mode_start)
        self.modeStartButton.setEnabled(False)
        seg.addWidget(self.modeStartButton)

        # Give the segment its OWN titled frame. Previously it was a bare layout dropped into the
        # Motor Control group with only a thin rule above it, so it ran straight into the specimen
        # and fracture controls below and the operator could not see where one ended and the next
        # began. A QGroupBox draws the boundary the eye is looking for.
        #
        # NOT a checkable QGroupBox, deliberately: Qt auto-disables every child of an unchecked
        # checkable group, which would kill the Start/STOP button mid-run. `_update_control_mode_
        # enabled` keeps that button live while a policy is running precisely so the operator can
        # always cancel. The enable checkbox therefore stays an ordinary child.
        from PyQt6.QtWidgets import QGroupBox
        self.advancedModesGroup = QGroupBox("Advanced test modes  (BETA)")
        self.advancedModesGroup.setObjectName("advancedModesGroup")   # styled as a NESTED group
        self.advancedModesGroup.setLayout(seg)
        self.advancedModesGroup.setToolTip("The six closed-loop protocols. Left disabled, the type and "
                                           "settings stay greyed so they cannot be changed by accident.")

        lay = self.motorControlGroup.layout()
        idx = lay.indexOf(self.emergencyStopButton)
        lay.insertWidget(idx, self.advancedModesGroup) if idx >= 0 else lay.addWidget(self.advancedModesGroup)
        self._update_control_mode_enabled()                 # start greyed until the operator enables it

    def _update_control_mode_enabled(self):
        """Grey the advanced-mode entries unless the segment is enabled (the header checkbox). The
        Start button additionally needs a live connection (tracked in self._testmode_direction_ok).
        While an advanced test is running the type/settings lock, but the Stop button stays live."""
        if getattr(self, "modeEnableCheck", None) is None:
            return
        running = getattr(self, "active_policy", None) is not None
        en = self.modeEnableCheck.isChecked()
        for w in (self.modeCombo, self.modeHelpButton, self.modeStack):
            w.setEnabled(en and not running)                # disabling the stack greys every spin box in it
        # keep help available even mid-run; only the editable type/settings lock
        self.modeHelpButton.setEnabled(en)
        if running:
            self.modeStartButton.setEnabled(True)           # never lock the operator out of Stop
        else:
            self.modeStartButton.setEnabled(en and getattr(self, "_testmode_direction_ok", False))

    def on_control_mode_start(self):
        """Start (or, if running, cancel) the advanced closed-loop mode chosen in the segment."""
        if getattr(self, "active_policy", None) is not None:
            self._stop_policy("cancelled by user"); return
        if not self._capture_ask_folder_before_test():      # before ANY motor command
            return
        if not self.connected or not self.motorsSwitch.isChecked():
            self.append_to_console("[Mode] Connect and enable motors first."); return
        if self.preload_active:
            self.append_to_console("[Mode] Finish or cancel the preload first."); return
        from control_policies import CyclicPolicy, StaircasePolicy, RelaxationPolicy, CreepPolicy
        m = self.modeCombo.currentText()
        expected = None
        if m == "Cyclic":
            lo, hi = self.cyc_lo.value(), self.cyc_hi.value()
            if hi <= lo:
                self.append_to_console("[Mode] Cyclic: High force must be > Low force."); return
            if lo < 20:
                # keep the specimen in tension between cycles: a ~0 N floor lets an inter-sample
                # overshoot push a thin dogbone into compression / buckling.
                self.append_to_console("[Mode] Cyclic: keep Low ≥ 20 N so the specimen stays in tension."); return
            policy = CyclicPolicy(lo, hi, int(self.cyc_n.value()), speed=self.cyc_spd.value(),
                                  waveform=self.cyc_wave.currentText().lower())
            # Cyclic used to pass no expected duration, so it inherited the bare 900 s runaway
            # timeout no matter how much work was asked for. A wide-bound run is far slower than a
            # narrow one (T6.3 took 27.6 s/cycle over 0.87 mm; a 400->1100 N sweep is ~3.4x the
            # travel, ~93 s/cycle), so 8 wide cycles project to ~770 s = 86 % of the guard — it
            # would abort a legitimate test near the end. Budget per cycle instead.
            expected = int(self.cyc_n.value()) * 120.0
        elif m == "Staircase":
            start, step, n = self.stc_start.value(), self.stc_step.value(), int(self.stc_n.value())
            levels = [start + i * step for i in range(n)]
            policy = StaircasePolicy(levels, self.stc_dwell.value(), speed=self.stc_spd.value(),
                                     ramp_shape=self.stc_shape.currentText().lower())
            expected = n * self.stc_dwell.value()          # total dwell time (ramps covered by the +300 s margin)
        elif m == "Relaxation":
            policy = RelaxationPolicy(self.rlx_strain.value(), self.rlx_dur.value(), speed=self.rlx_spd.value())
            expected = self.rlx_dur.value()
        elif m == "Creep":
            policy = CreepPolicy(self.crp_load.value(), self.crp_dur.value(), ramp_speed=self.crp_spd.value())
            expected = self.crp_dur.value()
        elif m.startswith("Staircase →"):
            if not self._confirm_destructive(
                    "Staircase to FRACTURE",
                    f"Steps the load up in {self.sfr_step.value():.0f} N increments from "
                    f"{self.sfr_start.value():.0f} N, dwelling {self.sfr_dwell.value():.0f} s at each level, "
                    "and KEEPS STEPPING until the specimen breaks."):
                return
            from control_policies import StaircaseToFracturePolicy
            policy = StaircaseToFracturePolicy(self.sfr_start.value(), self.sfr_step.value(),
                                               self.sfr_dwell.value(), speed=self.sfr_spd.value(),
                                               ramp_shape=self.sfr_shape.currentText().lower())
            expected = 40 * self.sfr_dwell.value()     # unknown level count -> allow a long run
        else:  # Progressive cyclic → FRACTURE
            if self.pcy_start.value() <= self.pcy_low.value():
                self.append_to_console("[Mode] Progressive cyclic: 1st peak must be > the unload floor."); return
            if not self._confirm_destructive(
                    "Progressive cyclic to FRACTURE",
                    f"Load-unload-reload with the peak rising {self.pcy_step.value():.0f} N each cycle "
                    f"(first peak {self.pcy_start.value():.0f} N, unloading to {self.pcy_low.value():.0f} N), "
                    "and KEEPS CYCLING until the specimen breaks."):
                return
            from control_policies import ProgressiveCyclicPolicy
            policy = ProgressiveCyclicPolicy(self.pcy_start.value(), self.pcy_step.value(),
                                             f_low=self.pcy_low.value(), speed=self.pcy_spd.value())
            expected = 900.0
        self._start_policy(policy, self.modeStartButton, "Start test", expected_duration_s=expected)

    # ---- small cross-session memory (Qt's own store; no new file to manage) -------------------
    def _remember(self, key, value):
        """Persist one operator setting across restarts. Deliberately tiny: only things whose reset
        would silently corrupt a RECORD, not general UI state."""
        try:
            from PyQt6.QtCore import QSettings
            QSettings("JU", "UTM_DIC").setValue(key, value)
        except Exception:
            pass

    def _recall(self, key, default=None):
        try:
            from PyQt6.QtCore import QSettings
            v = QSettings("JU", "UTM_DIC").value(key, default)
            return default if v is None else v
        except Exception:
            return default

    def _recall_bool(self, key, default=False):
        """Booleans need their own reader.

        QSettings on Windows round-trips a bool through the INI as the string "false", and
        bool("false") is True — so a plain _recall() reads every stored False back as True. Ask
        QSettings to do the conversion instead of guessing at the string.
        """
        try:
            from PyQt6.QtCore import QSettings
            return bool(QSettings("JU", "UTM_DIC").value(key, default, type=bool))
        except Exception:
            return default

    def _restore_infill(self):
        """Reinstate the last infill %, and SAY SO — a restored value that appears silently is just
        a different way to be wrong."""
        last = self._recall("specimen/infill_pct", None)
        if last is None:
            return
        try:
            val = int(last)
        except (TypeError, ValueError):
            return
        if 0 <= val <= 100:
            self.infillSpinBox.setValue(val)
            # The console does not exist yet during widget construction, so defer the notice to the
            # first turn of the event loop.
            try:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.append_to_console(
                    f"[Settings] Infill restored to {val} % from the last session. "
                    "It is a LABEL only — change it now if this specimen differs."))
            except Exception:
                pass

    def _confirm_destructive(self, title, what):
        """Fracture protocols destroy the specimen, so make the operator confirm — same discipline as
        the Fracture test button. Returns True to proceed."""
        from PyQt6.QtWidgets import QMessageBox
        # Echo the specimen metadata back: a destructive run cannot be repeated, so a stale label
        # (e.g. Infill left at 100 % for a 50 % specimen — happened on T7.2) is only catchable here.
        try:
            meta = (f"Specimen: {self.areaSpinBox.value():.1f} mm² · gauge "
                    f"{self.gaugeLengthSpinBox.value():.1f} mm · INFILL {self.infillSpinBox.value()} %")
        except Exception:
            meta = ""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(f"{title} — destructive test")
        msg.setText(f"Run {title}?  This DESTROYS the specimen.")
        msg.setInformativeText(what + "\n\n" + meta +
                               "\n\nConfirm you have:\n" + self._prep_checklist() +
                               "   •  set the specimen dimensions + INFILL above correctly\n\n"
                               "Stop / E-Stop aborts at any time.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def on_mode_help(self):
        """Pop up an annotated diagram of the currently-selected test type + a one-line caption, so the
        operator sees exactly what each setting in the row controls. Images from ui_help/ (generated by
        generate_mode_help.py)."""
        import os
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
        from PyQt6.QtGui import QPixmap
        mode = self.modeCombo.currentText()
        # slug: the fracture modes contain "→" and spaces, which don't belong in a filename
        slug = mode.lower().replace("→", "to").replace(" ", "_").strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_help", f"{slug}.png")
        caps = {
            "Cyclic": "Repeatedly loads then unloads the specimen between Low and High force for the given "
                      "number of Cycles (Speed = peak ramp rate). Reveals hysteresis / stiffness change per "
                      "cycle. Waveform: Triangle (constant-speed ramps) or Sine (eases at each peak — smooth "
                      "cycles). Both stay within Low/High; period is emergent, not set — low frequency only.",
            "Staircase": "Steps the load up — Start, Start+Step, Start+2·Step … for Levels steps — holding "
                         "(Dwell) at each so you can read the stress-relaxation at every level. Ramp: Linear "
                         "(constant speed) or Smooth (eases into each level — gentler arrival).",
            "Relaxation": "Ramps to a fixed strain (needs DIC), then holds the crosshead still for Duration "
                          "while the force decays — the material's stress-relaxation response.",
            "Creep": "Ramps to a fixed Load, then holds that force ~constant for Duration while the strain "
                     "slowly grows — the material's creep response.",
            "Staircase → FRACTURE": "DESTRUCTIVE. Like Staircase, but it keeps adding steps until the specimen "
                     "breaks. One specimen gives the modulus re-measured at every level, a mini "
                     "stress-relaxation at every level, and a sharp yield onset — the dwell drop stays small "
                     "while elastic then grows abruptly once a level passes yield.",
            "Progressive cyclic → FRACTURE": "DESTRUCTIVE. Load–unload–reload with the peak rising each cycle "
                     "until fracture. Every unload measures the modulus at that damage state, so one specimen "
                     "yields the stiffness-degradation curve D = 1 − Eᵢ/E₀ vs stress, the permanent set per "
                     "cycle, and the hysteresis energy as it evolves toward failure.",
        }
        limits = {
            "Cyclic": "Limits — Low 20–5000 N (kept in tension) · High > Low, ≤5000 N · Cycles 1–1000 · "
                      "Speed 0.005–0.5 mm/s.  Keep High below yield to avoid fatigue fracture.",
            "Staircase": "Limits — Start 0–5000 N · Step 10–2000 N · Levels 1–20 · Dwell 1–600 s · "
                         "Speed 0.005–0.5 mm/s.  Keep the top level (Start+(Levels−1)·Step) below yield.",
            "Relaxation": "Limits — Hold strain 0.001–0.2 (keep below yield ≈0.015 for an elastic hold) · "
                          "Duration 1–3600 s · Speed 0.005–0.5 mm/s.  Needs DIC green 2/2.",
            "Creep": "Limits — Load 10–5000 N (use ≤60–70% of UTS to avoid runaway) · Duration 1–3600 s · "
                     "Speed 0.005–0.5 mm/s.",
            "Staircase → FRACTURE": "Limits — Start 0–5000 N · Step 10–2000 N · Dwell 1–600 s · "
                     "Speed 0.005–0.5 mm/s · max 60 levels.  Pick Step so ~8–12 levels reach fracture "
                     "(100% infill breaks ≈3.2–3.4 kN, 50% ≈1.3–1.8 kN): too fine and the run drags, "
                     "too coarse and you lose resolution near yield.",
            "Progressive cyclic → FRACTURE": "Limits — 1st peak 0–5000 N (> unload floor) · Peak step "
                     "10–2000 N · Unload to 20–2000 N · Speed 0.005–0.5 mm/s · max 40 cycles.  Keep the "
                     "unload floor ≥20 N so the specimen never goes slack.",
        }
        backstops = ("Always-on safety net (any mode): 10 kN force · 30 mm travel · stall guard · E-Stop.  "
                     "Motor delivers ~3.2–3.4 kN normally (all six 100% infill specimens fractured there); "
                     "a session that stalls nearer ~2.6 kN is thermally derated, not a hard ceiling.")
        # The three colours below were picked against a white dialog: #333 body text is all but
        # invisible on a dark background, and the #0a6 / #a33 accents lose their punch. Read them
        # from the active palette instead. The diagram itself is a white-background PNG generated
        # offline, so rather than let it sit as a glaring hole it is mounted on an explicit white
        # card with a border — it then reads as a FIGURE, which is the usual way to place a light
        # diagram in a dark UI.
        import theme as _theme
        t = _theme.get(getattr(self, "_theme", _theme.DEFAULT))
        dark = t["name"] == "dark"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"{mode} test — parameters")
        lay = QVBoxLayout(dlg)
        img = QLabel(); pix = QPixmap(path)
        if pix.isNull():
            img.setText(f"(diagram not found — run generate_mode_help.py)\n{path}")
        else:
            img.setPixmap(pix)
        img.setStyleSheet(
            "background: #ffffff; border: 1px solid %s; border-radius: 6px; padding: 6px;"
            % (t["border"] if dark else "#cccccc"))
        lay.addWidget(img)
        wmax = max(360, pix.width())
        cap = QLabel(caps.get(mode, "")); cap.setWordWrap(True)
        cap.setStyleSheet("color:%s; padding:4px 2px;" % t["text"]); cap.setMaximumWidth(wmax)
        lay.addWidget(cap)
        lim = QLabel(limits.get(mode, "")); lim.setWordWrap(True)
        lim.setStyleSheet("color:%s; font-weight:bold; padding:2px;" % t["ok"])
        lim.setMaximumWidth(wmax)
        lay.addWidget(lim)
        net = QLabel(backstops); net.setWordWrap(True)
        net.setStyleSheet("color:%s; padding:2px 2px 6px 2px;" % t["bad"])
        net.setMaximumWidth(wmax)
        lay.addWidget(net)
        dlg.exec()

    def _start_policy(self, policy, button=None, start_label="Start mode", expected_duration_s=None):
        """Arm a control policy: latch tension ONCE, then live SetSpeed only (preload discipline).
        `expected_duration_s` (relaxation/creep/staircase holds) extends the runaway timeout so a
        legitimately long hold is not cut off at the 900 s default."""
        import time
        from control_policies import Signals
        from control_policies import StrainRatePolicy, RelaxationPolicy, CyclicPolicy, StaircasePolicy
        self.active_policy = policy
        # Waveform modes sweep the speed continuously, so the 0.01 mm/s SetSpeed deadband would
        # quantise a 0.01-0.10 mm/s sine into only ~10 velocity steps (visible as straight, stepped
        # flanks in T6). Use a finer deadband for those; the 0.15 s throttle still caps the command
        # rate. Strain-rate keeps the coarse deadband (its speed is near-constant; avoids jitter).
        self._policy_speed_eps = 0.002 if isinstance(policy, (CyclicPolicy, StaircasePolicy)) else 0.01
        self._policy_timeout_s = (self.POLICY_TIMEOUT_S if expected_duration_s is None
                                  else max(self.POLICY_TIMEOUT_S, expected_duration_s + 300))
        self._policy_button = button
        self._policy_start_label = start_label
        self._capture_autostart(getattr(policy, "name", "test mode"))
        self._policy_last_speed = 0.0; self._policy_last_speed_t = 0.0
        self._policy_start_t = time.monotonic()
        self._policy_msg_t = 0.0                             # throttle for the ~1 Hz live-progress status line
        self._policy_dir = "tension"                        # firmware direction currently latched (tension|compression|hold)
        self._policy_uses_dic = isinstance(policy, (StrainRatePolicy, RelaxationPolicy))  # DIC-steered → dead-DIC guard
        self._policy_dic_watch = (self.latest_dic_cauchy, self._policy_start_t)
        self._stall_hist = []                               # arm the stall guard for this run
        first = policy.step(Signals(t=self._policy_start_t, load=self.current_load,
                                    pos=self.motor_displacement_mm, strain=self.latest_dic_cauchy))
        self.upRadioButton.blockSignals(True); self.upRadioButton.setChecked(True); self.upRadioButton.blockSignals(False)
        self.serial_manager.send_command(f"SetSpeed {self._fw_speed(max(first.speed, 0.02))}")
        self.serial_manager.send_command("Down")     # firmware Down = physical tension on this rig
        self._start_movement_grace_period()
        if button is not None:
            button.setText("Stop mode")
        self._update_control_mode_enabled()                 # lock type/settings while a test runs
        self.append_to_console(f"[Mode] {policy.start_message()}")
        self.set_status(f"Test mode: {policy.name} ...")

    def _policy_step(self):
        """Per-load-sample control step (mirrors _preload_check): safety net → policy → direction/SetSpeed.
        Handles tension / compression / hold so cyclic·staircase·relaxation·creep run, not just the
        tension-only strain-rate pull. Guards are PHASE-AWARE: the stall guard is silent during an
        intentional HOLD (dwell/relaxation/creep hold), and the dead-DIC guard applies only to
        DIC-steered modes (strain-rate / relaxation ramp)."""
        import time
        from control_policies import Signals
        now = time.monotonic()
        # hard safety net, independent of the policy
        if self.current_load >= self.POLICY_MAX_FORCE_N or abs(self.motor_displacement_mm) >= self.POLICY_MAX_TRAVEL_MM:
            if self.connected:
                self.serial_manager.send_command("Stop"); self.serial_manager.send_command("EStop")
            self._stop_policy(f"SAFETY halt — {self.current_load:.0f} N / {self.motor_displacement_mm:.1f} mm", warn=True)
            return
        if now - self._policy_start_t >= self._policy_timeout_s:
            self._stop_policy("timed out", warn=True); return
        moving = self._policy_dir in ("tension", "compression")
        # STALL GUARD — only while the motor is COMMANDED to move (never during an intentional hold, or
        # the dwell/relaxation/creep holds would false-trip it). Commanded to move but crosshead frozen
        # under load -> halt. The DIC-staleness guard MISSES a motor stall at its force ceiling because
        # the specimen keeps creeping (S17 jittered 62 s at ~2.9 kN with no auto-halt).
        if moving:
            self._stall_hist.append((now, self.motor_displacement_mm, self._policy_last_speed))
            while self._stall_hist and now - self._stall_hist[0][0] > self.STALL_WINDOW_S:
                self._stall_hist.pop(0)
            if (self.current_load > self.STALL_MIN_LOAD_N and self._stall_hist
                    and now - self._stall_hist[0][0] >= self.STALL_WINDOW_S - 0.5):
                advanced = abs(self.motor_displacement_mm - self._stall_hist[0][1])
                cmd_avg = sum(h[2] for h in self._stall_hist) / len(self._stall_hist)
                need = self._stall_threshold_mm(cmd_avg)
                if need > 0 and advanced < need:
                    if self.connected:
                        self.serial_manager.send_command("Stop"); self.serial_manager.send_command("EStop")
                    self._stop_policy(
                        f"STALL — crosshead advanced {advanced:.3f} mm in {self.STALL_WINDOW_S:.0f} s "
                        f"(needed {need:.3f}; commanded ~{cmd_avg:.4f} mm/s = {cmd_avg * self.STALL_WINDOW_S:.3f} mm) "
                        f"at {self.current_load:.0f} N — motor hit its force limit", warn=True)
                    return
        # DIC-staleness guard (DIC-steered modes only), staged so a strain-rate loop can never ramp the
        # speed up blind: (a) FREEZE the speed once strain has been stale > STALE_FREEZE_S, then
        # (b) hard-HALT if it stays frozen > DEAD_DIC_S (camera lost). Force-steered modes (cyclic /
        # staircase / creep) read the load cell, which never goes stale, so they skip this.
        stale = 0.0
        if self._policy_uses_dic:
            last_val, last_t = self._policy_dic_watch
            if abs(self.latest_dic_cauchy - last_val) > 1e-5:
                self._policy_dic_watch = (self.latest_dic_cauchy, now)
            stale = now - last_t
            if self._policy_last_speed > 0 and stale > self.POLICY_DEAD_DIC_S:
                if self.connected:
                    self.serial_manager.send_command("Stop")
                self._stop_policy("DIC strain frozen (camera lost?) — halted for safety", warn=True); return
        cmd = self.active_policy.step(Signals(t=now, load=self.current_load,
                                              pos=self.motor_displacement_mm, strain=self.latest_dic_cauchy))
        if cmd.done:
            self._stop_policy(cmd.message); return
        if cmd.message and now - getattr(self, "_policy_msg_t", 0.0) >= 1.0:
            self.set_status(f"Test mode: {cmd.message}")   # ~1 Hz live heartbeat (e.g. "creep 12/60 s")
            self._policy_msg_t = now
        want = cmd.direction
        # ---- HOLD: stop the crosshead; holding torque keeps position (rig-confirmed) ----
        if want == "hold":
            if self._policy_dir != "hold":
                if self.connected:
                    self.serial_manager.send_command("Stop")
                self.stopRadioButton.blockSignals(True); self.stopRadioButton.setChecked(True); self.stopRadioButton.blockSignals(False)
                self._policy_dir = "hold"; self._policy_last_speed = 0.0; self._stall_hist = []
            return
        # ---- MOVE: tension (firmware Down) or compression (firmware Up) ----
        fw = "Down" if want == "tension" else "Up"
        spd = cmd.speed
        if self._policy_uses_dic and want == "tension" and stale > self.POLICY_STALE_FREEZE_S:
            spd = self._policy_last_speed          # strain stale -> HOLD last good speed, never accelerate blind
        if want != self._policy_dir:
            # direction change / resume from hold: latch the new direction (direct reversal is clean —
            # rig-confirmed auto-decel ~1 s). SetSpeed first, then the direction command.
            if self.connected:
                self.serial_manager.send_command(f"SetSpeed {self._fw_speed(max(spd, 0.02))}")
                self.serial_manager.send_command(fw)
            rb = self.upRadioButton if want == "tension" else self.downRadioButton
            rb.blockSignals(True); rb.setChecked(True); rb.blockSignals(False)
            self._policy_dir = want; self._policy_last_speed = spd; self._policy_last_speed_t = now
            self._stall_hist = []                  # fresh baseline after a reversal (net travel resets)
        elif (abs(spd - self._policy_last_speed) >= getattr(self, "_policy_speed_eps", 0.01)
                and now - self._policy_last_speed_t >= 0.15):
            self._policy_last_speed = spd; self._policy_last_speed_t = now
            if self.connected:
                self.serial_manager.send_command(f"SetSpeed {self._fw_speed(spd)}")

    def _stop_policy(self, message, warn=False):
        """Stop the motor and end the active test-mode policy (mirrors _stop_preload)."""
        self._dump_policy_log(getattr(self, 'active_policy', None))
        self.active_policy = None
        self.movement_start_grace_period = False
        if getattr(self, 'grace_period_timer', None) is not None:
            self.grace_period_timer.stop()
        self.stopRadioButton.blockSignals(True); self.stopRadioButton.setChecked(True); self.stopRadioButton.blockSignals(False)
        if self.connected:
            self.serial_manager.send_command("Stop")
        btn = getattr(self, '_policy_button', None)
        if btn is not None:
            btn.setText(getattr(self, '_policy_start_label', 'Start mode'))
        self._update_control_mode_enabled()                 # restore type/settings now the test ended
        self._capture_autostop("test mode")
        self.append_to_console(f"[Mode] {message}")
        self.set_status(f"Test mode: {message}", is_warning=warn)

    def _dump_policy_log(self, policy):
        """Fracture protocols accumulate a per-level / per-cycle record in `policy.log`. Print it as a
        table when the mode ends so the operator can read the result immediately — the CSV still has
        the full time series for proper offline analysis."""
        log = getattr(policy, "log", None)
        if not log:
            return
        try:
            name = getattr(policy, "name", "mode")
            self.append_to_console(f"[Mode] --- {name} summary ({len(log)} records) ---")
            if name == "staircase-fracture":
                self.append_to_console("[Mode]  level   target    arrive      end   relax-drop")
                for e in log:
                    if e.get("event") == "fracture":
                        self.append_to_console(f"[Mode]  FRACTURE on level {e['level']} "
                                               f"(target {e['level_N']:.0f} N) at {e['load']:.0f} N")
                    else:
                        self.append_to_console(
                            f"[Mode]  {e['level']:5d}  {e['level_N']:7.0f}  {e['arrive_load']:8.0f}  "
                            f"{e['end_load']:7.0f}  {e['relax_drop_N']:9.1f} N")
            elif name == "progressive-cyclic":
                self.append_to_console("[Mode]  cycle   target     peak   trough    unload-K (N/mm)")
                for e in log:
                    if e.get("event") == "fracture":
                        self.append_to_console(f"[Mode]  FRACTURE on cycle {e['cycle']} "
                                               f"at peak {e['fracture_peak']:.0f} N")
                        continue
                    if "trough_load" not in e or "peak_load" not in e:
                        continue
                    dF = e["peak_load"] - e["trough_load"]
                    dP = e["peak_pos"] - e["trough_pos"]
                    ku = (dF / dP) if abs(dP) > 1e-6 else float("nan")
                    self.append_to_console(
                        f"[Mode]  {e['cycle']:5d}  {e['target_N']:7.0f}  {e['peak_load']:7.0f}  "
                        f"{e['trough_load']:7.0f}  {ku:14.0f}")
        except Exception as e:
            self.append_to_console(f"[Mode] could not print summary: {e}")

    # ===== Recipes / Prepare-specimen / Auto-stop-at-fracture (offline-built helpers) =====
    def _setup_recipe_controls(self):
        """Add a Recipe dropdown + Load/Save, a 'Prepare test' one-button, and an
        'Auto-stop at fracture' toggle to the Motor Control group. Recipes come from
        utm_recipes.py; auto-stop reuses the shared LiveFractureDetector during a MANUAL pull."""
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QPushButton, QCheckBox, QSpinBox
        r1 = QHBoxLayout()
        settings_help = ("Save your specimen & test settings — dimensions, DIC mode, preload, speed, infill — "
                         "under a name and reuse them in one click. Pick a saved profile here, then press Load "
                         "to apply it; press Save… to store the current inputs. The starter profile — "
                         "'Default' — is always available and carries sensible settings for every test "
                         "type, including the fracture protocols. Adjust the forces to the specimen "
                         "before a destructive run.")
        settings_label = QLabel("Settings:"); settings_label.setToolTip(settings_help)
        r1.addWidget(settings_label)
        self.recipeCombo = QComboBox(); self.recipeCombo.setMinimumWidth(150)
        self.recipeCombo.setToolTip(settings_help)
        self.recipeLoadButton = QPushButton("Load")
        self.recipeSaveButton = QPushButton("Save…")
        self.recipeLoadButton.setToolTip("Load — apply the selected saved settings to all the inputs "
                                         "(dimensions, DIC mode, preload, speed, infill).")
        self.recipeSaveButton.setToolTip("Save… — store the current inputs as a named settings profile you can reload later.")
        r1.addWidget(self.recipeCombo); r1.addWidget(self.recipeLoadButton); r1.addWidget(self.recipeSaveButton)
        r1.addSpacing(16)
        r1.addWidget(QLabel("Infill %:"))
        self.infillSpinBox = QSpinBox()
        self.infillSpinBox.setRange(0, 100)
        self.infillSpinBox.setValue(100)
        self.infillSpinBox.setToolTip("Infill % does NOT change any recorded test data. It is a label only — "
                                      "kept for the saved settings, the CSV header and the report.\n"
                                      "Remembered across restarts, so set it once per SPECIMEN.")
        # Infill is a LABEL, so nothing downstream ever catches a stale one, and the only gate that
        # echoes it back is the destructive-test confirm dialog. A NON-destructive run (cyclic,
        # creep) has no such gate — which is exactly how T6.4, T6.5 and both T9 runs recorded
        # "Infill: 100 %" on 50 % specimens while T7.3, a destructive run, came out right.
        # Fix: remember it across restarts so it is set once per SPECIMEN, not once per session.
        self._restore_infill()
        self.infillSpinBox.valueChanged.connect(
            lambda v: self._remember("specimen/infill_pct", int(v)))
        r1.addWidget(self.infillSpinBox)
        r2 = QHBoxLayout()
        self.prepareTestButton = QPushButton("Prepare test")
        self.prepareTestButton.setObjectName("prepareTestButton")   # emphasised by theme
        self.prepareTestButton.setToolTip(
            "One click: clear the consoles and plots, then tare POSITION and FORCE so the test "
            "starts from zero.\n\nIt does NOT touch Px₀ — only the Calibrate Px₀ button moves the "
            "pixel reference. Prepare reports what Px₀ currently is, and warns if it was never set.")
        self.autoStopFractureCheck = QCheckBox("Auto-stop at fracture")
        self.autoStopFractureCheck.setObjectName("autoStopFractureCheck")   # emphasised by theme
        self.autoStopFractureCheck.setToolTip("During a MANUAL tension pull, stop the motor automatically when the "
                                              "load collapses (fracture). Same detector as the offline analysis.")
        self.autoStopFractureCheck.setChecked(True)   # on by default (safety); a loaded profile can override
        self.fractureTestButton = QPushButton("Fracture test")
        self.fractureTestButton.setObjectName("fractureTestButton")         # emphasised by theme
        self.fractureTestButton.setToolTip("One-click run to fracture: confirms your checklist (specimen mounted, "
                                           "preloaded, Prepare test done), then pulls in TENSION and auto-stops "
                                           "at fracture (with the force/travel backstop). Stop / E-Stop aborts.")
        r2.addWidget(self.prepareTestButton); r2.addWidget(self.autoStopFractureCheck)
        r2.addWidget(self.fractureTestButton); r2.addStretch()

        # These are the two buttons an operator reaches for most often, and they were the hardest to
        # find: bare rows wedged between the advanced-mode block and Emergency STOP. Their own titled
        # frame separates them from the protocols above, and the run order reads top to bottom —
        # pick a settings profile, Prepare test, then Fracture test.
        from PyQt6.QtWidgets import QGroupBox, QVBoxLayout
        self.specimenTestGroup = QGroupBox("Specimen  ·  prepare and fracture")
        self.specimenTestGroup.setObjectName("specimenTestGroup")     # styled as a NESTED group
        _stg = QVBoxLayout(self.specimenTestGroup)
        _stg.setContentsMargins(6, 4, 6, 4); _stg.setSpacing(4)
        _stg.addLayout(r1)          # settings profile + infill  (set up first)
        _stg.addLayout(r2)          # Prepare test · auto-stop · Fracture test  (then run)
        self.prepareTestButton.setMinimumHeight(28)
        self.fractureTestButton.setMinimumHeight(28)

        lay = self.motorControlGroup.layout()
        idx = lay.indexOf(self.advancedModesGroup)          # sit ABOVE the advanced modes
        if idx < 0:
            idx = lay.indexOf(self.emergencyStopButton)
        if idx >= 0:
            lay.insertWidget(idx, self.specimenTestGroup)
        else:
            lay.addWidget(self.specimenTestGroup)
        self.recipeLoadButton.clicked.connect(self.on_recipe_load)
        self.recipeSaveButton.clicked.connect(self.on_recipe_save)
        self.prepareTestButton.clicked.connect(self.on_prepare_test)
        self.fractureTestButton.clicked.connect(self.on_fracture_test)
        try:
            from utm_recipes import ensure_default
            ensure_default()
        except Exception:
            pass
        self._refresh_recipes()
        # 100 % infill is the headline specimen type, so it is the profile the app opens on. The
        # combo is name-sorted and "1" < "5", so it is also index 0 — the findText keeps the
        # intent explicit (and correct) if a user later adds a profile that sorts above it.
        from utm_recipes import DEFAULT
        # Reopen on the profile last used, falling back to the 100 % default. Always reopening on
        # Always reopening on the starter is what made the infill label reset every session
        # (see _restore_infill).
        i = self.recipeCombo.findText(str(self._recall("settings/last_profile", DEFAULT)))
        if i < 0:
            i = self.recipeCombo.findText(DEFAULT)
        if i >= 0:
            self.recipeCombo.blockSignals(True)      # widgets may not all exist yet
            self.recipeCombo.setCurrentIndex(i)
            self.recipeCombo.blockSignals(False)
        # PICKING a profile now APPLIES it. Previously the combo only changed the label and the
        # operator had to notice the separate Load button, so selecting another profile looked
        # like it did nothing at all -- and a test could be run under whatever was on screen before.
        self.recipeCombo.currentIndexChanged.connect(self._on_recipe_selected)

    def _refresh_recipes(self):
        """Repopulate the recipe dropdown from recipes/*.json, preserving the selection."""
        if getattr(self, 'recipeCombo', None) is None:
            return
        try:
            from utm_recipes import list_recipes
            recipes = list_recipes()
        except Exception as e:
            self.append_to_console(f"[Settings] could not list saved settings: {e}"); return
        cur = self.recipeCombo.currentText()
        self.recipeCombo.blockSignals(True)
        self.recipeCombo.clear()
        for r in recipes:
            self.recipeCombo.addItem(r.name)
        i = self.recipeCombo.findText(cur)
        if i >= 0:
            self.recipeCombo.setCurrentIndex(i)
        self.recipeCombo.blockSignals(False)

    def _mode_widget_map(self):
        """Advanced-test-mode parameter widgets, keyed by the EXACT dropdown label then by the
        recipe key. Used by BOTH recipe save and load, so the two can never drift apart — adding
        a mode means adding one entry here and nothing else."""
        m = {}
        def add(label, **kw):
            if all(v is not None for v in kw.values()):   # skip if the UI isn't built yet
                m[label] = kw
        add("Cyclic", low=getattr(self, "cyc_lo", None), high=getattr(self, "cyc_hi", None),
            cycles=getattr(self, "cyc_n", None), speed=getattr(self, "cyc_spd", None),
            waveform=getattr(self, "cyc_wave", None))
        add("Staircase", start=getattr(self, "stc_start", None), step=getattr(self, "stc_step", None),
            levels=getattr(self, "stc_n", None), dwell=getattr(self, "stc_dwell", None),
            speed=getattr(self, "stc_spd", None), ramp=getattr(self, "stc_shape", None))
        add("Relaxation", strain=getattr(self, "rlx_strain", None),
            duration=getattr(self, "rlx_dur", None), speed=getattr(self, "rlx_spd", None))
        add("Creep", load=getattr(self, "crp_load", None), duration=getattr(self, "crp_dur", None),
            speed=getattr(self, "crp_spd", None))
        add("Staircase → FRACTURE", start=getattr(self, "sfr_start", None),
            step=getattr(self, "sfr_step", None), dwell=getattr(self, "sfr_dwell", None),
            speed=getattr(self, "sfr_spd", None), ramp=getattr(self, "sfr_shape", None))
        add("Progressive cyclic → FRACTURE", first_peak=getattr(self, "pcy_start", None),
            peak_step=getattr(self, "pcy_step", None), unload_to=getattr(self, "pcy_low", None),
            speed=getattr(self, "pcy_spd", None))
        return m

    def _read_mode_params(self):
        """Snapshot EVERY mode's settings (not just the selected one) so switching mode after a
        load still gives sane values."""
        out = {}
        for label, widgets in self._mode_widget_map().items():
            vals = {}
            for key, w in widgets.items():
                try:
                    vals[key] = w.currentText() if hasattr(w, "currentText") else w.value()
                except Exception:
                    continue
            if vals:
                out[label] = vals
        return out

    def _apply_mode_params(self, params):
        """Restore per-mode settings. Silently skips anything unknown so an older/newer recipe
        never blocks a load."""
        if not isinstance(params, dict):
            return
        wm = self._mode_widget_map()
        for label, vals in params.items():
            widgets = wm.get(label)
            if not widgets or not isinstance(vals, dict):
                continue
            for key, v in vals.items():
                w = widgets.get(key)
                if w is None:
                    continue
                try:
                    if hasattr(w, "currentText"):
                        i = w.findText(str(v))
                        if i >= 0:
                            w.setCurrentIndex(i)
                    else:
                        w.setValue(type(w.value())(v))      # int for QSpinBox, float for QDoubleSpinBox
                except Exception:
                    continue

    def _on_recipe_selected(self, _index):
        """Selecting a profile applies it immediately, and says so in the console."""
        name = self.recipeCombo.currentText()
        if not name:
            return
        self.on_recipe_load()
        self._remember("settings/last_profile", name)
        self.append_to_console(
            f"[Settings] applied '{name}' — dimensions, preload, speed, DIC preset, auto-stop "
            "and ALL SIX advanced-mode parameter sets. Edit any field afterwards to override it, "
            "or press Save… to store your edits as a new profile.")

    def on_recipe_load(self):
        """Apply the selected recipe to the dimension / preload / speed / DIC-mode inputs."""
        from utm_recipes import find
        r = find(self.recipeCombo.currentText())
        if r is None:
            self.append_to_console("[Settings] nothing selected."); return
        self.areaSpinBox.setValue(r.area_mm2)
        self.gaugeLengthSpinBox.setValue(r.gauge_mm)
        self.preloadTargetSpinBox.setValue(r.preload_N)
        if self.speedUnitMmRadio.isChecked():
            self.setSpeedSpinBox.setValue(r.test_speed_mm_s)
        elif self.MM_PER_S_PER_RPM > 0:
            self.setSpeedSpinBox.setValue(r.test_speed_mm_s / self.MM_PER_S_PER_RPM)
        i = self.specimenModeCombo.findText(r.specimen_mode)
        if i >= 0:
            self.specimenModeCombo.setCurrentIndex(i)
        if getattr(self, 'strainRateSpinBox', None) is not None:
            self.strainRateSpinBox.setValue(r.strain_rate)
        if getattr(self, 'autoStopFractureCheck', None) is not None:
            self.autoStopFractureCheck.setChecked(bool(r.auto_stop_fracture))
        if getattr(self, 'infillSpinBox', None) is not None:
            self.infillSpinBox.setValue(int(round(r.infill_pct)))
        # --- advanced test mode: per-mode params, then the selected mode itself ---
        self._apply_mode_params(getattr(r, "mode_params", None))
        mode_txt = ""
        if getattr(self, 'modeCombo', None) is not None and getattr(self, 'modeEnableCheck', None) is not None:
            i = self.modeCombo.findText(str(getattr(r, "mode", "manual")))
            if i >= 0:
                self.modeCombo.setCurrentIndex(i)
                self.modeEnableCheck.setChecked(True)
                mode_txt = f", mode {self.modeCombo.currentText()}"
            else:
                # "manual" (or an unknown label from a newer app) -> leave the advanced segment OFF
                self.modeEnableCheck.setChecked(False)
                mode_txt = ", mode manual"
            self._update_control_mode_enabled()
        self.append_to_console(f"[Settings] loaded '{r.name}' — "
                               f"preload {r.preload_N:.0f} N, {r.test_speed_mm_s:.3f} mm/s, "
                               f"DIC {r.specimen_mode}{mode_txt}")
        self.set_status(f"Settings '{r.name}' applied")

    def on_recipe_save(self):
        """Save the current inputs as a named recipe (prompts for a name)."""
        from PyQt6.QtWidgets import QInputDialog
        from utm_recipes import TestRecipe
        name, ok = QInputDialog.getText(self, "Save settings", "Settings name:")
        if not ok or not name.strip():
            return
        r = TestRecipe(
            name=name.strip(),
            specimen_mode=self.specimenModeCombo.currentText(),
            infill_pct=(self.infillSpinBox.value() if getattr(self, 'infillSpinBox', None) is not None else 100.0),
            area_mm2=self.areaSpinBox.value(),
            gauge_mm=self.gaugeLengthSpinBox.value(),
            preload_N=self.preloadTargetSpinBox.value(),
            test_speed_mm_s=self.get_speed_rpm() * self.MM_PER_S_PER_RPM,
            strain_rate=(self.strainRateSpinBox.value() if getattr(self, 'strainRateSpinBox', None) is not None else 0.001),
            auto_stop_fracture=(self.autoStopFractureCheck.isChecked() if getattr(self, 'autoStopFractureCheck', None) is not None else True),
            # the advanced mode is only "selected" when the segment is actually armed
            mode=(self.modeCombo.currentText()
                  if (getattr(self, 'modeEnableCheck', None) is not None
                      and self.modeEnableCheck.isChecked()
                      and getattr(self, 'modeCombo', None) is not None)
                  else "manual"),
            mode_params=self._read_mode_params(),
        )
        try:
            path = r.save()
        except Exception as e:
            self.append_to_console(f"[Settings] save failed: {e}"); return
        self._refresh_recipes()
        i = self.recipeCombo.findText(r.name)
        if i >= 0:
            self.recipeCombo.setCurrentIndex(i)
        self.append_to_console(f"[Settings] saved '{r.name}' -> {path}")
        self.set_status(f"Settings '{r.name}' saved")

    def on_prepare_test(self):
        """One click: clear the consoles and plots, then tare POSITION and FORCE.

        It does NOT touch Px₀. Only the Calibrate Px₀ button changes the pixel reference — one
        control, one owner. The previous version re-tared DIC here unless Px₀ happened to have been
        captured at a lower load, which meant calibrating and preparing at the same load silently
        moved the strain zero, and whether it did depended on a 5 N comparison the operator could
        not see. Px₀ is the denominator of every strain in the test; it should move when, and only
        when, somebody asks for it.
        """
        # Fresh start — clear both consoles + BOTH plots, so the new specimen starts on empty axes
        self.consoleTextEdit.clear()
        if hasattr(self, 'cameraConsoleTextEdit'):
            self.cameraConsoleTextEdit.clear()
        for label, fn in [("stress-strain", getattr(self, 'on_clear_stress_strain_plot', None)),
                          ("load", getattr(self, 'on_clear_load_plot', None))]:
            if callable(fn):
                try:
                    fn()
                except Exception as e:
                    self.append_to_console(f"[Prepare] could not clear {label} plot: {e}")
        done, skipped = [], []
        # Position + force always tare
        for label, fn in [("position", getattr(self, 'on_tare_location', None)),
                          ("force", getattr(self, 'on_tare', None))]:
            if callable(fn):
                try:
                    fn(); done.append(label)
                except Exception as e:
                    self.append_to_console(f"[Prepare] {label} tare failed: {e}")
        # Px₀ is REPORTED here, never changed. Reporting it matters: Prepare is the last thing
        # pressed before a pull, so it is the right moment to say out loud what the strain
        # denominator is going to be — or that there isn't one yet.
        px0 = getattr(self.camera_manager, "initial_distance", None)
        px0_load = getattr(self, "_px0_load_N", None)
        if px0:
            at = f" (captured at {px0_load:.0f} N)" if px0_load is not None else ""
            self.append_to_console(f"[Prepare] Px₀ UNCHANGED at {px0:.1f} px{at} — "
                                   "only the Calibrate Px₀ button moves it.")
        else:
            skipped.append("Px₀ never calibrated")
            self.append_to_console("[Prepare] ⚠ Px₀ has NEVER been calibrated — strain has no "
                                   "reference. Press Calibrate Px₀ (before preload) or the pull "
                                   "will record no usable strain.")

        self.append_to_console(f"[Prepare] tared: {', '.join(done) if done else 'nothing'}"
                               + "  |  Px₀ left alone")
        if skipped:
            self.set_status("Prepared — position + force tared; ⚠ Px₀ NOT calibrated yet",
                            is_warning=True)
        else:
            self.set_status("Prepared — position + force tared; Px₀ unchanged")

    def on_fracture_test(self):
        """One-click run to fracture: checklist confirm -> arm auto-stop -> pull in tension.
        Reuses the manual auto-stop path (fracture detector + force/travel backstop); Stop / E-Stop aborts."""
        from PyQt6.QtWidgets import QMessageBox
        if not self.connected:
            self.append_to_console("[Fracture test] Not connected."); return
        if not self.motorsSwitch.isChecked():
            self.append_to_console("[Fracture test] Enable motors first."); return
        if self.preload_active or getattr(self, '_release_active', False) or getattr(self, 'active_policy', None) is not None:
            self.append_to_console("[Fracture test] Finish the preload / release / test mode first."); return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Fracture test — checklist")
        msg.setText("Run the specimen to FRACTURE?")
        msg.setInformativeText("Confirm you have:\n" + self._prep_checklist() +
                               "\nOn Yes, the gripper pulls in TENSION and auto-stops at fracture. "
                               "Keep Emergency STOP in reach.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            self.append_to_console("[Fracture test] cancelled."); return
        if not self._capture_ask_folder_before_test():      # still before ANY motor command
            return
        # arm auto-stop at fracture (fresh detector)
        if getattr(self, 'autoStopFractureCheck', None) is not None:
            self.autoStopFractureCheck.setChecked(True)
        self._autostop_detector = None
        self._stall_hist = []
        # start the tension pull at the current Set speed (Up = tension; firmware "Down")
        speed_mm_s = self.get_speed_rpm() * self.MM_PER_S_PER_RPM
        self.upRadioButton.blockSignals(True); self.upRadioButton.setChecked(True); self.upRadioButton.blockSignals(False)
        self.serial_manager.send_command(f"SetSpeed {self._fw_speed(speed_mm_s)}")
        self.serial_manager.send_command("Down")   # firmware "Down" = physical tension on this rig
        self._start_movement_grace_period()
        self._capture_autostart("fracture test")
        self.append_to_console(f"[Fracture test] pulling to fracture at {speed_mm_s:.3f} mm/s — auto-stop armed "
                               f"(backstop {self.POLICY_MAX_FORCE_N:.0f} N / {self.POLICY_MAX_TRAVEL_MM:.0f} mm). "
                               f"Press Stop / E-Stop to abort.")
        self.set_status("Fracture test — pulling to fracture ...")

    def _autostop_check(self):
        """Manual-pull fracture auto-halt: a hard force/travel backstop, then the live fracture detector."""
        # BACKSTOP (independent of the detector): hard Stop + EStop on force / travel limit,
        # so a manual auto-stop pull can't run away even if fracture detection misses.
        if self.current_load >= self.POLICY_MAX_FORCE_N or abs(self.motor_displacement_mm) >= self.POLICY_MAX_TRAVEL_MM:
            if self.connected:
                self.serial_manager.send_command("Stop"); self.serial_manager.send_command("EStop")
            self.stopRadioButton.blockSignals(True); self.stopRadioButton.setChecked(True); self.stopRadioButton.blockSignals(False)
            self._autostop_detector = None
            self.append_to_console(f"[Auto-stop] SAFETY LIMIT — halted at {self.current_load:.0f} N / "
                                   f"{abs(self.motor_displacement_mm):.1f} mm (backstop; fracture detector did not fire).")
            self.set_status("⚠ Auto-stop SAFETY limit — motor halted", is_warning=True)
            self._capture_autostop("safety halt")
            return
        # STALL GUARD: motor commanded to pull but the crosshead is frozen under load -> halt.
        # Triggers only on NEAR-ZERO movement (< STALL_MIN_ADVANCE_MM over STALL_WINDOW_S), so a
        # legitimately slow approach to fracture (still advancing) does NOT trip it.
        import time as _t
        _now = _t.monotonic()
        try:
            # the spin box holds RPM when the unit toggle is on RPM -- convert so the guard always
            # compares mm/s against mm of travel
            _cmd = float(self.setSpeedSpinBox.value())
            if not self.speedUnitMmRadio.isChecked():
                _cmd *= self.MM_PER_S_PER_RPM
        except Exception:
            _cmd = 0.1
        self._stall_hist.append((_now, self.motor_displacement_mm, _cmd))
        while self._stall_hist and _now - self._stall_hist[0][0] > self.STALL_WINDOW_S:
            self._stall_hist.pop(0)
        _advanced = abs(self.motor_displacement_mm - self._stall_hist[0][1]) if self._stall_hist else 0.0
        _need = self._stall_threshold_mm(sum(h[2] for h in self._stall_hist) / len(self._stall_hist)) \
            if self._stall_hist else 0.0
        if (self.current_load > self.STALL_MIN_LOAD_N and self._stall_hist
                and _now - self._stall_hist[0][0] >= self.STALL_WINDOW_S - 0.5
                and _need > 0 and _advanced < _need):
            if self.connected:
                self.serial_manager.send_command("Stop"); self.serial_manager.send_command("EStop")
            self.stopRadioButton.blockSignals(True); self.stopRadioButton.setChecked(True); self.stopRadioButton.blockSignals(False)
            self._autostop_detector = None; self._stall_hist = []
            self.append_to_console(f"[Stall guard] STALL — crosshead advanced {_advanced:.3f} mm in "
                                   f"{self.STALL_WINDOW_S:.0f} s (needed {_need:.3f}) at {self.current_load:.0f} N "
                                   "while commanded to move. Motor halted.")
            self.set_status("⚠ Stall guard — motor halted (no crosshead movement)", is_warning=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Stall guard activated",
                                f"The test was stopped by the STALL GUARD.\n\n"
                                f"The crosshead did not move (< {self.STALL_MIN_ADVANCE_MM:.2f} mm in "
                                f"{self.STALL_WINDOW_S:.0f} s) while the motor was commanded to pull, at "
                                f"{self.current_load:.0f} N.\n\nLikely the motor hit its force limit — check that it "
                                f"is not hot, the driver current, and for binding; or use a smaller-cross-section "
                                f"specimen so the fracture force is within the rig's capacity.")
            return
        from utm_analysis import LiveFractureDetector
        if getattr(self, '_autostop_detector', None) is None:
            self._autostop_detector = LiveFractureDetector()
        cm = getattr(self, 'camera_manager', None)
        lpx = getattr(cm, 'latest_dic_L_px', 0.0) if cm is not None else 0.0
        if self._autostop_detector.update(self.current_load, ec=self.latest_dic_cauchy, lpx=lpx):
            if self.connected:
                self.serial_manager.send_command("Stop")
            self.stopRadioButton.blockSignals(True); self.stopRadioButton.setChecked(True); self.stopRadioButton.blockSignals(False)
            self._autostop_detector = None
            self.append_to_console("[Auto-stop] fracture detected (load collapse) — motor stopped.")
            self.set_status("Auto-stopped at fracture")
            # Keep filming through the post-fracture hold. Stopping on the trigger would end the
            # recording at the one moment the operator most wants to look at, and the anchor hold
            # that follows is what the force anchor is computed from.
            self._capture_stop_after(self.CAPTURE_POST_FRACTURE_S, "fracture + post-hold")

    def on_emergency_stop(self):
        """Emergency stop button pressed"""
        self.append_to_console("EMERGENCY STOP activated!")
        self._reset_preload_ui()
        self.active_policy = None                           # EStop also kills any closed-loop test mode
        self._release_active = False
        self._restore_release_buttons()
        self._return_active = False
        if getattr(self, 'returnZeroButton', None) is not None:
            self.returnZeroButton.setText("Return to 0 mm")
        self.set_status("⚠ EMERGENCY STOP - Motors halted", is_warning=True)
        if self.connected:
            self.serial_manager.send_command("EStop")

        # Reset direction to STOP
        self.stopRadioButton.blockSignals(True)
        self.stopRadioButton.setChecked(True)
        self.stopRadioButton.blockSignals(False)

        # Turn off motors switch and trigger the full cleanup
        # (stop velocity polling, update controls, reset speed display)
        self.motorsSwitch.setChecked(False)
        self.on_motors_toggle(False)

    # ========== Position & Incremental Move Functions ==========

    def _auto_tare_on_connect(self):
        """Auto-tare position and load cell after connection (called with delay)"""
        if self.connected:
            self.on_tare_location()
            self.on_tare()
            self.append_to_console("Auto-tare complete")

    def on_tare_location(self):
        """Tare the motor position (zero the displacement)"""
        # Calculate current absolute position from raw encoder value
        angle_deg = -self.motor_position_raw * (360.0 / 4096.0)
        rotations = angle_deg / 360.0
        screw_rotations = rotations / 20.0  # 20:1 gear ratio
        current_position_mm = screw_rotations * 5.0  # 5mm pitch

        self.motor_position_zero = current_position_mm
        self.motor_displacement_mm = 0.0
        self.append_to_console(f"Motor position tared (offset: {self.motor_position_zero:.4f} mm)")
        self.displacementLabel.setText("δ = 0.0000 mm")

    def on_move_up(self):
        """Move up by specified distance"""
        distance = self.moveDistanceSpinBox.value()
        firmware_speed = self.get_firmware_speed()
        speed_rpm = self.get_speed_rpm()
        self.append_to_console(f"Moving up {distance} mm at {speed_rpm:.1f} RPM")
        self.set_status(f"Moving UP {distance} mm...")

        # Mark incremental move active (disables stall detection during move)
        self.incremental_move_active = True
        # Start grace period to allow motor to start before detecting completion
        self._start_incremental_grace_period()

        # Update direction indicator to show Up (block signals to prevent sending direction command)
        self.upRadioButton.blockSignals(True)
        self.upRadioButton.setChecked(True)
        self.upRadioButton.blockSignals(False)

        if self.connected:
            # Set speed first
            self.serial_manager.send_command(f"SetSpeed {firmware_speed}")
            # 200 steps/rev * 8 microstepping * 20 gear ratio / 5mm pitch
            steps = round(200 * 8 * 20 * distance / 5)
            self.serial_manager.send_command(f"MoveSteps {steps}")

    def on_move_down(self):
        """Move down by specified distance"""
        distance = self.moveDistanceSpinBox.value()
        firmware_speed = self.get_firmware_speed()
        speed_rpm = self.get_speed_rpm()
        self.append_to_console(f"Moving down {distance} mm at {speed_rpm:.1f} RPM")
        self.set_status(f"Moving DOWN {distance} mm...")

        # Mark incremental move active (disables stall detection during move)
        self.incremental_move_active = True
        # Start grace period to allow motor to start before detecting completion
        self._start_incremental_grace_period()

        # Update direction indicator to show Down (block signals to prevent sending direction command)
        self.downRadioButton.blockSignals(True)
        self.downRadioButton.setChecked(True)
        self.downRadioButton.blockSignals(False)

        if self.connected:
            # Set speed first
            self.serial_manager.send_command(f"SetSpeed {firmware_speed}")
            steps = -round(200 * 8 * 20 * distance / 5)
            self.serial_manager.send_command(f"MoveSteps {steps}")

    # ===== SF11 — auto-metadata: tie a saved CSV to its capture folder, registry row, report =====
    #
    # A run used to leave three artefacts on disk with nothing joining them: the CSV, the report,
    # and a multi-gigabyte capture folder whose only connection to the force data was the operator
    # remembering which was which. That is the bookkeeping step this removes.

    def _capture_run_for(self, t_first, t_last):
        """The capture folder whose recording window OVERLAPS this data, or None.

        Overlap, not "the last one": run two tests before saving and last-one silently attaches the
        wrong frames to the force data — a mislabelled link is worse than no link, because it looks
        authoritative. A capture still running (end=None) is treated as extending to now.
        """
        best = None
        for r in self._capture_runs:
            start, end = r["start"], r["end"] or datetime.now()
            if start <= t_last and end >= t_first:                      # intervals intersect
                overlap = (min(end, t_last) - max(start, t_first)).total_seconds()
                if best is None or overlap > best[0]:
                    best = (overlap, r)
        return best[1] if best else None

    def _sf11_after_save(self, csv_path):
        """Everything that used to be a remembered manual step after pressing Save."""
        import utm_capture as _cap
        done = []

        # 1. the capture link (the other half is written into the CSV header by _export_csv)
        run = getattr(self, "_pending_capture_run", None)
        if run:
            p = _cap.write_manifest(run["dir"], {
                "csv": os.path.abspath(csv_path),
                "csv_name": os.path.basename(csv_path),
                "file_id": self.fileIdLineEdit.text().strip() or None,
                "captured_from": run["start"].isoformat(timespec="seconds"),
                "captured_to": (run["end"] or datetime.now()).isoformat(timespec="seconds"),
                "area_mm2": self.cross_sectional_area,
                "gauge_mm": self.gauge_length,
                "app_version": __version__,
            })
            if p:
                done.append(f"linked capture {os.path.basename(run['dir'])}")

        # 2. the registry. analyze() needs a detectable fracture, so a cyclic/creep/relaxation run
        # legitimately fails here — that is not an error worth alarming about, just a skip.
        if self.autoRegistryAct.isChecked():
            try:
                import utm_registry
                rec = utm_registry.add(csv_path, extra={"area": self.cross_sectional_area,
                                                        "gauge": self.gauge_length})
                done.append(f"registry: {rec.get('specimen') or '?'} "
                            f"UTS {rec.get('uts', 0):.1f} MPa")
            except Exception as e:
                self.append_to_console(f"[SF11] registry skipped — {type(e).__name__}: {e}. "
                                       "(Normal for a non-destructive run: no fracture to analyse.)")

        # 3. the report
        if self.autoReportAct.isChecked():
            try:
                # Automatic path, straight after a successful save: the data is saved by
                # definition, and a modal folder picker here would stall an unattended run. It
                # goes beside the CSV, which is what "On save: generate the report" promises.
                self.on_generate_report(ask_location=False, prompt_unsaved=False)
                done.append("report")
            except Exception as e:
                self.append_to_console(f"[SF11] report failed: {e}")

        if done:
            self.append_to_console("[SF11] " + " · ".join(done))

    # ========== Data Export Functions ==========

    def on_save_data(self):
        """Save data to CSV file with metadata header"""
        # Check if there's data to save
        if len(self.load_plot_times) == 0:
            QMessageBox.warning(self, "No Data", "No data to save. Record some data first.")
            return

        # Generate default filename with timestamp and optional File ID prefix
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_id = self.fileIdLineEdit.text().strip()
        if file_id:
            default_filename = f"{file_id}_UTM_Test_{timestamp_str}.csv"
        else:
            default_filename = f"UTM_Test_{timestamp_str}.csv"

        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Test Data",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            self._export_csv(file_path)
            self._last_saved_csv = file_path
            self.data_unsaved = False
            self._update_plot_title()
            self.append_to_console(f"Data saved to: {file_path}")
            self._sf11_after_save(file_path)      # capture link, registry row, optional report
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save data:\n{str(e)}")
            self.append_to_console(f"Export error: {str(e)}")

    def on_generate_report(self, _checked=False, *, ask_location=True, prompt_unsaved=True):
        """Build a one-page PDF report (+ individual vector graphs) from a test CSV, using the
        current UI settings, save it where the operator chooses, and open it.

        A report can only be built from a SAVED CSV — the analysis reads the file, not the live
        buffer. So an unsaved run is caught up front (`prompt_unsaved`): without that check the
        button silently reported on whichever test was saved LAST, producing a complete and
        entirely plausible report for the wrong specimen, filed into that specimen's folder.

        The output folder is then asked for (`ask_location`), defaulting to the CSV's own folder so
        the ordinary case is one Enter and the report lands with the test data, the plots and the
        capture it describes. build_report() otherwise defaults to a central
        Software/UTM_PyQt6/reports/ — right for the CLI, wrong from the app.

        `_checked` swallows the bool that QPushButton.clicked passes positionally. Both keyword
        flags are turned OFF by the SF11 auto-report, which runs immediately after a save: the data
        is saved by definition, and a modal folder picker in an automatic path would block it.
        """
        import os
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        last = getattr(self, "_last_saved_csv", None)
        if prompt_unsaved and getattr(self, "data_unsaved", False) and self.load_plot_times:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Save the test data first")
            box.setText("The current run has not been saved.")
            box.setInformativeText(
                "A report is built from a saved CSV, not from the live buffer.\n\n"
                + (f"Generating now would report on the PREVIOUS test\n"
                   f"({os.path.basename(last)}), not this one."
                   if last and os.path.exists(last) else
                   "There is no saved test to report on yet."))
            save_btn = box.addButton("Save data now", QMessageBox.ButtonRole.AcceptRole)
            old_btn = (box.addButton("Report on the previous test",
                                     QMessageBox.ButtonRole.DestructiveRole)
                       if last and os.path.exists(last) else None)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(save_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is save_btn:
                self.on_save_data()                     # opens the normal Save Test Data dialog
                if getattr(self, "data_unsaved", False):
                    self.append_to_console("[Report] save cancelled — no report generated.")
                    return
                # on_save_data may already have produced the report via SF11 auto-report.
                if self.autoReportAct.isChecked():
                    return
            elif clicked is not old_btn:
                self.append_to_console("[Report] cancelled."); return

        # Whatever the operator actually saved or opened — including a name they typed over the
        # suggested one, and including a different folder. Only a file that has since MOVED or been
        # renamed outside the app falls through to the picker, and then the picker starts in the
        # folder it was last seen in, which is where the renamed copy almost always still is.
        csv_path = getattr(self, "_last_saved_csv", None)
        if not csv_path or not os.path.exists(csv_path):
            start = os.path.dirname(csv_path) if csv_path else ""
            if csv_path:
                self.append_to_console(f"[Report] {os.path.basename(csv_path)} is no longer at that "
                                       "path — renamed or moved? Pick the CSV to report on.")
            csv_path, _ = QFileDialog.getOpenFileName(
                self, "Select test CSV for the report", start, "CSV Files (*.csv);;All Files (*)")
            if not csv_path:
                return
        try:
            speed_mm_s = self.get_speed_rpm() * self.MM_PER_S_PER_RPM
        except Exception:
            speed_mm_s = None
        comment = self.commentLineEdit.text().strip() if hasattr(self, "commentLineEdit") else None
        file_id = self.fileIdLineEdit.text().strip() if hasattr(self, "fileIdLineEdit") else None
        settings = {
            "id": file_id or None,
            "specimen_mode": self.specimenModeCombo.currentText(),
            "preload": f"{self.preloadTargetSpinBox.value():.0f}",
            "speed": (f"{speed_mm_s:.3f}" if speed_mm_s is not None else None),
            "area": self.cross_sectional_area,
            "gauge": self.gauge_length,
            "scale": self.force_scale,
            "offset": self.force_offset,
            "comment": comment or None,
        }
        # Default to the CSV's own folder — the specimen folder — so Enter is the right answer and
        # the report keeps company with the data it describes. Anywhere else stays one click away.
        spec_dir = os.path.dirname(os.path.abspath(csv_path))
        out_dir = spec_dir
        if ask_location:
            chosen = QFileDialog.getExistingDirectory(
                self, "Save the report in ...  (default: the specimen folder)", spec_dir,
                QFileDialog.Option.ShowDirsOnly)
            if not chosen:
                self.append_to_console("[Report] cancelled — no folder chosen."); return
            out_dir = chosen
        try:
            from utm_report import build_report
            paths = build_report(csv_path, settings=settings, out_dir=out_dir)
        except Exception as e:
            QMessageBox.critical(self, "Report error", f"Failed to generate report:\n{e}")
            self.append_to_console(f"Report error: {e}")
            return
        pdf = paths[0]
        where = ("beside the test data" if os.path.abspath(out_dir) == spec_dir
                 else "OUTSIDE the specimen folder")
        self.append_to_console(f"Report saved {where}: {pdf}")
        self.append_to_console(f"   {len(paths)} files written into {out_dir}")
        self.set_status(f"Report saved: {os.path.basename(pdf)}")

        # Then open it. Failing to open is NOT failing to generate, so say which one happened —
        # swallowing the error silently left the operator staring at a viewer that never appeared,
        # with no hint that the file was on disk all along.
        opened = self._open_externally(pdf)
        if not opened:
            self.append_to_console("   (could not launch a PDF viewer — the file is still saved)")

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Report generated")
        box.setText(("Report saved and opened." if opened else "Report saved."))
        box.setInformativeText(
            f"{len(paths)} files (one-pager + individual graphs, each as PDF and PNG) written into "
            + ("the specimen folder:" if os.path.abspath(out_dir) == spec_dir else ":")
            + f"\n\n{out_dir}\n\n{os.path.basename(pdf)}"
            + ("" if opened else "\n\nNo PDF viewer could be launched — open it from the folder."))
        folder_btn = box.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is folder_btn:
            self._open_externally(out_dir)

    def _open_externally(self, path):
        """Hand a file or folder to the OS. True if something was launched.

        os.startfile is Windows-only — which is where the rig is, but the analysis scripts get run
        elsewhere — so fall back to Qt, which knows the platform-appropriate opener.
        """
        import os
        try:
            os.startfile(path)                      # noqa: S606 — Windows
            return True
        except (AttributeError, OSError):
            pass
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        except Exception:
            return False

    def _export_csv(self, file_path):
        """Export data to CSV file with metadata header"""
        # Calculate derived values
        n_points = len(self.load_plot_times)
        first_time = self.load_plot_times[0]
        last_time = self.load_plot_times[-1]
        duration_s = (last_time - first_time).total_seconds()

        # Calculate max stress and strain
        max_stress = self.max_load / self.cross_sectional_area if self.cross_sectional_area > 0 else 0
        # Find max strain (based on max position)
        max_position = max(self.load_plot_positions, key=abs) if self.load_plot_positions else 0
        max_strain = max_position / self.gauge_length if self.gauge_length > 0 else 0

        # Get comment from UI if available
        comment = ""
        if hasattr(self, 'commentLineEdit'):
            comment = self.commentLineEdit.text()

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            # Write metadata header
            f.write("# UTM Test Data Export\n")
            f.write("# https://github.com/cenmir/UTM\n")
            f.write("#\n")
            f.write(f"# Test Date: {first_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Duration: {duration_s:.1f} s\n")
            f.write(f"# Data Points: {n_points}\n")
            # SF11: the CSV half of the capture link. Matched by time overlap, not recency —
            # see _capture_run_for. Stashed so _sf11_after_save can write the other half.
            self._pending_capture_run = self._capture_run_for(first_time,
                                                              self.load_plot_times[-1])
            if self._pending_capture_run:
                f.write(f"# Capture: {os.path.abspath(self._pending_capture_run['dir'])}\n")
            if comment:
                f.write(f"# Comment: {comment}\n")
            f.write("#\n")
            f.write(f"# Calibration - Scale: {self.force_scale}, Offset: {self.force_offset}\n")
            infill_val = self.infillSpinBox.value() if getattr(self, 'infillSpinBox', None) is not None else ''
            f.write(f"# Specimen - Area: {self.cross_sectional_area} mm², Gauge Length: {self.gauge_length} mm, Infill: {infill_val} %\n")
            px_per_mm = getattr(self.camera_manager, 'px_per_mm', 0.0)
            f.write(f"# DIC Calibration - px_per_mm: {px_per_mm:.4f}\n")
            _bl = self.load_plot_dic_blobs
            _ok = sum(1 for b in _bl if b == 2)
            f.write(f"# DIC Health - {100.0*_ok/len(_bl):.0f}% frames tracked 2/2 ({_ok}/{len(_bl)})\n" if _bl else "# DIC Health - n/a\n")
            # STRAIN COVERAGE — a different question from marker tracking, and the one that was
            # missing. "2/2 markers" says the detector found them; this says how many load samples
            # actually carry a strain number. S24 (2026-08-14) recorded 2134/2135 on the line above
            # while only 571 of 2135 rows held a reading, and nothing in the file said so. That
            # sparseness is what disabled the fracture detector's strain-jump guard and put
            # epsilon_f at 17.5 % instead of 7.4 %.
            # WHICH STATE strain is measured from. Two runs analysed side by side are only
            # comparable if they share this, and the difference is ~0.13 % of strain at a 300 N
            # preload — small, but it lands straight on epsilon_f and toughness. The file has to
            # carry it; nobody reconstructs a convention from memory six months later.
            _after = self.px0_after_preload()
            _pl = getattr(self, "_px0_load_N", None)
            f.write(f"# DIC Px0 reference: {'AFTER preload' if _after else 'BEFORE preload'}"
                    + (f" (captured at {_pl:.0f} N)" if _pl is not None else "") + "\n")
            _n = len(self.load_plot_dic_L_px)
            _cov = sum(1 for v in self.load_plot_dic_L_px if v > 100.0)
            if _n:
                _pct = 100.0 * _cov / _n
                f.write(f"# DIC Coverage - {_pct:.0f}% of samples carry a strain reading "
                        f"({_cov}/{_n})"
                        + ("   <-- LOW: most rows have no strain; treat ef and toughness with "
                           "caution" if _pct < 50 else "") + "\n")
            f.write("#\n")
            f.write(f"# Max Load: {self.max_load:.2f} N\n")
            f.write(f"# Max Stress: {max_stress:.4f} MPa\n")
            f.write(f"# Max Strain: {max_strain:.6f}\n")
            f.write("#\n")
            f.write(f"# App Version: {__version__}\n")
            f.write(f"# Firmware Version: {self.firmware_version}\n")
            f.write("#\n")

            # Write data header
            f.write("Time_s,RawADC,Force_N,Position_mm,Speed_mm_s,Motor_Strain,Stress_MPa,DIC_Cauchy,DIC_True,DIC_Time_s,Lag_ms,MCU_Time_s,L_px,dx_px,DIC_Blobs\n")

            # First MCU timestamp for relative time calculation
            first_mcu_ms = self.load_plot_mcu_timestamps[0] if self.load_plot_mcu_timestamps else 0

            # Write data rows
            for i in range(n_points):
                elapsed_s = (self.load_plot_times[i] - first_time).total_seconds()
                raw_adc = self.load_plot_raw_forces[i]
                force = self.load_plot_forces[i]
                position = self.load_plot_positions[i] if i < len(self.load_plot_positions) else 0
                speed = self.load_plot_speeds[i] if i < len(self.load_plot_speeds) else 0
                strain = position / self.gauge_length if self.gauge_length > 0 else 0
                stress = force / self.cross_sectional_area if self.cross_sectional_area > 0 else 0
                dic_cauchy = self.load_plot_dic_cauchy[i] if i < len(self.load_plot_dic_cauchy) else 0.0
                dic_true = self.load_plot_dic_true[i] if i < len(self.load_plot_dic_true) else 0.0
                dic_L_px = self.load_plot_dic_L_px[i] if i < len(self.load_plot_dic_L_px) else 0.0
                dic_dx_px = self.load_plot_dic_dx_px[i] if i < len(self.load_plot_dic_dx_px) else 0.0
                dic_blobs = self.load_plot_dic_blobs[i] if i < len(self.load_plot_dic_blobs) else 2

                # DIC timestamp and lag calculation
                dic_ts = self.load_plot_dic_timestamps[i] if i < len(self.load_plot_dic_timestamps) else None
                if dic_ts is not None:
                    dic_elapsed_s = (dic_ts - first_time).total_seconds()
                    lag_ms = (elapsed_s - dic_elapsed_s) * 1000.0
                else:
                    dic_elapsed_s = 0.0
                    lag_ms = 0.0

                # MCU timestamp (relative to first sample, in seconds)
                mcu_ms = self.load_plot_mcu_timestamps[i] if i < len(self.load_plot_mcu_timestamps) else 0
                mcu_elapsed_s = (mcu_ms - first_mcu_ms) / 1000.0 if mcu_ms > 0 else 0.0

                f.write(f"{elapsed_s:.3f},{raw_adc:.0f},{force:.4f},{position:.4f},{speed:.4f},{strain:.6f},{stress:.4f},{dic_cauchy:.6f},{dic_true:.6f},{dic_elapsed_s:.3f},{lag_ms:.1f},{mcu_elapsed_s:.3f},{dic_L_px:.1f},{dic_dx_px:.1f},{int(dic_blobs)}\n")

    def on_open_data(self):
        """Open and load data from a CSV file"""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Test Data",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            self._import_csv(file_path)
            # An opened CSV is the file the app is now showing, so it is also the file a report
            # should be built from. Without this, Open Data followed by Generate report silently
            # reported on whatever was SAVED last — the same wrong-specimen trap as an unsaved run,
            # reached from the other direction.
            self._last_saved_csv = file_path
            self.append_to_console(f"Data loaded from: {file_path}")
            self.append_to_console("   Generate report will now report on this file.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to load data:\n{str(e)}")
            self.append_to_console(f"Import error: {str(e)}")

    def _import_csv(self, file_path):
        """Import data from CSV file with metadata header"""
        import re

        # Clear existing data
        self.load_plot_times.clear()
        self.load_plot_forces.clear()
        self.load_plot_raw_forces.clear()
        self.load_plot_positions.clear()
        self.load_plot_speeds.clear()
        self.load_plot_dic_cauchy.clear()
        self.load_plot_dic_true.clear()
        self.load_plot_dic_L_px.clear()
        self.load_plot_dic_dx_px.clear()
        self.load_plot_dic_blobs.clear()
        self.stress_strain_strains.clear()
        self.stress_strain_stresses.clear()

        # Metadata to extract
        comment = ""
        calibration_scale = None
        calibration_offset = None
        specimen_area = None
        gauge_length = None
        dic_px_per_mm = None

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Parse metadata from header comments and output to console
        self.append_to_console("--- Loading CSV file ---")
        data_start_line = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('#'):
                # Output preamble to console
                self.append_to_console(line)
                # Parse metadata
                if '# Comment:' in line:
                    comment = line.replace('# Comment:', '').strip()
                elif '# DIC Calibration' in line:
                    # Parse: # DIC Calibration - px_per_mm: 12.3456
                    match = re.search(r'px_per_mm:\s*([+-]?\d*\.?\d+)', line)
                    if match:
                        dic_px_per_mm = float(match.group(1))
                elif '# Calibration' in line:
                    # Parse: # Calibration - Scale: -0.0065, Offset: -24.5185
                    match = re.search(r'Scale:\s*([+-]?\d*\.?\d+),\s*Offset:\s*([+-]?\d*\.?\d+)', line)
                    if match:
                        calibration_scale = float(match.group(1))
                        calibration_offset = float(match.group(2))
                elif '# Specimen' in line:
                    # Parse: # Specimen - Area: 80.0 mm², Gauge Length: 80.0 mm
                    match = re.search(r'Area:\s*([+-]?\d*\.?\d+)', line)
                    if match:
                        specimen_area = float(match.group(1))
                    match = re.search(r'Gauge Length:\s*([+-]?\d*\.?\d+)', line)
                    if match:
                        gauge_length = float(match.group(1))
            elif line and not line.startswith('#'):
                # First non-comment, non-empty line should be header
                if 'Time_s' in line or 'Force_N' in line:
                    data_start_line = i + 1
                    break
                else:
                    data_start_line = i
                    break

        # Update UI with loaded metadata
        if calibration_scale is not None:
            self.scaleSpinBox.blockSignals(True)
            self.scaleSpinBox.setValue(calibration_scale)
            self.scaleSpinBox.blockSignals(False)
            self.force_scale = calibration_scale

        if calibration_offset is not None:
            self.offsetSpinBox.blockSignals(True)
            self.offsetSpinBox.setValue(calibration_offset)
            self.offsetSpinBox.blockSignals(False)
            self.force_offset = calibration_offset

        if specimen_area is not None:
            self.areaSpinBox.blockSignals(True)
            self.areaSpinBox.setValue(specimen_area)
            self.areaSpinBox.blockSignals(False)
            self.cross_sectional_area = specimen_area

        if gauge_length is not None:
            self.gaugeLengthSpinBox.blockSignals(True)
            self.gaugeLengthSpinBox.setValue(gauge_length)
            self.gaugeLengthSpinBox.blockSignals(False)
            self.gauge_length = gauge_length

        if comment and hasattr(self, 'commentLineEdit'):
            self.commentLineEdit.setText(comment)

        if dic_px_per_mm is not None and hasattr(self, 'camera_manager'):
            self.camera_manager.px_per_mm = dic_px_per_mm

        # Parse data rows
        # Use first timestamp as base time
        base_time = datetime.now()

        for line in lines[data_start_line:]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(',')
            if len(parts) >= 3:
                try:
                    elapsed_s = float(parts[0])
                    raw_adc = float(parts[1]) if len(parts) > 1 else 0
                    force = float(parts[2]) if len(parts) > 2 else 0
                    position = float(parts[3]) if len(parts) > 3 else 0
                    speed = float(parts[4]) if len(parts) > 4 else 0
                    strain = float(parts[5]) if len(parts) > 5 else 0
                    stress = float(parts[6]) if len(parts) > 6 else 0
                    dic_cauchy = float(parts[7]) if len(parts) > 7 else 0.0
                    dic_true = float(parts[8]) if len(parts) > 8 else 0.0
                    dic_time_s = float(parts[9]) if len(parts) > 9 else 0.0
                    # parts[10] is Lag_ms, computed on export — skip on import
                    mcu_time_s = float(parts[11]) if len(parts) > 11 else 0.0
                    # New L_px / dx_px columns (added after 8.6.4 diagnostic run).
                    # Older CSVs without these columns default to 0.0.
                    dic_L_px = float(parts[12]) if len(parts) > 12 else 0.0
                    dic_dx_px = float(parts[13]) if len(parts) > 13 else 0.0

                    # Create timestamp from elapsed time
                    from datetime import timedelta
                    timestamp = base_time + timedelta(seconds=elapsed_s)
                    dic_timestamp = base_time + timedelta(seconds=dic_time_s) if dic_time_s > 0 else None
                    # Reconstruct MCU timestamp in ms (relative)
                    mcu_ms = int(mcu_time_s * 1000) if mcu_time_s > 0 else 0

                    self.load_plot_times.append(timestamp)
                    self.load_plot_raw_forces.append(raw_adc)
                    self.load_plot_forces.append(force)
                    self.load_plot_positions.append(position)
                    self.load_plot_speeds.append(speed)
                    self.load_plot_dic_cauchy.append(dic_cauchy)
                    self.load_plot_dic_true.append(dic_true)
                    self.load_plot_dic_timestamps.append(dic_timestamp)
                    self.load_plot_dic_L_px.append(dic_L_px)
                    self.load_plot_dic_dx_px.append(dic_dx_px)
                    self.load_plot_mcu_timestamps.append(mcu_ms)
                    self.stress_strain_strains.append(strain)
                    self.stress_strain_stresses.append(stress)
                except ValueError:
                    continue  # Skip malformed rows

        # Recalculate max load
        if self.load_plot_forces:
            self.max_load = max(self.load_plot_forces, key=abs)
            self.maxLoadValue.setText(f"{self.max_load:.2f}")
        else:
            self.max_load = 0.0
            self.maxLoadValue.setText("0.00")

        # Recalculate max stress/strain
        if self.stress_strain_stresses:
            self.max_stress = max(self.stress_strain_stresses, key=abs)
            self.maxStressValue.setText(f"{self.max_stress:.4f}")
        else:
            self.max_stress = 0.0
            self.maxStressValue.setText("0.0000")

        if self.stress_strain_strains:
            self.max_strain = max(self.stress_strain_strains, key=abs)
            self.maxStrainValue.setText(f"{self.max_strain:.6f}")
        else:
            self.max_strain = 0.0
            self.maxStrainValue.setText("0.000000")

        # Update current points count
        self.currentPointsValue.setText(str(len(self.load_plot_forces)))
        self.ssCurrentPointsValue.setText(str(len(self.stress_strain_stresses)))

        # Mark data as not unsaved (just loaded)
        self.data_unsaved = False
        self._update_plot_title()

        # Reset the range sliders
        self.cropRangeSlider.blockSignals(True)
        self.cropRangeSlider.setRange(0, 100)
        self.cropRangeSlider.blockSignals(False)

        self.ssCropRangeSlider.blockSignals(True)
        self.ssCropRangeSlider.setRange(0, 100)
        self.ssCropRangeSlider.blockSignals(False)

        # Force plot updates
        self.load_plot_needs_update = True
        self.stress_strain_plot_needs_update = True
        self._update_load_plot()
        self._update_stress_strain_plot()

    # ========== Serial Communication Signal Handlers ==========

    def on_connection_state_changed(self, connected):
        """Handle connection state changes from SerialManager"""
        self.connected = connected

        if connected:
            self.update_status_lamp(True)
            self.append_to_console("✓ Connected to UTM")
            self.set_status("Connected to UTM - Ready")
            # Ensure switch is on (it should be, but just in case)
            if not self.connectionSwitch.isChecked():
                self.connectionSwitch.blockSignals(True)
                self.connectionSwitch.setChecked(True)
                self.connectionSwitch.blockSignals(False)
            # Start motor position polling
            self._start_motor_polling()
            # Auto-tare position and load cell after a short delay to allow data to arrive
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._auto_tare_on_connect)
        else:
            self.update_status_lamp(False)
            # Only show "Disconnected" if we were previously connected
            # Otherwise the error message is more informative
            if self.connectionSwitch.isChecked():
                self.set_status("Connection failed")
                self.append_to_console("Connection failed")
            else:
                self.set_status("Disconnected")
            # Update switch state - block signals to prevent triggering disconnect again
            if self.connectionSwitch.isChecked():
                self.connectionSwitch.blockSignals(True)
                self.connectionSwitch.setChecked(False)
                self.connectionSwitch.blockSignals(False)
            # Stop all motor polling
            self._stop_motor_polling()

        # Update all control enabled states
        self.update_controls_enabled_state()

    def on_serial_data_received(self, data):
        """Handle raw serial data (display in console based on toggle states)"""
        # Filter out position/velocity data based on toggle states
        # These are parsed separately and displayed via their own handlers
        if data.startswith("Total Angle:"):
            # Position data - only show if position toggle is on
            # (handled by on_motor_position_data)
            return
        if data.startswith("Velocity:"):
            # Velocity data - only show if velocity toggle is on
            # (handled by on_motor_velocity_data)
            return

        # Display other received data in console
        self.append_to_console(f"<< {data}")

    def _match_dic_to_mcu_time(self, mcu_timestamp_ms):
        """Time-match a load cell sample to the nearest DIC reading using MCU clock.

        Uses the MCU→PC time bridge (anchor) to estimate when this sample was
        actually taken, then searches dic_history for the closest reading.

        Returns (cauchy, true_strain, dic_timestamp, L_px, dx_px) or
        (0.0, 0.0, None, 0.0, 0.0) if no match found or DIC reading is stale
        (> DIC_STALE_THRESHOLD_MS).

        dic_history tuple layout (camera_manager): (timestamp, cauchy, true_strain, L_px, dx_px)
        """
        dic_history = self.camera_manager.dic_history
        if not dic_history or self._time_anchor_pc is None or mcu_timestamp_ms == 0:
            # No history or no anchor — fall back to latest snapshot
            return (
                getattr(self, 'latest_dic_cauchy', 0.0),
                getattr(self, 'latest_dic_true_strain', 0.0),
                getattr(self.camera_manager, 'latest_dic_timestamp', None),
                getattr(self.camera_manager, 'latest_dic_L_px', 0.0),
                getattr(self.camera_manager, 'latest_dic_dx_px', 0.0),
            )

        # Estimate the true PC time of this load cell sample using MCU clock
        mcu_offset_ms = mcu_timestamp_ms - self._time_anchor_mcu_ms
        estimated_pc_time = self._time_anchor_pc + timedelta(milliseconds=mcu_offset_ms)

        # Search dic_history for nearest reading to estimated_pc_time
        best_entry = None
        best_gap_ms = float('inf')
        for entry in dic_history:
            gap_ms = abs((entry[0] - estimated_pc_time).total_seconds() * 1000.0)
            if gap_ms < best_gap_ms:
                best_gap_ms = gap_ms
                best_entry = entry

        if best_entry is None or best_gap_ms > self.DIC_STALE_THRESHOLD_MS:
            # No match or too stale — return zeros with None timestamp
            return 0.0, 0.0, None, 0.0, 0.0

        # Back-compat: older tuples may only have 3 fields (no L_px/dx_px)
        L_px = best_entry[3] if len(best_entry) > 3 else 0.0
        dx_px = best_entry[4] if len(best_entry) > 4 else 0.0
        return best_entry[1], best_entry[2], best_entry[0], L_px, dx_px

    def on_load_cell_data(self, raw_value, mcu_timestamp_ms=0):
        """Handle parsed load cell data with optional MCU timestamp (millis)"""
        # If calibration is active, collect raw values
        if self.calibration_active:
            self.calibration_raw_buffer.append(raw_value)

        # Calculate calibrated force: F = -(raw * scale) - offset
        force = -(raw_value * self.force_scale) - self.force_offset

        self.current_load = force
        self.update_load_display()
        self._update_cross_readout()          # the numbers the OTHER plot tab cannot show

        # Auto-preload: stop the motor once the target load is reached (or a safety limit trips)
        if self.preload_active:
            self._preload_check()
        elif getattr(self, '_release_active', False):
            self._release_check()
        elif getattr(self, '_return_active', False):
            self._return_check()
        elif getattr(self, 'active_policy', None) is not None:
            self._policy_step()
        elif (getattr(self, 'autoStopFractureCheck', None) is not None and self.autoStopFractureCheck.isChecked()
              and self.upRadioButton.isChecked() and self.motorsSwitch.isChecked()):
            self._autostop_check()          # manual tension pull: auto-halt on fracture

        # Add to plot data if:
        # 1. Load cell data stream is enabled (loadCellSwitch)
        # 2. Plot checkbox is checked (loadTogglePlotCheckBox)
        load_cell_on = hasattr(self, 'loadCellSwitch') and self.loadCellSwitch.isChecked()
        plot_enabled = hasattr(self, 'loadTogglePlotCheckBox') and self.loadTogglePlotCheckBox.isChecked()

        if load_cell_on and plot_enabled:
            now = datetime.now()

            # Establish time anchor on first sample (MCU↔PC clock bridge)
            if self._time_anchor_pc is None and mcu_timestamp_ms > 0:
                self._time_anchor_pc = now
                self._time_anchor_mcu_ms = mcu_timestamp_ms

            # Store all data points
            self.load_plot_times.append(now)
            self.load_plot_forces.append(force)
            self.load_plot_raw_forces.append(raw_value)
            self.load_plot_mcu_timestamps.append(mcu_timestamp_ms)
            self.load_plot_positions.append(self.motor_displacement_mm)
            # Convert RPM to mm/s: (RPM / 60) * (5mm / 20) = RPM * 5 / 1200
            speed_mm_s = self.motor_velocity_rpm * 5.0 / 1200.0
            self.load_plot_speeds.append(speed_mm_s)

            # Time-matched DIC lookup: use MCU timestamp to find the DIC reading
            # closest to when this sample was actually taken (not when Python received it)
            dic_cauchy, dic_true, dic_ts, dic_L_px, dic_dx_px = self._match_dic_to_mcu_time(mcu_timestamp_ms)
            self.load_plot_dic_cauchy.append(dic_cauchy)
            self.load_plot_dic_true.append(dic_true)
            self.load_plot_dic_timestamps.append(dic_ts)
            self.load_plot_dic_L_px.append(dic_L_px)
            self.load_plot_dic_dx_px.append(dic_dx_px)
            self.load_plot_dic_blobs.append(int(self._live_blob_count()))

            # Calculate stress and strain for stress-strain plot
            # Strain = displacement / gauge_length (dimensionless)
            strain = self.motor_displacement_mm / self.gauge_length if self.gauge_length > 0 else 0
            # Stress = force / area (N/mm² = MPa)
            stress = force / self.cross_sectional_area if self.cross_sectional_area > 0 else 0

            self.stress_strain_strains.append(strain)
            self.stress_strain_stresses.append(stress)

            # Update max load if this is a new maximum (by absolute value, preserving sign)
            if abs(force) > abs(self.max_load):
                self.max_load = force
                self.maxLoadValue.setText(f"{self.max_load:.2f}")

            # Update max stress/strain if new maximum (by absolute value, preserving sign)
            if abs(stress) > abs(self.max_stress):
                self.max_stress = stress
                self.maxStressValue.setText(f"{self.max_stress:.4f}")
            if abs(strain) > abs(self.max_strain):
                self.max_strain = strain
                self.maxStrainValue.setText(f"{self.max_strain:.6f}")

            # Update current points count (same for both plots)
            self.currentPointsValue.setText(str(len(self.load_plot_forces)))
            self.ssCurrentPointsValue.setText(str(len(self.stress_strain_stresses)))

            # Mark data as unsaved and update plot title
            if not self.data_unsaved:
                self.data_unsaved = True
                self._update_plot_title()

            # Flag both plots for update
            self.load_plot_needs_update = True
            self.stress_strain_plot_needs_update = True

    def on_motor_position_data(self, raw_angle):
        """Handle parsed motor position data from encoder"""
        # Store raw value
        self.motor_position_raw = raw_angle

        # Convert raw angle to mm: angle_deg = -raw * (360/4096)
        angle_deg = -raw_angle * (360.0 / 4096.0)
        rotations = angle_deg / 360.0
        screw_rotations = rotations / 20.0  # 20:1 gear ratio
        position_mm = screw_rotations * 5.0  # 5mm pitch

        # Calculate displacement relative to tare point
        self.motor_displacement_mm = position_mm - self.motor_position_zero

        # Update displacement label
        self.displacementLabel.setText(f"δ = {self.motor_displacement_mm:.4f} mm")

        # Display to console if toggle is on
        if self.display_position_to_console:
            self.append_to_console(f"Position: {self.motor_displacement_mm:.4f} mm (raw: {raw_angle})")

        # TODO: Update linear gauge visual

    def on_motor_velocity_data(self, vel1, vel2):
        """Handle parsed motor velocity data with stall detection"""
        self.motor_velocity_rpm = vel1
        self.motor_velocity_avg_rpm = vel2

        # Display to console if toggle is on
        if self.display_velocity_to_console:
            self.append_to_console(f"Velocity: {vel1:.2f} RPM (avg: {vel2:.2f} RPM)")

        # Update speed display label to show MEASURED velocity when motors are running
        if self.motorsSwitch.isChecked():
            self._update_measured_speed_display()

        # Check if incremental move completed (velocity near zero)
        # Skip detection during grace period (motor is still starting)
        if self.incremental_move_active:
            if not self.incremental_move_grace_period:
                if abs(vel1) < self.stall_velocity_threshold and abs(vel2) < self.stall_velocity_threshold:
                    # Incremental move completed - set direction to STOP
                    self.incremental_move_active = False
                    self.stopRadioButton.blockSignals(True)
                    self.stopRadioButton.setChecked(True)
                    self.stopRadioButton.blockSignals(False)
                    self.append_to_console("Incremental move completed")
                    self.set_status("Incremental move completed")
            # Skip stall detection during incremental moves
            return

        # Stall detection: check if motors should be moving but aren't
        # Only applies to continuous movement (Up/Down direction), not incremental moves
        # Skip during grace period (motor is still accelerating)
        if (self.stall_detection_enabled and self.motorsSwitch.isChecked()
                and not self.movement_start_grace_period and not self.preload_active):
            # Check if direction is not STOP (motors should be moving)
            motors_should_move = not self.stopRadioButton.isChecked()

            if motors_should_move:
                # Check both instantaneous and averaged velocity
                if abs(vel1) < self.stall_velocity_threshold and abs(vel2) < self.stall_velocity_threshold:
                    self.stall_count += 1
                    if self.stall_count >= self.stall_count_threshold:
                        self._handle_motor_stall()
                else:
                    # Reset stall counter if we're moving
                    self.stall_count = 0
            else:
                # Motors are in STOP, reset stall counter
                self.stall_count = 0

        # TODO: Update speed gauge visual

    def _handle_motor_stall(self):
        """Handle detected motor stall - emergency stop and warn user"""
        self.append_to_console("⚠ WARNING: MOTOR STALL DETECTED!")
        self._reset_preload_ui()
        self.append_to_console("⚠ Motors stopped for safety!")
        self.set_status("⚠ MOTOR STALL DETECTED - Motors stopped for safety!", is_warning=True)

        # Trigger emergency stop
        if self.connected:
            self.serial_manager.send_command("EStop")

        # Reset stall counter
        self.stall_count = 0

        # Reset direction to STOP
        self.stopRadioButton.blockSignals(True)
        self.stopRadioButton.setChecked(True)
        self.stopRadioButton.blockSignals(False)

        # Turn off motors switch and trigger the full cleanup
        self.motorsSwitch.setChecked(False)
        self.on_motors_toggle(False)
    
    def on_firmware_version(self, version):
        """Handle firmware version received from ESP32"""
        self.firmware_version = version
        self.append_to_console(f"✓ ESP32 Firmware v{version}")
        self.append_to_console(f"✓ Application v{__version__}")
        
        # Check version compatibility (optional - for future use)
        # if version != expected_version:
        #     self.append_to_console("⚠ Warning: Firmware version mismatch!")


    def on_serial_error(self, error_msg):
        """Handle serial communication errors"""
        self.append_to_console(f"⚠ ERROR: {error_msg}")


    # ========== Application Lifecycle ==========

    # ---- appearance -------------------------------------------------------------------------
    def _build_view_menu(self):
        """View ▸ Appearance ▸ Dark / Light, in the menu bar the .ui already carries."""
        from PyQt6.QtGui import QAction, QActionGroup
        bar = self.menuBar()
        menu = bar.addMenu("&View")
        appearance = menu.addMenu("&Appearance")
        self._themeActions = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for key, label, keyseq in (("dark", "&Dark", "Ctrl+Shift+D"),
                                   ("light", "&Light", "Ctrl+Shift+L")):
            act = QAction(label, self, checkable=True)
            act.setShortcut(keyseq)
            act.triggered.connect(lambda _checked, k=key: self.apply_theme(k))
            group.addAction(act)
            appearance.addAction(act)
            self._themeActions[key] = act

    # ===== Frame capture / video recording (Settings menu) ======================================
    #
    # Both OFF by default: they cost real disk (see the rate figures in the menu tooltips) and a
    # test that silently filled a drive would be worse than no feature. Arming a checkbox does not
    # start anything either — it declares intent, and the actual start happens when a test starts
    # (or when the operator hits Start now).
    #
    # Nothing here runs on the GUI thread except flipping flags. Frames go straight from the camera
    # thread into utm_capture's bounded buffers; encoding happens on its own worker threads, which
    # is why the feed, the plots and the load-cell rate are unaffected.
    CAPTURE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

    # ===== SF12 — DIC auto-calibration ==========================================================
    #
    # The preset's exposure and threshold were chosen once, by hand, under one set of LEDs. When the
    # lighting drifts those numbers quietly stop being right and the first symptom is a ruined test.
    # This sweeps both against a measured trackability score (utm_autocal) and proposes the winner.
    #
    # Deliberately PROPOSES rather than applies: it changes what the DIC measures, so it ends in a
    # dialog showing the before/after numbers, and Cancel puts the camera back exactly as it was.
    # Multiples of the CURRENT exposure, so the sweep is centred on wherever the rig is now. That
    # also means a badly-wrong starting value can leave the true optimum outside the range — the
    # handler detects a winner sitting at either END and says to run it again rather than
    # presenting an edge value as if it were the answer.
    AUTOCAL_EXPOSURE_STEPS = (0.3, 0.5, 0.7, 1.0, 1.4, 2.0, 2.8)
    AUTOCAL_FRAMES = 4                    # frames scored per exposure — see utm_autocal.pick_best
    AUTOCAL_SETTLE_S = 0.35               # let the sensor and the grab queue catch up after a change

    def on_autocalibrate_dic(self):
        """Sweep exposure x threshold, score each, and offer the best."""
        import time as _t
        from PyQt6.QtWidgets import QProgressDialog, QMessageBox
        import utm_autocal as AC
        cm = self.camera_manager
        if getattr(cm, "camera", None) is None:
            self.append_to_console("[Camera auto-cal] Start the camera first."); return
        if self.capture.active:
            self.append_to_console("[Camera auto-cal] Stop the capture first — this changes exposure "
                                   "mid-stream and would put mixed settings in one recording.")
            return

        start_exp = getattr(cm, "EXPOSURE_TIME", None)
        start_thr = cm.THRESHOLD
        kw = dict(min_area=cm.MIN_AREA, max_area=cm.MAX_AREA, min_circ=cm.MIN_CIRCULARITY)
        samples, best_thr_for = [], {}

        dlg = QProgressDialog("Sweeping exposure…", "Cancel", 0,
                              len(self.AUTOCAL_EXPOSURE_STEPS), self)
        dlg.setWindowTitle("DIC auto-calibration")
        dlg.setMinimumDuration(0); dlg.setValue(0)
        try:
            for i, mult in enumerate(self.AUTOCAL_EXPOSURE_STEPS):
                if dlg.wasCanceled():
                    break
                got = cm.set_exposure(start_exp * mult)
                if got is None:
                    continue
                dlg.setLabelText(f"Exposure {got/1000:.1f} ms  ({i+1}/"
                                 f"{len(self.AUTOCAL_EXPOSURE_STEPS)})")
                dlg.setValue(i); QApplication.processEvents()
                _t.sleep(self.AUTOCAL_SETTLE_S)

                mets, thrs = [], []
                for _ in range(self.AUTOCAL_FRAMES):
                    f = cm.latest_frame
                    if f is None:
                        break
                    t, best, _all = AC.best_threshold(f, cm.THRESHOLD_TYPE, **kw)
                    if t is not None:
                        thrs.append(t); mets.append(best)
                    else:
                        mets.append(AC.frame_score(f, start_thr, cm.THRESHOLD_TYPE, **kw))
                    _t.sleep(1.0 / max(1, getattr(cm, "FRAME_RATE", 35)))
                    QApplication.processEvents()
                if mets:
                    samples.append((got, mets))
                    if thrs:
                        best_thr_for[got] = float(sorted(thrs)[len(thrs) // 2])   # median
        finally:
            dlg.close()

        win, table = AC.pick_best(samples)
        if not win:
            cm.set_exposure(start_exp)
            self.append_to_console("[Camera auto-cal] No setting tracked both markers. Check the "
                                   "specimen is in frame and the markers are not obscured, then "
                                   "retry.")
            QMessageBox.warning(self, "DIC auto-calibration",
                                "No exposure found where both markers were detected.\n\n"
                                "Exposure has been put back. Check framing and lighting.")
            return

        new_exp = win["setting"]
        new_thr = best_thr_for.get(new_exp, start_thr)
        # A winner at either end of the swept range means the real optimum is probably beyond it.
        # Saying so is the difference between a useful tool and one that quietly hands back the
        # best of a set of bad options.
        swept = sorted(s for s, _ in samples)
        at_edge = len(swept) > 1 and new_exp in (swept[0], swept[-1])
        edge_note = ("\n\n⚠ The best value is at the EDGE of the swept range, so the true optimum "
                     "is probably further out. Apply this, then run auto-calibrate AGAIN — the "
                     "next sweep centres on the new value and will reach it." if at_edge else "")
        rows = "\n".join(
            f"   {r['setting']/1000:6.1f} ms   detect {r['detect_rate']*100:3.0f} %   "
            f"contrast {r['contrast']:.2f}   clipped {r['clipped_pct']:4.1f} %   "
            f"score {r['score']:.2f}" + ("   ← best" if r["setting"] == new_exp else "")
            for r in table)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("DIC auto-calibration")
        box.setText(f"Best: exposure {new_exp/1000:.1f} ms, threshold {new_thr:.0f}")
        box.setInformativeText(
            f"Now:  {start_exp/1000:.1f} ms, threshold {start_thr:.0f}\n"
            f"New:  {new_exp/1000:.1f} ms, threshold {new_thr:.0f}\n\n"
            f"{rows}\n\n"
            "Score is mostly CONTRAST MARGIN — how far the markers sit from the threshold — "
            "because that is what predicts whether tracking survives a flicker, not whether it "
            f"works right now.{edge_note}\n\nApply? Cancel puts the camera back as it was.")
        box.setStandardButtons(QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Apply)
        if box.exec() != QMessageBox.StandardButton.Apply:
            cm.set_exposure(start_exp)
            self.append_to_console("[Camera auto-cal] cancelled — exposure and threshold unchanged.")
            return

        cm.set_exposure(new_exp)
        cm.THRESHOLD = new_thr
        self.append_to_console(
            f"[Camera auto-cal] applied: exposure {start_exp/1000:.1f} → {new_exp/1000:.1f} ms, "
            f"threshold {start_thr:.0f} → {new_thr:.0f}  "
            f"(detect {win['detect_rate']*100:.0f} %, contrast {win['contrast']:.2f})")
        if at_edge:
            self.append_to_console("[Camera auto-cal] ⚠ best value was at the EDGE of the swept range — "
                                   "run auto-calibrate again to reach the true optimum.")
        self.append_to_console("[Camera auto-cal] this session only — the preset in camera_manager.py is "
                               "unchanged, so a restart returns to the hand-set values.")
        self._update_camera_params()

    def on_camera_params_manual(self):
        """Type the camera parameters, with the live trackability check beside the fields."""
        from PyQt6.QtWidgets import QDialog
        from utm_camdlg import CameraParamsDialog
        if self.capture.active:
            self.append_to_console("[Camera] Stop the capture first — changing exposure mid-stream "
                                   "would put mixed settings in one recording.")
            return
        cm = self.camera_manager
        before = (getattr(cm, "EXPOSURE_TIME", None), cm.THRESHOLD)
        dlg = CameraParamsDialog(cm, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.append_to_console(
                f"[Camera] manual: exposure {before[0]/1000 if before[0] else 0:.1f} → "
                f"{cm.EXPOSURE_TIME/1000 if cm.EXPOSURE_TIME else 0:.1f} ms, "
                f"threshold {before[1]:.0f} → {cm.THRESHOLD:.0f}, "
                f"area {cm.MIN_AREA}–{cm.MAX_AREA} px², circ ≥ {cm.MIN_CIRCULARITY:.2f}")
            self.append_to_console("[Camera] this session only — the preset in camera_manager.py "
                                   "is unchanged.")
        else:
            self.append_to_console("[Camera] manual setup cancelled — parameters unchanged.")
        self._update_camera_params()

    # Below this many strain readings per second the DIC is the bottleneck, not the camera, and the
    # readout says so. Chosen against the load-cell rate (~11 Hz): once DIC drops under half of it,
    # most CSV rows carry no strain and everything downstream degrades — including the fracture
    # detector, which is exactly how S24's epsilon_f came out at 17.5 % instead of 7.4 %.
    DIC_RATE_WARN_HZ = 6.0

    def _add_cross_readout(self, which):
        """Add the live numbers THIS tab's plot does not draw, into the data box already on it.

        Stress/Strain plots stress against strain and never shows force; Load Plot shows force and
        never shows stress or strain. Whichever tab you are watching, the missing quantity was the
        one you had to switch tabs to read — during a pull, which is exactly when you cannot.

        They live INSIDE the existing Stress/Strain Data and Load Data boxes rather than in a strip
        of their own: those boxes already exist, already hold live numbers, and already have the
        horizontal room. A separate strip spent ~24 px of vertical space per tab to say the same
        thing, and vertical space is the scarce axis on this page.

        Qt labels, deliberately NOT matplotlib text — anything drawn into the figure would be baked
        into every PNG and PDF the report saves.
        """
        from PyQt6.QtWidgets import QFormLayout
        if which == "ss":
            group, fields = self.stressDataGroup, (("Force:", "xrForce", "#1f6fb4"),)
        else:
            group = self.loadDataGroup
            fields = (("Stress:", "xrStress", "#7048e8"),
                      ("Strain (DIC):", "xrStrain", "#0066cc"))

        lay = group.layout()
        if lay is None:
            # Load Data is positioned by absolute geometry from the .ui — rows at y = 100 and 130
            # in a box fixed at 190 px, so there is room for ONE more row and two are needed. Give
            # it a real QFormLayout and migrate the existing pairs in, so it sizes itself from here.
            #
            # Collect by DESCENDANT, not direct child, and sort on the position mapped INTO the
            # group. Qt Designer wraps a nested layout in an unnamed "layoutWidget", so Current Load
            # is a grandchild: a direct-children scan silently left that pair absolutely positioned
            # and it floated on top of the migrated rows.
            labels = [c for c in group.findChildren(QLabel)]
            labels.sort(key=lambda c: (c.mapTo(group, c.rect().topLeft()).y(),
                                       c.mapTo(group, c.rect().topLeft()).x()))
            wrappers = {c.parentWidget() for c in labels if c.parentWidget() is not group}
            lay = QFormLayout(group)
            lay.setContentsMargins(10, 6, 10, 6)
            lay.setHorizontalSpacing(10)
            lay.setVerticalSpacing(5)
            lay.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lay.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for i in range(0, len(labels) - 1, 2):
                for c in (labels[i], labels[i + 1]):
                    c.setParent(group)              # out of the wrapper, into the group
                    c.setMinimumSize(0, 0)
                    c.setMaximumSize(16777215, 16777215)
                lay.addRow(labels[i], labels[i + 1])
            for wdg in wrappers:                    # the emptied Designer wrappers
                wdg.setParent(None)
                wdg.deleteLater()
        for caption, attr, colour in fields:
            cap = QLabel(caption)
            cap.setStyleSheet("color:#8a8f98;")
            val = QLabel("—")                     # value carries the UNIT, so it reads "1,234.5 N"
            val.setStyleSheet(f"font-weight: bold; color: {colour};")
            setattr(self, attr, val)
            lay.addRow(cap, val)

    def _update_cross_readout(self):
        """Refresh the cross-tab numbers. Called from the live load hook, so it costs one
        setText per tab and never touches either canvas."""
        f = self.current_load
        lb = getattr(self, "xrForce", None)
        if lb is not None:
            lb.setText("—" if f is None else f"{f:,.1f} N")
        lb = getattr(self, "xrStress", None)
        if lb is not None:
            area = getattr(self, "cross_sectional_area", 0.0) or 0.0
            lb.setText(f"{f/area:.2f} MPa" if (f is not None and area > 0) else "—")
        lb = getattr(self, "xrStrain", None)
        if lb is not None:
            ec = getattr(self, "latest_dic_cauchy", None)
            lb.setText(f"{ec*100:.4f} %" if ec else "—")

    def _update_camera_params(self):
        """Live camera settings BESIDE the strain values they produce.

        These used to live in the group-box title. They belong next to the numbers instead: when a
        strain reading looks wrong the next question is always "what is the camera set to", and
        that should be answerable in the same glance rather than by looking up to the heading.

        The readout carries the MEASURED grab rate and the MEASURED DIC rate, not the camera's
        configured frame rate. On S24 the title said "35 fps" while frames arrived at 19.9 and only
        3.0 strain readings per second reached the CSV. Nothing on screen showed that 6x loss.
        """
        p = self.camera_manager.camera_params()
        if not p:
            txt, tip, warn = "—", "", False
        else:
            bits = []
            if "exposure_us" in p:
                bits.append(f"exp {p['exposure_us']/1000:.1f} ms")
            # The Black preset's threshold is 0 because its type carries THRESH_OTSU — the level is
            # computed per frame. Printing "thr 0" would read as a broken setting.
            import cv2 as _cv2
            if getattr(self.camera_manager, "THRESHOLD_TYPE", 0) & _cv2.THRESH_OTSU:
                bits.append("thr auto")
            else:
                bits.append(f"thr {p['threshold']:.0f}")
            if "gain" in p and p["gain"]:
                bits.append(f"gain {p['gain']:.1f}")
            grab, dic = p.get("fps_grab", 0.0), p.get("hz_dic", 0.0)
            if grab:
                bits.append(f"{grab:.0f} fps")
            warn = bool(grab) and dic < self.DIC_RATE_WARN_HZ
            if grab or dic:
                bits.append(f"DIC {dic:.1f} Hz" + (" ⚠" if warn else ""))
            txt = "  ·  ".join(bits)
            tip = (f"Exposure {p.get('exposure_us', 0)/1000:.1f} ms · "
                   f"threshold {p['threshold']:.0f} ({p.get('mode','?')} preset)\n"
                   f"ROI {p.get('roi','?')} · frame mean {p.get('mean', 0):.0f} grey\n\n"
                   f"Frames grabbed   {grab:.1f} /s   (camera configured for "
                   f"{p.get('fps_actual', 0):.0f})\n"
                   f"Strain readings  {dic:.1f} /s\n\n"
                   + ("⚠ Far fewer strain readings than frames: most load samples will carry no "
                      "strain, which degrades the fracture detector and every integrated quantity."
                      if warn else
                      "These should be close. A large gap means frames are arriving but not "
                      "producing strain."))
        for lbl, w in (("dicParamsLabel", None), ("dicParamsLabelLP", None)):
            g = getattr(self, lbl, None)
            if g is not None:
                g.setText(txt)
                g.setToolTip(tip)
                g.setStyleSheet("color: #d29922; font-weight: bold;" if warn else "color: #8a8f98;")
        for name in ("cameraGroupBox", "cameraGroupBoxLP"):
            g = getattr(self, name, None)
            if g is not None and g.title() != "DIC Camera":
                g.setTitle("DIC Camera")

    def _make_capture_badges(self, row):
        """CAP (stills) and REC (video) beside the DIC health badge — indicator AND button.

        These are camera-style toggles rather than plain labels: the state light and the control
        are the same object, which is how every camera works and means the operator never has to
        find a menu mid-test. Deliberately tiny (10 px text, flat, no pill) — they share a row with
        the health badge and three live numbers, and anything bigger competes with the readings
        being watched during a pull.
        """
        from PyQt6.QtWidgets import QToolButton
        made = []
        for tip, slot in (("Start / stop saving PNG frames", self._toggle_png),
                          ("Start / stop AVI recording", self._toggle_video)):
            b = QToolButton()
            b.setCheckable(True)
            b.setAutoRaise(True)                 # flat until hovered — a chip, not a chunky button
            b.setToolTip(tip)
            b.setFixedHeight(22)
            b.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            b.clicked.connect(slot)
            row.addWidget(b)
            made.append(b)
        return made[0], made[1]

    def _toggle_png(self, on):
        """The CAP button: start/stop stills directly, independent of the auto-start tick."""
        self._capture_start(png=True, manual=True) if on else self._capture_stop(png=True)

    def _toggle_video(self, on):
        self._capture_start(video=True, manual=True) if on else self._capture_stop(video=True)

    def _build_settings_menu(self):
        """Settings ▸ frame capture + video recording, with manual start/stop beside each."""
        from PyQt6.QtGui import QAction
        menu = self.menuBar().addMenu("&Settings")

        # ONE dialog instead of two enable ticks plus two view submenus. The menu form could not
        # answer the question that actually matters -- how much disk this will eat -- because the
        # answer depended on six checkboxes across two submenus and nothing added them up.
        act_setup = QAction("Capture setup…", self)
        act_setup.setToolTip("What to record (stills, video, and which views of each), where it "
                             "goes, and what it costs per minute of test.")
        act_setup.triggered.connect(self.on_capture_setup)
        menu.addAction(act_setup)

        # The arm flags and the view lists are now owned by that dialog. They stay as QActions so
        # every existing path -- _capture_autostart, _capture_sync_menu, the suites -- is unchanged;
        # they are simply not shown in the menu any more.
        self.actCaptureArm = QAction("armed: PNG stills", self, checkable=True)
        self.actRecordArm = QAction("armed: AVI video", self, checkable=True)
        self.actCaptureArm.toggled.connect(self._on_capture_armed)
        self.actRecordArm.toggled.connect(self._on_record_armed)
        self._styleActions = {k: QAction(k, self, checkable=True) for k in ("raw", "speckle", "boost")}
        self._vidStyleActions = {k: QAction(k, self, checkable=True) for k in ("raw", "speckle", "boost")}
        self._styleActions["raw"].setChecked(True)
        self._vidStyleActions["raw"].setChecked(True)
        # Still wired to the sync handlers: the dialog is the visible route, but these remain the
        # single place the view lists are derived from, so setting one anywhere stays truthful.
        for a in self._styleActions.values():
            a.toggled.connect(self._sync_png_styles)
        for a in self._vidStyleActions.values():
            a.toggled.connect(self._sync_video_styles)

        self.actCaptureStart = QAction("Start capturing now", self)
        self.actCaptureStart.triggered.connect(lambda: self._capture_start(png=True, manual=True))
        self.actCaptureStop = QAction("Stop capturing", self)
        self.actCaptureStop.triggered.connect(lambda: self._capture_stop(png=True))
        self.actRecordStart = QAction("Start recording now", self)
        self.actRecordStart.triggered.connect(lambda: self._capture_start(video=True, manual=True))
        self.actRecordStop = QAction("Stop recording", self)
        self.actRecordStop.triggered.connect(lambda: self._capture_stop(video=True))
        for a in (self.actCaptureStart, self.actCaptureStop,
                  self.actRecordStart, self.actRecordStop):
            menu.addAction(a)


        menu.addSeparator()
        # Two ways to set the camera up, both ending in the same place. Kept as two ACTIONS rather
        # than a Manual/Auto radio pair: a mode whose only effect is to open a dialog the moment you
        # pick it is not really a mode, and a stale radio would leave the menu claiming a state the
        # camera is not in.
        cam_menu = menu.addMenu("DIC camera setup")
        cam_menu.setToolTipsVisible(True)
        act_cal = QAction("Auto-calibrate…", self)
        act_cal.setToolTip("Sweep exposure and threshold against a measured trackability score, "
                           "then show the result before applying anything.\n"
                           "Use it when the lighting has changed — the preset's numbers were "
                           "chosen by hand under one set of LEDs.")
        act_cal.triggered.connect(self.on_autocalibrate_dic)
        cam_menu.addAction(act_cal)

        # The strain-zero convention. A measurement decision, so it is set once, remembered, and
        # written into every CSV header — not a habit that lives in whoever ran the test.
        act_px0 = QAction("Zero strain AFTER preload", self, checkable=True)
        act_px0.setChecked(self.px0_after_preload())
        act_px0.setToolTip(
            "OFF — Px₀ is frozen before preload, so strain covers every bit of deformation the "
            "specimen saw.\n"
            "ON  — Px₀ is frozen after preload, so strain starts from the seated state and the "
            "preload stretch is excluded.\n\n"
            "At 300 N on 80 mm² the two differ by roughly 0.13 % of strain, which lands directly "
            "on ε_f and toughness. Do not mix conventions within a series.")
        act_px0.toggled.connect(self.on_px0_convention_changed)
        cam_menu.addAction(act_px0)
        self.actPx0AfterPreload = act_px0

        act_man = QAction("Set parameters manually…", self)
        act_man.setToolTip("Type exposure, threshold and the blob gates yourself.\n"
                           "Every change is re-scored against the live frame as you make it, so "
                           "you can see whether a value tracks before committing to it.")
        act_man.triggered.connect(self.on_camera_params_manual)
        cam_menu.addAction(act_man)

        menu.addSeparator()
        # SF11 — the bookkeeping that used to be remembered manual steps after pressing Save.
        self.autoRegistryAct = QAction("On save: add to the test registry", self, checkable=True)
        self.autoRegistryAct.setToolTip(
            "Append the saved test to registry.json with its computed E / σ_y / UTS / ε_f / anchor.\n"
            "Was a CLI you had to remember to run (utm_registry.py scan).\n"
            "Skipped automatically on a non-destructive run — the analysis needs a fracture.")
        self.autoRegistryAct.toggled.connect(
            lambda on: self._remember("sf11/registry", bool(on)))
        menu.addAction(self.autoRegistryAct)

        self.autoReportAct = QAction("On save: generate the report", self, checkable=True)
        self.autoReportAct.setToolTip("Build the one-page PDF + graphs next to the CSV, "
                                      "without the extra click. Takes a few seconds.")
        self.autoReportAct.toggled.connect(lambda on: self._remember("sf11/report", bool(on)))
        menu.addAction(self.autoReportAct)

        menu.addSeparator()
        folder = menu.addMenu("Where to save")
        act_set = QAction("Set capture folder…", self)
        act_set.setToolTip("Where new capture runs are created. Each run still gets its own "
                           "timestamped sub-folder inside it.")
        act_set.triggered.connect(self._choose_capture_folder)
        folder.addAction(act_set)

        self.actAskFolder = QAction("Ask me before each test", self, checkable=True)
        self.actAskFolder.setToolTip("Prompt for a folder when you press Start test or Fracture "
                                     "test — BEFORE the motor moves, never during.")
        self.actAskFolder.toggled.connect(lambda on: self._remember("capture/ask_folder", bool(on)))
        folder.addAction(self.actAskFolder)

        folder.addSeparator()
        self.actMoveLast = QAction("Move last capture to…", self)
        self.actMoveLast.setToolTip("Relocate the run that just finished — for deciding where it "
                                    "belongs after seeing how the test went.")
        self.actMoveLast.triggered.connect(self._move_last_capture)
        folder.addAction(self.actMoveLast)

        act_open = QAction("Open capture folder…", self)
        act_open.triggered.connect(self._open_capture_folder)
        folder.addAction(act_open)

        # Restore what was armed last session. blockSignals so restoring does not print the
        # "ARMED" console line before the operator has done anything.
        # The ARMED state is deliberately NOT remembered across sessions. Everything else in this
        # app restores (theme, window size, infill), but auto-capture writes ~1.9 GB per minute:
        # arming it last week and forgetting is how a drive fills during a run that cannot be
        # repeated. Every session starts disarmed; the STYLE preference is harmless and does persist.
        pw = str(self._recall("capture/png_styles", "raw") or "raw").split(",")
        for k, a in self._styleActions.items():
            a.blockSignals(True); a.setChecked(k in pw); a.blockSignals(False)
        self._sync_png_styles(confirm=False)     # restore, not a new decision — see the docstring
        want = str(self._recall("capture/video_styles", "raw") or "raw").split(",")
        for k, a in self._vidStyleActions.items():
            a.blockSignals(True); a.setChecked(k in want); a.blockSignals(False)
        self._sync_video_styles()
        self.capture.root = self._recall("capture/root", self.CAPTURE_ROOT) or self.CAPTURE_ROOT
        self.actAskFolder.blockSignals(True)
        self.actAskFolder.setChecked(self._recall_bool("capture/ask_folder", False))
        self.actAskFolder.blockSignals(False)
        # Registry ON by default: it is cheap, it self-skips when there is no fracture, and a test
        # missing from the registry is the bug this feature exists to stop. Report OFF — it costs
        # seconds and the operator often wants to crop the data first.
        for act, key, dflt in ((self.autoRegistryAct, "sf11/registry", True),
                               (self.autoReportAct, "sf11/report", False)):
            act.blockSignals(True)
            act.setChecked(self._recall_bool(key, dflt))
            act.blockSignals(False)
        self._capture_sync_menu()

    def _make_style(self, key):
        """Build a Style, giving `speckle` the SAME threshold basis the blob detector uses."""
        import utm_capture as _cap
        cm = self.camera_manager
        if key == "speckle":
            return _cap.style_speckle(getattr(cm, "THRESHOLD", 150),
                                      getattr(cm, "THRESHOLD_TYPE", None))
        if key == "boost":
            return _cap.style_boost()
        return _cap.style_raw()

    def _sync_video_styles(self, *_):
        """Turn the video tick-boxes into the list of AVIs the next recording will write.

        Deliberately not applied to a recording already in progress: adding or removing a file
        half way through would leave one AVI shorter than the other with no record of why.
        """
        keys = [k for k, a in self._vidStyleActions.items() if a.isChecked()]
        if not keys:                             # never leave the operator with no video at all
            self._vidStyleActions["raw"].blockSignals(True)
            self._vidStyleActions["raw"].setChecked(True)
            self._vidStyleActions["raw"].blockSignals(False)
            keys = ["raw"]
        self._remember("capture/video_styles", ",".join(keys))
        styles = [self._make_style(k) for k in keys]
        if self.capture.recording:
            self._pending_video_styles = styles
            self.append_to_console("[Capture] video views changed — applies to the NEXT recording; "
                                   "the one in progress is unchanged.")
        else:
            self.capture.video_styles = styles
            self.append_to_console("[Capture] video views: "
                                   + " + ".join(s.label.split(" (")[0].split(" —")[0]
                                                for s in styles))

    TEST_MIN_FOR_ESTIMATE = 1.0          # the warning is quoted per minute of test

    def _sync_png_styles(self, *_, confirm=True):
        """Turn the stills tick-boxes into the list of frame folders the next capture writes.

        Selecting a SECOND view is confirmed, because stills are where the disk actually goes: a
        second raw view is another ~1.9 GB/min against ~0.3 for a second video view. The dialog
        quotes GB for a one-minute test, which is the length of a real fracture pull.

        `confirm=False` for the STARTUP restore. Re-selecting what the operator already agreed to
        last session is not a new decision, and raising a modal during __init__ hangs the app before
        there is a window to show it against — which is exactly what it did.
        """
        keys = [k for k, a in self._styleActions.items() if a.isChecked()]
        if not keys:
            self._styleActions["raw"].blockSignals(True)
            self._styleActions["raw"].setChecked(True)
            self._styleActions["raw"].blockSignals(False)
            keys = ["raw"]
        styles = [self._make_style(k) for k in keys]

        if confirm and len(styles) > 1 and not self._confirm_png_multi(styles):
            # Declined: drop back to the single view that was already in effect.
            keep = (self.capture.png_styles[0].key if self.capture.png_styles else "raw")
            for k, a in self._styleActions.items():
                a.blockSignals(True); a.setChecked(k == keep); a.blockSignals(False)
            return

        self._remember("capture/png_styles", ",".join(s.key for s in styles))
        if self.capture.capturing:
            self._pending_style = styles
            self.append_to_console("[Capture] stills views changed — applies to the NEXT capture.")
        else:
            self.capture.png_styles = styles
            self.append_to_console(
                "[Capture] PNG stills: " + " + ".join(s.key for s in styles)
                + f"  (~{sum(s.gb_per_min(png=True) for s in styles):.2f} GB per minute)")

    def _confirm_png_multi(self, styles):
        """Say what it will cost, in GB, before writing several stills views of the same run."""
        from PyQt6.QtWidgets import QMessageBox
        m = self.TEST_MIN_FOR_ESTIMATE
        per = [(s, s.gb_per_min(png=True) * m) for s in styles]
        total = sum(g for _, g in per)
        vid = sum(s.gb_per_min() * m for s in self.capture.video_styles) \
            if self.actRecordArm.isChecked() or self.capture.recording else 0.0

        lines = "\n".join(f"    •  {s.label.split(' (')[0].split(' —')[0]}"
                          f"{'':<4}~{g:.2f} GB" for s, g in per)
        body = (f"Saving {len(styles)} stills views writes every frame {len(styles)} times over.\n\n"
                f"For a 1-minute test at 35 fps:\n{lines}\n"
                f"    ─────────────────────────\n"
                f"    stills total     ~{total:.2f} GB")
        if vid:
            body += f"\n    video also       ~{vid:.2f} GB\n    RUN TOTAL        ~{total + vid:.2f} GB"
        body += ("\n\nA fracture pull often runs longer than a minute — scale accordingly.\n"
                 "Speckle is cheap; a second RAW-quality view is not.")

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Save several stills views?")
        box.setText(f"That is roughly {total:.2f} GB per minute of test.")
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def on_capture_setup(self):
        """One panel: what to record, in what views, where, and the running disk total."""
        from PyQt6.QtWidgets import QDialog
        from utm_capdlg import CaptureSetupDialog
        if self.capture.active:
            self.append_to_console("[Capture] Stop the current capture before changing setup.")
            return
        dlg = CaptureSetupDialog(self.capture, self._make_style, self,
                                 armed=(self.actCaptureArm.isChecked(),
                                        self.actRecordArm.isChecked()))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        png_on, avi_on = dlg.apply_to(self.capture)
        self._remember("capture/root", self.capture.root)
        self._remember("capture/png_styles", ",".join(s.key for s in self.capture.png_styles))
        self._remember("capture/video_styles", ",".join(s.key for s in self.capture.video_styles))
        for act, on in ((self.actCaptureArm, png_on), (self.actRecordArm, avi_on)):
            act.blockSignals(True); act.setChecked(on); act.blockSignals(False)
        # Mirror onto the hidden view actions so anything still reading them stays truthful.
        for acts, styles in ((self._styleActions, self.capture.png_styles),
                             (self._vidStyleActions, self.capture.video_styles)):
            keys = {s.key for s in styles}
            for k, a in acts.items():
                a.blockSignals(True); a.setChecked(k in keys); a.blockSignals(False)
        gb = (sum(s.gb_per_min(png=True) for s in self.capture.png_styles) if png_on else 0) + \
             (sum(s.gb_per_min() for s in self.capture.video_styles) if avi_on else 0)
        self.append_to_console(
            f"[Capture] stills: {'+'.join(s.key for s in self.capture.png_styles)}"
            f"{' (armed)' if png_on else ' (off)'}  ·  "
            f"video: {'+'.join(s.key for s in self.capture.video_styles)}"
            f"{' (armed)' if avi_on else ' (off)'}  ·  ~{gb:.2f} GB per minute of test")
        self.append_to_console(f"[Capture] folder: {self.capture.root}")
        self._capture_sync_menu()

    def _on_capture_armed(self, on):
        self.append_to_console(
            "[Capture] PNG frames ARMED — starts with the next test, or use Start capturing now."
            if on else "[Capture] PNG frames disarmed.")
        if not on and self.capture.capturing:
            self._capture_stop(png=True)
        self._capture_sync_menu()

    def _on_record_armed(self, on):
        self.append_to_console(
            "[Capture] AVI recording ARMED — starts with the next test, or use Start recording now."
            if on else "[Capture] AVI recording disarmed.")
        if not on and self.capture.recording:
            self._capture_stop(video=True)
        self._capture_sync_menu()

    def _capture_sync_menu(self):
        """Grey out whichever start/stop cannot apply, so the menu states the current state."""
        cap, rec = self.capture.capturing, self.capture.recording
        for act, live, armed in ((self.actCaptureStart, cap, self.actCaptureArm.isChecked()),
                                 (self.actRecordStart, rec, self.actRecordArm.isChecked())):
            act.setEnabled(armed and not live)
        self.actCaptureStop.setEnabled(cap)
        self.actRecordStop.setEnabled(rec)
        self._update_capture_badges()

    def _capture_label(self):
        """Folder suffix: the File ID box if it has one, so a run is findable afterwards."""
        for attr in ("fileIdLineEdit", "fileNameLineEdit", "testIdLineEdit"):
            w = getattr(self, attr, None)
            if w is not None and hasattr(w, "text") and w.text().strip():
                return "".join(c if (c.isalnum() or c in "-_") else "_" for c in w.text().strip())[:40]
        return None

    def _capture_start(self, *, png=False, video=False, manual=False, reason=""):
        """Start whichever sinks were asked for. Silent no-op if the camera is not running."""
        cm = self.camera_manager
        if getattr(cm, "camera", None) is None:
            if manual:
                self.append_to_console("[Capture] Start the camera first.")
            return
        label = self._capture_label()
        started = []
        if png and not self.capture.capturing:
            p = self.capture.start_png(label=label)
            started.append("PNG → " + ", ".join(os.path.basename(x) for x in p) + "/")
        if video and not self.capture.recording:
            frame = getattr(cm, "latest_frame", None)
            if frame is None:
                self.append_to_console("[Capture] No frame yet — cannot size the video.")
            else:
                h, w = frame.shape[:2]
                p = self.capture.start_video((w, h), label=label)
                started.append("AVI → " + ", ".join(os.path.basename(x) for x in p)
                               + f"  in {os.path.dirname(p[0])}" if p else "AVI → (none)")
        if started:
            cm.frame_sink = self.capture.submit          # arm the camera-thread hook
            # Record WHEN this folder was live. On save, the CSV is matched to the capture whose
            # window overlaps the data — not simply to the most recent one, which would mislabel
            # the frames the moment two tests are run before saving.
            d = self.capture.run_dir()
            if not any(r["dir"] == d for r in self._capture_runs):
                self._capture_runs.append({"dir": d, "start": datetime.now(), "end": None})
            for s in started:
                self.append_to_console(f"[Capture] started{(' ' + reason) if reason else ''}: {s}")
        self._capture_sync_menu()

    def _capture_stop(self, *, png=False, video=False, reason=""):
        """Stop sinks and report what landed on disk, including any dropped frames."""
        self._last_capture_dir = self.capture.run_dir() if self.capture.active else \
            getattr(self, "_last_capture_dir", None)
        if png and self.capture.capturing:
            self.capture.stop_png()
        if video and self.capture.recording:
            self.capture.stop_video()
        if not self.capture.active:
            self.camera_manager.frame_sink = None        # disarm the hot path entirely
            for r in self._capture_runs:
                if r["dir"] == self._last_capture_dir and r["end"] is None:
                    r["end"] = datetime.now()
            pending = getattr(self, "_pending_style", None)
            if pending is not None:                      # style chosen mid-run applies now
                self.capture.png_styles = pending
                self._pending_style = None
            pv = getattr(self, "_pending_video_styles", None)
            if pv is not None:
                self.capture.video_styles = pv
                self._pending_video_styles = None
        s = self.capture.stats()
        parts = []
        if png:
            parts.append(f"{s['png_written']} PNG" + (f" ({s['png_dropped']} dropped)"
                                                      if s['png_dropped'] else ""))
        if video:
            parts.append(f"{s['vid_written']} video frames" + (f" ({s['vid_dropped']} dropped)"
                                                               if s['vid_dropped'] else ""))
        if parts:
            self.append_to_console(f"[Capture] stopped{(' ' + reason) if reason else ''} — "
                                   + " · ".join(parts))
            if s["png_dropped"] or s["vid_dropped"]:
                self.append_to_console("[Capture] ⚠ frames were DROPPED — the disk could not keep "
                                       "up. The gap is in index.csv; consider recording video only.")
            if s["error"]:
                self.append_to_console(f"[Capture] ⚠ writer error: {s['error']}")
        # Say so in the STATUS BAR too, not only the console.
        #
        # A fracture test ends with "Auto-stopped at fracture" and then, four seconds later, the
        # capture finishes quietly. Standing at the rig you had no way to know the recording had
        # closed cleanly — or that it had dropped frames — without scrolling the console. The
        # status bar is where you are already looking when the motor stops.
        if parts and not self.capture.active:
            dropped = s["png_dropped"] + s["vid_dropped"]
            where = os.path.basename(self._last_capture_dir or "")
            if s["error"]:
                self.set_status(f"⚠ Capture FAILED — {s['error']}", is_warning=True)
            elif dropped:
                self.set_status(f"⚠ Capture saved with {dropped} dropped frame(s) — "
                                + " · ".join(parts), is_warning=True)
            else:
                base = self.statusLineEdit.text()
                lead = f"{base}  ·  " if base and "Auto-stopped" in base else ""
                self.set_status(f"{lead}Capturing completed and saved — "
                                + " · ".join(parts) + (f"  →  {where}" if where else ""))
        self._capture_sync_menu()

    def _capture_autostart(self, what):
        """Called when a test starts. Only ARMED features begin."""
        png = self.actCaptureArm.isChecked() if getattr(self, "actCaptureArm", None) else False
        vid = self.actRecordArm.isChecked() if getattr(self, "actRecordArm", None) else False
        if png or vid:
            self._capture_start(png=png, video=vid, reason=f"with {what}")

    CAPTURE_POST_FRACTURE_S = 4.0

    def _capture_autostop(self, what):
        """Called when a test ends. Stops whatever is running, auto-started or not."""
        if self.capture.active:
            self._capture_stop(png=self.capture.capturing, video=self.capture.recording,
                               reason=f"with {what}")

    def _capture_stop_after(self, seconds, what):
        """Stop after a delay, so a run keeps filming past the event that ended it."""
        if not self.capture.active:
            return
        self.append_to_console(f"[Capture] still running — stops in {seconds:.0f} s ({what}).")
        QTimer.singleShot(int(seconds * 1000), lambda: self._capture_autostop(what))

    def _choose_capture_folder(self):
        """Pick the root that new runs are created in. Remembered across sessions."""
        from PyQt6.QtWidgets import QFileDialog
        start = self.capture.root if os.path.isdir(self.capture.root) else os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "Capture folder — where new runs are created",
                                             start)
        if not d:
            return
        self.capture.root = d
        self._remember("capture/root", d)
        self.append_to_console(f"[Capture] folder set to {d}")
        if self.capture.active:
            self.append_to_console("[Capture] the run in progress keeps its current folder.")

    def _capture_ask_folder_before_test(self):
        """Prompt for a folder at the START of a user-initiated test, if that option is on.

        Called from the button handlers BEFORE any motor command — never from the auto-start hook,
        which fires once the pull is already under way. A modal dialog while the crosshead is
        moving would block the control loop and the Stop button behind it.
        Returns False only if the operator cancelled the dialog, which aborts the test.
        """
        if not getattr(self, "actAskFolder", None) or not self.actAskFolder.isChecked():
            return True
        if not (self.actCaptureArm.isChecked() or self.actRecordArm.isChecked()):
            return True                       # nothing armed, nowhere to save
        from PyQt6.QtWidgets import QFileDialog
        start = self.capture.root if os.path.isdir(self.capture.root) else os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "Save this test's capture in…", start)
        if not d:
            self.append_to_console("[Capture] folder prompt cancelled — test not started.")
            return False
        self.capture.root = d
        return True

    def _move_last_capture(self):
        """Relocate the run that just finished, for deciding where it belongs after the fact."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import shutil
        src = getattr(self, "_last_capture_dir", None)
        if not src or not os.path.isdir(src):
            self.append_to_console("[Capture] no finished capture to move.")
            return
        if self.capture.active:
            self.append_to_console("[Capture] stop the current capture first.")
            return
        dest_root = QFileDialog.getExistingDirectory(self, "Move the last capture into…",
                                                     os.path.dirname(src))
        if not dest_root:
            return
        dest = os.path.join(dest_root, os.path.basename(src))
        try:
            if os.path.exists(dest):
                QMessageBox.warning(self, "Move capture", f"{dest} already exists — not moving.")
                return
            shutil.move(src, dest)            # same-volume rename, or a real copy across drives
            self._last_capture_dir = dest
            self.append_to_console(f"[Capture] moved to {dest}")
        except Exception as e:
            QMessageBox.warning(self, "Move capture", f"Could not move:\n{e}")

    def _open_capture_folder(self):
        os.makedirs(self.CAPTURE_ROOT, exist_ok=True)
        try:
            os.startfile(self.CAPTURE_ROOT)              # Windows-only, which is where the rig is
        except Exception as e:
            self.append_to_console(f"[Capture] folder: {self.CAPTURE_ROOT}  ({e})")

    def _update_capture_badges(self):
        """The two chips on the feed. REC blinks; CAP is steady — a blinking pair reads as an error.

        Driven from the DIC health timer (2 Hz), which is exactly a camera-style blink rate and
        costs nothing extra.
        """
        self._cap_blink = not getattr(self, "_cap_blink", False)
        cap, rec = self.capture.capturing, self.capture.recording
        st = self.capture.stats()
        off = "color:#6b7280; font-size:10px; font-weight:bold; padding:0 3px; border:none;"
        for name in ("capBadge", "capBadgeLP"):
            b = getattr(self, name, None)
            if b is None:
                continue
            b.setText("● CAP" if cap else "○ CAP")
            b.setStyleSheet("color:#2f9e44; font-size:10px; font-weight:bold; padding:0 3px;"
                            " border:none;" if cap else off)
            b.setToolTip(f"PNG frames: {st['png_written']} written into "
                         f"{st['png_files']} folder(s) — "
                         + ", ".join(p.style.key for p in self.capture.pngs)
                         + "\nClick to stop." if cap else
                         "Click to start saving PNG frames")
            # The buttons are also driven by test auto-start/stop, so their checked state has to
            # follow the sink rather than the last click.
            if b.isChecked() != cap:
                b.blockSignals(True); b.setChecked(cap); b.blockSignals(False)
        for name in ("recBadge", "recBadgeLP"):
            b = getattr(self, name, None)
            if b is None:
                continue
            b.setText("● REC" if rec else "○ REC")
            if rec:
                b.setStyleSheet(("color:#e03131;" if self._cap_blink else "color:#7a1f1f;")
                                + " font-size:10px; font-weight:bold; padding:0 3px; border:none;")
            else:
                b.setStyleSheet(off)
            b.setToolTip(f"AVI: {st['vid_written']} frames into {st['vid_files']} file(s) — "
                         + ", ".join(v.style.key for v in self.capture.videos)
                         + "\nClick to stop." if rec else "Click to start recording AVI")
            if b.isChecked() != rec:
                b.blockSignals(True); b.setChecked(rec); b.blockSignals(False)

    def apply_theme(self, name, *, announce=True):
        """Switch the whole GUI between dark and light, and remember the choice.

        Three things have to move together or the result is a dark shell around white rectangles:
        the Qt stylesheet, the two embedded matplotlib canvases (plain artists that know nothing
        about Qt), and the handful of colours hard-coded at their call sites."""
        import theme as _theme
        from PyQt6.QtWidgets import QApplication
        t = _theme.get(name)
        name = t["name"]
        self._theme = name

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_theme.stylesheet(name))

        # --- matplotlib: restyle in place, then force a redraw -------------------------------
        for fig, ax, note, guides, traces, canvas in (
            (getattr(self, "load_figure", None), getattr(self, "load_ax", None),
             getattr(self, "load_annotation", None),
             (getattr(self, "load_crosshair_h", None), getattr(self, "load_crosshair_v", None)),
             ((getattr(self, "load_line", None), 1), (getattr(self, "load_markers", None), 1)),
             getattr(self, "load_canvas", None)),
            (getattr(self, "ss_figure", None), getattr(self, "ss_ax", None),
             getattr(self, "ss_annotation", None),
             (getattr(self, "ss_crosshair_h", None), getattr(self, "ss_crosshair_v", None)),
             ((getattr(self, "ss_line", None), 1), (getattr(self, "ss_markers", None), 1),
              (getattr(self, "ss_dic_line", None), 2), (getattr(self, "ss_dic_markers", None), 2)),
             getattr(self, "ss_canvas", None)),
        ):
            if fig is None or ax is None:
                continue
            _theme.style_axes(fig, ax, name, annotation=note, guides=guides, traces=traces)
            if canvas is not None:
                canvas.draw_idle()

        # --- the toolbars sit on the figure background, so they follow it --------------------
        for tb in (getattr(self, "load_toolbar", None), getattr(self, "ss_toolbar", None)):
            if tb is not None:
                tb.setStyleSheet("background-color: %s;" % t["plot_bg"])

        # --- colours written into call sites -------------------------------------------------
        for attr in ("dicCauchyLabel", "dicCauchyLabelLP"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setStyleSheet("font-weight: bold; color: %s;" % t["info"])
        for attr in ("dicTrueLabel", "dicTrueLabelLP"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setStyleSheet("font-weight: bold; color: %s;" % t["amber_text"])

        sep = getattr(self, "_modeSeparatorLine", None)
        if sep is not None:
            sep.setStyleSheet("color:%s;" % (t["border"] if name == "dark" else "#bbbbbb"))

        # The crop sliders are custom-painted, so QSS cannot reach them — a 200-grey groove reads as
        # a glaring white bar across a dark GUI.
        from PyQt6.QtGui import QColor
        groove = QColor(t["raised_hi"]) if name == "dark" else QColor(200, 200, 200)
        for attr in ("cropRangeSlider", "ssCropRangeSlider"):
            sl = getattr(self, attr, None)
            if sl is not None and hasattr(sl, "set_groove_color"):
                sl.set_groove_color(groove)

        self._refresh_dic_badges()

        if getattr(self, "_themeActions", None):
            act = self._themeActions.get(name)
            if act is not None and not act.isChecked():
                act.setChecked(True)

        self._remember("ui/theme", name)
        if announce:
            self.append_to_console("[View] %s mode." % name.capitalize())

    def _refresh_dic_badges(self):
        """Re-push the DIC health chips so they pick up the new palette immediately rather than at
        the next camera frame (they are repainted from a timer that only runs with a live camera)."""
        try:
            self._update_dic_health()
        except Exception:
            pass

    # ---- window geometry: fit the screen it actually opens on --------------------------------
    #
    # DESIGN_SIZE is the target for a 15" laptop. Such a panel is usually 1920x1080 physical, but
    # Windows ships those at 150 % scaling, so the space Qt can actually use is 1280x720 LOGICAL
    # pixels. The .ui file asks for 1232x1098 — 378 px taller than that desktop — so the window
    # opened with its bottom below the screen and the layout could not be reached.
    DESIGN_SIZE = (1180, 700)

    def fit_to_screen(self):
        """Clamp the window to the screen's available area and centre it.

        Deliberately adaptive rather than a hard-coded resolution: the same build has to be usable
        on the laptop AND on the external monitor, and availableGeometry() already excludes the
        taskbar. A remembered size from a previous session is honoured, but is itself re-clamped —
        otherwise a size saved on the big monitor would reopen off-screen on the laptop.
        """
        from PyQt6.QtGui import QGuiApplication
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        margin = 24                                    # leave the frame some air

        w, h = self.DESIGN_SIZE
        saved = self._recall("window/size", None)
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                w, h = int(saved[0]), int(saved[1])
            except (TypeError, ValueError):
                w, h = self.DESIGN_SIZE

        # never larger than the desktop, never smaller than the window's own minimum
        w = max(self.minimumWidth(),  min(w, avail.width()  - margin))
        h = max(self.minimumHeight(), min(h, avail.height() - margin))
        self.resize(w, h)

        frame = self.frameGeometry()
        frame.moveCenter(avail.center())
        self.move(max(avail.left(), frame.left()), max(avail.top(), frame.top()))

    def closeEvent(self, event):
        """Handle application close event"""
        from PyQt6.QtWidgets import QMessageBox
        # Remember the size the operator settled on (re-clamped on the next open, see fit_to_screen).
        try:
            if not self.isMaximized() and not self.isFullScreen():
                self._remember("window/size", [self.width(), self.height()])
        except Exception:
            pass

        reply = QMessageBox.question(
            self,
            'Confirm Exit',
            'Are you sure you want to close the application?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Flush any capture BEFORE tearing anything down: the worker threads are daemons, so
            # exiting with frames still buffered would truncate the AVI and lose the last stills.
            try:
                if self.capture.active:
                    self._capture_stop(png=self.capture.capturing, video=self.capture.recording,
                                       reason="on exit")
            except Exception:
                pass
            # Disconnect serial port if connected
            if self.connected:
                self.serial_manager.disconnect()
            
            print("Goodbye!")
            event.accept()
        else:
            event.ignore()

# ========== DIC Camera Functions ==========

    def _setup_camera_display(self):
        """Create and insert the DIC camera display group into the Stress/Strain tab"""

        # Create the main group box
        self.cameraGroupBox = QGroupBox("DIC Camera")
        camera_layout = QVBoxLayout(self.cameraGroupBox)
        camera_layout.setContentsMargins(4, 4, 4, 4)
        camera_layout.setSpacing(4)

        # --- Button row (top, above camera feed) ---
        from PyQt6.QtWidgets import QComboBox
        button_row = QHBoxLayout()
        self.specimenModeCombo = QComboBox()
        self.specimenModeCombo.addItems(["White", "Black"])
        self.specimenModeCombo.setFixedWidth(80)
        self.specimenModeCombo.setToolTip("White = black dots on white specimen\nBlack = white dots on black specimen")
        self.startCameraButton = QPushButton("Start Camera")
        self.stopCameraButton = QPushButton("Stop Camera")
        # Both names for the same operation, side by side. "Tare DIC" is what this was called
        # before it was renamed, and it is still the name that comes to mind at the rig — but a
        # second button that also SET Px₀ would give the reference two owners, which is the bug
        # class already fixed once when Prepare test was re-taring it. So this is an alias: same
        # handler, same confirmation, no second path to the same state.
        self.tareDICAliasButton = QPushButton("Tare DIC")
        self.tareDICAliasButton.setToolTip(
            "The same operation as Calibrate Px₀ — freezes the pixel reference that DIC strain is "
            "measured against.\nKept under its older name because that is what it is called in the "
            "protocol sheets.")
        self.tareDICAliasButton.setEnabled(False)
        self.tareDICButton = QPushButton("Calibrate Px₀")
        self.tareDICButton.setToolTip(
            "Freeze Px₀  —  this IS the DIC tare, renamed.\n"
            "Px₀ is the marker separation in pixels that every strain is measured against: strain "
            "is (Px − Px₀)/Px₀, so whatever is already stretched into the specimen when you press "
            "this is invisible for the rest of the test.\n\n"
            "WHEN to press it is set by Settings ▸ DIC camera setup ▸ 'Zero strain AFTER preload', "
            "and the CSV header records which was used.\n\n"
            "The frozen marker pair stays on the live feed in cyan, so you can watch the green "
            "live pair pull away from it.")
        self.stopCameraButton.setEnabled(False)
        self.tareDICButton.setEnabled(False)
        button_row.addWidget(QLabel("Specimen:"))
        button_row.addWidget(self.specimenModeCombo)
        button_row.addWidget(self.startCameraButton)
        button_row.addWidget(self.stopCameraButton)
        button_row.addWidget(self.tareDICButton)
        button_row.addWidget(self.tareDICAliasButton)
        camera_layout.addLayout(button_row)

        # --- Info row: L0 and DIC Strain ---
        info_row = QHBoxLayout()
        self.dicHealthLabel = QLabel("DIC —")
        self.dicHealthLabel.setStyleSheet("font-weight: bold; padding: 1px 6px; border-radius: 6px; color: white; background: #8a8f98;")
        self.dicHealthLabel.setToolTip("Live DIC tracking health: markers found / % of recent frames tracked / pixel jitter.")
        # It is a status CHIP, so pin it to the height of its own text. A bare QLabel keeps the
        # default growable policy, so it happily absorbed the row's spare height and rendered as a
        # 150 px slab of colour — space that belongs to the camera feed underneath.
        self.dicHealthLabel.setFixedHeight(22)
        self.dicHealthLabel.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        info_row.addWidget(self.dicHealthLabel)
        self.capBadge, self.recBadge = self._make_capture_badges(info_row)
        info_row.addSpacing(16)
        info_row.addWidget(QLabel("Px₀:"))
        self.dicL0Label = QLabel("— px")   # Px₀ readout
        self.dicL0Label.setStyleSheet("font-weight: bold;")
        info_row.addWidget(self.dicL0Label)
        info_row.addSpacing(20)
        info_row.addWidget(QLabel("Eng ε:"))
        self.dicCauchyLabel = QLabel("—")
        self.dicCauchyLabel.setStyleSheet("font-weight: bold; color: #0066cc;")
        info_row.addWidget(self.dicCauchyLabel)
        info_row.addSpacing(12)
        info_row.addWidget(QLabel("True ε:"))
        self.dicTrueLabel = QLabel("—")
        self.dicTrueLabel.setStyleSheet("font-weight: bold; color: #cc6600;")
        info_row.addWidget(self.dicTrueLabel)
        info_row.addSpacing(20)
        # Camera settings sit BESIDE the numbers they produce, not in the group title. Exposure and
        # threshold are what those two strain figures are made of — when the strain looks wrong the
        # next question is always "what is the camera set to", and the answer should be in the same
        # glance rather than at the top of the box.
        self.dicParamsLabel = QLabel("—")
        self.dicParamsLabel.setStyleSheet("color: #8a8f98;")
        info_row.addWidget(self.dicParamsLabel)
        info_row.addStretch()
        camera_layout.addLayout(info_row)

        # --- Camera feed display label (below buttons) ---
        self.cameraFeedLabel = QLabel("Camera not started")
        self.cameraFeedLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # WHY Ignored + an explicit minimumSize, and not Expanding:
        # QLabel derives its sizeHint AND its minimumSizeHint from the pixmap it is holding. The feed
        # scales each frame to the label's CURRENT size and calls setPixmap, so with an Expanding
        # policy the label's hint grew to that frame, the layout granted it, the next frame was
        # scaled to the new larger width, and the window ratcheted outwards a few pixels per frame
        # until it hit the edge of the screen. That is the "GUI expands when I start the camera" bug.
        # QSizePolicy.Ignored makes the sizeHint irrelevant, and an EXPLICIT minimumSize overrides
        # minimumSizeHint — together they stop a pixmap from ever driving the layout.
        self.cameraFeedLabel.setMinimumSize(160, 120)
        self.cameraFeedLabel.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.cameraFeedLabel.setStyleSheet(
            "background-color: #1a1a1a; color: #888888; border: 1px solid #444;"
        )
        # Stretch = 1 is what actually gives the feed the leftover height. QSizePolicy.Ignored kills
        # the pixmap ratchet but, unlike Expanding, it carries no ExpandFlag — so on its own it does
        # NOT claim spare space, and the button/info rows above quietly took it instead. An explicit
        # stretch factor makes the claim independent of the size policy.
        camera_layout.addWidget(self.cameraFeedLabel, 1)

        # --- Insert group box below the stress-strain plot ---
        # stressStrainTab has no layout (absolute positioning from .ui)
        # We install a VBoxLayout on it and reparent the plot frame into it
        tab = self.stressStrainTab
        from PyQt6.QtWidgets import QSplitter, QGridLayout

        # Top panel: plot + controls + cropping
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(2, 2, 2, 2)
        top_layout.setSpacing(2)

        self.stressStrainPlotFrame.setParent(top_widget)
        top_layout.addWidget(self.stressStrainPlotFrame)

        # Compact controls row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(4)
        for group in [self.stressDataGroup, self.ssPlotControlsGroup, self.specimenDimensionsGroup]:
            group.setParent(top_widget)
            # 140, not 108: MEASURED natural heights are Stress/Strain data 83, Specimen dimensions
            # 91, and Plot Controls 137 — its grid is five rows deep. Capping the row at 108 clipped
            # the Clear Plot / Tare buttons, the display-rate spin box and the strain-source combo.
            # A maximum below a widget's own sizeHint does not compress it gracefully, it truncates.
            group.setMaximumHeight(146)   # natural 141 after the wider group-box title margins
            controls_row.addWidget(group)
        self._add_cross_readout("ss")        # force, inside the Stress/Strain Data box
        top_layout.addLayout(controls_row)

        # Replace absolute positioning in Plot Controls with a compact grid layout
        pc_grid = QGridLayout()
        pc_grid.setContentsMargins(4, 2, 4, 2)
        pc_grid.setSpacing(2)
        pc_grid.addWidget(self.clearStressStrainButton, 0, 0)
        pc_grid.addWidget(self.ssAutoScaleCheckBox, 0, 1)
        pc_grid.addWidget(self.tareButton_2, 1, 0)
        pc_grid.addWidget(self.ssShowMarkersCheckBox, 1, 1)
        pc_grid.addWidget(self.ssTogglePlotCheckBox, 2, 0, 1, 2)
        pc_grid.addWidget(self.displayRateLabel_2, 3, 0)
        pc_grid.addWidget(self.displayRateSpinBox_2, 3, 1)
        from PyQt6.QtWidgets import QComboBox
        pc_grid.addWidget(QLabel("Strain source:"), 4, 0)
        self.strainSourceCombo = QComboBox()
        # Display text says what the quantity IS. "Cauchy strain" is a synonym for ENGINEERING
        # strain, but sitting next to "True" it reads as if Cauchy = true (which is only correct
        # for STRESS) — that mislabelling reached the report axes. userData carries a stable key so
        # the plotting code never has to match on display text again.
        for _label, _key in (("Motor (crosshead)", "motor"),
                             ("DIC engineering  ΔL/L₀", "eng"),
                             ("DIC true / log  ln(L/L₀)", "true"),
                             ("Both (engineering + Motor)", "both_motor"),
                             ("Both (engineering + true)", "both_true")):
            self.strainSourceCombo.addItem(_label, _key)
        self.strainSourceCombo.setCurrentIndex(1)  # default: DIC engineering
        self.strainSourceCombo.setToolTip(
            "Which strain the stress-strain plot uses.\n\n"
            "DIC engineering  ΔL/L₀  — the reported basis. Matches ISO 527 and the add:north TDS,\n"
            "and pairs correctly with engineering stress F/A₀.\n"
            "DIC true / log  ln(L/L₀) — same measurement, log definition. Both are exact; they\n"
            "differ by only ~1.6 % at our 3 % failure strain.\n\n"
            "CSV columns keep their original names (DIC_Cauchy = engineering, DIC_True = log) so\n"
            "existing analysis scripts and past tests still work.")
        self.strainSourceCombo.currentIndexChanged.connect(self._on_strain_source_changed)
        pc_grid.addWidget(self.strainSourceCombo, 4, 1)
        old_pc_layout = self.ssPlotControlsGroup.layout()
        if old_pc_layout is not None:
            QWidget().setLayout(old_pc_layout)
        self.ssPlotControlsGroup.setLayout(pc_grid)

        # Data cropping — compact layout
        self.ssDataCroppingGroup.setParent(top_widget)
        self.ssDataCroppingGroup.setMinimumHeight(0)
        self.ssDataCroppingGroup.setMaximumHeight(84)   # natural 79; 54 clipped the Crop Data button
        crop_layout = QVBoxLayout()
        crop_layout.setContentsMargins(4, 2, 4, 2)
        crop_layout.setSpacing(2)
        crop_layout.addWidget(self.ssCropRangeSlider)
        crop_btn_row = QHBoxLayout()
        crop_btn_row.addWidget(self.cropDataButton_2)
        crop_btn_row.addStretch()
        crop_layout.addLayout(crop_btn_row)
        old_layout = self.ssDataCroppingGroup.layout()
        if old_layout is not None:
            QWidget().setLayout(old_layout)
        self.ssDataCroppingGroup.setLayout(crop_layout)
        top_layout.addWidget(self.ssDataCroppingGroup)

        # Splitter: top (plot+controls) | bottom (camera) — draggable.
        # The plot frame arrives from the .ui with a minimum tall enough to pin the splitter open,
        # which is why the camera was squeezed to a sliver at the bottom of the tab no matter what
        # sizes were requested. Relax it so the splitter can honour the split, then give the camera
        # a real share: on a 700 px window the specimen has to be visible without scrolling.
        # Keep the LEFT column's own minimum under the ~650 px a 15" laptop offers, or it re-triggers
        # the outer scroll that the control-panel fix just removed. Measured budget at a 700 px
        # window: plot 150 + controls 112 + cropping 58 + camera 250 + margins ≈ 600.
        # The plot is the thing that can afford to shrink here — the point of the screen is to SEE
        # THE SPECIMEN, and the plot is still fully readable on the Load Plot tab.
        # The stronger group-box outlines cost ~4 px per box; the plot gives that back at the
        # smallest window so no page scroll returns. It is the draggable pane, and 1180x700 is
        # the floor case — at any realistic window the splitter gives it far more.
        self.stressStrainPlotFrame.setMinimumHeight(125)
        # 200 is the camera group's own natural floor (button row + info row + a 120 px feed); asking
        # for more just wastes height. The 50 px the controls reclaimed above comes out of the
        # camera's SHARE below, not its floor.
        self.cameraGroupBox.setMinimumHeight(200)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.cameraGroupBox)
        # setSizes is the lever that actually sets the default split (the stretch factors only govern
        # how FURTHER resizing is shared). Calibrated against the operator's own screenshot: 340 was
        # the split that left the graph looking squeezed, and the response is linear at roughly
        # +0.7 px of plot per +1 px here, so 390 buys the graph ~35 px while the feed keeps ~390 px —
        # still comfortably more than the ~310 px it had when the specimen was already clearly
        # visible. The splitter is draggable, so this is only the starting position.
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([440, 280])   # +50 to the top: the controls row grew, the plot did not shrink
        splitter.setChildrenCollapsible(False)

        # Install the splitter into the tab
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(splitter)

    def _build_load_plot_camera_monitor(self):
        """DIC-camera panel for the Load Plot tab — a full duplicate of the Stress/Strain
        controls (Start/Stop/Tare/Specimen) plus feed + strain readouts. Both control sets
        drive the same handlers and are kept in sync via _set_camera_controls()."""
        from PyQt6.QtWidgets import QGroupBox, QComboBox
        box = QGroupBox("DIC Camera")
        self.cameraGroupBoxLP = box          # so _update_camera_params can retitle both mirrors
        lay = QVBoxLayout(box)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # --- Control row (mirrors the Stress/Strain controls) ---
        btn_row = QHBoxLayout()
        self.specimenModeComboLP = QComboBox()
        self.specimenModeComboLP.addItems(["White", "Black"])
        self.specimenModeComboLP.setFixedWidth(80)
        self.specimenModeComboLP.setToolTip(
            "White = black dots on white specimen\nBlack = white dots on black specimen")
        self.startCameraButtonLP = QPushButton("Start Camera")
        self.stopCameraButtonLP = QPushButton("Stop Camera")
        self.tareDICButtonLP = QPushButton("Calibrate Px₀")
        # Same alias as the Stress/Strain tab — one handler, no second owner of Px₀. The Load Plot
        # tab has its own camera row precisely so a whole test can be run without leaving it, so it
        # needs the same pair of names.
        self.tareDICAliasButtonLP = QPushButton("Tare DIC")
        self.tareDICAliasButtonLP.setToolTip(self.TARE_ALIAS_TIP)
        self.stopCameraButtonLP.setEnabled(False)
        self.tareDICButtonLP.setEnabled(False)
        self.tareDICAliasButtonLP.setEnabled(False)
        btn_row.addWidget(QLabel("Specimen:"))
        btn_row.addWidget(self.specimenModeComboLP)
        btn_row.addWidget(self.startCameraButtonLP)
        btn_row.addWidget(self.stopCameraButtonLP)
        btn_row.addWidget(self.tareDICButtonLP)
        btn_row.addWidget(self.tareDICAliasButtonLP)
        lay.addLayout(btn_row)

        info_row = QHBoxLayout()
        self.dicHealthLabelLP = QLabel("DIC —")
        self.dicHealthLabelLP.setStyleSheet("font-weight: bold; padding: 1px 6px; border-radius: 6px; color: white; background: #8a8f98;")
        self.dicHealthLabelLP.setToolTip("Live DIC tracking health: markers found / % of recent frames tracked / pixel jitter.")
        self.dicHealthLabelLP.setFixedHeight(22)          # a chip, not a slab — see dicHealthLabel
        self.dicHealthLabelLP.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        info_row.addWidget(self.dicHealthLabelLP)
        self.capBadgeLP, self.recBadgeLP = self._make_capture_badges(info_row)
        info_row.addSpacing(16)
        info_row.addWidget(QLabel("Px₀:"))
        self.dicL0LabelLP = QLabel("— px")
        self.dicL0LabelLP.setStyleSheet("font-weight: bold;")
        info_row.addWidget(self.dicL0LabelLP)
        info_row.addSpacing(20)
        info_row.addWidget(QLabel("Eng ε:"))
        self.dicCauchyLabelLP = QLabel("—")
        self.dicCauchyLabelLP.setStyleSheet("font-weight: bold; color: #0066cc;")
        info_row.addWidget(self.dicCauchyLabelLP)
        info_row.addSpacing(12)
        info_row.addWidget(QLabel("True ε:"))
        self.dicTrueLabelLP = QLabel("—")
        self.dicTrueLabelLP.setStyleSheet("font-weight: bold; color: #cc6600;")
        info_row.addWidget(self.dicTrueLabelLP)
        info_row.addSpacing(20)
        self.dicParamsLabelLP = QLabel("—")           # mirror — see dicParamsLabel
        self.dicParamsLabelLP.setStyleSheet("color: #8a8f98;")
        info_row.addWidget(self.dicParamsLabelLP)
        info_row.addStretch()
        lay.addLayout(info_row)

        self.cameraFeedLabelLP = QLabel("Camera not started")
        self.cameraFeedLabelLP.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cameraFeedLabelLP.setMinimumSize(160, 120)     # see cameraFeedLabel: pixmap ratchet
        self.cameraFeedLabelLP.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.cameraFeedLabelLP.setStyleSheet(
            "background-color: #1a1a1a; color: #888888; border: 1px solid #444;"
        )
        lay.addWidget(self.cameraFeedLabelLP, 1)         # stretch — see cameraFeedLabel
        return box

    # ---- live-feed overlay -------------------------------------------------------------------
    # Two marker pairs are drawn on the feed: where the speckles WERE when Px₀ was frozen, and
    # where they are NOW. Strain is (Px − Px₀)/Px₀, so the gap between the two pairs *is* the
    # measurement — showing it makes a bad tare (slack specimen, tare taken under preload, a marker
    # that jumped to a different blob) visible at a glance instead of only in the strain number.
    #
    # They are told apart by three things at once, not by colour alone: hue, line style, and RADIUS.
    # The radius matters most — at the instant of calibration the two pairs sit exactly on top of
    # each other, and same-size rings would simply disappear into one another.
    #
    # The frozen ring is drawn at a radius that straddles the EDGE of the speckle blob, so the same
    # stroke crosses near-black and near-white within a few pixels. No single colour survives that,
    # so every frozen mark is laid down twice: a casing first, the colour on top.
    #
    # The CASING has to oppose the mark. Cyan is a light colour, so it needs a near-black casing —
    # on the blob the cyan carries itself and the casing is simply invisible, while on the bright
    # specimen (where the travel arrows live) the casing is the whole reason the mark is legible.
    # Pairing cyan with the white casing that suited dark blue is what made the arrows wash out.
    PX0_RING_R   = 26
    LIVE_RING_R  = 20
    #
    # CASE_EXTRA is total added width, i.e. HALF of it per side, and it has to stay small: the feed
    # is displayed at roughly 0.4 scale, so a casing much wider than a pixel per side gets averaged
    # into the colour it is meant to protect and the cyan turns muddy green next to the live line.
    PX0_BGR      = (255, 255, 0)      # cyan — frozen reference
    PX0_CASE_BGR = (16, 16, 16)       # near-black casing, so it reads on specimen AND on blob
    PX0_CASE_EXTRA = 2
    LIVE_BGR     = (0, 255, 0)        # green — live
    DRIFT_MIN_PX = 8                  # below this a leader arrow is a stub, so don't draw one

    @staticmethod
    def _dashed_line(img, p1, p2, color, thickness=1, dash=14, gap=10):
        """A dashed straight line — cv2 has no dash style of its own."""
        x1, y1 = p1
        x2, y2 = p2
        span = math.hypot(x2 - x1, y2 - y1)
        if span < 1:
            return
        step = dash + gap
        n = int(span // step) + 1
        for i in range(n):
            a = (i * step) / span
            b = min(1.0, (i * step + dash) / span)
            cv2.line(img,
                     (int(x1 + (x2 - x1) * a), int(y1 + (y2 - y1) * a)),
                     (int(x1 + (x2 - x1) * b), int(y1 + (y2 - y1) * b)),
                     color, thickness, cv2.LINE_AA)

    @classmethod
    def _dashed_ring(cls, img, center, r, color, thickness=2):
        """Four 70° arcs — a dashed circle, so the frozen marker reads as a ghost, not a target."""
        for a in (0, 90, 180, 270):
            cv2.ellipse(img, center, (r, r), 0, a + 10, a + 80, color, thickness, cv2.LINE_AA)

    def _draw_dic_overlay(self, display, centroids):
        """Frozen Px₀ pair + live pair on the BGR frame, BEFORE the display rotation."""
        ref = getattr(self.camera_manager, "initial_centroids", None)
        has_ref = bool(ref) and len(ref) == 2

        # LIVE FIRST, frozen on top. Both lines run down the same specimen axis, so one has to sit
        # over the other. Painting the frozen line UNDER a solid green one left only a hairline of
        # colour showing past the green core, and at the ~0.4 display scale that averages to teal —
        # the frozen line effectively disappeared. Because the frozen line is DASHED, putting it on
        # top instead gives alternating frozen-dash / live-gap along the shared axis: both are fully
        # saturated, and past the frozen end-points the line goes pure green, which is the stretch.
        if len(centroids) == 2:
            live = sorted(centroids, key=lambda c: c[1])      # same axial order as the frozen pair
            p1 = (int(live[0][0]), int(live[0][1]))
            p2 = (int(live[1][0]), int(live[1][1]))
            for c in (p1, p2):
                cv2.circle(display, c, self.LIVE_RING_R, self.LIVE_BGR, 2, cv2.LINE_AA)
            cv2.line(display, p1, p2, self.LIVE_BGR, 2, cv2.LINE_AA)

        if has_ref:
            r1 = (int(ref[0][0]), int(ref[0][1]))
            r2 = (int(ref[1][0]), int(ref[1][1]))
            # Casing pass, then colour pass — see PX0_CASE_BGR.
            for col, extra in ((self.PX0_CASE_BGR, self.PX0_CASE_EXTRA), (self.PX0_BGR, 0)):
                self._dashed_line(display, r1, r2, col, 5 + extra, dash=26, gap=18)
                for c in (r1, r2):
                    self._dashed_ring(display, c, self.PX0_RING_R, col, 4 + extra)

        if len(centroids) != 2:
            return

        # One caliper per marker, frozen → live: the travel of THAT speckle, not just the pair's
        # separation. Both arrows growing outward = the specimen stretched; both pointing the same
        # way = the whole field translated (rig slip / camera knock), which strain alone would hide.
        #
        # Drawn OFF TO THE SIDE rather than centre-to-centre. Early travel is smaller than the rings
        # themselves, so an arrow on the axis spends the interesting part of the test buried under
        # the very markers it is measuring.
        if not has_ref:
            return
        for (rx, ry), cur in zip(ref, (p1, p2)):
            if abs(cur[1] - ry) < self.DRIFT_MIN_PX:
                continue
            xo = min(display.shape[1] - 3, int(cur[0]) + self.PX0_RING_R + 30)
            # The caliper is the smallest mark on the frame and the one carrying the least ink, so
            # it is drawn a step HEAVIER than the rings rather than a step lighter, and its tick is
            # wide enough to read as a datum line rather than a speck.
            tip = min(0.45, 20.0 / abs(cur[1] - ry))
            for col, extra in ((self.PX0_CASE_BGR, self.PX0_CASE_EXTRA), (self.PX0_BGR, 0)):
                cv2.line(display, (xo - 11, int(ry)), (xo + 11, int(ry)),
                         col, 3 + extra, cv2.LINE_AA)                    # tick at the frozen end
                cv2.arrowedLine(display, (xo, int(ry)), (xo, cur[1]), col, 3 + extra,
                                cv2.LINE_AA, tipLength=tip)

    # Caption colours are RGB — _draw_dic_caption runs AFTER the BGR→RGB conversion, unlike the
    # overlay. A light TINT of the mark colour, not the mark colour itself: #0D47A1 is chosen to sit
    # on a bright specimen, and the caption sits on the dark surround above it, so the same value
    # cannot serve both. Same hue keeps the link; the lightness follows the background.
    PX0_TEXT_RGB  = (120, 240, 255)
    PX0_WARN_RGB  = (255, 190, 90)
    CAPTION_BG    = (14, 18, 26)

    def _draw_dic_caption(self, rgb, centroids):
        """Px₀ vs now, in pixels, on the ROTATED frame. RGB here — the BGR swap already happened."""
        px0 = self.camera_manager.initial_distance
        if px0:
            text = f"Px0 {px0:.0f} px"
            if len(centroids) == 2:
                now = abs(centroids[1][1] - centroids[0][1])
                text += f"   ->   now {now:.0f} px    ({now - px0:+.0f})"
            color = self.PX0_TEXT_RGB
        else:
            text, color = "Px0 not set - press Calibrate Px0", self.PX0_WARN_RGB

        h = rgb.shape[0]
        fs = max(0.45, min(1.4, h / 380.0))
        th = max(2, int(round(1.8 * fs)))
        # A filled plate, not an outline. The previous version drew a 5 px black casing around a
        # 1 px coloured stroke, so most of what reached the eye was the casing — the text read as
        # black-on-dark. A plate also makes the caption legible if it ever lands on the bright
        # specimen rather than the dark surround.
        (tw, tht), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
        x0, y0, pad = 6, 6, 5
        cv2.rectangle(rgb, (x0, y0), (x0 + tw + 2 * pad, y0 + tht + base + 2 * pad),
                      self.CAPTION_BG, -1)
        cv2.rectangle(rgb, (x0, y0), (x0 + tw + 2 * pad, y0 + tht + base + 2 * pad),
                      color, 1, cv2.LINE_AA)
        cv2.putText(rgb, text, (x0 + pad, y0 + pad + tht), cv2.FONT_HERSHEY_SIMPLEX, fs,
                    color, th, cv2.LINE_AA)

    # The camera grabs at 35 fps and every one of those frames is MEASURED — that is the science and
    # it is untouched. Only the PICTURE is throttled here. Painting it costs ~6 ms of the GUI thread
    # per frame (colour convert, rotate, QImage, two pixmap scales); at 35 fps that is a fifth of the
    # thread spent redrawing a specimen that moves at 0.1 mm/s. Nobody can see the difference between
    # 12 fps and 35 fps on that; everybody can see a laggy button.
    FEED_MAX_FPS = 12

    def update_camera_feed(self, frame, centroids=None):
        try:
            now = time.monotonic()
            if (now - getattr(self, "_last_feed_paint", 0.0)) < 1.0 / self.FEED_MAX_FPS:
                return
            self._last_feed_paint = now

            # Make a copy to draw on
            display = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            # Blob overlay — frozen Px₀ reference (cyan, dashed) + live markers (green, solid).
            # The centroids arrive WITH the frame; re-detecting them here would be a second pass
            # over the same pixels and a second round of blobs_detected / error_occurred signals.
            if centroids is None:
                centroids = self.camera_manager.detect_blobs(frame)
            self._draw_dic_overlay(display, centroids)

            # Convert BGR to RGB for Qt, rotate 90° so specimen appears horizontal
            display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            display_rgb = cv2.rotate(display_rgb, cv2.ROTATE_90_CLOCKWISE)
            # Caption goes on AFTER the rotation — text drawn before it would come out sideways.
            self._draw_dic_caption(display_rgb, centroids)
            h, w, ch = display_rgb.shape
            bytes_per_line = ch * w

            qt_image = QImage(display_rgb.data.tobytes(), w, h,
                              bytes_per_line, QImage.Format.Format_RGB888)

            pixmap = QPixmap.fromImage(qt_image)
            if not pixmap.isNull():
                # render to the Stress/Strain feed and the Load Plot mirror (each to its own size)
                for lbl in (self.cameraFeedLabel, getattr(self, "cameraFeedLabelLP", None)):
                    if lbl is None:
                        continue
                    # Scale into the label's CONTENT rect, and never up-scale past it. Combined with
                    # the Ignored size policy set on both feed labels, this guarantees the frame can
                    # never push the layout outwards — the label follows the window, not the reverse.
                    box = lbl.contentsRect()
                    tw, th = max(1, box.width() - 2), max(1, box.height() - 2)
                    scaled = pixmap.scaled(
                        tw, th,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    lbl.setPixmap(scaled)
        except Exception as e:
            print(f"Feed error: {e}")

    # ===== Live DIC health badge (Phase C) =====
    def _live_blob_count(self):
        """Marker count, or 0 if no frame has arrived recently.

        `_dic_blob_count` is a scalar snapshot that only changes when a frame arrives, so if the
        camera stops it FREEZES at its last value and every consumer keeps reading a healthy "2".
        In T6.4 (S22, 2026-08-11) the DIC pipeline died at t=145 s and this reported 2/2 for the
        remaining 152 s -- the CSV header claimed "100 % frames tracked (3364/3364)" across a total
        blackout, and half the test's strain data was lost with no warning. Age it out instead."""
        if not self._dic_blob_t or (time.monotonic() - self._dic_blob_t) > self.DIC_BLOB_STALE_S:
            return 0
        return self._dic_blob_count

    def _on_dic_blobs(self, blobs):
        """A good frame: record its marker count for the health badge."""
        n = len(blobs)
        self._dic_blob_count = n
        self._dic_blob_t = time.monotonic()          # freshness stamp - see _live_blob_count()
        self._dic_blob_history.append(n)
        if len(self._dic_blob_history) > 60:
            del self._dic_blob_history[:-60]

    def _on_dic_error_count(self, msg):
        """A dropped frame ('...found N'): record it so tracking% reflects the dropout."""
        import re
        m = re.search(r"found (\d+)", str(msg))
        if not m:
            return
        n = int(m.group(1))
        self._dic_blob_count = n
        self._dic_blob_t = time.monotonic()
        self._dic_blob_history.append(n)
        if len(self._dic_blob_history) > 60:
            del self._dic_blob_history[:-60]

    # One definition for both tabs. The Load Plot camera monitor is built BEFORE the Stress/Strain
    # camera group, so the LP button cannot read this off the other button.
    TARE_ALIAS_TIP = ("The same operation as Calibrate Px₀ — freezes the pixel reference that DIC "
                      "strain is measured against.\nKept under its older name because that is what "
                      "it is called in the protocol sheets.")

    MARGIN_EVERY_S = 2.0        # contrast-margin recompute interval — see _update_dic_health

    def _update_dic_health(self):
        """Refresh the live DIC health badge (~2 Hz timer)."""
        # Same 2 Hz tick drives the CAP/REC chips — that is a camera-style blink rate already, and
        # a second timer for two labels would be waste on a thread this feature must not disturb.
        try:
            self._update_capture_badges()
            self._update_camera_params()
        except Exception:
            pass
        cm = getattr(self, "camera_manager", None)
        badges = [getattr(self, n, None) for n in ("dicHealthLabel", "dicHealthLabelLP")]
        if all(b is None for b in badges):
            return
        idle = "font-weight: bold; padding: 1px 6px; border-radius: 6px; color: white; background: #8a8f98;"
        if cm is None or getattr(cm, "camera", None) is None:      # camera not running -> idle badge
            self._dic_blob_history.clear()
            for b in badges:
                if b is not None:
                    b.setText("DIC —"); b.setStyleSheet(idle)
            return
        try:
            from utm_dic import dic_health, health_text
        except Exception:
            return
        h = dic_health(cm.dic_history, blob_history=self._dic_blob_history,
                       current_blobs=self._dic_blob_count,
                       expected_markers=getattr(self, "_expected_markers", 2))
        txt = health_text(h)
        colour = h["color"]
        # CONTRAST MARGIN — the one thing the existing badge could not see. Tracking %, marker count
        # and jitter all report whether it is working NOW; margin reports how close it is to not
        # working, which is what you want to know BEFORE the pull rather than after. A frame can sit
        # at a confident 2/2 with the markers 9 grey levels from the cut and lose them on a flicker.
        #
        # Auto-calibration deliberately never runs by itself, so this is how the operator finds out
        # that it is worth running.
        # Scoring costs ~4 ms, and this badge refreshes at 2 Hz — enough of a periodic hitch to show
        # up in the GUI-latency check. Margin is a property of the LIGHTING, which moves over
        # seconds to minutes, so it is recomputed every MARGIN_EVERY_S and cached in between.
        tip = ""
        now = time.monotonic()
        frame = getattr(cm, "latest_frame", None)
        if frame is not None and h.get("blobs") != 0 and \
                now - getattr(self, "_margin_t", 0.0) >= self.MARGIN_EVERY_S:
            self._margin_t = now
            try:
                import utm_autocal as _ac
                m = _ac.frame_score(frame, cm.THRESHOLD, cm.THRESHOLD_TYPE,
                                    min_area=cm.MIN_AREA, max_area=cm.MAX_AREA,
                                    min_circ=cm.MIN_CIRCULARITY)
                self._margin = m.get("margin") if m["n_blobs"] == 2 else None
            except Exception:
                self._margin = None
        margin = getattr(self, "_margin", None)
        if margin is not None:
            txt += f" · margin {margin:.0f}"
            if margin < _AC_MIN_MARGIN:
                # Downgrade a green badge: it IS tracking, which is exactly why this is worth
                # saying — nothing else on screen would tell you it is about to stop.
                colour = "#d29922"
                txt = txt.replace("DIC OK", "DIC FRAGILE")
                tip = (f"\n\n⚠ Markers are only {margin:.0f} grey levels from the threshold. "
                       "Tracking now, but one lighting flicker from losing them.\n"
                       "Settings ▸ DIC camera setup ▸ Auto-calibrate… would fix this.")
        style = f"font-weight: bold; padding: 1px 6px; border-radius: 6px; color: white; background: {colour};"
        for b in badges:
            if b is not None:
                b.setText(txt); b.setStyleSheet(style)
                b.setToolTip("Live DIC tracking health: markers found / % of recent frames tracked "
                             "/ pixel jitter / contrast margin in grey levels." + tip)

    def update_dic_strain_label(self, cauchy, true_strain):
        self.latest_dic_cauchy = cauchy
        self.latest_dic_true_strain = true_strain
        self.dicCauchyLabel.setText(f"{cauchy:.6f}")
        self.dicTrueLabel.setText(f"{true_strain:.6f}")
        if hasattr(self, "dicCauchyLabelLP"):
            self.dicCauchyLabelLP.setText(f"{cauchy:.6f}")
            self.dicTrueLabelLP.setText(f"{true_strain:.6f}")

        # --- 8.4.6 VALIDATION (temporary) — throttled to ~1 Hz ---
        import time
        now = time.monotonic()
        if now - getattr(self, '_last_val_log', 0) >= 1.0:
            self._last_val_log = now
            motor_strain = self.motor_displacement_mm / self.gauge_length if self.gauge_length > 0 else 0
            self.append_to_console(
                f"[DIC] ε_c={cauchy:.6f} | ε_t={true_strain:.6f} | Motor={motor_strain:.6f} | Δ(ε_c−Motor)={cauchy - motor_strain:.6f}"
            )

    # Blob-detection failures are emitted per FRAME, so a lighting problem writes 35 identical lines
    # a second into the camera console — which buries the one line that would tell you what changed
    # and makes the console useless exactly when you need to read it. Identical messages are
    # coalesced into one line per second carrying the repeat count. The health HUD is fed from the
    # same signal separately and still sees EVERY frame, so tracking % stays exact.
    CAM_ERR_COALESCE_S = 1.0

    def on_camera_error(self, msg):
        now = time.monotonic()
        same = (msg == self._cam_err_last)
        if same and (now - self._cam_err_t) < self.CAM_ERR_COALESCE_S:
            self._cam_err_n += 1
            return
        repeats = f"   (x{self._cam_err_n + 1})" if same and self._cam_err_n else ""
        self._cam_err_last, self._cam_err_t, self._cam_err_n = msg, now, 0
        self.append_to_console(f"[Camera Error] {msg}{repeats}")

    def on_camera_connection_changed(self, connected):
        self.append_to_console(f"[Camera] {'Connected' if connected else 'Disconnected'}")

    def _set_camera_controls(self, running):
        """Flip enabled-state of BOTH control sets (Stress/Strain + Load Plot) together."""
        for start in (self.startCameraButton, getattr(self, "startCameraButtonLP", None)):
            if start is not None:
                start.setEnabled(not running)
        for w in (self.stopCameraButton, self.tareDICButton,
                  getattr(self, "tareDICAliasButton", None),
                  getattr(self, "stopCameraButtonLP", None),
                  getattr(self, "tareDICButtonLP", None),
                  getattr(self, "tareDICAliasButtonLP", None)):
            if w is not None:
                w.setEnabled(running)
        for combo in (self.specimenModeCombo, getattr(self, "specimenModeComboLP", None)):
            if combo is not None:
                combo.setEnabled(not running)

    def on_specimen_mode_changed(self, mode):
        # Keep both tab combos in sync without re-triggering this handler.
        for combo in (self.specimenModeCombo, getattr(self, "specimenModeComboLP", None)):
            if combo is not None and combo.currentText() != mode:
                combo.blockSignals(True)
                combo.setCurrentText(mode)
                combo.blockSignals(False)
        self.camera_manager.set_specimen_mode(mode)
        self.append_to_console(f"[Camera] Specimen mode: {mode}")

    def on_start_camera(self):
        # Apply the dropdown's preset (ROI + threshold) before connecting. The combo's
        # initial "White" value is set before its signal is connected, so on_specimen_mode_changed
        # never fires on startup — without this the camera would start in the default Black
        # preset (wrong ROI + wrong polarity → "found 0 blobs") regardless of the selection.
        self.camera_manager.set_specimen_mode(self.specimenModeCombo.currentText())
        if self.camera_manager.connect_camera():
            self.camera_manager.start_acquisition()
            self.camera_active = True
            self._set_camera_controls(running=True)
            self.append_to_console("[Camera] Started")
        else:
            self.append_to_console("[Camera] Failed to connect")

    def on_stop_camera(self):
        self.camera_manager.stop_acquisition()
        self.camera_manager.disconnect_camera()
        self.camera_active = False
        self._set_camera_controls(running=False)
        self.cameraFeedLabel.setText("Camera not started")
        self.cameraFeedLabel.setPixmap(QPixmap())
        #self.dicStrainLabel.setText("—")
        self.dicCauchyLabel.setText("—")
        self.dicTrueLabel.setText("—")
        self.dicL0Label.setText("— px")
        if hasattr(self, "cameraFeedLabelLP"):
            self.cameraFeedLabelLP.setText("Camera not started")
            self.cameraFeedLabelLP.setPixmap(QPixmap())
            self.dicCauchyLabelLP.setText("—")
            self.dicTrueLabelLP.setText("—")
            self.dicL0LabelLP.setText("— px")
        self.append_to_console("[Camera] Stopped")

    # Load above which Px₀ is almost certainly being captured on an already-stretched specimen.
    # 300 N on an 80 mm² 50 %-infill dogbone is 3.75 MPa; at E ~1.5 GPa that is ~2500 µε already in
    # the specimen — 96x the 26 µε DIC noise floor, and strain referenced to it silently EXCLUDES
    # that. This is the same effect that makes T9's creep/instantaneous ratio an upper bound.
    PX0_LOAD_WARN_N = 25.0

    def on_calibrate_px0(self):
        """The Calibrate Px₀ BUTTON. Confirms the specimen state first, then captures.

        This is now the ONLY path that moves Px₀ — Prepare test no longer tares DIC. Kept as a
        wrapper rather than connecting on_tare_dic directly because `clicked` passes a bool as the
        first positional argument: as a slot it would arrive in `confirm` as False and silently
        skip the dialog."""
        self.on_tare_dic(confirm=True)

    def _prep_checklist(self):
        """The pre-test steps, in the order the CURRENT strain-zero convention requires.

        Not just a relabelling: the convention changes the SEQUENCE. Under the after-preload rule
        the preload comes first and Px₀ is frozen on the seated specimen, so a checklist that still
        read "Calibrate Px₀ (BEFORE preload) · applied preload" would be walking the operator
        through the opposite procedure to the one the app is set up for.

        Calibrate Px₀ stays ahead of Prepare test in both, because Prepare test tares the FORCE —
        after it the load reads ~0 N, and the Px₀ dialog would then object that the preload it
        expects is not there.
        """
        if self.px0_after_preload():
            return ("   •  mounted the specimen\n"
                    "   •  applied preload\n"
                    "   •  pressed Calibrate Px₀ (AFTER preload)\n"
                    "   •  pressed Prepare test (tared)\n")
        return ("   •  mounted the specimen\n"
                "   •  pressed Calibrate Px₀ (BEFORE preload)\n"
                "   •  applied preload\n"
                "   •  pressed Prepare test (tared)\n")

    def on_px0_convention_changed(self, on):
        """Switching the strain-zero convention invalidates the Px₀ currently held, because that
        one was frozen under the OTHER rule. Say so rather than letting the next test inherit it."""
        self._remember("dic/px0_after_preload", bool(on))
        where = "AFTER preload (seated state)" if on else "BEFORE preload (unloaded state)"
        self.append_to_console(f"[DIC] Strain zero convention: {where}. Recorded in every CSV header.")
        if self.camera_manager.initial_distance is not None:
            self.append_to_console(
                "[DIC] ⚠ The Px₀ currently held was frozen under the previous convention — "
                "re-run Calibrate Px₀ before the next test, or its strain will not mean what the "
                "header says.")

    def px0_after_preload(self):
        """Which state strain is measured FROM. A convention, not a preference.

        BEFORE preload — zero at the as-mounted, near-unloaded specimen. Strain then covers every
        bit of deformation the specimen ever saw, including what the preload put in.

        AFTER preload — zero at the seated, preloaded state. Reproducible, and it starts from a
        defined force rather than from however the specimen happened to sit in the grips; but the
        preload stretch is excluded from every reading that follows.

        Neither is wrong. Mixing them silently IS: at 300 N on 80 mm² the two differ by roughly
        0.13 % of strain, which lands directly on epsilon_f and on toughness. So the choice is
        explicit, it is remembered, and it is written into the CSV header of every test.

        DEFAULTS TO AFTER-PRELOAD as of 2026-08-14 (from S25 onward). It starts strain from a
        defined force rather than from however the specimen happened to sit in the grips, which is
        the more reproducible of the two. S24 and everything before it were run BEFORE preload —
        their headers say so, and the two are not directly comparable on ef or toughness without
        accounting for the offset.
        """
        return self._recall_bool("dic/px0_after_preload", True)

    def _confirm_px0(self, load):
        """Ask before freezing the strain zero. This is the one click in the workflow whose TIMING
        changes the numbers, so it is worth a question — and the question depends on the convention
        in force, because "300 N showing" is a mistake under one and the whole point of the other."""
        from PyQt6.QtWidgets import QMessageBox
        after = self.px0_after_preload()
        # "Wrong" means: not in the state this convention expects.
        hot = (load <= self.PX0_LOAD_WARN_N) if after else (load > self.PX0_LOAD_WARN_N)
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning if hot else QMessageBox.Icon.Question)
        msg.setWindowTitle("Calibrate Px₀")
        msg.setText("Freeze the pixel reference now?")
        body = ("Px₀ is the marker separation that every strain is measured against, so this sets "
                "the ZERO of strain.\n\nConfirm that:\n"
                "   •  the specimen is mounted in BOTH grips\n"
                "   •  it is straight — not slack, not bowed\n"
                + ("   •  preload HAS been applied and settled\n" if after
                   else "   •  preload has NOT been applied yet\n")
                + f"\nConvention: zero strain at the {'PRELOADED' if after else 'UNLOADED'} state"
                + f"\nLoad right now: {load:.1f} N")
        if hot and after:
            body += (f"\n\n⚠  This convention expects the preload to be ON, but the load is only "
                     f"{load:.1f} N. Freezing here measures strain from the unloaded state instead "
                     "— the opposite of what is set.")
        elif hot:
            area = getattr(self, "cross_sectional_area", 0.0) or 0.0
            extra = f" — that is {load/area:.2f} MPa already in it" if area > 0 else ""
            body += (f"\n\n⚠  That is above {self.PX0_LOAD_WARN_N:.0f} N, so the specimen is already "
                     f"stretched{extra}. Anything already in it becomes invisible to every strain "
                     "reading from here on. Release the load first, or switch the convention in "
                     "Settings ▸ DIC camera setup.")
        msg.setInformativeText(body)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel if hot
                             else QMessageBox.StandardButton.Yes)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def on_tare_dic(self, confirm=False):
        """Freeze Px₀ — the marker separation in pixels that every strain is measured against.

        WHEN this is captured defines the zero of strain, so it is a measurement decision, not
        bookkeeping: strain is (Px − Px₀)/Px₀, so anything already stretched into the specimen at
        capture time is invisible for the rest of the test.

        Which state to capture from is the convention in px0_after_preload() — before preload on a
        straight, barely-loaded specimen, or after it on a seated one. Both are defensible; the
        header records which, because mixing them within a series is not.
        """
        load = abs(getattr(self, "current_load", 0.0) or 0.0)
        if confirm and not self._confirm_px0(load):
            self.append_to_console("[DIC] Px₀ calibration cancelled — reference unchanged.")
            return
        self.camera_manager.gauge_length_mm = self.gauge_length
        self.camera_manager.tare_dic()
        if self.camera_manager.initial_distance is None:
            return
        px0 = self.camera_manager.initial_distance
        self._px0_load_N = load
        txt = f"{px0:.1f} px  @ {load:.0f} N"
        for lbl in (getattr(self, "dicL0Label", None), getattr(self, "dicL0LabelLP", None)):
            if lbl is not None:
                lbl.setText(txt)
        self.append_to_console(
            f"[DIC] Px₀ = {px0:.1f} px  (gauge {self.gauge_length:.1f} mm → "
            f"{self.camera_manager.px_per_mm:.2f} px/mm), captured at {load:.1f} N")
        if self.px0_after_preload():
            area = getattr(self, "cross_sectional_area", 0.0) or 0.0
            self.append_to_console(
                f"[DIC] Convention: strain is measured from the PRELOADED state ({load:.0f} N"
                + (f" = {load/area:.2f} MPa" if area > 0 else "") + "). The stretch already in the "
                "specimen is excluded by design; the CSV header records this.")
        elif load > self.PX0_LOAD_WARN_N:
            self.append_to_console(
                f"[DIC] ⚠ Px₀ was captured under {load:.0f} N. Strain is measured from HERE, so the "
                "stretch already in the specimen is excluded from every reading. Release the load, "
                "press Calibrate Px₀ again, THEN preload.")

def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)

    # Create and show the main window. fit_to_screen() runs AFTER construction so it sees the
    # finished layout's minimums, and BEFORE show() so the window never flashes at the wrong size.
    window = UTMApplication()
    window.fit_to_screen()
    window.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
