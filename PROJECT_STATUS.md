# UTM Project Status & Session Log

**Last Updated:** 2026-01-03

---

## 🔴 MANDATORY: Before Starting ANY Work

**Read these files in order:**
1. This file (PROJECT_STATUS.md) - understand current state
2. **APP_DESCRIPTION.qmd** (lines 111-255) - GUI layout specification
3. **Software/Matlab/GUI.png** - MATLAB reference implementation
4. **Software/Matlab/MatlabApp.png** - MATLAB reference implementation

**The APP_DESCRIPTION.qmd is the SOURCE OF TRUTH for GUI structure!**

---

## Current Project State

### Overall Status
- **Phase:** Early Development - MATLAB to PyQt6 Migration
- **Active Work:** PyQt6 GUI Implementation
- **Production System:** MATLAB GUI (Software/UTM.mlapp) - fully functional
- **Target System:** Python/PyQt6 (Software/UTM_PyQt6/) - in progress

### Completion Summary

**Firmware (D32_Firmware/):** ✅ Stable
- Arduino/ESP32 firmware fully functional
- Serial protocol established and tested
- Sensor integration complete (HX711, AS5600)

**MATLAB GUI (Software/):** ✅ Production Ready
- Full-featured application operational
- All 7 phases implemented
- Used for teaching at Jönköping University

**PyQt6 GUI (Software/UTM_PyQt6/):** 🚧 ~48% Complete (v0.2.6)
- Phase 1 (Foundation): 95% - GUI + serial communication implemented
- Phase 2 (Data Acquisition): 20% - parsing ready, motor polling active
- Phase 3 (Advanced Control): 60% - Speed control with limits, SpeedGauge widget
- Phase 4-7: Structure ready, implementation pending

---

## PyQt6 Development Progress

### ✅ Completed (Phase 1 - Partial)

**Files Created:**
- `Software/UTM_PyQt6/main.py` - Application entry point with basic structure
- `Software/UTM_PyQt6/ui/utm_mainwindow.ui` - UI file with Console tab
- `Software/UTM_PyQt6/requirements.txt` - Dependencies defined

**Functionality Working:**
- Console tab with monospace text display
- Command input with Send button (Enter key support)
- Clear Console button
- Auto-scroll checkbox (enabled by default)
- Timestamp checkbox
- Close confirmation dialog
- Basic signal-slot wiring

### 🚧 In Progress

None currently.

### ⏳ Next Steps (Recommended Priority)

**Option 1: Serial Communication (Recommended)**
- Implement SerialManager class using PyQt6.QtSerialPort
- Add connection controls to UI (scan COM ports, dropdown, connect button)
- Add status lamp indicator
- Test basic command send/receive with Arduino
- Parse serial responses

**Option 2: Main GUI Layout**
- Expand UI in Qt Designer with connection panel
- Add motor control section (enable, direction, E-stop)
- Add data stream toggles (load cell, position, velocity)
- Create layout structure for all tabs

**Current Blockers:** None - ready to proceed with either option.

---

## Session History

### Session: 2026-01-02 (Morning)

**What We Did:**
1. Explored the UTM codebase structure
2. Located the actual PyQt6 project files in `Software/UTM_PyQt6/`
3. Reviewed current implementation state:
   - main.py has console tab functionality
   - utm_mainwindow.ui defines basic window (1232×813px)
4. Created comprehensive CLAUDE.md documentation:
   - Serial protocol specifications
   - Key calculations (position, force, stress-strain)
   - Hardware architecture
   - Development commands
   - PyQt6 implementation guidance
5. Created this PROJECT_STATUS.md tracking file

**Decisions Made:**
- Confirmed PyQt6 as the target framework (not PySide6)
- Using matplotlib for plotting (may switch to pyqtgraph for performance)
- QtSerialPort preferred over pyserial for Qt integration
- Will maintain MATLAB .mat export format for compatibility

**Questions/Issues Raised:**
- None currently

**Next Session Should Start With:**
- Review this PROJECT_STATUS.md file
- Decide between serial communication vs. GUI layout expansion
- Begin implementation of chosen direction

---

### Session: 2026-01-02 (Afternoon)

**What We Did:**
1. Added two new tabs (Stress/Strain, Load Plot) to utm_mainwindow.ui
2. Added placeholder controls for specimen dimensions and plot controls
3. Wired up signal handlers in main.py for new controls
4. **DISCOVERED CRITICAL ISSUE**: Missing entire right control panel!

**Major Discovery:**
- The current UI is missing the **persistent right control panel** that appears on all tabs
- This panel contains ALL motor controls, connection management, and data toggles
- The APP_DESCRIPTION.qmd fully documents this (lines 113-177)
- Current implementation only has tabs - completely missing ~40% of the GUI

**Lessons Learned:**
- ⚠️ **ALWAYS read APP_DESCRIPTION.qmd before starting GUI work**
- ⚠️ **ALWAYS review MATLAB screenshots (GUI.png, MatlabApp.png)**
- Updated CLAUDE.md with mandatory session start checklist

**What Needs To Be Done:**
- Complete UI redesign to include right control panel
- Right panel contains:
  - Connection controls (COM port, connect button, status lamp)
  - Data stream toggles (Load Cell, Position, Velocity)
  - Speed gauge (circular, custom widget)
  - Direction control (Up/Stop/Down)
  - Motors On/Off toggle
  - Emergency STOP button
  - Position gauge (linear, custom widget)
  - Incremental move controls
  - Save Data button

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md
2. Read APP_DESCRIPTION.qmd (lines 111-255 for GUI layout)
3. Review GUI.png and MatlabApp.png
4. Redesign UI with proper two-panel layout (tabs left, controls right)

### Session: 2026-01-02 (Evening) - RIGHT PANEL IMPLEMENTED! ✅

**What We Did:**
1. ✅ **Completely restructured the UI layout**
   - Changed from single-column (tabs only) to two-column layout
   - Left: QTabWidget with all tabs (Console, Stress/Strain, Load Plot)
   - Right: Persistent control panel (300-350px wide)

2. ✅ **Implemented complete right control panel** with 7 sections:
   - **Connection Group**: Scan COM ports, dropdown, connect checkbox, status lamp (30×30px circle)
   - **Data Streams Group**: Load Cell, Position, Velocity toggles
   - **Speed Control Group**: Circular gauge placeholder (150×150px), RPM/mm/s toggle, speed display, Set RPM spinbox
   - **Motor Control Group**: Direction radio buttons (Up/Stop/Down), Motors toggle, Emergency STOP button (red, 50px)
   - **Position Group**: Linear gauge placeholder (60×120px), displacement label, Tare Location button
   - **Incremental Move Group**: Move Up/Down buttons, distance spinbox (default 1.5mm)
   - **Save Data Button**: 40px height at bottom

3. ✅ **Wired up all controls in main.py**
   - Added 15+ signal handler functions
   - Connection management (scan, connect/disconnect, status lamp updates)
   - Data stream toggles (load cell, position, velocity)
   - Motor controls (direction, enable/disable, emergency stop)
   - Position control (tare, incremental moves)
   - Data export
   - All handlers log to console and have TODOs for serial implementation

4. ✅ **Updated documentation**
   - Updated CLAUDE.md with mandatory 3-step session start checklist
   - Added warning about APP_DESCRIPTION.qmd being source of truth
   - Documented the lesson learned

**Code Changes:**
- Modified: `Software/UTM_PyQt6/ui/utm_mainwindow.ui` (redesigned from 379 to 809 lines)
- Modified: `Software/UTM_PyQt6/main.py` (added 130+ lines of handler functions)

**Testing:**
- ✅ Application runs successfully with new layout
- ✅ All controls are accessible and functional
- ✅ Status lamp changes color on connection toggle
- ✅ Emergency stop resets direction and disables motors
- ✅ All actions log to console tab

**Current State:**
- **GUI Structure**: 100% complete (matches APP_DESCRIPTION.qmd specification)
- **Signal Wiring**: 100% complete
- **Placeholder Widgets**: Ready for custom QPainter implementation
- **Serial Communication**: 0% (next major task)
- **Matplotlib Integration**: 0% (next major task)

**Decisions Made:**
- Used QCheckBox for toggles (will consider custom switches later)
- Used QRadioButton for direction (matches MATLAB knob behavior)
- Used styled QPushButton for Emergency STOP (red with hover effects)
- Used QLabel with styleSheet for status lamp and gauge placeholders

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Choose next implementation direction:
   - **Option A**: Implement SerialManager class and COM port communication
   - **Option B**: Replace gauge placeholders with custom QPainter widgets
   - **Option C**: Add matplotlib canvases to plot tabs
3. Recommended: Start with Option A (serial communication) to enable testing with hardware

### Session: 2026-01-02 (Late Evening) - SESSION WRAP-UP AGENT CREATED! ✅

**What We Did:**
1. ✅ **Created session wrap-up agent** using proper Claude Agent SDK pattern
   - Initially attempted Python script approach (.claude/agents/session-wrapup/agent.py)
   - User corrected: "no python files should be used! There is a builtin way"
   - Researched correct approach using claude-code-guide agent
   - Recreated as Markdown file with YAML frontmatter

2. ✅ **Implemented .claude/agents/session-wrapup.md**
   - YAML frontmatter with name, description, tools, model
   - Comprehensive documentation workflow
   - Git safety protocol following CLAUDE.md guidelines
   - SESSION_STATUS.md update template
   - UTM project-specific handling instructions

**File Changes:**
- Added: `.claude/agents/session-wrapup.md` (148 lines) - Subagent definition
- Removed: `.claude/agents/session-wrapup/` directory (incorrect Python approach)
- Removed: `.claude/skills.json` (not needed for subagents)

**Lessons Learned:**
- ⚠️ **Claude Code uses Markdown-based subagents, not Python scripts**
- Subagents = `.md` files with YAML frontmatter in `.claude/agents/`
- The Agent SDK can be used programmatically, but for Claude Code integration, use subagents
- Subagents are automatically available once the file is created

**Agent Capabilities:**
- Reads PROJECT_STATUS.md and git status
- Updates session history with detailed entries
- Creates git commits with proper Claude Code attribution
- Commits only: .py, .ui, .md, .qmd, requirements.txt files
- Follows git safety protocol (no force push, no destructive commands)
- Provides structured session documentation template

**Current State:**
- **Session Wrap-Up Agent**: 100% complete and ready to use
- **Integration**: Agent can be invoked in future sessions for documentation
- **Usage**: "Use the session-wrapup agent" or invoke via Task tool

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Test the session-wrapup agent if desired
3. Choose next implementation direction:
   - **Option A (Recommended)**: Implement SerialManager class and COM port communication
   - **Option B**: Replace gauge placeholders with custom QPainter widgets
   - **Option C**: Add matplotlib canvases to plot tabs

### Session: 2026-01-02 (Night) - SERIAL COMMUNICATION IMPLEMENTED! ✅

**What We Did:**
1. ✅ **Implemented SerialManager class** (`serial_manager.py`)
   - Uses PyQt6.QtSerialPort for Qt-native serial communication
   - Signal-based architecture: connection_changed, data_received, load_cell_data, position_data, velocity_data, firmware_version, error_occurred
   - Connection handshake with firmware version verification
   - 2-second timeout for handshake failure detection
   - Response parsing for all firmware data types

2. ✅ **Added safety measures throughout**
   - On connect: EStop → Disable → GetVersion (verify connection)
   - On disconnect: Stop → Disable → close port
   - On motors toggle OFF: Stop → Disable (prevents runaway on re-enable)
   - Direction reset to STOP before enabling/disabling motors

3. ✅ **Created custom toggle switch widget** (`widgets.py`)
   - Initially tried qfluentwidgets library (had font warnings)
   - Created pure PyQt6 FluentSwitch class with no external dependencies
   - Windows Fluent Design styling (blue accent, animated toggle)
   - Smooth animation using QPropertyAnimation
   - Disabled state styling included

4. ✅ **Replaced checkboxes with toggle switches**
   - Connection checkbox → FluentSwitch
   - Motors checkbox → FluentSwitch
   - Runtime widget replacement in apply_styles()

5. ✅ **Removed qfluentwidgets dependency completely**
   - Removed from imports in main.py
   - Changed promoted widgets in .ui file back to standard Qt classes
   - Removed customwidgets section from utm_mainwindow.ui

**Files Created/Modified:**
- Created: `Software/UTM_PyQt6/serial_manager.py` (291 lines)
- Created: `Software/UTM_PyQt6/widgets.py` (228 lines)
- Modified: `Software/UTM_PyQt6/main.py` (version 0.2.0, FluentSwitch imports)
- Modified: `Software/UTM_PyQt6/ui/utm_mainwindow.ui` (removed qfluentwidgets)
- Modified: `Software/UTM_PyQt6/requirements.txt` (no changes needed - pure PyQt6)

**Testing:**
- ✅ Application starts without errors
- ✅ Toggle switches animate smoothly
- ✅ COM port scanning works
- ✅ Serial connection with handshake timeout
- ⏳ Hardware testing pending (need physical device)

**Current State:**
- **GUI Structure**: 100% complete
- **Signal Wiring**: 100% complete
- **Serial Communication**: 90% complete (parsing done, hardware test pending)
- **Custom Widgets**: Toggle switches done, gauges still placeholders
- **Matplotlib Integration**: 0%

**Version:** 0.2.0 (pre-release, serial communication milestone)

**Decisions Made:**
- Version 0.x.x for development (not 1.x.x which implies production-ready)
- Pure PyQt6 toggle switch instead of qfluentwidgets (no external UI dependencies)
- Safety-first serial protocol (always EStop/Disable on connect)

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Test serial communication with physical hardware
3. Choose next implementation direction:
   - **Option A**: Implement data plotting (matplotlib or pyqtgraph)
   - **Option B**: Replace gauge placeholders with custom QPainter widgets
   - **Option C**: Add load cell calibration workflow

### Session: 2026-01-02 (Late Night) - UI CONTROLS ENHANCED! ✅

**What We Did:**
1. ✅ **Replaced all remaining checkboxes with FluentSwitch toggles**
   - Load Cell toggle → FluentSwitch
   - Position toggle → FluentSwitch
   - Velocity toggle → FluentSwitch
   - Created helper `_replace_checkbox_with_switch()` for clean widget replacement

2. ✅ **Implemented speed unit selection system**
   - Replaced RPM checkbox with two radio buttons ("mm/s" and "RPM")
   - Added "Speed unit:" label for clarity
   - QButtonGroup ensures mutual exclusivity
   - Default: mm/s (matches physical intuition)

3. ✅ **Dynamic speed display and conversion**
   - Speed label updates based on unit selection
   - Automatic value conversion when switching units
   - Conversion factor: `MM_PER_S_PER_RPM = 5.0 / 20.0 / 60.0` (~0.004167)
   - Lead screw: 5mm pitch, 20:1 gear ratio
   - Spinbox limits adjust: mm/s (0-10), RPM (0-240)

4. ✅ **Motor control respects speed selector**
   - Direction commands (Up/Down) now use SetSpeed from selector
   - Firmware receives speed as RPM × 10 (e.g., 1200 = 120 RPM)

5. ✅ **Incremental move respects speed selector**
   - Move Up/Down buttons use speed from selector
   - Direction indicator updates to show movement direction
   - Used `blockSignals()` to prevent sending redundant commands

6. ✅ **Fixed direction indicator behavior**
   - When using incremental move, direction radio button updates visually
   - Prevents confusion when direction shows "Stop" during movement

**Code Patterns Used:**
```python
# Speed conversion
rpm = mm_per_s / MM_PER_S_PER_RPM
mm_per_s = rpm * MM_PER_S_PER_RPM

# Firmware speed command
firmware_speed = int(speed_rpm * 10)
serial_manager.send_command(f"SetSpeed {firmware_speed}")

# Update radio without triggering signal
self.upRadioButton.blockSignals(True)
self.upRadioButton.setChecked(True)
self.upRadioButton.blockSignals(False)
```

**Files Modified:**
- Modified: `Software/UTM_PyQt6/main.py`
  - Added `_replace_checkbox_with_switch()` helper
  - Added `_setup_speed_unit_controls()` for radio buttons
  - Added `_init_speed_controls()`, `on_speed_unit_changed()`, `on_speed_value_changed()`
  - Added `_update_speed_display()`, `get_speed_rpm()`, `get_firmware_speed()`
  - Updated `on_direction_changed()` to use speed selector
  - Updated `on_move_up()`, `on_move_down()` with speed and direction indicator

**Testing:**
- ✅ Application imports without errors
- ✅ Python syntax validation passed
- ⏳ Full UI testing pending (requires PyQt6 environment)
- ⏳ Hardware testing pending

**Current State:**
- **GUI Structure**: 100% complete
- **Signal Wiring**: 100% complete
- **Toggle Switches**: 100% complete (all checkboxes replaced)
- **Speed Control**: 100% complete (unit selection, conversion, motor integration)
- **Serial Communication**: 90% complete (hardware test pending)
- **Custom Gauges**: Placeholders only (0%)
- **Matplotlib Integration**: 0%

**Version:** 0.2.0 (pre-release)

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Test UI changes with physical hardware
3. Choose next implementation direction:
   - **Option A**: Implement data plotting (matplotlib or pyqtgraph)
   - **Option B**: Replace gauge placeholders with custom QPainter widgets
   - **Option C**: Add load cell calibration workflow

### Session: 2026-01-03 (Early Morning) - DATA STREAM ARCHITECTURE REDESIGNED! ✅

**What We Did:**
1. ✅ **Removed Position and Velocity switches from UI**
   - These switches were redundant - motor data should be automatic
   - Removed `positionSwitch` and `velocitySwitch` from Data Streams group
   - Added `_remove_data_stream_row()` helper to cleanly remove UI elements
   - Data Streams group now only contains Load Cell toggle

2. ✅ **Renamed position variables to motor terminology**
   - `position_zero` → `motor_position_zero`
   - `current_position_mm` → `motor_displacement_mm`
   - `current_velocity_rpm` → `motor_velocity_rpm`
   - Added `motor_position_raw` for raw encoder value
   - Added `motor_velocity_avg_rpm` for averaged velocity
   - Clear separation: motor/encoder data vs. future DIC strain data

3. ✅ **Implemented automatic motor data polling**
   - `motor_position_timer` (10 Hz) - always runs when connected
   - `motor_velocity_timer` (5 Hz) - runs when motors are enabled
   - Position polling starts on connect, stops on disconnect
   - Velocity polling starts on motor enable, stops on disable

4. ✅ **Added motor stall detection safety feature**
   - Monitors velocity when motors should be moving (direction ≠ STOP)
   - Detects stall when velocity < 0.5 RPM for 3 consecutive readings
   - Triggers emergency stop and disables motors on stall
   - Displays warning message in console
   - Configurable: `stall_velocity_threshold`, `stall_count_threshold`

**Design Decision: Motor vs DIC Strain**
- **Motor Position**: Encoder-based displacement from lead screw movement
  - Always available when connected
  - Polled automatically at 10 Hz
  - Used for basic displacement measurement
- **DIC Strain** (future): Camera-based strain measurement
  - Will have its own toggle in Stress/Strain tab
  - Optical measurement independent of motor
  - For more accurate strain measurement on specimen

**Files Modified:**
- Modified: `Software/UTM_PyQt6/main.py`
  - Removed position/velocity switches
  - Added `_remove_data_stream_row()` helper
  - Renamed all position variables to motor terminology
  - Added polling timers in `init_state()`
  - Added `_start_motor_polling()`, `_stop_motor_polling()`
  - Added `_start_velocity_polling()`, `_stop_velocity_polling()`
  - Added `_poll_motor_position()`, `_poll_motor_velocity()`
  - Renamed `on_position_data()` → `on_motor_position_data()`
  - Renamed `on_velocity_data()` → `on_motor_velocity_data()`
  - Added stall detection in `on_motor_velocity_data()`
  - Added `_handle_motor_stall()` for safety response

**Testing:**
- ✅ Python syntax validation passed
- ⏳ Hardware testing pending

**Current State:**
- **GUI Structure**: 100% complete
- **Signal Wiring**: 100% complete
- **Motor Data Polling**: 100% complete (auto-polling with stall detection)
- **Serial Communication**: 90% complete (hardware test pending)
- **Stall Detection**: 100% complete
- **Custom Gauges**: Placeholders only (0%)
- **Matplotlib Integration**: 0%
- **DIC Integration**: 0% (future feature)

**Version:** 0.2.1 (pre-release, motor data architecture milestone)

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Test motor polling and stall detection with hardware
3. Choose next implementation direction:
   - **Option A**: Implement data plotting (matplotlib or pyqtgraph)
   - **Option B**: Replace gauge placeholders with custom QPainter widgets
   - **Option C**: Add DIC toggle to Stress/Strain tab

### Session: 2026-01-03 (Morning) - SPEED CONTROL & GAUGE IMPLEMENTED! ✅

**What We Did:**
1. ✅ **Added software speed limits (MAX_RPM = 450)**
   - `MAX_RPM = 450` constant in main.py
   - `MAX_MM_PER_S = MAX_RPM * MM_PER_S_PER_RPM` (~1.875 mm/s)
   - Spinbox limits automatically adjust based on unit selection
   - `get_firmware_speed()` clamps speed to MAX_RPM with warning

2. ✅ **Fixed firmware MoveUp/MoveDown speed limits**
   - MoveUp() and MoveDown() now use `MAX_SPEED_RPM10` constant
   - Previously had hardcoded 5000 (500 RPM) which exceeded safety limit
   - Firmware version updated to 1.3.1

3. ✅ **Changed speed spinbox behavior**
   - Changed from `valueChanged` to `editingFinished` signal
   - Speed only updates when Enter is pressed or focus is lost
   - Prevents sending commands while user is typing

4. ✅ **Implemented SpeedGauge custom widget**
   - Created circular gauge in `widgets.py` using QPainter
   - Features:
     - Symmetric range: -max to +max with 0 at 12 o'clock
     - Needle indicator pointing to current value
     - Color gradient based on absolute speed (green→yellow→red)
     - Tick marks at major divisions
     - Labels showing -max, 0, +max values
     - Digital readout in center
   - Supports both RPM and mm/s units
   - Updates in real-time with motor velocity data

5. ✅ **Position/Velocity console display toggles**
   - Re-added position and velocity switches to Data Streams group
   - These control whether data is printed to console (not polling)
   - Polling is automatic - switches only affect display

6. ✅ **Movement start grace period**
   - 1-second grace period after starting movement
   - Allows motor to accelerate before stall detection activates
   - Prevents false stall alarms on startup

**Files Modified:**
- `D32_Firmware/src/main.cpp` - MoveUp/MoveDown speed limits, v1.3.1
- `Software/UTM_PyQt6/main.py` - Speed limits, gauge integration, v0.2.4
- `Software/UTM_PyQt6/widgets.py` - SpeedGauge class with symmetric range

**SpeedGauge Widget Details:**
```python
# Gauge layout (arc spans 270°):
#     -450 ←──── 0 ────→ +450
#       ╲        │        ╱
#        ╲       │       ╱
#         ╲      │      ╱
#          ╲     │     ╱
#           ╲    │    ╱
# 7 o'clock  ╲   │   ╱  5 o'clock
#             ╲  │  ╱
#              ╲ │ ╱
#               ╲│╱
#                ● (center cap)
#              [value]
#               RPM

# Key methods:
gauge.setValue(120.0)   # Positive or negative
gauge.setMaxValue(450)  # Range becomes -450 to +450
gauge.setUnit("RPM")    # Or "mm/s"
```

**Current State:**
- **GUI Structure**: 100% complete
- **Signal Wiring**: 100% complete
- **Motor Data Polling**: 100% complete (with grace period)
- **Stall Detection**: 100% complete
- **Speed Control**: 100% complete (limits + conversion)
- **SpeedGauge Widget**: 100% complete (symmetric, animated)
- **Custom Linear Gauge**: Placeholder only (0%)
- **Matplotlib Integration**: 0%

**Version:** 0.2.4 (pre-release, speed control milestone)

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Test speed gauge and motor controls with hardware
3. Choose next implementation direction:
   - **Option A**: Implement data plotting (matplotlib or pyqtgraph)
   - **Option B**: Implement linear position gauge widget
   - **Option C**: Add load cell calibration workflow

### Session: 2026-01-03 (Afternoon) - UI CLEANUP & CENTERING ✅

**What We Did:**
1. ✅ **Bumped version from 0.2.5 to 0.2.6**
   - Updated `__version__` in main.py
   - Committed status bar and incremental move grace period changes

2. ✅ **Removed linear gauge from Position group**
   - User decision: don't want to use the linear gauge
   - Removed `positionGaugePlaceholder` widget from utm_mainwindow.ui
   - Removed reference to it in `update_controls_enabled_state()`
   - Renamed group from "Position" to "Crosshead position" (standard UTM terminology)

3. ✅ **Centered Speed Control contents horizontally**
   - Initial attempt using `alignment="Qt::AlignHCenter"` on items failed
   - Error: `addLayout: too many arguments` - Qt doesn't support alignment on layout items
   - **Solution**: Used spacer-based centering approach
   - Wrapped speedGaugePlaceholder in `horizontalLayout_speedGaugeCenter` with left/right spacers
   - Added spacers to `horizontalLayout_speedUnit` and `horizontalLayout_setSpeed`
   - Updated `_setup_speed_gauge()` to find placeholder in new nested layout

**Design Decision: Crosshead vs Gripper**
- "Crosshead" = standard term for the moving part of a UTM
- "Gripper" = the clamps that hold the specimen
- User agreed with recommendation to use "Crosshead position"

**Files Modified:**
- `Software/UTM_PyQt6/main.py`
  - Version 0.2.6
  - Removed `positionGaugePlaceholder` reference
  - Updated `_setup_speed_gauge()` to use `horizontalLayout_speedGaugeCenter`
- `Software/UTM_PyQt6/ui/utm_mainwindow.ui`
  - Renamed Position group to "Crosshead position"
  - Removed linear gauge placeholder
  - Added centering spacers to Speed Control group

**Current State:**
- **GUI Structure**: 100% complete
- **Signal Wiring**: 100% complete
- **Motor Data Polling**: 100% complete
- **Stall Detection**: 100% complete
- **Speed Control**: 100% complete (limits + conversion + centered UI)
- **SpeedGauge Widget**: 100% complete
- **Linear Position Gauge**: Removed (user decision)
- **Matplotlib Integration**: 0%

**Version:** 0.2.6 (pre-release, UI cleanup milestone)

**Next Session Should Start With:**
1. Read PROJECT_STATUS.md (this file)
2. Test centered Speed Control UI with application
3. Choose next implementation direction:
   - **Option A**: Implement data plotting (matplotlib or pyqtgraph)
   - **Option B**: Add load cell calibration workflow
   - **Option C**: Implement crosshead position display improvements

---

## Technical Decisions Log

### Architecture Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| PyQt6 (not PySide6) | Already defined in requirements.txt | 2026-01-02 |
| QtSerialPort over pyserial | Better Qt integration, signal-based | 2026-01-02 |
| pandas DataFrame for data storage | Easy export, manipulation, memory efficiency | 2026-01-02 |
| matplotlib (may switch to pyqtgraph) | Standard choice, may need performance upgrade | 2026-01-02 |
| Motor vs DIC terminology | Motor = encoder-based, DIC = camera-based strain | 2026-01-03 |
| Auto-poll motor data | No switches needed - always poll when connected/enabled | 2026-01-03 |
| Stall detection | Safety feature - stop motors if velocity near zero | 2026-01-03 |
| MAX_RPM = 450 | Hardware safety limit, enforced in software and firmware | 2026-01-03 |
| Symmetric gauge range | -max to +max with 0 at top - shows direction of rotation | 2026-01-03 |
| editingFinished signal | Speed only updates on Enter/focus-lost, not while typing | 2026-01-03 |
| Crosshead position (not Gripper) | Standard UTM terminology for moving part | 2026-01-03 |
| Removed linear gauge | User preference - displacement shown as text only | 2026-01-03 |
| Spacer-based centering | Qt item alignment doesn't work for nested layouts | 2026-01-03 |

### Design Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| Signal/Slot | Serial communication, UI events | Qt native, thread-safe |
| QThread for serial I/O | SerialManager | Non-blocking I/O, prevents GUI freeze |
| Manager classes | Data, Plot, Calibration, Camera | Separation of concerns |
| Two-timer architecture | Connection health + data polling | Matches MATLAB implementation |

---

## Known Issues & TODOs

### Immediate TODOs
- [ ] Implement SerialManager class
- [ ] Add COM port scanning and dropdown
- [ ] Create status lamp widget
- [ ] Test serial connection with Arduino
- [ ] Add motor enable/disable functionality

### Future Work
- [ ] Custom circular gauge widget (speed display)
- [ ] Custom linear gauge widget (position display)
- [ ] Range slider widget for plot cropping
- [ ] Camera integration (Basler pypylon)
- [ ] DIC (Digital Image Correlation) implementation

### Known Limitations
- MATLAB .mlapp files are binary (not directly version controllable)
- Real-time plotting may have performance issues with matplotlib
- Custom widgets require significant QPainter implementation

---

## Reference Files

**Essential Documentation:**
- `CLAUDE.md` - Comprehensive guide for Claude Code
- `APP_DESCRIPTION.md` - MATLAB to PyQt6 conversion guide (856 lines)
- `PROJECT_REQUIREMENTS.md` - Hardware and software specifications
- `README.md` - Project overview and background

**Active Development:**
- `Software/UTM_PyQt6/main.py` - Main application file
- `Software/UTM_PyQt6/ui/utm_mainwindow.ui` - Qt Designer UI
- `D32_Firmware/D32_Firmware.ino` - Arduino firmware (stable)

**Reference Implementation:**
- `Software/UTM.mlapp` - Production MATLAB GUI (binary)
- `Software/UTM_exported.m` - MATLAB source export (reference)

---

## Environment Info

**Development Machine:** Windows (win32)
**Python Version:** (to be confirmed - check with `python --version`)
**Qt Version:** PyQt6 >= 6.6.0
**Arduino IDE:** (version to be confirmed)
**Hardware Connected:** (to be confirmed - check COM ports)

---

## Notes for Future Sessions

1. **Always read this file first** to understand current state
2. **Update this file** when:
   - Completing major milestones
   - Making architectural decisions
   - Encountering blockers
   - Wrapping up a work session
3. **Session wrap-up checklist:**
   - Update "Current Project State" section
   - Add entry to "Session History"
   - Update completion percentages
   - Note any new decisions or blockers
   - List recommended next steps

---

## Quick Start Commands

```bash
# Run current PyQt6 application
cd Software/UTM_PyQt6
python main.py

# Install dependencies
pip install -r requirements.txt

# Edit UI in Qt Designer
pyqt6-tools designer ui/utm_mainwindow.ui
```

---

*This file should be updated at the end of each work session to maintain continuity.*
