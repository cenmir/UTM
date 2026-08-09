from pypylon import pylon
from camera_manager import CameraManager
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import cv2
import sys

app = QApplication(sys.argv)
cm = CameraManager()

# Connect signal handlers

# def on_frame_ready(frame):
#     print(f"Frame received — shape: {frame.shape}")

frame_count = [0]

def on_frame_ready(frame):
    frame_count[0] += 1
    if frame_count[0] == 10:
        cv2.imwrite("live_frame.png", frame)
        print("Saved live_frame.png")
    print(f"Frame received — shape: {frame.shape}")

def on_blobs_detected(centroids):
    print(f"Blobs detected: {centroids}")

def on_strain_updated(strain):
    print(f"DIC Strain: {strain:.6f}")

def on_error(msg):
    print(f"ERROR: {msg}")

def on_connection_changed(connected):
    print(f"Camera connected: {connected}")

cm.frame_ready.connect(on_frame_ready)
cm.blobs_detected.connect(on_blobs_detected)
cm.dic_strain_updated.connect(on_strain_updated)
cm.error_occurred.connect(on_error)
cm.connection_changed.connect(on_connection_changed)

# Step 1: Connect
if not cm.connect_camera():
    print("Failed to connect — exiting")
    sys.exit(1)

# Step 2: Start acquisition
cm.start_acquisition()

# Step 3: Tare after 1 second
def do_tare():
    print("\n--- Taring DIC ---")
    cm.tare_dic()
    if cm.initial_distance:
        print(f"Initial distance: {cm.initial_distance:.1f} px")
    else:
        print("Tare failed - check blob detection")

# Step 4: Stop after 5 seconds
def do_stop():
    print("\n--- Stopping ---")
    cm.stop_acquisition()
    cm.disconnect_camera()
    app.quit()

tare_timer = QTimer()
tare_timer.setSingleShot(True)
tare_timer.timeout.connect(do_tare)
tare_timer.start(1000)

stop_timer = QTimer()
stop_timer.setSingleShot(True)
stop_timer.timeout.connect(do_stop)
stop_timer.start(5000)

sys.exit(app.exec())