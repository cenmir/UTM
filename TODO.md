# DIC Strain Measurement Development TODO

This document outlines the tasks required to implement Digital Image Correlation (DIC) strain measurement for the UTM application (Phase 8).

---

## Overview

DIC uses camera-based tracking of markers on the specimen to measure strain optically, independent of the motor/encoder position. This provides more accurate strain measurement directly on the specimen surface.

**Current Status:** 0% complete (not started)

---

## Prerequisites

### Hardware Required
- [ ] Basler acA2440-35um USB 3.0 camera
- [ ] Azure-2514M lens (25mm, f/1.4, 5MP, 2/3" sensor)
- [ ] LED lighting for specimen illumination
- [ ] Specimen markers (2 high-contrast dots/stickers on specimen)

### Software Dependencies to Install
```bash
pip install pypylon          # Basler camera SDK (requires Pylon installation)
pip install opencv-python    # Image processing and blob detection
```

**Note:** pypylon requires the Basler Pylon Camera Software Suite to be installed first:
- Download from: https://www.baslerweb.com/en/downloads/software-downloads/

---

## Implementation Tasks

### Phase 8.1: Camera Setup & Basic Capture

- [ ] **Install Basler Pylon SDK** on development machine
- [ ] **Add dependencies to requirements.txt**
  - `pypylon>=1.9.0`
  - `opencv-python>=4.8.0`

- [ ] **Create `camera_manager.py`** with CameraManager class
  - [ ] Camera discovery and connection
  - [ ] Configuration settings:
    - ROI: [888, 300, 303, 1756]
    - Frame rate: 35 fps
    - Exposure: 2500 us
    - Gamma: 0.5
    - Pixel format: Mono8
  - [ ] Start/stop acquisition methods
  - [ ] Frame capture with 90 degree rotation
  - [ ] PyQt signals for frame_ready, error_occurred, connection_changed
  - [ ] Proper cleanup on disconnect

### Phase 8.2: UI Integration

- [ ] **Add Camera controls to Stress/Strain tab** (see APP_DESCRIPTION.qmd line 248)
  - [ ] "Start Camera" button
  - [ ] "Stop Camera" button
  - [ ] "Tare DIC" button (set initial gauge length)
  - [ ] L0 display label (initial distance in pixels -> mm)
  - [ ] Current DIC strain display label

- [ ] **Add Image display area** to Stress/Strain tab
  - [ ] QLabel or matplotlib canvas for camera feed
  - [ ] Overlay for blob markers and bounding boxes
  - [ ] Distance annotation between tracked points

- [ ] **Add DIC toggle switch** to Data Streams group (optional)
  - [ ] Enable/disable DIC strain recording

### Phase 8.3: Blob Detection (OpenCV)

- [ ] **Implement blob detection** in camera_manager.py
  ```python
  # MATLAB equivalent workflow:
  # 1. Binarize with global threshold (cv2.threshold with THRESH_OTSU)
  # 2. Invert binary image
  # 3. Find contours or use SimpleBlobDetector
  # 4. Filter by area: 100-1000 pixels
  # 5. Get centroids of exactly 2 blobs
  ```

- [ ] **Blob detection parameters** (matching MATLAB):
  - Minimum blob area: 100 px
  - Maximum blob area: 1000 px
  - Maximum blob count: 8 (but need exactly 2 for DIC)
  - Error handling when blob count != 2

- [ ] **Centroid extraction** from detected blobs
  - [ ] Return (x, y) coordinates of blob centers
  - [ ] Handle case when blobs not found (poor lighting, markers missing)

### Phase 8.4: Point Tracking & DIC Strain Calculation

- [ ] **Implement two-point tracking**
  - [ ] Track the two blob centroids frame-to-frame
  - [ ] Calculate horizontal distance between centroids
  - [ ] Store initial distance on "Tare DIC" button press

- [ ] **DIC Strain calculation**
  ```python
  # DIC Strain Formula:
  initial_distance = None  # Set on tare
  current_distance = abs(centroid2_x - centroid1_x)
  dic_strain = (current_distance - initial_distance) / initial_distance
  ```

- [ ] **Pixel to mm conversion** (optional, for L0 display)
  - [ ] Calibration factor: pixels per mm
  - [ ] Or use known specimen gauge length for reference

### Phase 8.5: Integration with Stress-Strain Plot

- [ ] **Add DIC strain as alternative strain source**
  - [ ] Toggle between motor-based strain and DIC strain
  - [ ] Or plot both on stress-strain curve (different colors)

- [ ] **Synchronize DIC data with force data**
  - [ ] Timestamp correlation between camera frames and load cell readings
  - [ ] Handle different sampling rates (camera 35 Hz, load cell 10 Hz)

- [ ] **Update data export** to include DIC strain column
  - [ ] Add `DIC_Strain` column to CSV export
  - [ ] Add camera settings to metadata header

### Phase 8.6: Testing & Validation

- [ ] **Unit tests for blob detection**
  - [ ] Test with sample images of specimen markers
  - [ ] Test edge cases: no blobs, too many blobs, merged blobs

- [ ] **Hardware integration test**
  - [ ] Verify camera connects and captures frames
  - [ ] Verify blob detection works with real specimen
  - [ ] Compare DIC strain vs motor-based strain

- [ ] **Performance testing**
  - [ ] Ensure 35 fps capture doesn't block GUI
  - [ ] Memory usage monitoring (frame buffer management)

---

## Code Architecture

### New Files to Create

```
Software/UTM_PyQt6/
├── camera_manager.py      # CameraManager class with pypylon
├── blob_detector.py       # OpenCV blob detection utilities (optional, can be in camera_manager)
```

### CameraManager Class Structure

```python
class CameraManager(QObject):
    """Manages Basler camera capture and blob detection for DIC"""

    # Signals
    frame_ready = pyqtSignal(np.ndarray)      # Emitted on new frame
    blobs_detected = pyqtSignal(list)          # List of (x, y) centroids
    dic_strain_updated = pyqtSignal(float)     # Current DIC strain value
    error_occurred = pyqtSignal(str)           # Error messages
    connection_changed = pyqtSignal(bool)      # Camera connected/disconnected

    # Configuration
    ROI = [888, 300, 303, 1756]
    FRAME_RATE = 35
    EXPOSURE_TIME = 2500
    GAMMA = 0.5

    # Methods
    def connect_camera(self) -> bool
    def disconnect_camera(self)
    def start_acquisition(self)
    def stop_acquisition(self)
    def capture_frame(self) -> np.ndarray
    def detect_blobs(self, frame) -> list
    def calculate_dic_strain(self, centroids) -> float
    def tare_dic(self)  # Set initial gauge length
```

---

## Camera Configuration Reference

From MATLAB TestingTracking.m:

| Parameter | Value | PyPylon Equivalent |
|-----------|-------|-------------------|
| ROI | [888, 300, 303, 1756] | `camera.OffsetX`, `OffsetY`, `Width`, `Height` |
| Frame Rate | 35 fps | `camera.AcquisitionFrameRate` |
| Exposure | 2500 us | `camera.ExposureTime` |
| Gamma | 0.5 | `camera.Gamma` |
| Pixel Format | Mono8 | `camera.PixelFormat` |
| Trigger | Manual/Continuous | `camera.TriggerMode` |

---

## References

- **MATLAB Reference Implementation:** `Software/data/TestingTracking.m`
- **Camera Settings Test:** `Software/data/TestingImageAquisition.m`
- **APP_DESCRIPTION.qmd:** Lines 398-424 (Camera/DIC Integration section)
- **pypylon Documentation:** https://github.com/basler/pypylon
- **OpenCV Blob Detection:** https://docs.opencv.org/4.x/d0/d7a/classcv_1_1SimpleBlobDetector.html

---

## Notes

1. **Two markers required:** The DIC implementation uses exactly 2 high-contrast markers on the specimen. If fewer or more blobs are detected, the system should show an error.

2. **Lighting is critical:** Poor lighting will cause blob detection to fail. Need consistent LED illumination.

3. **Frame rotation:** Camera captures landscape but specimen is vertical. Apply 90 degree rotation (`rot90` in MATLAB, `cv2.rotate` in OpenCV).

4. **Thread safety:** Camera capture should run in a separate thread to avoid blocking the GUI. Use Qt signals to communicate frame data.

5. **Memory management:** Don't store all frames - process and discard. Only keep the current frame for display.
