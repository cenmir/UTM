import cv2
import numpy as np

img = cv2.imread("Software/UTM_PyQt6/output/diagnostics/test_roi.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

print(f"Image shape: {gray.shape}")
print(f"Min pixel value: {gray.min()}")
print(f"Max pixel value: {gray.max()}")
print(f"Mean pixel value: {gray.mean():.1f}")

# Save binary at several threshold values so we can compare
for thresh in [40, 60, 80, 100, 120, 150]:
    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite(f"binary_{thresh}.png", binary)
    print(f"Saved binary_{thresh}.png")