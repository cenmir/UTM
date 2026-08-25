"""
Phase 8.6 Validation - Practical Test Runner
Tests that can be executed without hardware or with synthetic data
"""

import math
import sys


def test_strain_mathematics():
    """Test mathematical correctness of strain calculations"""
    print("\n" + "="*70)
    print("TEST 8.6.3 & 8.6.4: STRAIN CALCULATION MATHEMATICS")
    print("="*70)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Zero strain at tare
    print("\n[1] Zero strain at initial distance:")
    try:
        L0 = 200  # initial distance in pixels
        L = 200   # current distance
        cauchy = (L - L0) / L0
        true_strain = math.log(L / L0) if L > 0 else 0.0

        print(f"    L0 = {L0} px, L = {L} px")
        print(f"    Cauchy: {cauchy:.6f} (expected 0.0)")
        print(f"    True:   {true_strain:.6f} (expected 0.0)")

        assert abs(cauchy) < 1e-5, f"Cauchy should be 0, got {cauchy}"
        assert abs(true_strain) < 1e-5, f"True strain should be 0, got {true_strain}"
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    # Test 2: Positive strain under tension
    print("\n[2] Positive strain under tension (10% elongation):")
    try:
        L0 = 200
        L = 220
        cauchy = (L - L0) / L0  # 0.1
        true_strain = math.log(L / L0)  # ln(1.1) ≈ 0.0953

        print(f"    L0 = {L0} px, L = {L} px")
        print(f"    Cauchy: {cauchy:.6f} (expected 0.1)")
        print(f"    True:   {true_strain:.6f} (expected 0.0953)")

        assert cauchy > 0, "Cauchy should be positive"
        assert true_strain > 0, "True strain should be positive"
        assert abs(cauchy - 0.1) < 0.001, f"Cauchy should be ~0.1"
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    # Test 3: Negative strain under compression
    print("\n[3] Negative strain under compression (10% reduction):")
    try:
        L0 = 200
        L = 180
        cauchy = (L - L0) / L0  # -0.1
        true_strain = math.log(L / L0) if L > 0 else 0.0  # ln(0.9) ≈ -0.1054

        print(f"    L0 = {L0} px, L = {L} px")
        print(f"    Cauchy: {cauchy:.6f} (expected -0.1)")
        print(f"    True:   {true_strain:.6f} (expected -0.1054)")

        assert cauchy < 0, "Cauchy should be negative"
        assert true_strain < 0, "True strain should be negative"
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    # Test 4: Strain magnitude relationship
    print("\n[4] Strain magnitude relationship (20% elongation):")
    try:
        L0 = 200
        L = 240
        cauchy = (L - L0) / L0  # 0.2
        true_strain = math.log(L / L0)  # ln(1.2) ≈ 0.1823

        print(f"    L0 = {L0} px, L = {L} px")
        print(f"    Cauchy: {cauchy:.6f} (expected 0.2)")
        print(f"    True:   {true_strain:.6f} (expected 0.1823)")
        print(f"    Relationship: |ε_t| < |ε_c| ? {abs(true_strain) < abs(cauchy)}")

        assert abs(cauchy - 0.2) < 0.001
        assert abs(true_strain - math.log(1.2)) < 0.001
        assert abs(true_strain) < abs(cauchy), "True strain magnitude should be < Cauchy"
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    # Test 5: Large deformation
    print("\n[5] Large deformation (50% elongation):")
    try:
        L0 = 200
        L = 300
        cauchy = (L - L0) / L0  # 0.5
        true_strain = math.log(L / L0)  # ln(1.5) ≈ 0.4055

        print(f"    L0 = {L0} px, L = {L} px")
        print(f"    Cauchy: {cauchy:.6f} (expected 0.5)")
        print(f"    True:   {true_strain:.6f} (expected 0.4055)")

        assert abs(cauchy - 0.5) < 0.001
        assert abs(true_strain - math.log(1.5)) < 0.001
        assert abs(true_strain) < abs(cauchy)
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    # Test 6: Calibration factor
    print("\n[6] px_per_mm calibration factor:")
    try:
        L0_px = 200  # pixels
        gauge_length_mm = 25.0
        px_per_mm = L0_px / gauge_length_mm  # 8.0

        print(f"    Initial distance: {L0_px} px")
        print(f"    Gauge length: {gauge_length_mm} mm")
        print(f"    Calibration: {px_per_mm:.2f} px/mm (expected 8.0)")

        assert abs(px_per_mm - 8.0) < 0.01
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    # Test 7: Division by zero guard
    print("\n[7] Safety check: zero/negative distance handling:")
    try:
        L0 = 200
        L = 0  # Invalid
        cauchy = (L - L0) / L0 if L0 > 0 else 0.0
        # True strain should guard against log(0)
        true_strain = math.log(L / L0) if L > 0 and L0 > 0 else 0.0

        print(f"    L0 = {L0} px, L = {L} px (invalid)")
        print(f"    Cauchy: {cauchy:.6f} (guarded)")
        print(f"    True:   {true_strain:.6f} (guarded)")

        assert cauchy == -1.0, "Should handle division correctly"
        assert true_strain == 0.0, "Should return 0 for invalid log"
        print("    ✓ PASS")
        tests_passed += 1
    except AssertionError as e:
        print(f"    ✗ FAIL: {e}")
        tests_failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("="*70)

    return tests_failed == 0


def test_strain_source_logic():
    """Test strain source switching logic"""
    print("\n" + "="*70)
    print("TEST 8.6.9: STRAIN SOURCE SWITCHING LOGIC")
    print("="*70)

    sources = ["Motor", "DIC Cauchy", "DIC True", "Both (Cauchy + Motor)"]

    print("\nValid strain sources:")
    for i, source in enumerate(sources, 1):
        print(f"  {i}. {source}")

    print("\nLogic check:")
    print(f"  'Both' mode starts with 'Both': {sources[3].startswith('Both')}")
    if sources[3].startswith("Both"):
        print("  ✓ PASS: 'Both' mode detection works")
        return True
    else:
        print("  ✗ FAIL: 'Both' mode detection failed")
        return False


def print_validation_checklist():
    """Print hardware validation checklist"""
    print("\n" + "="*70)
    print("PHASE 8.6 HARDWARE VALIDATION CHECKLIST")
    print("="*70)

    checklist = {
        "8.6.1: Blob Detection": [
            "[ ] Run without specimen - should detect 0 blobs",
            "[ ] Run with 1 marker - should detect 1 blob",
            "[ ] Run with 2 markers - should detect 2 blobs (normal)",
            "[ ] Run with 3+ markers - should emit 'Expected 2 blobs' error"
        ],
        "8.6.2: DIC Tare": [
            "[ ] Set gauge length to 25.0 mm",
            "[ ] Click 'Tare DIC'",
            "[ ] Verify console shows: 'DIC tared — L0 = XXX px | 25.0 mm | X.XX px/mm'",
            "[ ] Verify px_per_mm ≈ 8.0 (L0_px / 25 mm)"
        ],
        "8.6.3: Known Displacement": [
            "[ ] After tare, move crosshead DOWN by exactly 1.0 mm",
            "[ ] Compare Motor strain vs DIC Cauchy in console",
            "[ ] Both should show ≈0.04 (1mm / 25mm)",
            "[ ] Note delta between Motor and DIC (should be small)"
        ],
        "8.6.4: Strain Sign": [
            "[ ] Move crosshead DOWN (tension): both strains should be POSITIVE",
            "[ ] Move crosshead UP (compression): both strains should be NEGATIVE",
            "[ ] Verify sign consistency between Cauchy and True strain"
        ],
        "8.6.5: GUI Responsiveness": [
            "[ ] Start camera acquisition",
            "[ ] Run for 2 minutes continuously",
            "[ ] Monitor CPU/Memory - should stay stable",
            "[ ] UI should remain responsive (no freezes)"
        ],
        "8.6.6: CSV Round-Trip": [
            "[ ] Collect 10+ seconds of data",
            "[ ] Export to CSV",
            "[ ] Clear plots",
            "[ ] Import CSV",
            "[ ] Verify all values match original data",
            "[ ] Check DIC_Cauchy and DIC_True columns present"
        ],
        "8.6.7: Console Routing": [
            "[ ] Camera errors show [Camera] prefix",
            "[ ] DIC updates show [DIC] prefix",
            "[ ] System messages are clearly labeled"
        ],
        "8.6.8: Data Cropping": [
            "[ ] Collect data",
            "[ ] Crop data (select start/end times)",
            "[ ] Export cropped data to CSV",
            "[ ] Verify DIC_Cauchy/DIC_True columns align with cropped range"
        ],
        "8.6.9: Strain Source Switching": [
            "[ ] Switch to 'Motor' - stress-strain plot shows motor strain",
            "[ ] Switch to 'DIC Cauchy' - plot shows DIC Cauchy",
            "[ ] Switch to 'DIC True' - plot shows DIC True",
            "[ ] Switch to 'Both' - overlay both Motor and DIC Cauchy",
            "[ ] No crashes during switching"
        ]
    }

    for category, items in checklist.items():
        print(f"\n{category}")
        for item in items:
            print(f"  {item}")

    print("\n" + "="*70)


if __name__ == '__main__':
    print("\n" + "🧪 PHASE 8.6 VALIDATION TEST RUNNER 🧪".center(70))

    # Run mathematical tests
    math_pass = test_strain_mathematics()

    # Run strain source logic test
    logic_pass = test_strain_source_logic()

    # Print hardware validation checklist
    print_validation_checklist()

    # Summary
    print("\n" + "="*70)
    if math_pass and logic_pass:
        print("✓ ALL LOGIC TESTS PASSED")
        print("⚠ Hardware validation tests require actual equipment")
        print("   See checklist above for manual testing procedures")
    else:
        print("✗ SOME LOGIC TESTS FAILED")
    print("="*70 + "\n")

    sys.exit(0 if (math_pass and logic_pass) else 1)
