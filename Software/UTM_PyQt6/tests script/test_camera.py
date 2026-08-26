# Run from the APP directory (Software/UTM_PyQt6), which is also where this script's data and
# output paths are resolved from:  python tests/test_camera.py
# The app modules live one level up, so put that on the path before importing them.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from pypylon import pylon
from camera_manager import CameraManager
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
cm = CameraManager()
result = cm.connect_camera()
print("Connected:", result)
cm.disconnect_camera()