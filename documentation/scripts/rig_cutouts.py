"""Background-removed cutouts of the 2026-08-12 rig photographs, for the posters.

    python documentation/scripts/rig_cutouts.py

The office background (door, cabinet, carpet, cables on the floor) is pure distraction on a poster —
the eye should land on the machine. Model choice matters a lot here: the default **u2net is a salient
-object model and returns one blob**, so the wall and carpet visible THROUGH the frame openings survive
and the rig prints as a solid slab. **isnet-general-use cuts the openings out properly**, which is what
this machine needs — it is mostly holes. On top of the matte this script then

  * morphologically CLOSES the matte first, because isnet chews small holes through slender members
    (the central crossmember came out in fragments) — a 15 px close heals those without filling the
    big frame openings that are the whole point of using isnet,
  * keeps only the LARGEST connected component, so a stray chair leg or floor cable that the matte
    also picked out does not survive as a floating fragment,
  * hard-clamps the near-transparent tail to 0 and the near-opaque head to 255, because u2net leaves
    a haze of alpha ~10-40 across the whole background that prints as grey fog on white paper,
  * trims to the alpha bounding box, so the poster's layout engine gets a picture whose declared
    aspect ratio is the SUBJECT's, not the original frame's.

Output: RGBA PNGs. They are composited straight onto the poster's page colour.
"""
import os
import sys

import numpy as np
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))

SOURCES = [
    # (source, output, optional pre-crop as fractions (l, t, r, b) of the frame)
    ("documentation/figures/UTM rig_12-08-26.jpg",     "rig_cut_full.png",   None),
    ("documentation/figures/UTM rig_12-08-26 (1).jpg", "rig_cut_detail.png", None),
]

ALPHA_LO, ALPHA_HI = 40, 225        # below LO -> fully clear, above HI -> fully opaque
CLOSE_PX = 15                       # heals matte damage on slender members


def largest_component(mask):
    """Keep only the biggest blob in a boolean mask (drops floor cables, chair legs, wall marks)."""
    import cv2
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 1:
        return mask
    keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return lab == keep


def cutout(src, dst, precrop=None, pad=8):
    from rembg import remove, new_session

    im = Image.open(os.path.join(_HERE, "..", "figures", src)).convert("RGB")
    if precrop:
        W, H = im.size
        l, t, r, b = precrop
        im = im.crop((int(l * W), int(t * H), int(r * W), int(b * H)))

    if not hasattr(cutout, "_session"):
        cutout._session = new_session("isnet-general-use")
    out = remove(im, session=cutout._session, post_process_mask=True)

    a = np.array(out.split()[-1]).astype(np.int16)
    a = np.where(a < ALPHA_LO, 0, a)                       # kill the background haze
    a = np.where(a > ALPHA_HI, 255, a)
    import cv2
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_PX, CLOSE_PX))
    a = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_CLOSE, ker).astype(np.int16)
    solid = largest_component(a > 0)
    a = np.where(solid, a, 0).astype(np.uint8)

    rgba = np.dstack([np.array(out)[:, :, :3], a])
    img = Image.fromarray(rgba, "RGBA")

    bbox = img.getchannel("A").getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        img = img.crop((max(0, x0 - pad), max(0, y0 - pad),
                        min(img.width, x1 + pad), min(img.height, y1 + pad)))
    img.thumbnail((1600, 2600), Image.LANCZOS)
    img.save(os.path.join(_HERE, "..", "figures", dst))
    cover = 100.0 * (np.array(img.getchannel("A")) > 0).mean()
    return dst, img.size, cover


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for src, dst, pc in SOURCES:
        name, size, cover = cutout(src, dst, pc)
        print("  %-22s %sx%s  aspect %.3f  subject fills %.0f %% of the frame"
              % (name, size[0], size[1], size[0] / size[1], cover))
