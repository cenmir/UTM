# Recalibrate ROI — Playbook

Use this when `camera_setup.py` reports **0 blobs** (or shows blobs near the ROI edge) after you move the camera or specimen. The workflow transforms the new dot positions into a pylon ROI.

---

## When to do this

- `camera_setup.py` verdict = FAIL with "0 blobs in most frames"
- Blob edge margin < 30 px (camera drift will clip)
- Any bench setup change: camera mount, lens, specimen swap, lighting

---

## Step-by-step

### 1. Capture the full sensor

```
python grab_full_frame.py
```

Output: `setup_output/full_frame.png` — shows the whole 2448×2048 sensor (post-rotation 2048×2448).

### 2. Overlay a coordinate grid

```
python grid_full_frame.py
```

Output: `setup_output/full_frame_grid.png` — red grid at 100 px spacing with axis labels.

### 3. Read the dot centers off the grid

From the gridded image, note the **center pixel** of each dot in **post-rotation** coordinates:

```
Top dot    : (x_post_top,    y_post_top)
Bottom dot : (x_post_bottom, y_post_bottom)
```

Typical values have `y_post_top` small (near 0) and `y_post_bottom` larger (~1500).

### 4. Transform to pre-rotation (pylon) coordinates

Pylon applies the ROI **before** rotation, so we transform the post-rotation clicks back:

```
x_pre = y_post
y_pre = 2047 − x_post
```

(Constant 2047 = `sensor_height − 1` for the 2448×2048 sensor.)

You now have two points in pre-rotation space:

```
Top dot    : (x_pre_top,    y_pre_top)    ≈ small y_post  → small x_pre,  y_pre near 2047 − x_post_top
Bottom dot : (x_pre_bot,    y_pre_bot)
```

### 5. Build the ROI

The ROI is a rectangle in pre-rotation coordinates: `[OffsetX, OffsetY, Width, Height]`.

```
x_pre range covered: [OffsetX,           OffsetX + Width]
y_pre range covered: [OffsetY,           OffsetY + Height]
```

Pick values that enclose **both dots** with at least **~40 px margin** around each dot (dots are ~80 px diameter, so margin from dot edge matters).

**Basler rounding rules** (required, or pylon will reject):
| Parameter | Must be multiple of |
|---|---|
| OffsetX | 4 |
| Width   | 4 |
| OffsetY | 16 |
| Height  | 16 |

**Sensor limits:**
- `OffsetX + Width  ≤ 2448`
- `OffsetY + Height ≤ 2048`

### 6. Edit `camera_manager.py`

Two places must stay in sync:

**Line ~36 (class default):**
```python
ROI = [OffsetX, OffsetY, Width, Height]
```

**Line ~57 (Black preset) or line ~47 (White preset):**
```python
"roi": [OffsetX, OffsetY, Width, Height],
```

### 7. Verify

```
python camera_setup.py --mode black
```

Expect:
- Detection rate ≥ 95 %
- Distance std dev < 0.5 px
- Edge margin ≥ 30 px on both blobs

If PASS → you're ready to tare and run.

---

## Worked example (2026-04-22)

Grid reading:
- Top dot post    = (895, 50)
- Bottom dot post = (820, 1490)

Transform:
- Top dot pre    = (50,   2047 − 895)  = (50,   1152)
- Bottom dot pre = (1490, 2047 − 820)  = (1490, 1227)

Envelope with margin:
- x_pre : [0, 1700]     → OffsetX=0, Width=1700 (both ÷4 ✓)
- y_pre : [1072, 1328]  → OffsetY=1072 (÷16 ✓), Height=256 (÷16 ✓)

Final: `ROI = [0, 1072, 1700, 256]`

---

## Quick reference — the whole chain in one shell session

```
python grab_full_frame.py
python grid_full_frame.py
# --- read dot centers from setup_output/full_frame_grid.png ---
# --- compute new ROI using the transform above ---
# --- edit camera_manager.py (2 places) ---
python camera_setup.py --mode black
```

---

## Tips

- **Pick the preset first.** White specimen (dark dots) → `--mode white`. Dark specimen (light dots) → `--mode black`. The preset controls threshold polarity and minimum circularity.
- **Bigger margin is cheap.** Going from `Height=208` to `Height=256` costs ~25 % more pixels per frame but gives you 48 px extra vertical drift tolerance.
- **Don't chase tight margins** unless you need max frame rate. Wider ROI = more forgiving to small camera jiggles.
- **History matters**: note the old ROI in a comment before editing, so you can roll back if needed.
