import cv2
import numpy as np

img = cv2.imread("1000143067.jpg")
h, w = img.shape[:2]
scale = 900 / h
img = cv2.resize(img, (int(w * scale), 900))

PAD = 180
padded = cv2.copyMakeBorder(img, PAD, PAD, PAD, PAD,
                             cv2.BORDER_CONSTANT, value=(240, 240, 240))

def px(x): return x + PAD
def py(y): return y + PAD

# Corrected coordinates — specimen zone removed, renumbered 1-9
# White electronics box is at ~(330, 310), crosshead beam at ~(330, 490)
annotations = [
    (1,  210, 65,   "Stepper motors x2",          (180, 80,  200), "left"),
    (2,  200, 270,  "Lead screws x2",              (180, 80,  200), "left"),
    (3,  330, 310,  "Electronics / controller",    (180, 100, 20),  "right"),
    (4,  330, 540,  "Crosshead - moving beam",     (40,  100, 220), "right"),
    (5,  290, 660,  "Upper grip",                  (30,  150, 50),  "left"),
    (6,  320, 760,  "Lower grip - fixed",          (30,  150, 50),  "left"),
    (7,  350, 630,  "Load cell",                   (10,  120, 200), "right"),
    (8,  445, 580,  "Emergency stop",              (40,  40,  200), "right"),
    (9,  158, 490,  "AL extrusion frame",   (100, 100, 100), "left"),
]

font       = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 0.55
circle_r   = 14

for (num, cx, cy, label, color, side) in annotations:
    cx, cy = px(cx), py(cy)

    cv2.circle(padded, (cx, cy), circle_r, color, -1)
    cv2.circle(padded, (cx, cy), circle_r, (255, 255, 255), 1)

    ts = cv2.getTextSize(str(num), font, 0.45, 1)[0]
    cv2.putText(padded, str(num), (cx - ts[0]//2, cy + ts[1]//2),
                font, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    if side == "left":
        end_x = cx - circle_r - 100
        end_y = cy
        cv2.line(padded, (cx - circle_r, cy), (end_x, end_y), color, 1, cv2.LINE_AA)
        tw = cv2.getTextSize(label, font, font_scale, 1)[0][0]
        label_x = end_x - tw - 8
    else:
        end_x = cx + circle_r + 100
        end_y = cy
        cv2.line(padded, (cx + circle_r, cy), (end_x, end_y), color, 1, cv2.LINE_AA)
        label_x = end_x + 5

    ts2 = cv2.getTextSize(label, font, font_scale, 1)[0]
    cv2.rectangle(padded,
                  (label_x - 4, end_y - ts2[1] - 6),
                  (label_x + ts2[0] + 4, end_y + 4),
                  (20, 20, 20), -1)
    cv2.putText(padded, label, (label_x, end_y), font, font_scale,
                (255, 255, 255), 1, cv2.LINE_AA)

cv2.imwrite("utm_annotated.png", padded)
print("Saved utm_annotated.png")