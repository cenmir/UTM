# UTM Project Status & Session Log

**Last Updated:** 2026-01-02

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

**PyQt6 GUI (Software/UTM_PyQt6/):** 🚧 ~5% Complete
- Phase 1 (Foundation): 20% - Console tab functional
- Phase 2-7: Not started

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

---

## Technical Decisions Log

### Architecture Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| PyQt6 (not PySide6) | Already defined in requirements.txt | 2026-01-02 |
| QtSerialPort over pyserial | Better Qt integration, signal-based | 2026-01-02 |
| pandas DataFrame for data storage | Easy export, manipulation, memory efficiency | 2026-01-02 |
| matplotlib (may switch to pyqtgraph) | Standard choice, may need performance upgrade | 2026-01-02 |

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
