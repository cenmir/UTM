"""
Serial Communication Manager for UTM Application

Handles all serial communication with the Arduino/ESP32 firmware using PyQt6.QtSerialPort.
Provides signals for asynchronous communication and thread-safe data handling.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QIODevice, QTimer
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo


class SerialManager(QObject):
    """Manages serial communication with the UTM firmware"""

    # Signals for asynchronous communication
    connection_changed = pyqtSignal(bool)  # True=connected, False=disconnected
    data_received = pyqtSignal(str)        # Raw data line received
    load_cell_data = pyqtSignal(float)     # Parsed load cell value
    position_data = pyqtSignal(float)      # Parsed position value
    velocity_data = pyqtSignal(float, float)  # Parsed velocity values (val1, val2)
    firmware_version = pyqtSignal(str)     # Firmware version string
    error_occurred = pyqtSignal(str)       # Error message

    def __init__(self):
        super().__init__()

        self.serial_port = QSerialPort()
        self.serial_port.readyRead.connect(self._on_data_ready)
        self.serial_port.errorOccurred.connect(self._on_error)

        self.connected = False
        self.port_open = False  # Port is open but not yet confirmed
        self.awaiting_handshake = False  # Waiting for firmware response
        self.buffer = ""  # Buffer for incomplete lines

        # Connection timeout timer
        self.handshake_timer = QTimer()
        self.handshake_timer.setSingleShot(True)
        self.handshake_timer.timeout.connect(self._on_handshake_timeout)
        
    @staticmethod
    def scan_ports():
        """
        Scan for available COM ports
        
        Returns:
            list: List of available COM port names (e.g., ['COM3', 'COM4'])
        """
        ports = QSerialPortInfo.availablePorts()
        port_names = [port.portName() for port in ports]
        return port_names
    
    def connect(self, port_name, baud_rate=9600):
        """
        Connect to a serial port
        
        Args:
            port_name (str): Name of the port to connect to (e.g., 'COM3')
            baud_rate (int): Baud rate (default: 9600)
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        if self.connected:
            self.disconnect()
        
        self.serial_port.setPortName(port_name)
        self.serial_port.setBaudRate(baud_rate)
        self.serial_port.setDataBits(QSerialPort.DataBits.Data8)
        self.serial_port.setParity(QSerialPort.Parity.NoParity)
        self.serial_port.setStopBits(QSerialPort.StopBits.OneStop)
        self.serial_port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        
        if self.serial_port.open(QIODevice.OpenModeFlag.ReadWrite):
            # Import QThread for delay
            from PyQt6.QtCore import QThread

            # Wait a bit for port to stabilize
            QThread.msleep(100)

            # Read any buffered data (e.g., welcome message from Arduino startup)
            # before clearing buffers
            if self.serial_port.bytesAvailable() > 0:
                buffered_data = self.serial_port.readAll()
                try:
                    text = buffered_data.data().decode('utf-8', errors='ignore')
                    # Process buffered messages
                    for line in text.split('\n'):
                        line = line.strip()
                        if line:
                            self.data_received.emit(line)
                except:
                    pass

            # Now clear any remaining stale data
            self.serial_port.clear(QSerialPort.Direction.AllDirections)
            self.buffer = ""

            # Port is open but not yet confirmed by firmware response
            self.port_open = True
            self.awaiting_handshake = True

            # SAFETY FIRST: Send emergency stop and disable
            self._send_raw("EStop")
            QThread.msleep(50)

            self._send_raw("Disable")
            QThread.msleep(50)

            # Query firmware version to verify bidirectional communication
            # Connection will be confirmed when we receive the version response
            self._send_raw("GetVersion")

            # Start handshake timeout (2 seconds to receive firmware version)
            self.handshake_timer.start(2000)

            return True
        else:
            error_msg = f"Failed to open {port_name}: {self.serial_port.errorString()}"
            self.error_occurred.emit(error_msg)
            return False
    
    def disconnect(self):
        """Disconnect from the serial port"""
        # Cancel any pending handshake
        self.handshake_timer.stop()
        self.awaiting_handshake = False

        if self.serial_port.isOpen():
            # Send stop and disable commands before disconnecting
            if self.connected:
                self._send_raw("Stop")
                self._send_raw("Disable")

            self.serial_port.close()

        self.port_open = False
        self.connected = False
        self.connection_changed.emit(False)
    
    def _send_raw(self, command):
        """
        Send a command without checking connection state (for internal use during handshake)

        Args:
            command (str): Command string

        Returns:
            bool: True if command sent successfully, False otherwise
        """
        if not self.serial_port.isOpen():
            return False

        command_bytes = (command + "\n").encode('utf-8')
        bytes_written = self.serial_port.write(command_bytes)
        self.serial_port.flush()
        return bytes_written > 0

    def send_command(self, command):
        """
        Send a command to the Arduino

        Args:
            command (str): Command string (e.g., 'Enable', 'SetSpeed 1200')

        Returns:
            bool: True if command sent successfully, False otherwise
        """
        if not self.connected or not self.serial_port.isOpen():
            self.error_occurred.emit("Cannot send command: Not connected")
            return False

        return self._send_raw(command)
    
    def _on_data_ready(self):
        """Internal handler for when data is available to read"""
        # Read all available data
        data = self.serial_port.readAll()
        
        try:
            # Decode bytes to string
            text = data.data().decode('utf-8', errors='ignore')
            
            # Add to buffer and process complete lines
            self.buffer += text
            
            # Process all complete lines in the buffer
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.strip()
                
                if line:
                    # Emit raw data
                    self.data_received.emit(line)
                    
                    # Parse specific data types
                    self._parse_response(line)
                    
        except Exception as e:
            self.error_occurred.emit(f"Error reading data: {str(e)}")
    
    def _parse_response(self, line):
        """
        Parse different types of responses from the Arduino
        
        Args:
            line (str): A line of text received from the serial port
        """
        try:
            # Check for specific response patterns
            if line.startswith("Welcome to"):
                # Welcome message - connection established
                pass
            
            elif line.startswith("Total Angle:"):
                # Position data: "Total Angle: [value]\t[value]"
                parts = line.split(':')[1].strip().split('\t')
                if parts:
                    raw_angle = float(parts[0])
                    self.position_data.emit(raw_angle)
            
            elif line.startswith("Velocity:"):
                # Velocity data: "Velocity: [val1]\t[val2]"
                parts = line.split(':')[1].strip().split('\t')
                if len(parts) >= 2:
                    vel1 = float(parts[0])
                    vel2 = float(parts[1])
                    self.velocity_data.emit(vel1, vel2)
            
            elif line.startswith("Firmware Version:"):
                # Firmware version: "Firmware Version: 1.1.0"
                version = line.split(':', 1)[1].strip()

                # If awaiting handshake, this confirms the connection
                if self.awaiting_handshake:
                    self._confirm_connection()

                self.firmware_version.emit(version)
            
            elif line.startswith("Command:"):
                # Command echo - ignore
                pass
            
            else:
                # Try to parse as load cell data (single numeric value)
                try:
                    value = float(line)
                    self.load_cell_data.emit(value)
                except ValueError:
                    # Not a number, just a regular message
                    pass
                    
        except Exception as e:
            # Don't emit error for parsing failures - just ignore malformed data
            pass
    
    def _on_error(self, error):
        """Internal handler for serial port errors"""
        if error != QSerialPort.SerialPortError.NoError:
            error_msg = f"Serial error: {self.serial_port.errorString()}"
            self.error_occurred.emit(error_msg)
            
            # If it's a critical error, disconnect
            if error in [QSerialPort.SerialPortError.DeviceNotFoundError,
                        QSerialPort.SerialPortError.PermissionError,
                        QSerialPort.SerialPortError.ResourceError]:
                self.disconnect()
    
    def is_connected(self):
        """Check if currently connected"""
        return self.connected and self.serial_port.isOpen()

    def _confirm_connection(self):
        """Called when firmware responds - confirms the connection is fully established"""
        self.handshake_timer.stop()
        self.awaiting_handshake = False
        self.connected = True
        self.connection_changed.emit(True)

    def _on_handshake_timeout(self):
        """Called when firmware doesn't respond within timeout period"""
        if self.awaiting_handshake:
            self.awaiting_handshake = False
            self.error_occurred.emit("Connection timeout: No response from firmware")
            # Close the port since firmware isn't responding
            if self.serial_port.isOpen():
                self.serial_port.close()
            self.port_open = False
            self.connected = False
            self.connection_changed.emit(False)
