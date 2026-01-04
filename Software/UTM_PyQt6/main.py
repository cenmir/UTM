"""
UTM Control Application - PyQt6
Universal Testing Machine Control Software

Main application file that initializes the GUI and manages the application lifecycle.

============================================
APPLICATION VERSION - UPDATE ON EVERY COMMIT!
============================================
"""

__version__ = "0.5.3"


import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressDialog, QVBoxLayout, QFileDialog
from PyQt6.QtCore import QTimer
from PyQt6 import uic
from serial_manager import SerialManager
from widgets import FluentSwitch, SpeedGauge, RangeSlider
from datetime import datetime

# Matplotlib imports for embedding plots
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

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
        speed_unit_label = QLabel("Speed unit:")
        layout.addWidget(speed_unit_label)

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
        self.label_3.setText("Set speed:")

        # Add unit label after spinbox
        self.speedUnitValueLabel = QLabel("mm/s")
        self.horizontalLayout_setSpeed.addWidget(self.speedUnitValueLabel)

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
                self.speedGauge.setFixedSize(150, 150)
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
            # Remove the placeholder
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self.loadPlotPlaceholder:
                    layout.removeWidget(self.loadPlotPlaceholder)
                    self.loadPlotPlaceholder.hide()
                    self.loadPlotPlaceholder.deleteLater()
                    break
            # Add the canvas
            layout.addWidget(self.load_canvas)
        else:
            # Create a layout if none exists
            layout = QVBoxLayout(self.loadPlotFrame)
            layout.setContentsMargins(0, 0, 0, 0)
            self.loadPlotPlaceholder.hide()
            self.loadPlotPlaceholder.deleteLater()
            layout.addWidget(self.load_canvas)

        self.load_figure.tight_layout()

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
        self.ss_figure = Figure(figsize=(8, 4), dpi=100)
        self.ss_figure.set_facecolor('#f0f0f0')
        self.ss_canvas = FigureCanvas(self.ss_figure)

        # Create the axes
        self.ss_ax = self.ss_figure.add_subplot(111)
        self.ss_ax.set_xlabel('Strain (mm/mm)')
        self.ss_ax.set_ylabel('Stress (MPa)')
        self.ss_ax.set_title('Stress vs Strain')
        self.ss_ax.grid(True, alpha=0.3)

        # Create the line object (empty initially)
        self.ss_line, = self.ss_ax.plot([], [], 'b-', linewidth=1)
        self.ss_markers, = self.ss_ax.plot([], [], 'b.', markersize=3)

        # Create crop selection markers (vertical lines and shaded region)
        self.ss_crop_line_low = self.ss_ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5, visible=False)
        self.ss_crop_line_high = self.ss_ax.axvline(x=0, color='red', linestyle='--', linewidth=1.5, visible=False)
        self.ss_crop_span = self.ss_ax.axvspan(0, 1, alpha=0.2, color='yellow', visible=False)

        # Replace the placeholder with the canvas
        layout = self.stressStrainPlotFrame.layout()
        if layout is not None:
            # Remove the placeholder
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self.stressStrainPlotPlaceholder:
                    layout.removeWidget(self.stressStrainPlotPlaceholder)
                    self.stressStrainPlotPlaceholder.hide()
                    self.stressStrainPlotPlaceholder.deleteLater()
                    break
            # Add the canvas
            layout.addWidget(self.ss_canvas)
        else:
            # Create a layout if none exists
            layout = QVBoxLayout(self.stressStrainPlotFrame)
            layout.setContentsMargins(0, 0, 0, 0)
            self.stressStrainPlotPlaceholder.hide()
            self.stressStrainPlotPlaceholder.deleteLater()
            layout.addWidget(self.ss_canvas)

        self.ss_figure.tight_layout()

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

    def _update_load_plot(self):
        """Update the load plot (called by timer at 5 Hz)"""
        if not self.load_plot_needs_update:
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

    def _update_stress_strain_plot(self):
        """Update the stress-strain plot (called by timer)"""
        if not self.stress_strain_plot_needs_update:
            return

        self.stress_strain_plot_needs_update = False

        n_points = len(self.stress_strain_strains)
        if n_points == 0:
            return

        # Downsample for display if we have too many points
        if n_points > self.LOAD_PLOT_DOWNSAMPLE_THRESHOLD:
            # Calculate step size to get approximately DISPLAY_POINTS
            step = max(1, n_points // self.LOAD_PLOT_DISPLAY_POINTS)
            strains = self.stress_strain_strains[::step]
            stresses = self.stress_strain_stresses[::step]
            # Always include the last point for real-time feel
            if self.stress_strain_strains[-1] not in strains:
                strains = strains + [self.stress_strain_strains[-1]]
                stresses = stresses + [self.stress_strain_stresses[-1]]
        else:
            strains = list(self.stress_strain_strains)
            stresses = list(self.stress_strain_stresses)

        # Update the line data
        self.ss_line.set_data(strains, stresses)

        # Update markers if enabled
        if hasattr(self, 'ssShowMarkersCheckBox') and self.ssShowMarkersCheckBox.isChecked():
            self.ss_markers.set_data(strains, stresses)
            self.ss_markers.set_visible(True)
        else:
            self.ss_markers.set_visible(False)

        # Auto-scale if enabled
        if hasattr(self, 'ssAutoScaleCheckBox') and self.ssAutoScaleCheckBox.isChecked():
            if len(strains) > 1 and min(strains) != max(strains):
                self.ss_ax.set_xlim(min(strains), max(strains))
            # Recalculate y-axis limits
            self.ss_ax.relim()
            self.ss_ax.autoscale_view(scalex=False, scaley=True)

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
        self.tareButton_2.clicked.connect(self.on_tare)
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
        self.moveUpButton.clicked.connect(self.on_move_up)
        self.moveDownButton.clicked.connect(self.on_move_down)

        # Right panel - Data export/import
        self.saveDataButton.clicked.connect(self.on_save_data)
        self.openDataButton.clicked.connect(self.on_open_data)

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

    def append_to_console(self, message):
        """Append a message to the console with optional timestamp"""
        from datetime import datetime

        if self.timestampCheckBox.isChecked():
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            message = f"{timestamp} -> {message}"

        self.consoleTextEdit.append(message)

        # Auto-scroll to bottom if enabled
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
        """Clear the console text"""
        self.consoleTextEdit.clear()
        self.append_to_console("Console cleared")

    # ========== Stress/Strain Functions ==========

    def on_clear_stress_strain_plot(self):
        """Clear the stress-strain plot"""
        # TODO: Implement when matplotlib canvas is added
        self.append_to_console("Stress-Strain plot cleared")
        pass

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

        # Get x positions (strain values) for the markers
        low_strain = self.stress_strain_strains[low_idx]
        high_strain = self.stress_strain_strains[high_idx]

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
        self.force_offset = self.force_offset + self.current_load
        self.offsetSpinBox.blockSignals(True)
        self.offsetSpinBox.setValue(self.force_offset)
        self.offsetSpinBox.blockSignals(False)
        self.append_to_console(f"Force offset adjusted to {self.force_offset:.4f}")

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

        # Emergency stop - always enabled when connected (safety!)
        self.emergencyStopButton.setEnabled(connected)

        # Position group - enabled only when connected
        self.displacementLabel.setEnabled(connected)
        self.tareLocationButton.setEnabled(connected)

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

    def _init_speed_controls(self):
        """Initialize speed controls with mm/s defaults"""
        # Set spinbox for mm/s mode with safety limit
        self.setSpeedSpinBox.setMaximum(self.MAX_MM_PER_S)  # Limited by MAX_RPM
        self.setSpeedSpinBox.setDecimals(3)
        self.setSpeedSpinBox.setSingleStep(0.1)
        self.setSpeedSpinBox.setValue(0.1)  # Default 0.1 mm/s (~24 RPM)

        # Initialize speed display to 0 (no measured speed yet)
        self.speedDisplayLabel.setText("Speed: 0.00 mm/s")

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
        self.speedDisplayLabel.setText(f"Speed: {value:.2f} {unit}")

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
            self.serial_manager.send_command("Up")
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
            self.serial_manager.send_command("Down")
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

    def on_emergency_stop(self):
        """Emergency stop button pressed"""
        self.append_to_console("EMERGENCY STOP activated!")
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
            # Calculate steps: 200 steps/rev * 8 microstepping * 20 gear ratio / 5mm pitch
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
            # Calculate steps (negative for down)
            steps = -round(200 * 8 * 20 * distance / 5)
            self.serial_manager.send_command(f"MoveSteps {steps}")

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
            self.data_unsaved = False
            self._update_plot_title()
            self.append_to_console(f"Data saved to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save data:\n{str(e)}")
            self.append_to_console(f"Export error: {str(e)}")

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
            if comment:
                f.write(f"# Comment: {comment}\n")
            f.write("#\n")
            f.write(f"# Calibration - Scale: {self.force_scale}, Offset: {self.force_offset}\n")
            f.write(f"# Specimen - Area: {self.cross_sectional_area} mm², Gauge Length: {self.gauge_length} mm\n")
            f.write("#\n")
            f.write(f"# Max Load: {self.max_load:.2f} N\n")
            f.write(f"# Max Stress: {max_stress:.4f} MPa\n")
            f.write(f"# Max Strain: {max_strain:.6f}\n")
            f.write("#\n")
            f.write(f"# App Version: {__version__}\n")
            f.write(f"# Firmware Version: {self.firmware_version}\n")
            f.write("#\n")

            # Write data header
            f.write("Time_s,RawADC,Force_N,Position_mm,Speed_mm_s,Strain,Stress_MPa\n")

            # Write data rows
            for i in range(n_points):
                elapsed_s = (self.load_plot_times[i] - first_time).total_seconds()
                raw_adc = self.load_plot_raw_forces[i]
                force = self.load_plot_forces[i]
                position = self.load_plot_positions[i] if i < len(self.load_plot_positions) else 0
                speed = self.load_plot_speeds[i] if i < len(self.load_plot_speeds) else 0
                strain = position / self.gauge_length if self.gauge_length > 0 else 0
                stress = force / self.cross_sectional_area if self.cross_sectional_area > 0 else 0

                f.write(f"{elapsed_s:.3f},{raw_adc:.0f},{force:.4f},{position:.4f},{speed:.4f},{strain:.6f},{stress:.4f}\n")

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
            self.append_to_console(f"Data loaded from: {file_path}")
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
        self.stress_strain_strains.clear()
        self.stress_strain_stresses.clear()

        # Metadata to extract
        comment = ""
        calibration_scale = None
        calibration_offset = None
        specimen_area = None
        gauge_length = None

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

                    # Create timestamp from elapsed time
                    from datetime import timedelta
                    timestamp = base_time + timedelta(seconds=elapsed_s)

                    self.load_plot_times.append(timestamp)
                    self.load_plot_raw_forces.append(raw_adc)
                    self.load_plot_forces.append(force)
                    self.load_plot_positions.append(position)
                    self.load_plot_speeds.append(speed)
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
            self.ssMaxStressValue.setText(f"{self.max_stress:.4f}")
        else:
            self.max_stress = 0.0
            self.ssMaxStressValue.setText("0.0000")

        if self.stress_strain_strains:
            self.max_strain = max(self.stress_strain_strains, key=abs)
            self.ssMaxStrainValue.setText(f"{self.max_strain:.6f}")
        else:
            self.max_strain = 0.0
            self.ssMaxStrainValue.setText("0.000000")

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

    def on_load_cell_data(self, raw_value):
        """Handle parsed load cell data"""
        # If calibration is active, collect raw values
        if self.calibration_active:
            self.calibration_raw_buffer.append(raw_value)

        # Calculate calibrated force: F = -(raw * scale) - offset
        force = -(raw_value * self.force_scale) - self.force_offset

        self.current_load = force
        self.update_load_display()

        # Add to plot data if:
        # 1. Load cell data stream is enabled (loadCellSwitch)
        # 2. Plot checkbox is checked (loadTogglePlotCheckBox)
        load_cell_on = hasattr(self, 'loadCellSwitch') and self.loadCellSwitch.isChecked()
        plot_enabled = hasattr(self, 'loadTogglePlotCheckBox') and self.loadTogglePlotCheckBox.isChecked()

        if load_cell_on and plot_enabled:
            now = datetime.now()
            # Store all data points
            self.load_plot_times.append(now)
            self.load_plot_forces.append(force)
            self.load_plot_raw_forces.append(raw_value)
            self.load_plot_positions.append(self.motor_displacement_mm)
            # Convert RPM to mm/s: (RPM / 60) * (5mm / 20) = RPM * 5 / 1200
            speed_mm_s = self.motor_velocity_rpm * 5.0 / 1200.0
            self.load_plot_speeds.append(speed_mm_s)

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

        # Calculate displacement relative to tare point (positive going down)
        self.motor_displacement_mm = -(position_mm - self.motor_position_zero)

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
        if self.stall_detection_enabled and self.motorsSwitch.isChecked() and not self.movement_start_grace_period:
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

    def closeEvent(self, event):
        """Handle application close event"""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            'Confirm Exit',
            'Are you sure you want to close the application?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Disconnect serial port if connected
            if self.connected:
                self.serial_manager.disconnect()
            
            print("Goodbye!")
            event.accept()
        else:
            event.ignore()


def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)

    # Create and show the main window
    window = UTMApplication()
    window.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
