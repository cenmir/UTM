"""
UTM Control Application - PyQt6
Universal Testing Machine Control Software

Main application file that initializes the GUI and manages the application lifecycle.

============================================
APPLICATION VERSION - UPDATE ON EVERY COMMIT!
============================================
"""

__version__ = "0.2.7"


import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6 import uic
from serial_manager import SerialManager
from widgets import FluentSwitch, SpeedGauge

# Path to the UI file
UI_FILE = Path(__file__).parent / "ui" / "utm_mainwindow.ui"


class UTMApplication(QMainWindow):
    """Main application window for UTM control"""

    def __init__(self):
        super().__init__()

        # Load the UI file
        uic.loadUi(UI_FILE, self)

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

    def connect_signals(self):
        """Connect UI signals to their respective slot functions"""
        # Console controls
        self.sendButton.clicked.connect(self.on_send_command)
        self.clearConsoleButton.clicked.connect(self.on_clear_console)
        self.commandLineEdit.returnPressed.connect(self.on_send_command)

        # Stress/Strain tab controls
        self.clearStressStrainButton.clicked.connect(self.on_clear_stress_strain_plot)
        self.areaSpinBox.valueChanged.connect(self.on_specimen_dimensions_changed)
        self.gaugeLengthSpinBox.valueChanged.connect(self.on_specimen_dimensions_changed)

        # Load Plot tab controls
        self.clearLoadPlotButton.clicked.connect(self.on_clear_load_plot)
        self.tareButton.clicked.connect(self.on_tare)

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

        # Right panel - Save data
        self.saveDataButton.clicked.connect(self.on_save_data)

    def init_state(self):
        """Initialize application state variables"""
        from PyQt6.QtCore import QTimer

        # Serial communication
        self.serial_manager = SerialManager()
        self.connected = False

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
        self.max_load = 0.0
        self.cross_sectional_area = 80.0  # mm²
        self.gauge_length = 80.0  # mm

        # Calibration values
        self.force_scale = -0.0065
        self.force_offset = -24.5185

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

    def on_clear_load_plot(self):
        """Clear the load plot"""
        # TODO: Implement when matplotlib canvas is added
        self.max_load = 0.0
        self.update_load_display()
        self.append_to_console("Load plot cleared")
        pass

    def on_tare(self):
        """Zero the load cell (tare function)"""
        # TODO: Implement when serial communication is added
        self.append_to_console("Tare command sent (not yet implemented)")
        pass

    def update_load_display(self):
        """Update the load value displays"""
        self.currentLoadValue.setText(f"{self.current_load:.2f}")
        self.maxLoadValue.setText(f"{self.max_load:.2f}")

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
        self.setSpeedSpinBox.setValue(0.5)  # Default 0.5 mm/s (~120 RPM)

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
        """Save data to file"""
        self.append_to_console("Saving data...")
        # TODO: Implement data export
        self.append_to_console("Data saved (not yet implemented)")

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
        # Calculate calibrated force: F = -(raw * scale) - offset
        force = -(raw_value * self.force_scale) - self.force_offset
        
        self.current_load = force
        if force > self.max_load:
            self.max_load = force
        
        self.update_load_display()
        # TODO: Add to data storage and update plots

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
