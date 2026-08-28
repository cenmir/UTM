#!/usr/bin/env python3
"""Generate deploy/utm.ico (and utm.png) — the app / shortcut icon.

The mark is a stress-strain curve to fracture: steep elastic rise, yield knee,
work-hardening to UTS, then the load collapse the rig's fracture detector watches for.
Drawn per-size rather than downscaled, so it still reads at 16 px.

    python deploy/make_icon.py
"""
from PIL import Image, ImageDraw
import os

HERE = os.path.dirname(os.path.abspath(__file__))

GROUND = (13, 19, 22, 255)     # app dark-theme background
CURVE = (52, 198, 212, 255)    # app frozen-Px0 cyan
AXIS = (58, 78, 86, 255)

# normalised stress-strain curve: (strain, stress) in 0..1
CURVE_PTS = [
    (0.00, 0.00), (0.16, 0.52),                     # elastic
    (0.24, 0.68), (0.34, 0.78),                     # yield knee
    (0.50, 0.88), (0.66, 0.94), (0.76, 0.96),       # work hardening to UTS
    (0.84, 0.90), (0.90, 0.72), (0.94, 0.34),       # necking + collapse
]


def draw(size):
    ss = 8 if size < 64 else 4               # supersample for clean curves
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = int(S * 0.20)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=GROUND)

    pad_l = S * 0.24
    pad_b = S * 0.24
    pad_t = S * 0.17
    pad_r = S * 0.13
    w = S - pad_l - pad_r
    h = S - pad_t - pad_b

    def pt(e, sig):
        return (pad_l + e * w, S - pad_b - sig * h)

    # axes — thin, present but quiet; dropped at 16 px where they only add noise
    if size >= 24:
        aw = max(1, int(S * 0.022))
        d.line([pt(0, 0), pt(1.02, 0)], fill=AXIS, width=aw)
        d.line([pt(0, 0), pt(0, 1.04)], fill=AXIS, width=aw)

    cw = max(2, int(S * (0.085 if size < 32 else 0.070)))
    d.line([pt(e, s) for e, s in CURVE_PTS], fill=CURVE, width=cw,
           joint="curve")

    # fracture point — a deliberate terminal dot, the moment the test ends
    if size >= 32:
        cx, cy = pt(*CURVE_PTS[-1])
        r = cw * 0.85
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CURVE)

    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw(s) for s in sizes]

    ico = os.path.join(HERE, "utm.ico")
    frames[-1].save(ico, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])

    png = os.path.join(HERE, "utm.png")
    frames[-1].save(png, format="PNG")

    print("wrote %s  (%d bytes, sizes %s)" % (ico, os.path.getsize(ico), sizes))
    print("wrote %s  (256x256, for Linux .desktop and macOS)" % png)


if __name__ == "__main__":
    main()
