from pypylon import pylon
from camera_manager import CameraManager
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
cm = CameraManager()
result = cm.connect_camera()
print("Connected:", result)
cm.disconnect_camera()