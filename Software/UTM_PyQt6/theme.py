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
    "raised":      "#333a45",     # buttons
    "raised_hi":   "#3d4652",
    "text":        "#e4e7eb",
    "text_dim":    "#9aa3ae",
    "border":      "#3c444f",
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
    "text":        "#1a1a1a",
    "text_dim":    "#333333",
    "border":      "#bbbbbb",
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

QGroupBox {{
    background-color: {panel}; border: 1px solid {border}; border-radius: 5px;
    margin-top: 9px; padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px;
    color: {text_dim};
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

QCheckBox, QRadioButton, QLabel {{ background: transparent; color: {text}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {text_dim}; }}

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


def stylesheet(name):
    """QSS for the whole application. Light returns '' — the app's original Qt-default look, so
    switching back is a genuine revert rather than a second theme to keep in sync."""
    t = get(name)
    return "" if t["name"] == "light" else _DARK_QSS.format(**t)


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
