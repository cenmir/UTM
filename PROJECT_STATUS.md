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

**PyQt6 GUI (Software/UTM_PyQt6/):** 🚧 ~25% Complete
- Phase 1 (Foundation): 85% - GUI structure complete, serial pending
- Phase 2-7: Structure ready, implementation pending

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
