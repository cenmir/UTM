"""
UTM Control Application - PyQt6
Universal Testing Machine Control Software

Main application file that initializes the GUI and manages the application lifecycle.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6 import uic

# Path to the UI file
UI_FILE = Path(__file__).parent / "ui" / "utm_mainwindow.ui"


class UTMApplication(QMainWindow):
    """Main application window for UTM control"""

    def __init__(self):
        super().__init__()

        # Load the UI file
        uic.loadUi(UI_FILE, self)

        # Connect signals to slots
        self.connect_signals()

        # Initialize application state
        self.init_state()

        print("UTM Application initialized")

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
        self.connectionCheckBox.stateChanged.connect(self.on_connection_toggle)

        # Right panel - Data stream toggles
        self.loadCellCheckBox.stateChanged.connect(self.on_load_cell_toggle)
        self.positionCheckBox.stateChanged.connect(self.on_position_toggle)
        self.velocityCheckBox.stateChanged.connect(self.on_velocity_toggle)

        # Right panel - Motor controls
        self.upRadioButton.toggled.connect(self.on_direction_changed)
        self.stopRadioButton.toggled.connect(self.on_direction_changed)
        self.downRadioButton.toggled.connect(self.on_direction_changed)
        self.motorsCheckBox.stateChanged.connect(self.on_motors_toggle)
        self.emergencyStopButton.clicked.connect(self.on_emergency_stop)

        # Right panel - Position and incremental move
        self.tareLocationButton.clicked.connect(self.on_tare_location)
        self.moveUpButton.clicked.connect(self.on_move_up)
        self.moveDownButton.clicked.connect(self.on_move_down)

        # Right panel - Save data
        self.saveDataButton.clicked.connect(self.on_save_data)

    def init_state(self):
        """Initialize application state variables"""
        self.connected = False

        # Data storage
        self.current_load = 0.0
        self.max_load = 0.0
        self.cross_sectional_area = 80.0  # mm²
        self.gauge_length = 80.0  # mm

        # Console initialization
        self.append_to_console("UTM Control Application Started")
        self.append_to_console("Ready to connect to device")

        # Update UI with initial values
        self.update_load_display()

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

        # TODO: Send command to serial device
        if not self.connected:
            self.append_to_console("Error: Not connected to device")
        else:
            # This will be implemented when we add serial communication
            pass

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
        # TODO: Implement COM port scanning
        self.append_to_console("Scanning for COM ports...")
        self.comPortComboBox.clear()
        self.comPortComboBox.addItem("COM1")
        self.comPortComboBox.addItem("COM3")
        self.append_to_console("Found 2 COM ports")

    def on_connection_toggle(self, state):
        """Handle connection checkbox toggle"""
        if state:
            port = self.comPortComboBox.currentText()
            self.append_to_console(f"Connecting to {port}...")
            # TODO: Implement actual connection
            self.connected = True
            self.update_status_lamp(True)
            self.append_to_console("Connected to UTM")
        else:
            self.append_to_console("Disconnecting...")
            # TODO: Implement actual disconnection
            self.connected = False
            self.update_status_lamp(False)
            self.append_to_console("Disconnected from UTM")

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

    # ========== Data Stream Functions ==========

    def on_load_cell_toggle(self, state):
        """Toggle load cell data streaming"""
        if state:
            self.append_to_console("Load cell data ON")
            # TODO: Send LoadCellOn command
        else:
            self.append_to_console("Load cell data OFF")
            # TODO: Send LoadCellOff command

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

    def on_direction_changed(self):
        """Handle direction radio button changes"""
        if self.upRadioButton.isChecked():
            self.append_to_console("Direction: UP")
            # TODO: Send Up command
        elif self.downRadioButton.isChecked():
            self.append_to_console("Direction: DOWN")
            # TODO: Send Down command
        else:
            self.append_to_console("Direction: STOP")
            # TODO: Send Stop command

    def on_motors_toggle(self, state):
        """Toggle motor enable/disable"""
        if state:
            self.append_to_console("Motors ENABLED")
            # TODO: Send Enable command
        else:
            self.append_to_console("Motors DISABLED")
            # TODO: Send Disable command

    def on_emergency_stop(self):
        """Emergency stop button pressed"""
        self.append_to_console("EMERGENCY STOP activated!")
        # TODO: Send EStop command
        self.stopRadioButton.setChecked(True)
        self.motorsCheckBox.setChecked(False)

    # ========== Position & Incremental Move Functions ==========

    def on_tare_location(self):
        """Tare the position (zero the displacement)"""
        self.append_to_console("Position tared")
        self.displacementLabel.setText("δ = 0.0000 mm")
        # TODO: Implement position tare

    def on_move_up(self):
        """Move up by specified distance"""
        distance = self.moveDistanceSpinBox.value()
        self.append_to_console(f"Moving up {distance} mm")
        # TODO: Calculate steps and send MoveSteps command
        # steps = round(200 * 8 * 20 * distance / 5)

    def on_move_down(self):
        """Move down by specified distance"""
        distance = self.moveDistanceSpinBox.value()
        self.append_to_console(f"Moving down {distance} mm")
        # TODO: Calculate steps and send MoveSteps command (negative)
        # steps = round(200 * 8 * 20 * distance / 5)

    # ========== Data Export Functions ==========

    def on_save_data(self):
        """Save data to file"""
        self.append_to_console("Saving data...")
        # TODO: Implement data export
        self.append_to_console("Data saved (not yet implemented)")

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
