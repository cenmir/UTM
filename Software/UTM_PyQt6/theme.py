"""Dark / light theming for the UTM application.

    from theme import THEMES, stylesheet, style_axes

A GUI theme is not just a Qt stylesheet. Three separate things have to move together or the result
is a dark shell wrapped around white rectangles:

  1. **Qt widgets** — a QSS string applied to the QApplication.
  2. **The embedded matplotlib canvases** — figure/axes facecolour, spines, ticks, labels, grid, the
     hover annotation box and the crosshair/crop guide lines. These are plain matplotlib artists and
     know nothing about Qt, so they must be restyled explicitly and the canvas redrawn.
  3. **Colours hard-coded in main.py** — status lamps, the DIC health chip, the ±limit captions.
     Those are looked up from the active palette instead of being written into the call sites.

The custom-painted widgets (`SpeedGauge`, `ToggleSwitch`, `RangeSlider` in widgets.py) are already
drawn in dark greys and read correctly on both themes, so they are deliberately left alone.

LIGHT is deliberately a near-empty stylesheet: it is the app's original appearance, so switching to
light is a true revert rather than a second, subtly different look to maintain.
"""

# --------------------------------------------------------------------------- palettes
DARK = {
    "name":        "dark",
    "window":      "#1f2329",
    "base":        "#262b33",     # input backgrounds
    "panel":       "#2b313a",     # group boxes, tabs
    "panel_alt":   "#323945",     # NESTED group boxes — a step lighter so the nesting is visible
    "raised":      "#333a45",     # buttons
    "raised_hi":   "#3d4652",
    "text":        "#e4e7eb",
    "text_dim":    "#9aa3ae",
    "border":      "#3c444f",     # subtle dividers
    # Group-box outlines are NEUTRAL by design — no hue. Separation is carried by lightness and
    # line weight, so nothing competes with the status colours (green OK / amber warn / red stop),
    # which are the only things on this GUI that should read as "coloured".
    "border_strong": "#7f8b99",   # outer groups, 1 px
    "border_bright": "#a8b2bf",   # nested groups, 2 px — near-white against the panel
    "accent":      "#4da3ff",
    "accent_text": "#0b1116",
    "ok":          "#3fb950",
    "warn":        "#d29922",
    "bad":         "#f85149",
    "info":        "#58a6ff",
    "amber_text":  "#e3a008",
    # matplotlib
    "plot_bg":     "#262b33",
    "plot_axes":   "#1f2329",
    "plot_fg":     "#d5d9de",
    "plot_grid":   "#454d59",
    "plot_note_bg": "#333a45",
    "plot_note_ec": "#5a6470",
    "plot_guide":  "#8b949e",
    "trace_1":     "#4da3ff",
    "trace_2":     "#ff7b72",
}

LIGHT = {
    "name":        "light",
    "window":      "#f0f0f0",
    "base":        "#ffffff",
    "panel":       "#f0f0f0",
    "raised":      "#e6e6e6",
    "raised_hi":   "#dcdcdc",
    "panel_alt":   "#e8e8e8",
    "text":        "#1a1a1a",
    "text_dim":    "#333333",
    "border":      "#bbbbbb",
    "border_strong": "#999999",
    "border_bright": "#777777",
    "accent":      "#0066cc",
    "accent_text": "#ffffff",
    "ok":          "#00aa66",
    "warn":        "#cc8800",
    "bad":         "#aa3333",
    "info":        "#0066cc",
    "amber_text":  "#cc6600",
    "plot_bg":     "#f0f0f0",
    "plot_axes":   "#ffffff",
    "plot_fg":     "#000000",
    "plot_grid":   "#b0b0b0",
    "plot_note_bg": "white",
    "plot_note_ec": "gray",
    "plot_guide":  "gray",
    "trace_1":     "blue",
    "trace_2":     "red",
}

THEMES = {"dark": DARK, "light": LIGHT}
DEFAULT = "dark"


def get(name):
    return THEMES.get(name, THEMES[DEFAULT])


# --------------------------------------------------------------------------- Qt stylesheet
_DARK_QSS = """
QWidget {{ background-color: {window}; color: {text}; }}
QMainWindow, QDialog {{ background-color: {window}; }}
QToolTip {{ background-color: {panel}; color: {text}; border: 1px solid {border}; padding: 3px; }}

/* Group boxes carry the whole visual hierarchy of the control column, so their outline has to be
   clearly darker/lighter than the panel it sits on rather than a hairline that blends in. */
QGroupBox {{
    background-color: {panel}; border: 1px solid {border_strong}; border-radius: 5px;
    margin-top: 11px; padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 9px; padding: 0 5px;
    color: {text}; font-weight: bold;
}}
/* NESTED groups are distinguished by WEIGHT and LIGHTNESS, not by hue: a 2 px near-white outline
   and a background one step lighter than the parent. Keeping them neutral leaves green/amber/red
   meaning exactly one thing on this GUI — machine state. */
QGroupBox#advancedModesGroup, QGroupBox#specimenTestGroup {{
    background-color: {panel_alt};
    border: 2px solid {border_bright};
    margin-top: 12px;
}}

QTabWidget::pane {{ border: 1px solid {border}; background: {panel}; }}
QTabBar::tab {{
    background: {window}; color: {text_dim};
    border: 1px solid {border}; border-bottom: none;
    padding: 5px 14px; margin-right: 2px;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{ background: {panel}; color: {text}; }}
QTabBar::tab:hover {{ background: {raised}; }}

QPushButton {{
    background-color: {raised}; color: {text};
    border: 1px solid {border}; border-radius: 4px; padding: 4px 10px;
}}
QPushButton:hover  {{ background-color: {raised_hi}; }}
QPushButton:pressed{{ background-color: {accent}; color: {accent_text}; }}
QPushButton:disabled {{ background-color: {window}; color: {text_dim}; border-color: {window}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit, QListView, QTreeView {{
    background-color: {base}; color: {text};
    border: 1px solid {border}; border-radius: 4px; padding: 2px 4px;
    selection-background-color: {accent}; selection-color: {accent_text};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {text_dim}; background-color: {window};
}}
QComboBox QAbstractItemView {{
    background-color: {base}; color: {text};
    border: 1px solid {border}; selection-background-color: {accent};
    selection-color: {accent_text};
}}
QComboBox::drop-down {{ border: none; width: 16px; }}

/* Spin buttons MUST be given explicit geometry. Styling QSpinBox at all switches it to full
   stylesheet rendering, and any subcontrol left unstyled gets degenerate geometry - the
   up-button ended up with no hit area at all, so only the down arrow was clickable and the
   cursor fell through to the line edit's I-beam. */
QSpinBox, QDoubleSpinBox {{ padding-right: 18px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 16px; height: 9px; margin: 1px 1px 0 0;
    border: 1px solid {border}; border-radius: 2px; background: {window};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 16px; height: 9px; margin: 0 1px 1px 0;
    border: 1px solid {border}; border-radius: 2px; background: {window};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {accent}; }}
/* Arrows drawn from borders - a stylesheet-rendered spinbox loses its native ones. */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid {text};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {text};
}}

QCheckBox, QRadioButton, QLabel {{ background: transparent; color: {text}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {text_dim}; }}

/* Indicators MUST be styled explicitly. The moment a stylesheet touches QCheckBox/QRadioButton at
   all, Qt stops drawing the native indicator and falls back to the box model — which inherits the
   dark panel colour and leaves a dark circle on a dark background. That is why Direction read as
   bare words with no visible selection: "Stop" WAS checked, its dot was just invisible.
   The checked radio is a radial gradient because QSS cannot draw a dot inside a border box: the
   accent fills the inner 45 % of the radius, the base colour the rest, and the 1 px outline sits
   around both. */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    background-color: {base};
    border: 1px solid {border_bright};
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator {{ border-radius: 3px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {accent}; }}
QRadioButton::indicator:checked {{
    background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                      stop:0 {accent}, stop:0.45 {accent},
                                      stop:0.5 {base}, stop:1 {base});
    border-color: {accent};
}}
QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background-color: {window}; border-color: {border};
}}
QRadioButton::indicator:checked:disabled {{
    background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                      stop:0 {text_dim}, stop:0.45 {text_dim},
                                      stop:0.5 {window}, stop:1 {window});
    border-color: {border};
}}
QCheckBox::indicator:checked:disabled {{ background-color: {text_dim}; border-color: {border}; }}

QMenuBar {{ background-color: {window}; color: {text}; border-bottom: 1px solid {border}; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; }}
QMenuBar::item:selected {{ background: {raised}; }}
QMenu {{ background-color: {panel}; color: {text}; border: 1px solid {border}; }}
QMenu::item:selected {{ background-color: {accent}; color: {accent_text}; }}

QScrollBar:vertical   {{ background: {window}; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: {window}; height: 12px; margin: 0; }}
QScrollBar::handle {{ background: {raised_hi}; border-radius: 5px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {accent}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSplitter::handle {{ background: {border}; }}
QSplitter::handle:hover {{ background: {accent}; }}
QProgressBar {{ background: {base}; border: 1px solid {border}; border-radius: 4px; text-align: center; }}
QProgressBar::chunk {{ background: {accent}; }}
QStatusBar {{ background: {window}; color: {text_dim}; }}
"""


# The three controls an operator actually reaches for during a test. They sat in the same flat grey
# as every other button, so the eye had nothing to land on. Lifted by LIGHTNESS and WEIGHT only —
# a step lighter than a normal button, the same neutral outline the group boxes use, bold text — so
# nothing here competes with green/amber/red, which on this GUI mean machine state and nothing else.
#
# The :disabled rules are NOT optional. An ID selector outranks the generic QPushButton:disabled
# rule, so without them a disabled "Fracture test" would keep the emphasised look and read as armed
# when it is not — the exact opposite of what emphasis is for.
_EMPHASIS_QSS = """
QPushButton#prepareTestButton, QPushButton#fractureTestButton {{
    background-color: {raised_hi};
    border: 1px solid {border_strong};
    border-radius: 4px; padding: 5px 12px; font-weight: bold;
}}
QPushButton#prepareTestButton:hover, QPushButton#fractureTestButton:hover {{
    background-color: {panel_alt}; border-color: {border_bright};
}}
QPushButton#prepareTestButton:pressed, QPushButton#fractureTestButton:pressed {{
    background-color: {raised};
}}
QPushButton#prepareTestButton:disabled, QPushButton#fractureTestButton:disabled {{
    background-color: {window}; color: {text_dim};
    border-color: {border}; font-weight: normal;
}}
QCheckBox#autoStopFractureCheck {{
    background-color: {raised};
    border: 1px solid {border_strong};
    border-radius: 4px; padding: 3px 8px; font-weight: bold;
}}
QCheckBox#autoStopFractureCheck:disabled {{
    background-color: transparent; border-color: {border};
    color: {text_dim}; font-weight: normal;
}}
"""


def stylesheet(name):
    """QSS for the whole application.

    Light stays the app's ORIGINAL Qt-default look — switching back is a genuine revert, not a
    second theme to maintain — with one deliberate exception: the emphasis on the three test
    controls applies to both themes, because "which button do I press" should not depend on the
    colour scheme."""
    t = get(name)
    emphasis = _EMPHASIS_QSS.format(**t)
    return emphasis if t["name"] == "light" else _DARK_QSS.format(**t) + emphasis


# --------------------------------------------------------------------------- matplotlib
def style_axes(fig, ax, name, *, annotation=None, guides=(), crop_lines=(), traces=()):
    """Recolour an existing figure in place.

    The canvases are built once at start-up and merely redrawn afterwards, so a theme switch has to
    walk the artists rather than rebuild them. `annotation` is the hover box, `guides` the crosshair
    lines, `crop_lines` the red crop markers (left red in both themes — they are a warning colour,
    not decoration), `traces` (line, kind) pairs where kind is 1 or 2.
    """
    t = get(name)
    fig.set_facecolor(t["plot_bg"])
    ax.set_facecolor(t["plot_axes"])
    for spine in ax.spines.values():
        spine.set_color(t["plot_grid"])
    ax.tick_params(colors=t["plot_fg"], which="both")
    ax.xaxis.label.set_color(t["plot_fg"])
    ax.yaxis.label.set_color(t["plot_fg"])
    ax.title.set_color(t["plot_fg"])
    ax.grid(True, alpha=0.3, color=t["plot_grid"])

    if annotation is not None:
        annotation.set_color(t["plot_fg"])
        bbox = annotation.get_bbox_patch()
        if bbox is not None:
            bbox.set_facecolor(t["plot_note_bg"])
            bbox.set_edgecolor(t["plot_note_ec"])
    for g in guides:
        if g is not None:
            g.set_color(t["plot_guide"])
    for c in crop_lines:                     # deliberately NOT themed: red = "you are cropping"
        pass
    for line, kind in traces:
        if line is not None:
            line.set_color(t["trace_1"] if kind == 1 else t["trace_2"])

    leg = ax.get_legend()
    if leg is not None:
        leg.get_frame().set_facecolor(t["plot_note_bg"])
        leg.get_frame().set_edgecolor(t["plot_note_ec"])
        for txt in leg.get_texts():
            txt.set_color(t["plot_fg"])
