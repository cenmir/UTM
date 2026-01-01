# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🔴 IMPORTANT: Session Start Checklist

**Before starting ANY work in this repository, ALWAYS do these steps IN ORDER:**

1. **Read `PROJECT_STATUS.md`** to understand:
   - Current phase of development
   - What was completed in the last session
   - Active work in progress
   - Next recommended steps
   - Recent architectural decisions

2. **Read `APP_DESCRIPTION.qmd`** (856 lines) to understand:
   - Complete GUI layout with right control panel
   - All control components and their placement
   - Serial protocol specifications
   - Data processing formulas
   - Implementation architecture
   - **This is the SOURCE OF TRUTH for GUI structure**

3. **Review the MATLAB GUI screenshots**:
   - `Software/Matlab/GUI.png` - Load Plot tab view
   - `Software/Matlab/MatlabApp.png` - Console tab view
   - These show the actual working implementation

**CRITICAL:** The APP_DESCRIPTION.qmd contains the complete GUI specification including the persistent right control panel that appears on all tabs. DO NOT start GUI work without reviewing this document first!

**At the end of each work session, update `PROJECT_STATUS.md`** with:
- What was accomplished
- Current state and completion percentages
- Any decisions made or blockers encountered
- Recommended next steps for the following session

This ensures continuity across work sessions and prevents duplicate effort.

## Project Overview

This is a **Universal Testing Machine (UTM)** control system for materials testing, used at Jönköping University School of Engineering. The machine performs tensile testing to generate stress-strain curves for material characterization.

**Project Status:** Active migration from MATLAB GUI to Python/PyQt6 while maintaining firmware development.

Based on work by [Stefan from CNC Kitchen](https://www.youtube.com/watch?v=uvn-J8CbtzM) and students [Stephen Jose Mathew and Vijay Francis](https://hj.diva-portal.org/smash/get/diva2:1472019/FULLTEXT01.pdf).

## Development Commands

### Python/PyQt6 Application

```bash
# Setup development environment
cd Software/UTM_PyQt6
pip install -r requirements.txt

# Run the application
python main.py

# Edit UI in Qt Designer (if qt6-tools installed)
pyqt6-tools designer ui/utm_mainwindow.ui
```

### Arduino Firmware

```bash
# Flash firmware to ESP32
# 1. Open D32_Firmware/D32_Firmware.ino in Arduino IDE
# 2. Select board: ESP32 Dev Module
# 3. Upload via USB serial

# Monitor serial output
# Baud rate: 9600 (configurable to 57600, 115200, 250000)
# Expect: "Welcome to Mirzas Universal Testing Machine Firmware!"
```

### MATLAB Application (Legacy/Production)

```matlab
% Open in MATLAB App Designer
open('Software/UTM.mlapp')

% For version control, export to M-file after changes
% This creates Software/UTM_exported.m for git tracking
```

## Architecture Overview

### Three-Layer System

```
┌─────────────────────────────────────────┐
│   GUI Layer (MATLAB or PyQt6)          │
│   - Motor control interface             │
│   - Real-time plotting                  │
│   - Data acquisition & export           │
│   - Calibration workflows               │
└──────────────┬──────────────────────────┘
               │ Serial Protocol (text-based, 9600-250000 baud)
               ▼
┌─────────────────────────────────────────┐
│   Firmware Layer (Arduino/ESP32)        │
│   - Command parser                      │
│   - Sensor polling (HX711, AS5600)      │
│   - Stepper motor control (MobaTools)   │
└──────────────┬──────────────────────────┘
               │ I2C, Step/Dir signals
               ▼
┌─────────────────────────────────────────┐
│   Hardware Layer                        │
│   - HX711 load cell amplifier           │
│   - AS5600 magnetic encoders (×2)       │
│   - TMC2160 stepper drivers (×2)        │
│   - Nema 23 motors + 20:1 gearboxes     │
└─────────────────────────────────────────┘
```

### Serial Communication Protocol

**Critical boundary:** The text-based serial protocol is the contract between GUI and firmware. Changes require coordination across both layers.

**Command Format:** Plain text, LF or CRLF terminated

**Common Commands:**
```
Enable / Disable              # Motor driver enable/disable
Up / Down / Stop              # Continuous motion control
SetSpeed [rpm×10]             # Set speed (e.g., "SetSpeed 1200" = 120 RPM)
MoveSteps [steps]             # Incremental positioning
LoadCellOn / LoadCellOff      # Toggle force data streaming
SensorsOn / SensorsOff        # Toggle position/velocity streaming
GetTotalAngle                 # Query current position
GetVelocity                   # Query current speed
EStop                         # Emergency stop
```

**Response Patterns:**
```
Welcome to Mirzas Universal Testing Machine Firmware!  # Handshake
[raw_value]                                             # Load cell stream (10 Hz)
Total Angle: [position_raw]                            # Position response
Velocity: [rpm]\t[avg_rpm]                             # Velocity response
```

## Key Calculations & Conversions

### Position Calculation (Encoder → mm displacement)

```python
# Hardware geometry
ENCODER_BITS = 4096           # AS5600 12-bit encoder
GEAR_RATIO = 20               # Planetary gearbox reduction
LEAD_SCREW_PITCH = 5          # mm per screw revolution

# Conversion formula
angle_deg = -raw_angle * (360 / 4096)
rotations = angle_deg / 360
screw_rotations = rotations / GEAR_RATIO
position_mm = screw_rotations * LEAD_SCREW_PITCH
displacement = position_mm - position_zero  # Tare offset
```

### Force Calibration (Two-point method)

```python
# Calibration workflow
# Step 1: Measure zero-load for 10 seconds → force0_raw
# Step 2: Place known weight, measure for 10 seconds → force1_raw
# Step 3: Calculate scale and offset

scale = (weight_kg * 9.81) / (force1_raw - force0_raw)
offset = force0_raw * scale

# Apply calibration
force_calibrated = -(raw_force * scale) - offset  # Newtons
```

**Default calibration values:**
- Scale: -0.0065
- Offset: -24.5185

### Stress-Strain Calculations

```python
stress = force_calibrated / cross_sectional_area  # N/mm² (MPa)
strain = displacement / initial_gauge_length      # mm/mm (dimensionless)

# Default specimen dimensions
area = 80      # mm²
L0 = 80        # mm
```

### Incremental Move Steps

```python
# Convert mm distance to stepper steps
steps = round(200 * 8 * 20 * distance_mm / 5)
#             ^   ^  ^   ^
#             |   |  |   Lead screw pitch (mm)
#             |   |  Gear ratio
#             |   Microstepping (1/8)
#             Steps per revolution

# Simplified: steps = 640 * distance_mm
```

## File Structure & Key Components

### Firmware (`D32_Firmware/`)
- `D32_Firmware.ino` (500 lines) - Main firmware with command parser and sensor loops
- `Sensors.h/cpp` - AS5600 encoder wrapper class with I2C multiplexer support
- Dependencies: HX711 (Rob Tillaart), AS5600 (Rob Tillaart), MobaTools

### Software (`Software/`)

**MATLAB (Production):**
- `UTM.mlapp` - Binary App Designer file (primary GUI)
- `UTM_exported.m` - Exported M-code for version control
- Note: `.mlapp` is not source-controllable; export to M-file after changes

**Python/PyQt6 (In Progress):**
- `UTM_PyQt6/main.py` - Application entry point and signal wiring
- `UTM_PyQt6/ui/utm_mainwindow.ui` - Qt Designer UI definition
- Current status: Console tab functional, serial/plotting/control pending

**Data Processing:**
- `data/` - MATLAB scripts for post-processing experiment results

### Documentation
- `APP_DESCRIPTION.md` - Comprehensive conversion guide with protocol specs, formulas, and class architecture
- `PROJECT_REQUIREMENTS.md` - Hardware specs and dependency list
- `graphics/GUI.png` - Screenshot of MATLAB GUI reference

## Python/PyQt6 Implementation Architecture

### Recommended Class Structure

```python
UTMApplication(QMainWindow)
├─ SerialManager(QObject)      # Threaded serial I/O with signals
├─ DataManager                 # Buffer storage, calculations, export
├─ PlotManager                 # matplotlib canvas management
├─ CalibrationManager          # Two-point calibration workflow
└─ CameraManager (optional)    # Basler camera + DIC processing
```

### Threading Strategy

**Critical:** Use Qt's signal/slot mechanism for thread safety.

```python
# SerialThread emits signals, main thread updates GUI
class SerialThread(QThread):
    data_received = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)

# Main window connects to signals
self.serial_thread.data_received.connect(self.on_data_received)
```

### Timer Architecture

Two parallel timers manage data acquisition:

1. **Connection Monitor (500ms):** Health check, triggers connect/disconnect callbacks
2. **Data Polling (100ms):** Query position/velocity, receive load cell stream

### Data Storage Format

**In-memory (pandas DataFrame):**
```python
columns = ['timestamp', 'raw_force', 'force', 'position', 'strain', 'stress']
max_buffer = 500  # Auto-rescale plots after this limit
```

**Export formats:**
- `.mat` (scipy.io.savemat) - MATLAB compatibility
- `.csv` (pandas.to_csv) - Universal format
- `.h5` (pandas.to_hdf) - High-performance binary

## Hardware Specifics

### Load Cell
- HX711 amplifier on I2C pins 16/4
- 10 Hz polling rate (non-blocking)
- 24-bit ADC resolution
- Requires two-point calibration with known weight

### Position Encoders
- AS5600 magnetic encoders (×2)
- 12-bit resolution (4096 positions/revolution)
- Connected via TCA9548A I2C multiplexer at address 0x70
- Tracks cumulative position across power cycles

### Stepper Motors
- Nema 23 motors: AMP57TH76-4280
- TMC2160 drivers on MKS TMC2160_57 boards
- 1600 steps/rev (200 steps × 8 microstepping)
- 20:1 planetary gearbox reduction (EPL64/2)
- 5mm pitch lead screw

### Camera (Optional - not yet integrated)
- Basler acA2440-35um (USB 3.0)
- Lens: Azure-2514M (25mm, 5MP, 2/3" sensor)
- ROI: [888, 300, 303, 1756]
- Frame rate: 35 fps, Exposure: 2500 µs
- For Digital Image Correlation (DIC) strain measurement

## Development Phases (PyQt6 Conversion)

**Phase 1 - Foundation (MVP):**
- Serial connection management (scan, connect, disconnect)
- Motor enable/disable, direction control (Up/Stop/Down)
- Emergency stop button
- Console with command send/receive

**Phase 2 - Data Acquisition:**
- Load cell data streaming and parsing
- Load vs Time plot (matplotlib)
- Position polling and display
- Basic data storage (DataFrame)

**Phase 3 - Advanced Control:**
- Speed control (knob + numeric field)
- RPM ↔ mm/s conversion
- Velocity display (custom circular gauge)
- Incremental move functionality

**Phase 4 - Stress-Strain:**
- Real-time stress-strain calculations
- Stress-Strain plot
- User-configurable specimen dimensions (area, L₀)
- Moving average smoothing filter

**Phase 5 - Calibration & Export:**
- Two-point calibration workflow with dialogs
- Multi-format data export (.mat, .csv, .h5)
- Range slider for plot cropping
- Tare functionality (zero-adjustment)

**Phase 6 - Polish:**
- Custom gauge widgets (circular speed, linear position)
- Status lamp indicator
- Plot markers toggle
- Keyboard shortcuts

**Phase 7 - Camera/DIC (Optional):**
- Basler camera integration (pypylon)
- Blob detection (OpenCV)
- Two-point tracking for DIC strain measurement

## Critical Implementation Notes

### Custom Widgets Needed

The MATLAB GUI uses several custom components that require QPainter implementation:

1. **Circular Gauge (Speed):** Inherit QWidget, override paintEvent(), draw arc/needle/ticks
2. **Linear Gauge (Position):** Vertical bar with scale markers (-10 to +10 mm range)
3. **Range Slider:** Two handles for min/max selection (or use `qrangeslider` library)
4. **Status Lamp:** Simple circle with color property (green/black/red)

### Real-Time Plotting Performance

matplotlib can be slow for 10 Hz updates:

**Solutions:**
- Use blitting for fast canvas updates (only redraw changed data)
- Consider `pyqtgraph` as alternative (significantly faster)
- Limit plot points (downsample if > 500)
- Update only on new data, not on timer tick

### Serial Communication Options

1. **PyQt6.QtSerialPort (recommended):** Integrated with Qt event loop, signal-based
2. **pyserial:** Mature library, requires QThread wrapper

```python
# QtSerialPort example
from PyQt6.QtSerialPort import QSerialPort
serial = QSerialPort()
serial.setPortName(port)
serial.setBaudRate(9600)
serial.readyRead.connect(self.on_data_ready)
```

### State Management

Connection state drives UI enable/disable logic:

**Connected:**
- Enable: Motor controls, data toggles, emergency stop, tare, incremental move
- Disable: Baud rate, line ending, COM port selection

**Disconnected:**
- Enable: Baud rate, line ending, COM port selection
- Disable: All motor and data controls

### Data Validation

The formulas are tuned to physical machine geometry. When modifying calculations:

1. Verify against MATLAB implementation (`UTM_exported.m`)
2. Test with known reference weights (calibration validation)
3. Check sign conventions (negative multipliers in position/force formulas)
4. Validate units at each conversion step

## Testing Against Hardware

When testing with the physical UTM:

1. **Connection Test:** Send `Enable` then `Disable` - clears velocity noise on startup
2. **Load Cell Test:** Place known weight, verify calibrated force reading
3. **Position Test:** Move 10mm, verify displacement calculation matches physical movement
4. **Calibration Test:** Perform two-point calibration, compare scale/offset to defaults
5. **Stress-Strain Test:** Run complete tensile test, compare curve to MATLAB baseline

## Common Pitfalls

1. **Command Echo Handling:** Arduino may echo commands - filter "Command: ..." responses
2. **Buffer Overflow:** Load cell streams continuously - implement proper circular buffer
3. **Sign Conventions:** Position and force have negative multipliers (mechanical setup dependent)
4. **Tare Logic:** Tare adds average to offset, doesn't replace it
5. **Speed Units:** `SetSpeed` expects RPM × 10 (e.g., 1200 = 120 RPM)
6. **I2C Multiplexer:** Must call `tcaselect(channel)` before AS5600 reads
7. **Incremental Move:** Direction knob must update visual state during `MoveSteps` execution

## Data Export Compatibility

Maintain column ordering for MATLAB .mat file compatibility:

```python
# Export structure (cell array in MATLAB)
Data = {
    'Timestamps': datetime_array,
    'RawForce': raw_force_array,
    'Force': calibrated_force_array,
    'Position': position_array,
    'Strain': strain_array,
    'Stress': stress_array
}
```

Filename format: `[UserInput]_YYYYMMDD_HHmmss.mat`

## Version Control Notes

- `.mlapp` files are binary - always export to M-file after MATLAB GUI changes
- Firmware uses Arduino library dependencies - document version numbers
- PyQt6 .ui files are XML - can be directly version controlled
- Data files (.mat, .csv) are in .gitignore - only commit sample/reference data
