"""
Custom Widgets for UTM Application

Contains custom Qt widgets including toggle switches and gauges.
"""

# Source - https://stackoverflow.com/a/62364553
# Posted by eyllanesc, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-02, License - CC BY-SA 4.0
# Modified for PyQt6 compatibility

from PyQt6.QtCore import QObject, QSize, QPointF, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSlot, Qt
from PyQt6.QtGui import QPainter, QPalette, QLinearGradient, QGradient, QColor, QPen
from PyQt6.QtWidgets import QAbstractButton


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
