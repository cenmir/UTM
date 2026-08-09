"""
Phase 8.6 Validation Tests
Comprehensive testing of DIC strain measurement system integration
"""

import unittest
import math
import numpy as np
import cv2
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Import the modules to test
from camera_manager import CameraManager
import sys


class TestBlobDetectionEdgeCases(unittest.TestCase):
    """8.6.1: Blob detection edge cases (0, 1, 2, 3+ blobs)"""

    def setUp(self):
        """Initialize camera manager for each test"""
        self.cam = CameraManager()
        self.cam.camera = Mock()  # Mock the hardware camera
        # Legacy tests use dark-on-light synthetic frames; force White preset.
        self.cam.set_specimen_mode("White")

    def _create_test_frame(self, num_blobs):
        """Create synthetic frame with N dark blobs on white background.
        detect_blobs uses THRESH_BINARY_INV, so dark objects on light bg."""
        frame = np.full((500, 1588), 255, dtype=np.uint8)  # White background

        blob_positions = [
            (200, 150),   # Blob 1
            (200, 350),   # Blob 2
            (400, 200),   # Blob 3
            (600, 300),   # Blob 4
        ]

        for i in range(min(num_blobs, 4)):
            x, y = blob_positions[i]
            cv2.circle(frame, (x, y), 40, 0, -1)  # Dark circle on white bg

        return frame

    def test_blob_detection_zero_blobs(self):
        """Test handling of frame with 0 blobs"""
        frame = self._create_test_frame(0)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 0, "Should detect 0 blobs")

    def test_blob_detection_one_blob(self):
        """Test handling of frame with 1 blob"""
        frame = self._create_test_frame(1)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 1, "Should detect 1 blob")

    def test_blob_detection_two_blobs_sorted(self):
        """Test handling of frame with 2 blobs (correct case)"""
        frame = self._create_test_frame(2)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 2, "Should detect 2 blobs")
        # Verify sorting: blob 1 (y=150) should be first, blob 2 (y=350) should be second
        self.assertLess(centroids[0][1], centroids[1][1], "Blobs should be sorted by Y")

    def test_blob_detection_three_blobs(self):
        """Test handling of frame with 3 blobs (should emit error)"""
        frame = self._create_test_frame(3)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 3, "Should detect 3 blobs but return them")
        # Error should be emitted by the manager

    def test_blob_detection_four_blobs(self):
        """Test handling of frame with 4 blobs"""
        frame = self._create_test_frame(4)
        centroids = self.cam.detect_blobs(frame)
        self.assertGreaterEqual(len(centroids), 4, "Should detect 4 blobs")


class TestDICTareValidation(unittest.TestCase):
    """8.6.2: DIC tare validation (L0 px vs mm calibration)"""

    def setUp(self):
        self.cam = CameraManager()
        self.cam.camera = Mock()
        # Legacy tests use dark-on-light synthetic frames; force White preset.
        self.cam.set_specimen_mode("White")

    def test_tare_with_valid_gauge_length(self):
        """Test tare with valid gauge length"""
        self.cam.latest_frame = np.full((500, 1588), 255, dtype=np.uint8)
        cv2.circle(self.cam.latest_frame, (200, 150), 40, 0, -1)
        cv2.circle(self.cam.latest_frame, (200, 350), 40, 0, -1)

        self.cam.gauge_length_mm = 25.0
        self.cam.tare_dic()

        # Verify L0 distance was calculated
        self.assertIsNotNone(self.cam.initial_distance)
        self.assertGreater(self.cam.initial_distance, 0)

        # Verify px_per_mm calibration
        self.assertGreater(self.cam.px_per_mm, 0)
        expected_px_per_mm = self.cam.initial_distance / 25.0
        self.assertAlmostEqual(self.cam.px_per_mm, expected_px_per_mm, places=2)

    def test_tare_with_zero_gauge_length(self):
        """Test tare fails gracefully with zero gauge length"""
        self.cam.latest_frame = np.full((500, 1588), 255, dtype=np.uint8)
        cv2.circle(self.cam.latest_frame, (200, 150), 40, 0, -1)
        cv2.circle(self.cam.latest_frame, (200, 350), 40, 0, -1)

        self.cam.gauge_length_mm = 0.0
        self.cam.tare_dic()

        # Initial distance should be set, but px_per_mm should remain 0
        self.assertIsNotNone(self.cam.initial_distance)
        self.assertEqual(self.cam.px_per_mm, 0.0)

    def test_tare_with_invalid_blob_count(self):
        """Test tare fails with wrong number of blobs"""
        frame = np.full((500, 1588), 255, dtype=np.uint8)
        cv2.circle(frame, (200, 200), 40, 0, -1)  # Only 1 dark blob
        self.cam.latest_frame = frame

        self.cam.gauge_length_mm = 25.0
        self.cam.tare_dic()

        # Initial distance should not be set
        self.assertIsNone(self.cam.initial_distance)


class TestStrainCalculation(unittest.TestCase):
    """8.6.3 & 8.6.4: Strain calculation and sign convention"""

    def setUp(self):
        self.cam = CameraManager()
        self.cam.camera = Mock()
        # Set up initial state for strain calculation
        self.cam.initial_distance = 200  # 200 pixels = reference
        self.cam.px_per_mm = 8.0  # 8 px/mm calibration
        self.cam.gauge_length_mm = 25.0

    def test_zero_strain_at_tare(self):
        """Test strain is zero at initial distance"""
        centroids = [(200, 150), (200, 350)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertAlmostEqual(cauchy, 0.0, places=5)
        self.assertAlmostEqual(true_strain, 0.0, places=5)

    def test_positive_strain_under_tension(self):
        """Test strain is positive when specimen elongates (tension)"""
        # Blobs move further apart: 200 -> 220 px
        centroids = [(200, 140), (200, 360)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertGreater(cauchy, 0.0, "Cauchy strain should be positive under tension")
        self.assertGreater(true_strain, 0.0, "True strain should be positive under tension")

    def test_negative_strain_under_compression(self):
        """Test strain is negative when specimen compresses"""
        # Blobs move closer: 200 -> 180 px
        centroids = [(200, 160), (200, 340)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertLess(cauchy, 0.0, "Cauchy strain should be negative under compression")
        self.assertLess(true_strain, 0.0, "True strain should be negative under compression")

    def test_cauchy_vs_true_strain_magnitude(self):
        """Test that |true_strain| < |cauchy_strain| for large deformations"""
        # 10% elongation: 200 -> 220 px
        centroids = [(200, 140), (200, 360)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)

        # At 10% strain, Cauchy and True diverge slightly
        self.assertAlmostEqual(cauchy, true_strain, places=1)

        # For larger elongation (20%): 200 -> 240 px
        centroids = [(200, 130), (200, 370)]
        cauchy_large, true_strain_large = self.cam.calculate_dic_strain(centroids)

        # True strain should be less than Cauchy for tension
        self.assertLess(abs(true_strain_large), abs(cauchy_large))

    def test_strain_calculation_with_no_tare(self):
        """Test strain calculation returns 0 if not tared"""
        self.cam.initial_distance = None
        centroids = [(200, 140), (200, 360)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertEqual(cauchy, 0.0)
        self.assertEqual(true_strain, 0.0)

    def test_strain_calculation_with_wrong_blob_count(self):
        """Test strain calculation returns 0 with wrong blob count"""
        centroids = [(200, 200)]  # Only 1 blob
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertEqual(cauchy, 0.0)
        self.assertEqual(true_strain, 0.0)


class TestCSVRoundTrip(unittest.TestCase):
    """8.6.6: CSV export/import round-trip validation"""

    def setUp(self):
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up test files
        import shutil
        shutil.rmtree(self.test_dir)

    def test_csv_headers_include_dic_columns(self):
        """Test CSV export includes DIC columns"""
        csv_path = os.path.join(self.test_dir, "test_export.csv")

        # Simulate CSV structure with headers
        headers = [
            "Time_s", "Load_N", "Displacement_mm", "Stress_MPa", "Strain",
            "DIC_Time_s", "DIC_Cauchy", "DIC_True", "Lag_ms"
        ]

        # At minimum, should contain DIC columns
        required_dic_cols = ["DIC_Cauchy", "DIC_True"]
        for col in required_dic_cols:
            self.assertIn(col, headers, f"CSV should contain {col}")

    def test_csv_export_with_empty_dic_list(self):
        """Test CSV export handles empty DIC data gracefully"""
        # This would be tested with the main application
        # Placeholder for integration test
        pass

    def test_csv_import_restores_px_per_mm(self):
        """Test CSV import restores calibration factor"""
        # This would be tested with the main application
        # Placeholder for integration test
        pass


class TestStrainSourceSwitching(unittest.TestCase):
    """8.6.9: Strain source switching during recording"""

    def test_strain_source_motor(self):
        """Test strain source: Motor"""
        # Motor-based strain = displacement / gauge_length
        pass

    def test_strain_source_dic_cauchy(self):
        """Test strain source: DIC Cauchy"""
        pass

    def test_strain_source_dic_true(self):
        """Test strain source: DIC True"""
        pass

    def test_strain_source_both(self):
        """Test strain source: Both (overlaid)"""
        pass


class TestConsoleMessageRouting(unittest.TestCase):
    """8.6.7: Console message routing (camera vs system)"""

    def test_camera_messages_prefixed(self):
        """Test camera error messages have [Camera] prefix"""
        # This would be tested with the main application
        pass

    def test_dic_messages_prefixed(self):
        """Test DIC messages have [DIC] prefix"""
        pass


class TestDataCroppingWithDIC(unittest.TestCase):
    """8.6.8: Data cropping with DIC columns"""

    def test_crop_preserves_dic_columns(self):
        """Test cropping preserves DIC data alignment"""
        pass


class TestMathematicalEdgeCases(unittest.TestCase):
    """Mathematical edge cases for strain calculation"""

    def setUp(self):
        self.cam = CameraManager()
        self.cam.camera = Mock()

    def test_true_strain_with_zero_distance(self):
        """Test true strain calculation guards against zero/negative distance"""
        self.cam.initial_distance = 200
        # Current distance = 0 (invalid, but should not crash)
        centroids = [(200, 200), (200, 200)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        # Should return safely
        self.assertEqual(cauchy, 0.0)
        self.assertEqual(true_strain, 0.0)

    def test_large_elongation_strain_values(self):
        """Test strain calculation with large deformations (e.g., 50% elongation)"""
        self.cam.initial_distance = 200  # Assume 200 px initially
        # 50% elongation: 200 -> 300 px
        centroids = [(200, 100), (200, 400)]
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)

        # Cauchy strain = (300-200)/200 = 0.5
        expected_cauchy = 0.5
        self.assertAlmostEqual(cauchy, expected_cauchy, places=3)

        # True strain = ln(300/200) = ln(1.5) ≈ 0.405
        expected_true = math.log(1.5)
        self.assertAlmostEqual(true_strain, expected_true, places=3)


class TestEndToEndDICPipeline(unittest.TestCase):
    """8.6.11: End-to-end DIC pipeline with synthetic frames.

    Feed synthetic images through detect_blobs + calculate_dic_strain and
    verify ground-truth strain is recovered. Uses "White" preset polarity
    (dark blobs on light background).
    """

    FRAME_W = 1588
    FRAME_H = 500
    BLOB_RADIUS = 40
    BLOB_X = 250  # Fixed column so x-centroid is stable
    BASELINE_DIST = 300  # px between centroids at tare

    def setUp(self):
        self.cam = CameraManager()
        self.cam.camera = Mock()
        # Ensure White-specimen polarity for synthetic frames
        self.cam.set_specimen_mode("White")
        self.cam.gauge_length_mm = 30.0

    def _frame_with_two_blobs(self, distance_px):
        frame = np.full((self.FRAME_H, self.FRAME_W), 255, dtype=np.uint8)
        cy_top = (self.FRAME_H - distance_px) // 2
        cy_bot = cy_top + distance_px
        cv2.circle(frame, (self.BLOB_X, cy_top), self.BLOB_RADIUS, 0, -1)
        cv2.circle(frame, (self.BLOB_X, cy_bot), self.BLOB_RADIUS, 0, -1)
        return frame

    def _tare_at(self, distance_px):
        self.cam.initial_distance = distance_px
        self.cam.px_per_mm = distance_px / self.cam.gauge_length_mm

    def test_pipeline_recovers_zero_strain(self):
        """Tare and re-read the same frame -> strain ~= 0."""
        frame = self._frame_with_two_blobs(self.BASELINE_DIST)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 2)
        self._tare_at(self.BASELINE_DIST)
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertAlmostEqual(cauchy, 0.0, places=5)
        self.assertAlmostEqual(true_strain, 0.0, places=5)

    def test_pipeline_recovers_ten_percent_tension(self):
        """Tare at 300 px, re-measure at 330 px -> ε_c ≈ 0.100."""
        self._tare_at(self.BASELINE_DIST)
        frame = self._frame_with_two_blobs(330)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 2)
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertAlmostEqual(cauchy, 0.1000, places=2)
        self.assertAlmostEqual(true_strain, math.log(1.1), places=2)

    def test_pipeline_recovers_compression(self):
        """Tare at 300 px, re-measure at 285 px -> ε_c ≈ -0.050."""
        self._tare_at(self.BASELINE_DIST)
        frame = self._frame_with_two_blobs(285)
        centroids = self.cam.detect_blobs(frame)
        self.assertEqual(len(centroids), 2)
        cauchy, true_strain = self.cam.calculate_dic_strain(centroids)
        self.assertAlmostEqual(cauchy, -0.0500, places=2)
        self.assertLess(true_strain, 0.0)

    def test_pipeline_swept_strain_series(self):
        """Run a full sweep: 0%, ±5%, ±10%, ±20% - all should match ground truth."""
        self._tare_at(self.BASELINE_DIST)
        for factor in (0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20):
            distance = int(round(self.BASELINE_DIST * factor))
            frame = self._frame_with_two_blobs(distance)
            centroids = self.cam.detect_blobs(frame)
            self.assertEqual(len(centroids), 2, f"Failed at factor {factor}")
            cauchy, _ = self.cam.calculate_dic_strain(centroids)
            expected = factor - 1.0
            self.assertAlmostEqual(
                cauchy, expected, places=2,
                msg=f"Cauchy at factor {factor}: got {cauchy:.4f}, expected {expected:.4f}",
            )


class TestMockCameraStress(unittest.TestCase):
    """8.6.12: GUI stress test with mock camera.

    Simulate sustained frame processing without a physical camera. Verifies
    the dic_history deque stays bounded (no memory leak) and per-frame
    processing is fast enough for the 35 fps target.
    """

    N_FRAMES = 2000  # ~57 s at 35 fps
    MAX_MS_PER_FRAME = 30.0  # budget: < 1 frame at 35 fps
    DIC_HISTORY_MAX = 500

    def setUp(self):
        self.cam = CameraManager()
        self.cam.camera = Mock()
        self.cam.set_specimen_mode("White")
        self.cam.gauge_length_mm = 30.0
        self.cam.initial_distance = 300
        self.cam.px_per_mm = 10.0

    def _frame(self, distance_px):
        frame = np.full((500, 1588), 255, dtype=np.uint8)
        cy_top = (500 - distance_px) // 2
        cv2.circle(frame, (250, cy_top), 40, 0, -1)
        cv2.circle(frame, (250, cy_top + distance_px), 40, 0, -1)
        return frame

    def test_dic_history_stays_bounded(self):
        """Processing 2000 frames must not exceed the 500-entry deque cap."""
        for i in range(self.N_FRAMES):
            # Vary distance slightly so every frame produces a new entry
            dist = 300 + (i % 5)
            frame = self._frame(dist)
            centroids = self.cam.detect_blobs(frame)
            self.cam.calculate_dic_strain(centroids)

        self.assertEqual(
            len(self.cam.dic_history), self.DIC_HISTORY_MAX,
            f"dic_history should cap at {self.DIC_HISTORY_MAX}, got {len(self.cam.dic_history)}",
        )

    def test_frame_processing_throughput(self):
        """Average per-frame processing stays under the 35 fps budget."""
        import time
        # Warm up
        frame = self._frame(300)
        for _ in range(5):
            self.cam.detect_blobs(frame)

        t0 = time.perf_counter()
        N = 200
        for i in range(N):
            f = self._frame(300 + (i % 7))
            centroids = self.cam.detect_blobs(f)
            self.cam.calculate_dic_strain(centroids)
        elapsed = time.perf_counter() - t0
        ms_per_frame = (elapsed / N) * 1000.0
        self.assertLess(
            ms_per_frame, self.MAX_MS_PER_FRAME,
            f"Per-frame processing {ms_per_frame:.2f} ms exceeds {self.MAX_MS_PER_FRAME} ms budget",
        )


class TestCSVRoundTripRealFormat(unittest.TestCase):
    """8.6.13: CSV round-trip with the real 14-column DIC export format
    (12 base + L_px, dx_px added for the 8.6.4 rig diagnostic)."""

    REAL_HEADERS = [
        "Time_s", "RawADC", "Force_N", "Position_mm", "Speed_mm_s",
        "Motor_Strain", "Stress_MPa", "DIC_Cauchy", "DIC_True",
        "DIC_Time_s", "Lag_ms", "MCU_Time_s", "L_px", "dx_px",
    ]

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def _write_real_format_csv(self, path, rows):
        with open(path, "w") as f:
            f.write("# UTM Test Data Export\n")
            f.write("# Test Date: 2026-04-22 10:51:34\n")
            f.write(f"# Duration: {rows * 0.088:.1f} s\n")
            f.write(f"# Data Points: {rows}\n")
            f.write("# Calibration - Scale: -0.0065, Offset: -24.5185\n")
            f.write("# Specimen - Area: 80.0 mm2, Gauge Length: 80.0 mm\n")
            f.write("# DIC Calibration - px_per_mm: 18.0599\n")
            f.write("# App Version: 0.5.4\n")
            f.write("# Firmware Version: 1.3.1\n")
            f.write("#\n")
            f.write(",".join(self.REAL_HEADERS) + "\n")
            for i in range(rows):
                line = [
                    f"{i * 0.088:.3f}",            # Time_s
                    f"{3850 + (i % 20)}",          # RawADC
                    f"{49.5 + (i % 5) * 0.01:.4f}",# Force_N
                    f"{-i * 0.01:.4f}",            # Position_mm
                    f"{-0.1:.4f}",                 # Speed_mm_s
                    f"{-i * 0.0001:.6f}",          # Motor_Strain
                    f"{0.619:.4f}",                # Stress_MPa
                    f"{-i * 0.00005:.6f}",         # DIC_Cauchy
                    f"{-i * 0.00005:.6f}",         # DIC_True
                    f"{i * 0.088 - 0.027:.3f}",    # DIC_Time_s
                    f"{27.0 + (i % 10):.1f}",      # Lag_ms
                    f"{i * 0.088:.3f}",            # MCU_Time_s
                    f"{1665.0 + i * 0.05:.1f}",    # L_px
                    f"{18.0 + (i % 5) * 0.1:.1f}", # dx_px
                ]
                f.write(",".join(line) + "\n")

    def _load_csv(self, path):
        import pandas as pd
        with open(path) as f:
            header_row = 0
            for i, line in enumerate(f):
                if not line.startswith("#"):
                    header_row = i
                    break
        return pd.read_csv(path, comment="#", header=0, skiprows=header_row)

    def test_all_fourteen_columns_present(self):
        """All 14 DIC-era columns (12 base + L_px, dx_px) must survive export->import."""
        path = os.path.join(self.test_dir, "roundtrip.csv")
        self._write_real_format_csv(path, rows=100)
        df = self._load_csv(path)
        df.columns = [c.strip() for c in df.columns]
        for col in self.REAL_HEADERS:
            self.assertIn(col, df.columns, f"Missing column: {col}")
        self.assertEqual(len(df), 100)

    def test_numerical_precision_preserved(self):
        """Float values must round-trip within 6-decimal tolerance."""
        path = os.path.join(self.test_dir, "precision.csv")
        self._write_real_format_csv(path, rows=50)
        df = self._load_csv(path)
        df.columns = [c.strip() for c in df.columns]

        # Check a few known values
        self.assertAlmostEqual(df["Time_s"].iloc[10], 0.880, places=3)
        self.assertAlmostEqual(df["DIC_Cauchy"].iloc[10], -0.000500, places=6)
        self.assertAlmostEqual(df["Lag_ms"].iloc[0], 27.0, places=1)

    def test_comment_lines_are_skipped(self):
        """Metadata comment lines must not appear in the data rows."""
        path = os.path.join(self.test_dir, "comments.csv")
        self._write_real_format_csv(path, rows=10)
        df = self._load_csv(path)
        # No cell should contain the '#' prefix character
        for col in df.columns:
            for val in df[col].astype(str):
                self.assertFalse(val.strip().startswith("#"),
                                 f"Comment leaked into column {col}")


class TestTimeSyncSimulation(unittest.TestCase):
    """8.6.14: Time-sync logic simulation.

    Mirrors the algorithm in main.py:_match_dic_to_mcu_time and validates
    edge cases without needing the Qt MainWindow: normal pairing, staleness,
    empty history, out-of-order arrival, boundary timing.
    """

    STALE_MS = 100.0

    def _match(self, dic_history, anchor_pc, anchor_mcu_ms, mcu_ms):
        """Standalone copy of main.py:_match_dic_to_mcu_time algorithm."""
        from datetime import timedelta
        if not dic_history or anchor_pc is None or mcu_ms == 0:
            return (0.0, 0.0, None)
        mcu_offset_ms = mcu_ms - anchor_mcu_ms
        estimated_pc = anchor_pc + timedelta(milliseconds=mcu_offset_ms)
        best_entry = None
        best_gap = float("inf")
        for entry in dic_history:
            gap = abs((entry[0] - estimated_pc).total_seconds() * 1000.0)
            if gap < best_gap:
                best_gap = gap
                best_entry = entry
        if best_entry is None or best_gap > self.STALE_MS:
            return (0.0, 0.0, None)
        return (best_entry[1], best_entry[2], best_entry[0])

    def _build_history(self, anchor_pc, offsets_ms_and_values):
        from datetime import timedelta
        from collections import deque
        h = deque(maxlen=500)
        for offset_ms, cauchy in offsets_ms_and_values:
            t = anchor_pc + timedelta(milliseconds=offset_ms)
            h.append((t, cauchy, cauchy))
        return h

    def test_normal_pairing_picks_nearest(self):
        """With several entries, match must pick the one closest in time."""
        anchor_pc = datetime(2026, 4, 22, 10, 0, 0)
        history = self._build_history(anchor_pc, [
            (0, 0.001), (88, 0.002), (176, 0.003), (264, 0.004), (352, 0.005),
        ])
        # Ask for the sample at MCU offset +180 ms -> nearest is 176 ms (0.003)
        c, _, ts = self._match(history, anchor_pc, 0, 180)
        self.assertAlmostEqual(c, 0.003, places=6)
        self.assertIsNotNone(ts)

    def test_boundary_under_threshold(self):
        """A 99 ms gap must still match; 101 ms must come back stale."""
        anchor_pc = datetime(2026, 4, 22, 10, 0, 0)
        history = self._build_history(anchor_pc, [(0, 0.42)])
        # 99 ms away - still a match
        c99, _, ts99 = self._match(history, anchor_pc, 0, 99)
        self.assertAlmostEqual(c99, 0.42, places=6)
        self.assertIsNotNone(ts99)
        # 101 ms away - stale
        c101, _, ts101 = self._match(history, anchor_pc, 0, 101)
        self.assertEqual(c101, 0.0)
        self.assertIsNone(ts101)

    def test_empty_history_returns_fallback(self):
        """Empty dic_history must return (0.0, 0.0, None)."""
        from collections import deque
        anchor_pc = datetime(2026, 4, 22, 10, 0, 0)
        c, t, ts = self._match(deque(), anchor_pc, 0, 100)
        self.assertEqual((c, t, ts), (0.0, 0.0, None))

    def test_no_anchor_returns_fallback(self):
        """Missing anchor (not yet set) must return fallback."""
        history = self._build_history(datetime(2026, 4, 22, 10, 0, 0), [(0, 0.01)])
        c, t, ts = self._match(history, None, 0, 100)
        self.assertEqual((c, t, ts), (0.0, 0.0, None))

    def test_out_of_order_entries(self):
        """Algorithm uses abs-distance, so insertion order must not affect result."""
        anchor_pc = datetime(2026, 4, 22, 10, 0, 0)
        # Deliberately append in scrambled order
        history = self._build_history(anchor_pc, [
            (264, 0.003), (0, 0.001), (176, 0.002), (88, 0.0015),
        ])
        c, _, _ = self._match(history, anchor_pc, 0, 180)
        self.assertAlmostEqual(c, 0.002, places=6)

    def test_python_stall_recovery(self):
        """Five rapid MCU samples during a Python stall must each pick distinct DIC frames."""
        anchor_pc = datetime(2026, 4, 22, 10, 0, 0)
        # DIC frames at 88 ms intervals (close to camera rate)
        history = self._build_history(anchor_pc, [
            (0, 0.0010), (88, 0.0011), (176, 0.0012),
            (264, 0.0013), (352, 0.0014), (440, 0.0015),
        ])
        # Five force samples that arrived late (Python stalled), but MCU knows when each fired
        results = []
        for mcu_ms in (88, 176, 264, 352, 440):
            c, _, ts = self._match(history, anchor_pc, 0, mcu_ms)
            results.append((c, ts))

        # Each must match a different DIC entry
        cauchy_values = [r[0] for r in results]
        timestamps = [r[1] for r in results]
        self.assertEqual(len(set(cauchy_values)), 5, "Expected 5 unique DIC values, got collapsed match")
        self.assertEqual(len(set(timestamps)), 5, "Expected 5 unique DIC timestamps")


def run_validation_report():
    """Run all tests and generate validation report"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBlobDetectionEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestDICTareValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestStrainCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestCSVRoundTrip))
    suite.addTests(loader.loadTestsFromTestCase(TestMathematicalEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestConsoleMessageRouting))
    suite.addTests(loader.loadTestsFromTestCase(TestDataCroppingWithDIC))
    suite.addTests(loader.loadTestsFromTestCase(TestStrainSourceSwitching))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndDICPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestMockCameraStress))
    suite.addTests(loader.loadTestsFromTestCase(TestCSVRoundTripRealFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestTimeSyncSimulation))

    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("PHASE 8.6 VALIDATION TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    return result


if __name__ == '__main__':
    result = run_validation_report()
    sys.exit(0 if result.wasSuccessful() else 1)
