"""
Custom Widgets for UTM Application

Contains custom Qt widgets including toggle switches and gauges.
"""

# Source - https://stackoverflow.com/a/62364553
# Posted by eyllanesc, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-02, License - CC BY-SA 4.0
# Modified for PyQt6 compatibility

import math
from PyQt6.QtCore import QObject, QSize, QPointF, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSlot, Qt
from PyQt6.QtGui import QPainter, QPalette, QLinearGradient, QGradient, QColor, QPen, QFont, QConicalGradient, QBrush
from PyQt6.QtWidgets import QAbstractButton, QWidget


class SwitchPrivate(QObject):
    def __init__(self, q, parent=None):
        QObject.__init__(self, parent=parent)
        self.mPointer = q
        self.mPosition = 0.0
        self.mGradient = QLinearGradient()
        self.mGradient.setSpread(QGradient.Spread.PadSpread)

        self.animation = QPropertyAnimation(self)
        self.animation.setTargetObject(self)
        self.animation.setPropertyName(b'position')
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutExpo)

        self.animation.finished.connect(self.mPointer.update)

    @pyqtProperty(float)
    def position(self):
        return self.mPosition

    @position.setter
    def position(self, value):
        self.mPosition = value
        self.mPointer.update()

    def draw(self, painter):
        r = self.mPointer.rect()
        margin = r.height() / 10
        shadow = self.mPointer.palette().color(QPalette.ColorRole.Dark)
        light = self.mPointer.palette().color(QPalette.ColorRole.Light)
        button = self.mPointer.palette().color(QPalette.ColorRole.Button)
        painter.setPen(Qt.PenStyle.NoPen)

        self.mGradient.setColorAt(0, shadow.darker(130))
        self.mGradient.setColorAt(1, light.darker(130))
        self.mGradient.setStart(0, r.height())
        self.mGradient.setFinalStop(0, 0)
        painter.setBrush(self.mGradient)
        painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        self.mGradient.setColorAt(0, shadow.darker(140))
        self.mGradient.setColorAt(1, light.darker(160))
        self.mGradient.setStart(0, 0)
        self.mGradient.setFinalStop(0, r.height())
        painter.setBrush(self.mGradient)
        painter.drawRoundedRect(
            r.adjusted(int(margin), int(margin), int(-margin), int(-margin)),
            r.height() / 2,
            r.height() / 2
        )

        self.mGradient.setColorAt(0, button.darker(130))
        self.mGradient.setColorAt(1, button)

        painter.setBrush(self.mGradient)

        x = r.height() / 2.0 + self.mPosition * (r.width() - r.height())
        painter.drawEllipse(QPointF(x, r.height() / 2), r.height() / 2 - margin, r.height() / 2 - margin)

    @pyqtSlot(bool, name='animate')
    def animate(self, checked):
        self.animation.setDirection(
            QPropertyAnimation.Direction.Forward if checked else QPropertyAnimation.Direction.Backward
        )
        self.animation.start()


class Switch(QAbstractButton):
    """
    A toggle switch widget that looks like a modern iOS/Android toggle.

    Usage:
        switch = Switch()
        switch.setChecked(True)  # Turn on
        switch.clicked.connect(my_handler)  # Connect to handler
    """

    def __init__(self, parent=None):
        QAbstractButton.__init__(self, parent=parent)
        self.dPtr = SwitchPrivate(self)
        self.setCheckable(True)
        self.clicked.connect(self.dPtr.animate)

    def sizeHint(self):
        return QSize(60, 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.dPtr.draw(painter)

    def resizeEvent(self, event):
        self.update()

    def setChecked(self, checked):
        """Override to update visual state without animation when set programmatically"""
        super().setChecked(checked)
        # Update position immediately without animation
        self.dPtr.mPosition = 1.0 if checked else 0.0
        self.update()


class FluentSwitch(QAbstractButton):
    """
    A toggle switch widget styled like Windows Fluent Design.

    Features:
    - Flat design with rounded track
    - Accent color when checked (blue)
    - Gray border when unchecked
    - White circular indicator
    - Smooth animation on toggle

    Usage:
        switch = FluentSwitch()
        switch.setChecked(True)
        switch.checkedChanged.connect(my_handler)  # Note: use clicked signal
    """

    # Colors matching Fluent Design
    TRACK_ON_COLOR = QColor(0, 95, 184)       # Fluent blue accent
    TRACK_OFF_COLOR = QColor(50, 50, 50)      # Dark gray background
    TRACK_OFF_BORDER = QColor(158, 158, 158)  # Gray border when off
    INDICATOR_COLOR = QColor(255, 255, 255)   # White indicator
    TRACK_DISABLED = QColor(80, 80, 80)       # Disabled track
    INDICATOR_DISABLED = QColor(120, 120, 120)  # Disabled indicator

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)

        # Animation for smooth toggle
        self._position = 0.0
        self._animation = QPropertyAnimation(self, b"position")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        """Animate the switch when clicked"""
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if self.isChecked() else 0.0)
        self._animation.start()

    @pyqtProperty(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self.update()

    def sizeHint(self):
        return QSize(44, 22)

    def setChecked(self, checked):
        """Override to update visual state without animation when set programmatically"""
        super().setChecked(checked)
        self._position = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Track dimensions
        track_height = h - 2
        track_radius = track_height / 2

        # Indicator dimensions
        indicator_margin = 3
        indicator_radius = (track_height / 2) - indicator_margin

        # Determine colors based on state
        if not self.isEnabled():
            track_color = self.TRACK_DISABLED
            indicator_color = self.INDICATOR_DISABLED
            border_color = self.TRACK_DISABLED
        elif self._position > 0.5:
            # Interpolate colors for smooth transition
            track_color = self.TRACK_ON_COLOR
            indicator_color = self.INDICATOR_COLOR
            border_color = self.TRACK_ON_COLOR
        else:
            track_color = self.TRACK_OFF_COLOR
            indicator_color = self.INDICATOR_COLOR
            border_color = self.TRACK_OFF_BORDER

        # Draw track
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(track_color if self._position > 0.5 else Qt.GlobalColor.transparent)
        track_rect = QRectF(1, 1, w - 2, track_height)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)

        # Draw indicator (circle)
        # Position: left when off, right when on
        left_x = indicator_margin + indicator_radius + 1
        right_x = w - indicator_margin - indicator_radius - 1
        indicator_x = left_x + self._position * (right_x - left_x)
        indicator_y = h / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(indicator_color)
        painter.drawEllipse(QPointF(indicator_x, indicator_y), indicator_radius, indicator_radius)


class SpeedGauge(QWidget):
    """
    A circular speed gauge widget for displaying RPM or mm/s.

    Features:
    - Circular arc showing speed range from -max to +max
    - Zero point at top (12 o'clock position)
    - Needle indicator pointing to current value
    - Digital readout in center
    - Color gradient based on absolute speed (green low, red high)

    Usage:
        gauge = SpeedGauge()
        gauge.setValue(120.0)  # Set current speed (positive or negative)
        gauge.setMaxValue(450)  # Set maximum (default 450 RPM, range is -450 to +450)
        gauge.setUnit("RPM")  # Set unit label
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._max_value = 450.0  # Default max RPM (symmetric range: -max to +max)
        self._unit = "RPM"

        # Visual settings
        self._arc_width = 12
        # Arc spans from 7 o'clock (-max) through 12 o'clock (0) to 5 o'clock (+max)
        # In Qt coordinate system: 0° is 3 o'clock, positive is counter-clockwise
        # 225° is 7 o'clock (bottom-left), 90° is 12 o'clock (top), -45° (315°) is 5 o'clock (bottom-right)
        self._start_angle = 225  # 7 o'clock position (for -max)
        self._span_angle = 270   # Total arc span (225° to -45°, going clockwise)

        # Colors
        self._background_color = QColor(40, 40, 40)
        self._arc_background = QColor(60, 60, 60)
        self._text_color = QColor(220, 220, 220)
        self._needle_color = QColor(255, 80, 80)

        self.setMinimumSize(120, 120)

    def sizeHint(self):
        return QSize(150, 150)

    def setValue(self, value):
        """Set the current speed value (can be negative or positive)"""
        # Clamp to symmetric range: -max to +max
        self._value = max(-self._max_value, min(value, self._max_value))
        self.update()

    def value(self):
        return self._value

    def setMaxValue(self, max_val):
        """Set the maximum value on the gauge (range becomes -max to +max)"""
        self._max_value = abs(max_val)  # Ensure positive
        self.update()

    def setUnit(self, unit):
        """Set the unit label (e.g., 'RPM' or 'mm/s')"""
        self._unit = unit
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate dimensions
        side = min(self.width(), self.height())
        painter.translate(self.width() / 2, self.height() / 2)

        # Scale to fit
        scale = side / 160.0
        painter.scale(scale, scale)

        # Draw background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background_color)
        painter.drawEllipse(QPointF(0, 0), 75, 75)

        # Draw arc background (gray track)
        self._draw_arc(painter, self._arc_background, 0, self._span_angle)

        # Draw colored arc from center (0) to current value
        # Range is -max to +max, with 0 at center (top, 12 o'clock)
        # Left half (225° to 90°) is negative, right half (90° to -45°) is positive
        if self._max_value > 0:
            # Normalize value to -1 to +1 range
            normalized = self._value / self._max_value
            normalized = max(-1, min(1, normalized))

            # Calculate arc span from center (0 is at half of total span)
            # Positive values: arc goes from center toward right (clockwise)
            # Negative values: arc goes from center toward left (counter-clockwise)
            half_span = self._span_angle / 2  # 135 degrees

            # Color gradient based on absolute speed (green low, red high)
            abs_normalized = abs(normalized)
            if abs_normalized < 0.5:
                # Green to yellow
                r = int(100 + abs_normalized * 2 * 155)
                g = 200
                b = 100
            else:
                # Yellow to red
                r = 255
                g = int(200 - (abs_normalized - 0.5) * 2 * 150)
                b = int(100 - (abs_normalized - 0.5) * 2 * 100)

            arc_color = QColor(r, g, b)

            if normalized >= 0:
                # Positive: draw from center toward +max (clockwise from 90° toward -45°)
                arc_span = normalized * half_span
                self._draw_arc_from_center(painter, arc_color, arc_span, positive=True)
            else:
                # Negative: draw from center toward -max (counter-clockwise from 90° toward 225°)
                arc_span = abs(normalized) * half_span
                self._draw_arc_from_center(painter, arc_color, arc_span, positive=False)

        # Draw tick marks
        self._draw_ticks(painter)

        # Draw needle
        self._draw_needle(painter)

        # Draw center cap
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(80, 80, 80))
        painter.drawEllipse(QPointF(0, 0), 12, 12)
        painter.setBrush(QColor(60, 60, 60))
        painter.drawEllipse(QPointF(0, 0), 8, 8)

        # Draw digital readout
        self._draw_text(painter)

    def _draw_arc(self, painter, color, start_offset, span):
        """Draw an arc segment from the start position"""
        pen = QPen(color)
        pen.setWidth(self._arc_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        rect = QRectF(-60, -60, 120, 120)
        # Convert to Qt angles (16ths of a degree, 0 = 3 o'clock, counter-clockwise positive)
        start = (self._start_angle - start_offset) * 16
        span_qt = -span * 16  # Negative for clockwise
        painter.drawArc(rect, int(start), int(span_qt))

    def _draw_arc_from_center(self, painter, color, span, positive=True):
        """Draw an arc segment from the center (0 position at top) toward positive or negative max"""
        pen = QPen(color)
        pen.setWidth(self._arc_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        rect = QRectF(-60, -60, 120, 120)
        # Center position is at 90° (12 o'clock, top)
        # In Qt: angles are in 16ths of a degree, 0 = 3 o'clock, positive = counter-clockwise
        center_angle = 90  # 12 o'clock position

        if positive:
            # Draw clockwise from center toward +max (toward 5 o'clock / -45°)
            start = center_angle * 16
            span_qt = -span * 16  # Negative for clockwise
        else:
            # Draw counter-clockwise from center toward -max (toward 7 o'clock / 225°)
            start = center_angle * 16
            span_qt = span * 16  # Positive for counter-clockwise

        painter.drawArc(rect, int(start), int(span_qt))

    def _draw_ticks(self, painter):
        """Draw tick marks around the gauge with labels for -max, 0, +max"""
        painter.save()

        # Rotate to start position (7 o'clock for -max)
        painter.rotate(-(self._start_angle - 90))

        # 9 major ticks: -max, -3/4, -1/2, -1/4, 0, +1/4, +1/2, +3/4, +max
        num_major_ticks = 9
        num_minor_ticks = 2  # Between each major tick

        total_ticks = (num_major_ticks - 1) * (num_minor_ticks + 1) + 1
        angle_step = self._span_angle / (total_ticks - 1)

        for i in range(total_ticks):
            is_major = i % (num_minor_ticks + 1) == 0

            if is_major:
                painter.setPen(QPen(QColor(200, 200, 200), 2))
                inner_radius = 48
                outer_radius = 54
            else:
                painter.setPen(QPen(QColor(120, 120, 120), 1))
                inner_radius = 50
                outer_radius = 54

            painter.drawLine(QPointF(0, -inner_radius), QPointF(0, -outer_radius))
            painter.rotate(angle_step)

        painter.restore()

    def _draw_needle(self, painter):
        """Draw the needle indicator"""
        painter.save()

        # Calculate needle angle for symmetric range (-max to +max)
        # 0 is at 12 o'clock (0° rotation from vertical)
        # -max is at 7 o'clock (-135° from vertical)
        # +max is at 5 o'clock (+135° from vertical)
        if self._max_value > 0:
            # Normalize to -1 to +1
            normalized = self._value / self._max_value
            normalized = max(-1, min(1, normalized))
            # Convert to angle: -1 -> -135°, 0 -> 0°, +1 -> +135°
            half_span = self._span_angle / 2  # 135 degrees
            needle_angle = normalized * half_span
        else:
            needle_angle = 0

        painter.rotate(needle_angle)

        # Draw needle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._needle_color)

        # Needle as a triangle
        needle = [
            QPointF(0, -50),   # Tip
            QPointF(-4, 10),   # Base left
            QPointF(4, 10),    # Base right
        ]
        painter.drawPolygon(needle)

        painter.restore()

    def _draw_text(self, painter):
        """Draw the digital readout text"""
        # Value text
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(self._text_color)

        # Format value appropriately (handle negative values)
        abs_value = abs(self._value)
        sign = "-" if self._value < 0 else ""
        if abs_value >= 100:
            value_text = f"{sign}{abs_value:.0f}"
        elif abs_value >= 10:
            value_text = f"{sign}{abs_value:.1f}"
        else:
            value_text = f"{sign}{abs_value:.2f}"

        value_rect = QRectF(-40, 15, 80, 25)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, value_text)

        # Unit text
        font.setPointSize(9)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(150, 150, 150))

        unit_rect = QRectF(-40, 35, 80, 20)
        painter.drawText(unit_rect, Qt.AlignmentFlag.AlignCenter, self._unit)


class RangeSlider(QWidget):
    """
    A custom range slider widget with two handles for selecting a range.

    Emits rangeChanged signal when either handle is moved.
    Values are in percentage (0-100).
    """
    from PyQt6.QtCore import pyqtSignal
    rangeChanged = pyqtSignal(int, int)  # (low, high) percentages

    def __init__(self, parent=None):
        super().__init__(parent)
        self._low = 0
        self._high = 100
        self._pressed_handle = None  # 'low', 'high', or None
        self._handle_width = 12
        self._handle_height = 20
        self._track_height = 6

        self.setMinimumHeight(30)
        self.setMinimumWidth(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def low(self):
        """Get the low value (0-100)"""
        return self._low

    def high(self):
        """Get the high value (0-100)"""
        return self._high

    def setLow(self, value):
        """Set the low value (0-100)"""
        value = max(0, min(value, self._high))
        if value != self._low:
            self._low = value
            self.update()
            self.rangeChanged.emit(self._low, self._high)

    def setHigh(self, value):
        """Set the high value (0-100)"""
        value = max(self._low, min(value, 100))
        if value != self._high:
            self._high = value
            self.update()
            self.rangeChanged.emit(self._low, self._high)

    def setRange(self, low, high):
        """Set both values at once"""
        low = max(0, min(low, 100))
        high = max(low, min(high, 100))
        if low != self._low or high != self._high:
            self._low = low
            self._high = high
            self.update()
            self.rangeChanged.emit(self._low, self._high)

    def _value_to_x(self, value):
        """Convert a value (0-100) to x coordinate"""
        usable_width = self.width() - self._handle_width
        return int(self._handle_width / 2 + (value / 100.0) * usable_width)

    def _x_to_value(self, x):
        """Convert an x coordinate to a value (0-100)"""
        usable_width = self.width() - self._handle_width
        value = ((x - self._handle_width / 2) / usable_width) * 100
        return int(max(0, min(100, value)))

    def _handle_rect(self, which):
        """Get the rectangle for a handle ('low' or 'high')"""
        value = self._low if which == 'low' else self._high
        x = self._value_to_x(value)
        y = (self.height() - self._handle_height) // 2
        return QRectF(x - self._handle_width / 2, y, self._handle_width, self._handle_height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track background
        track_y = (self.height() - self._track_height) // 2
        track_rect = QRectF(self._handle_width / 2, track_y,
                           self.width() - self._handle_width, self._track_height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 200, 200))
        painter.drawRoundedRect(track_rect, 3, 3)

        # Selected range highlight
        low_x = self._value_to_x(self._low)
        high_x = self._value_to_x(self._high)
        if self._low > 0 or self._high < 100:
            selected_rect = QRectF(low_x, track_y, high_x - low_x, self._track_height)
            painter.setBrush(QColor(0, 120, 215))
            painter.drawRoundedRect(selected_rect, 3, 3)

        # Draw handles
        for which in ['low', 'high']:
            rect = self._handle_rect(which)

            # Handle shadow
            painter.setBrush(QColor(100, 100, 100))
            shadow_rect = QRectF(rect.x() + 1, rect.y() + 1, rect.width(), rect.height())
            painter.drawRoundedRect(shadow_rect, 3, 3)

            # Handle body
            if self._pressed_handle == which:
                painter.setBrush(QColor(0, 100, 180))
            else:
                painter.setBrush(QColor(0, 120, 215))
            painter.drawRoundedRect(rect, 3, 3)

            # Handle grip lines
            painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
            cx = rect.center().x()
            cy = rect.center().y()
            for offset in [-2, 0, 2]:
                painter.drawLine(QPointF(cx + offset, cy - 4), QPointF(cx + offset, cy + 4))
            painter.setPen(Qt.PenStyle.NoPen)

    def mousePressEvent(self, event):
        pos = event.position()
        low_rect = self._handle_rect('low')
        high_rect = self._handle_rect('high')

        # Check which handle was clicked (prefer the one on top if overlapping)
        if high_rect.contains(pos):
            self._pressed_handle = 'high'
        elif low_rect.contains(pos):
            self._pressed_handle = 'low'
        else:
            # Click on track - move nearest handle
            x = pos.x()
            low_x = self._value_to_x(self._low)
            high_x = self._value_to_x(self._high)
            if abs(x - low_x) < abs(x - high_x):
                self._pressed_handle = 'low'
                self.setLow(self._x_to_value(x))
            else:
                self._pressed_handle = 'high'
                self.setHigh(self._x_to_value(x))

        self.update()

    def mouseMoveEvent(self, event):
        if self._pressed_handle:
            value = self._x_to_value(event.position().x())
            if self._pressed_handle == 'low':
                self.setLow(value)
            else:
                self.setHigh(value)

    def mouseReleaseEvent(self, event):
        self._pressed_handle = None
        self.update()

    def sizeHint(self):
        return QSize(200, 30)
