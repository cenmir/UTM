import cv2
import numpy as np

img = cv2.imread("test_roi.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

THRESHOLD = 150

_, binary = cv2.threshold(gray, THRESHOLD, 255, cv2.THRESH_BINARY_INV)
cv2.imwrite("test_binary.png", binary)

contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

MIN_AREA = 2000
MAX_AREA = 200000
MIN_CIRCULARITY = 0.5  # 1.0 = perfect circle, sliver will be ~0.1

valid = []
for cnt in contours:
    area = cv2.contourArea(cnt)
    if MIN_AREA < area < MAX_AREA:
        perimeter = cv2.arcLength(cnt, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter ** 2)
            if circularity > MIN_CIRCULARITY:
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cx = M["m10"] / M["m00"]
                    cy = M["m01"] / M["m00"]
                    valid.append((cx, cy, area, circularity))

print(f"Blobs found: {len(valid)}")
for i, (x, y, area, circ) in enumerate(valid):
    print(f"  Blob {i+1}: x={x:.1f}, y={y:.1f}, area={area:.0f}, circularity={circ:.2f}")

output = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
for (x, y, area, circ) in valid:
    cv2.circle(output, (int(x), int(y)), 40, (0, 0, 255), 3)
    cv2.circle(output, (int(x), int(y)), 5, (0, 255, 0), -1)

if len(valid) == 2:
    p1 = (int(valid[0][0]), int(valid[0][1]))
    p2 = (int(valid[1][0]), int(valid[1][1]))
    cv2.line(output, p1, p2, (255, 0, 0), 2)
    distance = abs(valid[1][1] - valid[0][1])
    print(f"Distance between dots: {distance:.1f} pixels")
    print("SUCCESS - ready for camera_manager.py")
elif len(valid) != 2:
    print(f"ERROR: Need exactly 2 blobs, found {len(valid)}")

cv2.imwrite("test_blobs.png", output)