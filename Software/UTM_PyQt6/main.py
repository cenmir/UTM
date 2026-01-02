"""
UTM Control Application - PyQt6
Universal Testing Machine Control Software

Main application file that initializes the GUI and manages the application lifecycle.

============================================
APPLICATION VERSION - UPDATE ON EVERY COMMIT!
============================================
"""

__version__ = "0.2.0"


import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6 import uic
from serial_manager import SerialManager
from widgets import FluentSwitch

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

        # Right panel - Data stream toggles
        self.loadCellCheckBox.stateChanged.connect(self.on_load_cell_toggle)
        self.positionCheckBox.stateChanged.connect(self.on_position_toggle)
        self.velocityCheckBox.stateChanged.connect(self.on_velocity_toggle)

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
        # Serial communication
        self.serial_manager = SerialManager()
        self.connected = False
        
        # Connect serial manager signals
        self.serial_manager.connection_changed.connect(self.on_connection_state_changed)
        self.serial_manager.data_received.connect(self.on_serial_data_received)
        self.serial_manager.load_cell_data.connect(self.on_load_cell_data)
        self.serial_manager.position_data.connect(self.on_position_data)
        self.serial_manager.velocity_data.connect(self.on_velocity_data)
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
        
        # Position tracking
        self.position_zero = 0.0  # Tare offset
        self.current_position_mm = 0.0
        self.current_velocity_rpm = 0.0

        # Console initialization
        self.append_to_console("UTM Control Application Started")

        # Auto-scan for COM ports on startup
        self.auto_scan_ports()

        self.append_to_console("Ready to connect to device")

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

            # SAFETY: Block signals during connection to prevent accidental motor commands
            self.upRadioButton.blockSignals(True)
            self.downRadioButton.blockSignals(True)
            self.stopRadioButton.blockSignals(True)
            self.motorsSwitch.blockSignals(True)

            # Reset UI to safe state
            self.stopRadioButton.setChecked(True)
            self.motorsSwitch.setChecked(False)

            success = self.serial_manager.connect(port, baud_rate)

            # Restore signals
            self.upRadioButton.blockSignals(False)
            self.downRadioButton.blockSignals(False)
            self.stopRadioButton.blockSignals(False)
            self.motorsSwitch.blockSignals(False)

            if not success:
                self.append_to_console(f"Failed to connect to {port}")
                # Reset switch without triggering signal
                self.connectionSwitch.blockSignals(True)
                self.connectionSwitch.setChecked(False)
                self.connectionSwitch.blockSignals(False)
            else:
                # Port opened - waiting for handshake (status lamp will turn on when firmware responds)
                self.append_to_console("Waiting for firmware response...")
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

        # Data Streams group - enabled only when connected
        self.loadCellCheckBox.setEnabled(connected)
        self.positionCheckBox.setEnabled(connected)
        self.velocityCheckBox.setEnabled(connected)

        # Speed Control group - enabled only when connected
        self.speedGaugePlaceholder.setEnabled(connected)
        # TODO: Enable speed spinbox and other speed controls when they exist

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
        self.positionGaugePlaceholder.setEnabled(connected)
        self.displacementLabel.setEnabled(connected)
        self.tareLocationButton.setEnabled(connected)

        # Incremental Move group - enabled when connected AND motors enabled
        self.moveUpButton.setEnabled(direction_enabled)
        self.moveDownButton.setEnabled(direction_enabled)
        self.moveDistanceSpinBox.setEnabled(direction_enabled)

        # Save Data button - always enabled (can save data even when disconnected)

    # ========== Data Stream Functions ==========

    def on_load_cell_toggle(self, state):
        """Toggle load cell data streaming"""
        if state:
            self.append_to_console("Load cell data ON")
            if self.connected:
                self.serial_manager.send_command("LoadCellOn")
        else:
            self.append_to_console("Load cell data OFF")
            if self.connected:
                self.serial_manager.send_command("LoadCellOff")

    def on_position_toggle(self, state):
        """Toggle position data streaming"""
        if state:
            self.append_to_console("Position data ON")
            # TODO: Start position polling
        else:
            self.append_to_console("Position data OFF")
            # TODO: Stop position polling

    def on_velocity_toggle(self, state):
        """Toggle velocity data streaming"""
        if state:
            self.append_to_console("Velocity data ON")
            # TODO: Start velocity polling
        else:
            self.append_to_console("Velocity data OFF")
            # TODO: Stop velocity polling

    # ========== Motor Control Functions ==========

    def on_direction_changed(self, checked):
        """Handle direction radio button changes"""
        # Only process when button is being checked (not unchecked)
        # Radio buttons emit toggled(False) for old button and toggled(True) for new button
        if not checked:
            return
            
        if not self.connected:
            return
        
        # Default speed: 50 RPM (500 in firmware units = RPM × 10)
        # TODO: Get this from speed control UI when implemented
        default_speed_rpm = 50
        firmware_speed = default_speed_rpm * 10  # Firmware expects RPM × 10
        
        if self.upRadioButton.isChecked():
            self.append_to_console(f"Direction: UP at {default_speed_rpm} RPM")
            self.serial_manager.send_command(f"SetSpeed {firmware_speed}")
            self.serial_manager.send_command("Up")
        elif self.downRadioButton.isChecked():
            self.append_to_console(f"Direction: DOWN at {default_speed_rpm} RPM")
            self.serial_manager.send_command(f"SetSpeed {firmware_speed}")
            self.serial_manager.send_command("Down")
        else:
            self.append_to_console("Direction: STOP")
            self.serial_manager.send_command("Stop")

    def on_motors_toggle(self, state):
        """Toggle motor enable/disable"""
        if state:
            # SAFETY: Set direction to STOP before enabling motors
            self.stopRadioButton.blockSignals(True)
            self.stopRadioButton.setChecked(True)
            self.stopRadioButton.blockSignals(False)

            self.append_to_console("Motors ENABLED (direction set to STOP)")
            if self.connected:
                self.serial_manager.send_command("Enable")
        else:
            # SAFETY: Stop motor rotation and set direction to STOP before disabling
            self.stopRadioButton.blockSignals(True)
            self.stopRadioButton.setChecked(True)
            self.stopRadioButton.blockSignals(False)

            self.append_to_console("Motors DISABLED (stopped)")
            if self.connected:
                self.serial_manager.send_command("Stop")
                self.serial_manager.send_command("Disable")

        # Update direction and incremental move controls based on motor state
        self.update_controls_enabled_state()

    def on_emergency_stop(self):
        """Emergency stop button pressed"""
        self.append_to_console("EMERGENCY STOP activated!")
        if self.connected:
            self.serial_manager.send_command("EStop")
        self.stopRadioButton.setChecked(True)
        self.motorsSwitch.setChecked(False)

    # ========== Position & Incremental Move Functions ==========

    def on_tare_location(self):
        """Tare the position (zero the displacement)"""
        self.position_zero = self.current_position_mm
        self.append_to_console(f"Position tared (offset: {self.position_zero:.4f} mm)")
        self.displacementLabel.setText("δ = 0.0000 mm")

    def on_move_up(self):
        """Move up by specified distance"""
        distance = self.moveDistanceSpinBox.value()
        self.append_to_console(f"Moving up {distance} mm")
        if self.connected:
            # Calculate steps: 200 steps/rev * 8 microstepping * 20 gear ratio / 5mm pitch
            steps = round(200 * 8 * 20 * distance / 5)
            self.serial_manager.send_command(f"MoveSteps {steps}")

    def on_move_down(self):
        """Move down by specified distance"""
        distance = self.moveDistanceSpinBox.value()
        self.append_to_console(f"Moving down {distance} mm")
        if self.connected:
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
            # Ensure switch is on (it should be, but just in case)
            if not self.connectionSwitch.isChecked():
                self.connectionSwitch.blockSignals(True)
                self.connectionSwitch.setChecked(True)
                self.connectionSwitch.blockSignals(False)
        else:
            self.update_status_lamp(False)
            # Update switch state - block signals to prevent triggering disconnect again
            if self.connectionSwitch.isChecked():
                self.connectionSwitch.blockSignals(True)
                self.connectionSwitch.setChecked(False)
                self.connectionSwitch.blockSignals(False)

        # Update all control enabled states
        self.update_controls_enabled_state()

    def on_serial_data_received(self, data):
        """Handle raw serial data (display in console)"""
        # Display received data in console
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

    def on_position_data(self, raw_angle):
        """Handle parsed position data"""
        # Convert raw angle to mm: angle_deg = -raw * (360/4096)
        angle_deg = -raw_angle * (360.0 / 4096.0)
        rotations = angle_deg / 360.0
        screw_rotations = rotations / 20.0  # 20:1 gear ratio
        position_mm = screw_rotations * 5.0  # 5mm pitch
        
        self.current_position_mm = position_mm
        displacement = position_mm - self.position_zero
        
        # Update displacement label
        self.displacementLabel.setText(f"δ = {displacement:.4f} mm")
        # TODO: Update linear gauge visual

    def on_velocity_data(self, vel1, vel2):
        """Handle parsed velocity data"""
        self.current_velocity_rpm = vel1
        # TODO: Update speed gauge and label
        # For now, just store the value
    
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
