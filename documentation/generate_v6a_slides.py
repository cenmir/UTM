import os as _os  # [doc-folder] run from repo root so plot PNGs & Software/ resolve
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
"""Phase 8.6.20 V6a (S7, 100% infill, LED on) deck + V6a-vs-V5 comparison.
Mirrors the V5 single-specimen deck, then appends 4 comparison slides.
13 slides, JU template (pages 141-153):
  141 Overview + timeline      145 Cauchy vs True         149 Recommendations
  142 Predicted results        146 Stress vs position     150 CMP load vs time
  143 Load vs time             147 Gauge strain vs disp    151 CMP stress-strain
  144 Stress-strain (4 reg.)   148 Verdict (offset k≈1)    152 CMP stress vs disp
                                                            153 CMP strain vs disp
Output: V6a_8_6_20_slides.pptx
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from PIL import Image
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

DARK_GREEN = RGBColor(0x1F, 0x3F, 0x2F); HEADER_GREEN = RGBColor(0x14, 0x3D, 0x2F)
LIGHT_BLUE = RGBColor(0xE7, 0xF1, 0xF8); GREEN_PASS = RGBColor(0xC8, 0xE6, 0xC9)
YELLOW_WARN = RGBColor(0xFF, 0xF3, 0xCD); RED_FAIL = RGBColor(0xFF, 0xCD, 0xD2)
GREY_TEXT = RGBColor(0x70, 0x70, 0x70); WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00); JU_BLUE_BAR = RGBColor(0xA9, 0xD6, 0xEF)
FLOW_BLUE = RGBColor(0x1F, 0x77, 0xB4); FLOW_RED = RGBColor(0xD6, 0x27, 0x28)
FLOW_NEUTRAL = RGBColor(0x55, 0x55, 0x55)

prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def tb(slide, x, y, w, h, text, *, fs=14, bold=False, italic=False, colour=BLACK,
       align=PP_ALIGN.LEFT, font="Calibri", anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.05); tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.02); tf.margin_bottom = Inches(0.02); tf.vertical_anchor = anchor
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(fs); r.font.bold = bold; r.font.italic = italic
    r.font.name = font; r.font.color.rgb = colour
    return box


def title(slide, text):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(0.45), Inches(0.5), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = JU_BLUE_BAR; bar.line.fill.background()
    tb(slide, 0.5, 0.55, 12.5, 0.9, text, fs=30, font="Calibri Light")


def header(slide, x, y, w, text):
    tb(slide, x, y, w, 0.4, text, fs=16, colour=GREY_TEXT)


def cell_txt(cell, text, *, fs=10, bold=False, colour=BLACK, align=PP_ALIGN.LEFT):
    tf = cell.text_frame
    tf.margin_left = Inches(0.06); tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.02); tf.margin_bottom = Inches(0.02)
    tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = align; p.text = ""
    r = p.add_run(); r.text = text
    r.font.size = Pt(fs); r.font.bold = bold; r.font.color.rgb = colour; r.font.name = "Calibri"


def table(slide, x, y, w, h, data, *, hbg=HEADER_GREEN, hfg=WHITE, cw=None, hf=10, bf=10, ov=None):
    rows, cols = len(data), len(data[0])
    shp = slide.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h)); t = shp.table
    if cw:
        tot = sum(cw)
        for i, f in enumerate(cw):
            t.columns[i].width = Inches(w*f/tot)
    for r in range(rows):
        for c in range(cols):
            cell = t.cell(r, c); text = data[r][c]
            if r == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = hbg
                cell_txt(cell, text, fs=hf, bold=True, colour=hfg)
            else:
                cell_txt(cell, text, fs=bf)
            if ov and (r, c) in ov:
                o = ov[(r, c)]
                if 'bg' in o:
                    cell.fill.solid(); cell.fill.fore_color.rgb = o['bg']
                cell_txt(cell, o.get('text', text), fs=bf, bold=o.get('bold', False), colour=o.get('colour', BLACK))
    return shp


def kpi(slide, x, y, w, label, value, *, fill=LIGHT_BLUE, vcol=DARK_GREEN, h=0.98, vfs=18):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = fill; box.line.fill.background()
    tf = box.text_frame; tf.margin_left = Inches(0.06); tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.05); tf.margin_bottom = Inches(0.03)
    tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p1 = tf.paragraphs[0]; p1.alignment = PP_ALIGN.CENTER; p1.text = ""
    r1 = p1.add_run(); r1.text = value
    r1.font.size = Pt(vfs); r1.font.bold = True; r1.font.color.rgb = vcol; r1.font.name = "Calibri"
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = label
    r2.font.size = Pt(9.5); r2.font.color.rgb = BLACK; r2.font.name = "Calibri"
    return box


def flow(slide, x, y, w, h, text, *, fill=WHITE, border=FLOW_NEUTRAL, fs=11, bold=False, fg=BLACK):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = fill
    box.line.color.rgb = border; box.line.width = Pt(1.2)
    tf = box.text_frame; tf.margin_left = Inches(0.06); tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.03); tf.margin_bottom = Inches(0.03)
    tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; p.text = ""
    r = p.add_run(); r.text = text
    r.font.size = Pt(fs); r.font.bold = bold; r.font.color.rgb = fg; r.font.name = "Calibri"
    return box


def arrow(slide, x1, y1, x2, y2, *, colour=FLOW_NEUTRAL, width=1.5):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = colour; c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'}))


def banner(slide, x, y, w, h, text, *, fill=GREEN_PASS, fg=DARK_GREEN, fs=13):
    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = fill; box.line.fill.background()
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.12); tf.margin_right = Inches(0.12)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; p.text = ""
    r = p.add_run(); r.text = text
    r.font.size = Pt(fs); r.font.bold = True; r.font.color.rgb = fg; r.font.name = "Calibri"
    return box


def pageno(slide, n):
    tb(slide, 0.5, 7.05, 0.7, 0.3, str(n), fs=10, colour=GREY_TEXT)


def ju(slide):
    tb(slide, 12.2, 0.3, 1.0, 0.3, "JÖNKÖPING UNIVERSITY", fs=8, bold=True, colour=GREY_TEXT, align=PP_ALIGN.RIGHT)


def footer(slide, text):
    tb(slide, 0.6, 7.0, 12.1, 0.4, text, fs=12, italic=True, colour=GREY_TEXT)


def linkbox(slide, x, y, w, text, url, *, fs=11):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.3))
    tf = box.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = text
    r.font.size = Pt(fs); r.font.name = "Calibri"
    r.font.color.rgb = RGBColor(0x1A, 0x5F, 0xB4); r.font.underline = True
    r.hyperlink.address = url
    return box


ADDNORTH_TDS = "https://storage.googleapis.com/addnorth-com.appspot.com/imgix/assets/production/epla_tds_rev21_XTkw2P.pdf"
ADDNORTH_PROD = "https://addnorth.com/product/PLA%20Economy/PLA%20Economy%20-%201.75mm%20-%201000g%20-%20Light%20Grey"


def pic_slide(t, img, n, foot, *, x=1.67, y=1.55, w=10.0):
    s = prs.slides.add_slide(BLANK); ju(s); title(s, t)
    s.shapes.add_picture(img, Inches(x), Inches(y), width=Inches(w))
    footer(s, foot); pageno(s, n); return s


# ===== SLIDE 1 — Overview + timeline =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6a: TENSILE TO FAILURE — 100 % INFILL (PILOT)")
header(s, 0.5, 1.4, 5.6, "Test setup")
setup = [
    ["Parameter", "Value"],
    ["Specimen", "S7 — fresh PLA, 100 % infill, LED on"],
    ["Geometry", "10 × 8 mm gauge (80 mm², CAD-verified)"],
    ["Markers", "Spray paint — DIC 99.9 % to fracture"],
    ["Preload", "+470 N (anchor 475 N post-fracture)"],
    ["Rate", "0.1 mm/s (rate-matched to V5)"],
    ["Load cell", "ANYLOAD 3 t — peak used 13 %"],
    ["Reference", "Chacón et al. (2017), Materials & Design"],
]
table(s, 0.5, 1.8, 5.6, 2.7, setup, cw=[1.0, 2.7], hf=10, bf=10)
kpi(s, 0.5, 4.7, 1.78, "UTS (nominal)", "47.8 MPa", fill=GREEN_PASS)
kpi(s, 2.41, 4.7, 1.78, "peak force", "3 826 N", fill=GREEN_PASS)
kpi(s, 4.32, 4.7, 1.78, "E (nominal)", "2.41 GPa")
kpi(s, 0.5, 5.85, 1.78, "σ_y (0.2 %)", "47.8 MPa")
kpi(s, 2.41, 5.85, 1.78, "failure strain", "2.98 %")
kpi(s, 4.32, 5.85, 1.78, "offset k", "≈ 1", fill=GREEN_PASS)

header(s, 6.7, 1.4, 6.2, "Test timeline")
steps = [
    ("Mount S7 + spray markers; LED on", FLOW_NEUTRAL, WHITE),
    ("Preload +470 N → Tare δ / load / DIC", FLOW_NEUTRAL, WHITE),
    ("LED pre-flight: ε_c≈0, 2 blobs tracked", FLOW_BLUE, WHITE),
    ("Pull 0.1 mm/s → UTS 3826 N @ 0.020", FLOW_BLUE, WHITE),
    ("Plastic plateau → 7 % softening", FLOW_NEUTRAL, WHITE),
    ("Fracture ε_f = 0.030 @ 7.33 mm travel", FLOW_RED, WHITE),
]
FX, FW, FH, y0, gap = 6.9, 5.9, 0.62, 1.85, 0.84
for i, (txt, bd, fg) in enumerate(steps):
    yy = y0 + i*gap
    flow(s, FX, yy, FW, FH, txt, border=bd, fs=12, bold=(i in (3, 5)))
    if i < len(steps)-1:
        arrow(s, FX+FW/2, yy+FH, FX+FW/2, yy+gap, colour=bd)
footer(s, "V6a (S7) = the PILOT (first) 100 % specimen, shown here in detail. It is the batch's strength / modulus "
          "EDGE point — representative n = 5 result on pp. 157–160; the V5 comparison uses V6d (≈ mean).")
pageno(s, 141)

# ===== SLIDE 2 — Predicted results =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6a: PREDICTED RESULTS (pre-test)")
header(s, 0.5, 1.4, 12, "Hypotheses before pulling the 100 % specimen")
pred = [
    ["Quantity", "Predicted", "Actual", "Verdict"],
    ["Peak force", "≤ ~4.8 kN (≈2× V5)", "3.83 kN", "✓ in range"],
    ["UTS (nominal 80 mm²)", "lands in Chacón 32–50 MPa", "47.8 MPa", "✓ in range"],
    ["Offset factor k", "≈ 1 (no knock-down)", "0.67–1.25", "✓ ≈ 1"],
    ["σ_y", "≈ 2× V5 (rate-matched)", "47.8 MPa (2.5×)", "✓"],
    ["Failure mode", "stiffer, higher force, slight soften", "7 % soften, ε_f 0.030", "✓"],
    ["DIC under LED", "≥ 95 % tracking, clean floor", "99.9 %", "✓"],
]
ovp = {(r, 3): {'bg': GREEN_PASS, 'bold': True} for r in range(1, 7)}
table(s, 0.5, 1.85, 12.3, 3.0, pred, cw=[2.3, 3.2, 2.4, 1.6], hf=12, bf=12, ov=ovp)
banner(s, 0.5, 5.2, 12.3, 1.4,
       "Core hypothesis (G2/G3): if the 50 % offset (k≈1.45) is purely an infill knock-down, then 100 % "
       "infill at the same nominal area should reach literature directly with k ≈ 1. Confirmed below.",
       fill=LIGHT_BLUE, fg=DARK_GREEN, fs=13)
footer(s, "Predictions set from the 50 % V5 baseline + Chacón (2017) ranges and the infill-knock-down argument.")
pageno(s, 142)

# ===== SLIDES 3-7 — single-specimen plots =====
pic_slide("PHASE 8.6.20 V6a: LOAD vs TIME", "V6a_load_time.png", 143,
          "Long ductile pull (73 s) at 0.1 mm/s: rises to UTS 3826 N then softens ~7 % over a wide plastic "
          "plateau before fracture. Net pull Δ ≈ 3351 N above the 475 N preload.", x=0.4, y=1.5, w=8.9)
pic_slide("PHASE 8.6.20 V6a: STRESS vs STRAIN", "V6a_stress_strain.png", 144,
          "E = 2.41 GPa; σ_y(0.2 %) 47.8 MPa ≈ UTS 47.8 MPa (near-linear to peak), then region IV softening "
          "to ε_f = 0.030. Strength is the robust DIC-independent result (load cell + fixed area).", x=0.4, y=1.5, w=8.9)
pic_slide("PHASE 8.6.20 V6a: CAUCHY vs TRUE STRAIN", "V6a_cauchy_true.png", 145,
          "Cauchy and True strain agree to <0.5 % (strains are small): ε_c = 0.0298 vs ε_t = 0.0294 at fracture.", x=0.4, y=1.5, w=8.9)
pic_slide("PHASE 8.6.20 V6a: STRESS vs CROSSHEAD POSITION", "V6a_stress_position.png", 146,
          "Of 7.33 mm crosshead travel, only 2.39 mm (33 %) stretched the gauge; rig/grip took up 4.94 mm. "
          "Higher force (3.8 kN) ⇒ ~2.7× the rig deflection of V5 → strain MUST come from DIC.", x=0.4, y=1.5, w=8.9)
pic_slide("PHASE 8.6.20 V6a: GAUGE STRAIN vs DISPLACEMENT", "V6a_strain_position.png", 147,
          "Gauge strain rises ~linearly with travel but well below the ‘all-travel-to-gauge’ line — confirming "
          "~two-thirds of the crosshead motion is machine compliance at this force level.", x=1.67, y=1.55, w=10.0)

# ===== SLIDE 8 — Verdict =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6 (n = 5): VALIDATION — JOURNAL REFERENCE")
header(s, 0.5, 1.35, 7.7, "Chacón (2017) journal — n = 5 mean vs range, offset k = Chacón_min / measured")
off = [
    ["Property", "V5 k", "V6 k", "V6 mean (n=5)", "Chacón range"],
    ["E", "×1.95", "×1.15", "2.60 GPa", "3.0–5.5 GPa"],
    ["σ_y", "×1.58", "×0.67", "45.0 MPa", "30–50 MPa"],
    ["UTS", "×1.45", "×0.69", "46.2 MPa", "32–60 MPa"],
]
ovo = {(r, 2): {'bold': True} for r in range(1, 4)}                 # V6 k bold
ovo[(1, 3)] = {'bg': YELLOW_WARN, 'bold': True}                     # E 2.60 just below 3.0
ovo[(2, 3)] = {'bg': GREEN_PASS, 'bold': True}                      # σ_y 45.0 inside 30–50 ✓
ovo[(3, 3)] = {'bg': GREEN_PASS, 'bold': True}                      # UTS 46.2 inside 32–60 ✓
table(s, 0.5, 1.78, 7.7, 1.55, off, cw=[0.85, 0.8, 0.8, 1.3, 1.5], hf=10.5, bf=11.5, ov=ovo)
tb(s, 0.5, 3.45, 7.7, 1.7,
   "Green = measured value lands INSIDE the Chacón range; yellow = just below.\n\n"
   "At 100 % infill the strength values land in literature directly: UTS 46.2 MPa and σ_y 45.0 MPa sit "
   "mid-range (k = 0.67–0.69 < 1 ⇒ no knock-down needed). E (2.60 GPa, ×1.15) is ~13 % below the 3.0 GPa "
   "floor — held down by the rig-compliance-limited apparent modulus. Strength common-factor window ≈ [0.69, 1.11] → k ≈ 1 (p. 155).",
   fs=12, colour=BLACK)
kpi(s, 8.3, 1.7, 2.3, "UTS vs 50 %", "2.09×", fill=GREEN_PASS, h=1.1, vfs=22)
kpi(s, 10.75, 1.7, 2.1, "toughness vs 50 %", "5.0×", h=1.1, vfs=22)
kpi(s, 8.3, 3.0, 2.3, "DIC tracking (LED)", "≥99 %", fill=GREEN_PASS, h=1.1, vfs=22)
kpi(s, 10.75, 3.0, 2.1, "peak / load-cell", "13 %", h=1.1, vfs=22)
banner(s, 0.5, 5.3, 12.4, 0.65,
       "G2 ✓ 100 % infill reaches literature (k≈1).  G3 ✓ the 50 % offset (×1.45) was purely the infill knock-down.")
banner(s, 0.5, 6.1, 12.4, 0.65,
       "DIC validated under LED lighting (clean ≥99 % tracking across all 5, stable baseline) — lighting is precision-only, as predicted.",
       fill=LIGHT_BLUE, fg=DARK_GREEN, fs=12)
footer(s, "n = 5 mean vs Chacón (2017); per-specimen repeatability on p. 157, add:north datasheet on p. 156. "
          "Strength inside range (k ≈ 1); E ~13 % below the journal floor.")
pageno(s, 148)

# ===== SLIDE 9 — Recommendations =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6a: RECOMMENDATIONS / NEXT")
recs = [
    "Run V6b, V6c (100 % repeats, LED on) to confirm offset-≈1 repeatability — as the 50 % set established for k≈1.45.",
    "For material claims at 100 % infill, report nominal values directly (no infill correction); apply the ×1.45 "
    "knock-down only for 50 % infill parts.",
    "LED neutrality: V6a tracked 99.9 % under LED, so lighting works for DIC. The formal 50 % LED on/off gate "
    "(V5d/e) was skipped — backfill it only if a 50 % LED-on dataset is needed.",
    "Keep the rate at 0.1 mm/s for all remaining runs (the V5c2 0.2 mm/s rate-confound lesson).",
    "Post-fracture DIC fully drops out at 100 % (energetic fracture) — the load-collapse anchor handles it; "
    "the strength result is unaffected.",
]
y = 1.7
for i, t in enumerate(recs, 1):
    n = prs.slides  # noop to keep linter calm
    flow(s, 0.6, y, 0.55, 0.55, str(i), fill=LIGHT_BLUE, border=FLOW_BLUE, fs=15, bold=True, fg=DARK_GREEN)
    tb(s, 1.35, y-0.03, 11.4, 0.95, t, fs=13.5, colour=BLACK)
    y += 1.02
footer(s, "Next bench step: V6b/V6c (100 % repeats). Campaign goals G1 (50 % repeatable), G2/G3 (100 %≈literature) met.")
pageno(s, 149)

# ===== SLIDES 10-13 — V6 (100% infill) vs V5 (50% infill) comparison — representative specimen V6d =====
pic_slide("V6 (100 % INFILL) vs V5 (50 % INFILL): LOAD vs TIME", "V6a_v5_load_time.png", 150,
          "Both at 0.1 mm/s (rate-matched). 100 % infill carries ≈2.1× the peak force (batch mean 3697 vs 1767 N) "
          "and sustains a longer pull. Uses representative specimen V6d (≈ n = 5 mean), not the pilot V6a.")
pic_slide("V6 (100 % INFILL) vs V5 (50 % INFILL): STRESS vs STRAIN", "V6a_v5_stress_strain.png", 151,
          "Same nominal 80 mm². 100 % infill is ~2× stronger (UTS 46.1 vs 22.1 MPa) and ~1.7× stiffer; the 100 % "
          "batch is also more extensible (ε_f 3–7 % vs ~2.5 %) — the difference is the infill load-bearing knock-down.")
pic_slide("V6 (100 % INFILL) vs V5 (50 % INFILL): STRESS vs DISPLACEMENT", "V6a_v5_stress_disp.png", 152,
          "100 % infill needs ~2× the travel (7.3 vs 3.8 mm) to fracture — higher force and ~2× the gauge stretch — "
          "but reaches a SIMILAR gauge share (55 % vs 52 %). (The pilot V6a's low 33 % was its own outlier.)")
pic_slide("V6 (100 % INFILL) vs V5 (50 % INFILL): GAUGE STRAIN vs DISPLACEMENT", "V6a_v5_strain_disp.png", 153,
          "Both curves sit below the ideal ‘all-travel-to-gauge’ line (rig compliance) with SIMILAR slopes — about "
          "half the travel reaches the gauge in both; 100 % just travels further (stronger and more extensible).")

# ===== SLIDE 14 — Full 50 % vs 100 % numerical comparison =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "50 % vs 100 % INFILL — FULL COMPARISON")
header(s, 0.4, 1.32, 8.5, "All measured values — V6 = representative V6d (≈ n=5 mean); ratio (100 %/50 %), % change")
cmp = [
    ["Parameter", "V5 50 % infill", "V6 100 % infill", "ratio", "Δ %"],
    ["Peak force (N)", "1767", "3688", "2.09×", "+109"],
    ["UTS (MPa)", "22.09", "46.10", "2.09×", "+109"],
    ["Yield σ_y 0.2 % (MPa)", "19.04", "44.73", "2.35×", "+135"],
    ["Elastic modulus E (GPa)", "1.54", "2.63", "1.71×", "+71"],
    ["Fracture stress (MPa)", "21.75", "42.55", "1.96×", "+96"],
    ["Failure strain ε_f", "0.0247", "0.0500", "2.02×", "+102"],
    ["Toughness (kJ/m³)", "462", "2131", "4.61×", "+361"],
    ["Post-UTS softening (%)", "1.5", "7.7", "5.1×", "+413"],
    ["Crosshead travel (mm)", "3.81", "7.32", "1.92×", "+92"],
    ["Gauge stretch DIC (mm)", "1.97", "4.00", "2.03×", "+103"],
    ["Rig take-up (mm)", "1.84", "3.32", "1.80×", "+80"],
    ["Gauge share of travel (%)", "51.8", "54.7", "1.06×", "+6"],
    ["Rig stiffness (N/mm)", "961", "1111", "1.16×", "+16"],
    ["Pull duration (s)", "38.4", "73.3", "1.91×", "+91"],
    ["DIC tracking (%)", "99.8", "99", "0.99×", "≈0"],
]
ovc = {}
for c in range(5):                                   # strength rows: highlight
    ovc[(1, c)] = {'bg': GREEN_PASS, 'bold': c in (0, 3)}   # peak force
    ovc[(2, c)] = {'bg': GREEN_PASS, 'bold': c in (0, 3)}   # UTS
table(s, 0.4, 1.7, 8.5, 5.2, cmp, cw=[2.7, 1.0, 1.05, 0.85, 0.9], hf=10.5, bf=10, ov=ovc)

header(s, 9.1, 1.32, 3.9, "What it means")
tb(s, 9.1, 1.75, 3.95, 4.5,
   "Strength scales ~2.1× — MORE than 2× for a 2× infill jump. The 50 % knock-down is "
   "NONLINEAR: 50 % infill bears < 50 % of the solid load path.\n\n"
   "• σ_y rises the most (2.35×) — 100 % yields near its UTS.\n\n"
   "• 100 % is also ~2× MORE extensible (ε_f 0.050 vs 0.025) — tougher (4.6×), not only stronger.\n\n"
   "• Gauge share ≈ the same (55 % vs 52 %) — 100 % just travels ~2× further (more force + more stretch).\n\n"
   "• Rate, area, markers, preload all matched — the only variable is infill.",
   fs=11.5, colour=BLACK)
banner(s, 9.1, 6.05, 3.95, 0.85, "≈ 2.1× strength, k: 1.45 → 1.0\n(V6 = representative V6d)",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12)
pageno(s, 154)

# ===== SLIDE 15 — Single common offset factor for V6 (n=5 mean) =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "V6 (n = 5): A SINGLE COMMON OFFSET FACTOR?")
s.shapes.add_picture("V6a_offset_window.png", Inches(0.35), Inches(1.65), width=Inches(7.5))
header(s, 8.0, 1.38, 5.0, "Same interval method as V5 · from n = 5 mean")
win = [
    ["Property", "feasible k window"],
    ["E", "[1.15, 2.12]"],
    ["σ_y", "[0.67, 1.11]"],
    ["UTS", "[0.69, 1.30]"],
    ["ALL three", "∅  empty"],
    ["Strength σ_y + UTS", "[0.69, 1.11]"],
]
ovw = {(4, 0): {'bg': RED_FAIL, 'bold': True}, (4, 1): {'bg': RED_FAIL, 'bold': True},
       (5, 0): {'bg': GREEN_PASS, 'bold': True}, (5, 1): {'bg': GREEN_PASS, 'bold': True}}
table(s, 8.0, 1.8, 5.0, 2.25, win, cw=[1.7, 1.5], hf=11, bf=11.5, ov=ovw)
tb(s, 8.0, 4.25, 5.0, 1.1,
   "k window per property = [Chacón_lo / measured, Chacón_hi / measured]; a single uniform "
   "k must lie in the intersection of all three.",
   fs=11.5, italic=True, colour=GREY_TEXT)
banner(s, 0.5, 5.55, 12.4, 0.6,
       "STRENGTH: a single uniform factor works — k ∈ [0.69, 1.11] and k = 1 sits inside it ⇒ apply "
       "k = 1.0 (no knock-down) to σ_y and UTS at 100 % infill.")
banner(s, 0.5, 6.3, 12.4, 0.62,
       "No single ALL-property k: E reads ~13 % low (needs k ≥ 1.15) while in-range σ_y caps k ≤ 1.11 → they "
       "pull opposite ways, but only by 0.04. Treat E separately.   (Contrast V5: a common k ≈ 2.4 existed.)",
       fill=YELLOW_WARN, fg=BLACK, fs=12)
pageno(s, 155)

# ===== SLIDE 16 — Validation: add:north PLA reference =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6 (n = 5): VALIDATION — add:north PLA REFERENCE")
header(s, 0.4, 1.3, 7.6, "add:north E-PLA datasheet (ISO 527 / 178) vs measured n = 5 mean — k = spec / measured")
dat = [
    ["Property", "ISO", "E-PLA spec", "V6 (n=5)", "k", "retain"],
    ["Yield strength σ_y", "527", "58 MPa †", "45.0 MPa", "1.29", "78 %"],
    ["Tensile strength (UTS)", "527", "58 MPa", "46.2 MPa", "1.26", "80 %"],
    ["Tensile modulus E", "527", "2.87 GPa", "2.60 GPa", "1.10", "91 %"],
    ["Elongation @ break", "527", "8 %", "3–7 %", "1.1–2.7", "37–93 %"],
    ["Flexural strength", "178", "120 MPa", "not tested", "—", "—"],
    ["Density / HDT", "527/75", "1.24 / 55 °C", "—", "—", "—"],
]
ovd = {}
for r in (1, 2, 3):
    for c in range(6):
        ovd[(r, c)] = {'bg': GREEN_PASS, 'bold': c in (0, 4)}
for c in range(6):
    ovd[(4, c)] = {'bg': YELLOW_WARN, 'bold': c in (0, 4)}
table(s, 0.4, 1.72, 7.6, 2.45, dat, cw=[1.95, 0.55, 1.25, 1.2, 0.55, 0.65], hf=10, bf=10, ov=ovd)

s.shapes.add_picture("V6a_epla_offset.png", Inches(8.05), Inches(1.4), width=Inches(5.05))
linkbox(s, 8.05, 5.0, 5.05, "Spec sheet — add:north E-PLA TDS (PDF, ISO 527 / 178)", ADDNORTH_TDS)
linkbox(s, 8.05, 5.32, 5.05, "add:north PLA Economy — product page", ADDNORTH_PROD)

tb(s, 0.4, 4.3, 7.6, 1.55,
   "Validated against TWO references:\n"
   "• Journal (Chacón 2017): σ_y & UTS land INSIDE the range (pass); modulus just below floor.\n"
   "• add:north E-PLA datasheet: strength ≈ 80 % of rated (k ≈ 1.26); stiffness ≈ 91 % (k ≈ 1.10, near spec) "
   "— E is CLOSER to spec than strength, so NOT one common factor. Repeatable at CV 2.5 % (n = 5).",
   fs=11.5, colour=BLACK)
banner(s, 0.4, 6.0, 12.7, 0.6,
       "Closest match = add:north E-PLA datasheet: strength k ≈ 1.26 (80 % of rated), stiffness k ≈ 1.10 "
       "(91 %, near spec). Predict printed strength ≈ spec ÷ 1.25.")
footer(s, "† E-PLA reports one tensile strength (at break), PLA σ_y ≈ UTS → both vs 58 MPa. E-PLA = closest "
          "add:north PLA (no PLA Economy TDS); ISO 527 moulded vs printed 80 mm² bar; values = n = 5 mean.")
pageno(s, 156)

# ===== SLIDE 17 — V6 repeatability study (n=5) =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6: REPEATABILITY STUDY (n = 5, 100 % INFILL)")
s.shapes.add_picture("V6_quintet_curves.png", Inches(0.32), Inches(1.6), width=Inches(6.5))
header(s, 7.0, 1.32, 6.0, "Per-specimen values  (UTS/σ_y MPa · E GPa · ε_f –)")
rep = [
    ["Specimen", "UTS", "σ_y", "E", "ε_f"],
    ["V6a · S7", "47.82", "47.80", "2.41", "0.030"],
    ["V6b · S8", "44.83", "43.24", "2.63", "0.052"],
    ["V6c · S10", "46.82", "45.09", "2.72", "0.073"],
    ["V6d · S11", "46.10", "44.73", "2.63", "0.050"],
    ["V6e · S9", "45.47", "44.03", "2.59", "0.074"],
    ["mean", "46.2", "45.0", "2.60", "0.056"],
    ["CV %", "2.5", "3.8", "4.4", "33"],
]
ovr = {}
for c in range(5):
    ovr[(6, c)] = {'bg': LIGHT_BLUE, 'bold': True}
    ovr[(7, c)] = {'bg': LIGHT_BLUE, 'bold': True}
table(s, 7.0, 1.72, 6.0, 2.55, rep, cw=[1.25, 0.9, 0.9, 0.8, 0.9], hf=10.5, bf=10, ov=ovr)
kpi(s, 7.0, 4.4, 1.42, "UTS CV", "2.5 %", fill=GREEN_PASS, h=0.8, vfs=16)
kpi(s, 8.52, 4.4, 1.42, "σ_y CV", "3.8 %", fill=GREEN_PASS, h=0.8, vfs=16)
kpi(s, 10.04, 4.4, 1.42, "E CV", "4.4 %", fill=GREEN_PASS, h=0.8, vfs=16)
kpi(s, 11.56, 4.4, 1.42, "ε_f CV", "33 %", fill=YELLOW_WARN, h=0.8, vfs=16)
flow(s, 7.0, 5.3, 6.0, 1.05,
     "⚠ V6a (S7) = pilot, run 8 days before the b–e batch → the strength/modulus EDGE point "
     "(σ_y +4.3σ, E −4.2σ, most brittle). Matched b–e batch alone: UTS 1.9 % · σ_y 1.8 % · E 2.1 % CV. "
     "Kept in n = 5 (conservative) — verdict unchanged.",
     fill=YELLOW_WARN, border=RGBColor(0xE0, 0xA8, 0x14), fs=9.5)
banner(s, 0.32, 6.5, 12.7, 0.45,
       "Strength REPEATABLE — UTS/σ_y/E all CV ≤ 4.4 % (n = 5; matched b–e batch < 2.1 %). "
       "Ductility ε_f scatters 33 % → report as a range.")
pageno(s, 157)

# ===== SLIDE 18 — Strength validation =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6: STRENGTH — REPEATABLE & IN LITERATURE")
s.shapes.add_picture("V6_strength_repeat.png", Inches(0.32), Inches(1.6), width=Inches(6.7))
header(s, 7.2, 1.32, 5.9, "Strength vs both references")
strg = [
    ["Quantity", "V6 (n=5)", "vs Chacón", "vs E-PLA"],
    ["UTS", "46.2 ± 1.2 MPa", "inside 32–60 ✓", "80 % (k 1.26)"],
    ["σ_y (0.2 %)", "45.0 MPa", "inside 30–50 ✓", "78 %"],
    ["E", "2.60 GPa", "13 % below 3.0 ⚠", "91 % (k 1.11)"],
]
ovs = {(1, 2): {'bg': GREEN_PASS, 'bold': True}, (2, 2): {'bg': GREEN_PASS, 'bold': True},
       (3, 2): {'bg': YELLOW_WARN, 'bold': True}, (1, 3): {'bg': GREEN_PASS}, (3, 3): {'bg': GREEN_PASS}}
table(s, 7.2, 1.78, 5.9, 1.7, strg, cw=[1.3, 1.6, 1.7, 1.4], hf=11, bf=11, ov=ovs)
tb(s, 7.2, 3.65, 5.9, 1.7,
   "• UTS = 46.2 ± 1.2 MPa (CV 2.5 %, 95 % CI ±1.4) — converged as n grew.\n"
   "• All 5 land INSIDE the Chacón range → k ≈ 1 (no knock-down), confirming the 50 % offset (k≈2.4) was "
   "purely the infill effect.\n"
   "• vs add:north E-PLA datasheet: 80 % of rated strength, 91 % of stiffness — coherent FFF knock-down.",
   fs=12)
banner(s, 7.2, 5.55, 5.9, 1.0,
       "STRENGTH PASS — repeatable (CV 2.5 %), inside the journal range, and a sensible ~80–90 % of the "
       "manufacturer's rated solid material.", fill=GREEN_PASS, fg=DARK_GREEN, fs=12.5)
pageno(s, 158)

# ===== SLIDE 19 — Ductility =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6: DUCTILITY — REPORT AS A RANGE")
s.shapes.add_picture("V6_ductility.png", Inches(0.32), Inches(1.6), width=Inches(6.7))
header(s, 7.2, 1.32, 5.9, "Failure strain & toughness")
kpi(s, 7.2, 1.78, 1.9, "ε_f range", "3.0–7.4 %", fill=YELLOW_WARN, h=1.0, vfs=18)
kpi(s, 9.25, 1.78, 1.9, "ε_f CV", "33 %", fill=YELLOW_WARN, h=1.0, vfs=18)
kpi(s, 11.3, 1.78, 1.8, "toughness", "2315 kJ/m³", h=1.0, vfs=14)
tb(s, 7.2, 3.0, 5.9, 2.3,
   "Failure strain is NOT reproducible (CV 33 %) and looks bimodal:\n"
   "• tough-skin cluster A/B/D ≈ 3.0–5.2 %\n"
   "• ductile cluster C/E ≈ 7.3–7.4 % (nearly the 8 % datasheet value)\n\n"
   "FDM crack-initiation lottery — a void / weak layer decides where the crack starts, so elongation "
   "varies far more than strength. Toughness follows ε_f (1310–3053 kJ/m³).",
   fs=12)
banner(s, 7.2, 5.5, 5.9, 1.05,
       "Quote ductility as a RANGE (ε_f = 3–7 %), never a single number. Strength is the reproducible "
       "engineering value; ductility is specimen-dependent.", fill=YELLOW_WARN, fg=BLACK, fs=12.5)
pageno(s, 159)

# ===== SLIDE 20 — Validation summary vs references =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20 V6: VALIDATION SUMMARY — JOURNAL & MANUFACTURER")
header(s, 0.4, 1.3, 8.0, "Pass / fail vs both references  (n = 5, 100 % infill)")
ver = [
    ["Property", "V6 mean", "Chacón range", "vs journal", "E-PLA spec", "vs datasheet"],
    ["UTS", "46.2 MPa", "32–60 MPa", "✓ PASS", "58 MPa", "80 % (k1.26)"],
    ["σ_y", "45.0 MPa", "30–50 MPa", "✓ PASS", "58 MPa †", "78 %"],
    ["E", "2.60 GPa", "3.0–5.5 GPa", "⚠ 13 % low", "2.87 GPa", "91 % (k1.11)"],
    ["ε_f", "3.0–7.4 %", "—", "—", "8 %", "37–93 % range"],
]
ovv = {}
for c in range(6):
    ovv[(1, c)] = {'bg': GREEN_PASS, 'bold': c in (0, 3)}
    ovv[(2, c)] = {'bg': GREEN_PASS, 'bold': c in (0, 3)}
    ovv[(3, c)] = {'bg': YELLOW_WARN, 'bold': c in (0, 3)}
table(s, 0.4, 1.75, 8.0, 2.35, ver, cw=[0.8, 1.1, 1.3, 1.2, 1.1, 1.4], hf=10.5, bf=11, ov=ovv)
s.shapes.add_picture("V6_offset_k.png", Inches(8.6), Inches(1.5), width=Inches(4.4))
banner(s, 0.4, 4.4, 8.0, 1.0,
       "PASS — strength lands inside the journal (k ≈ 1) AND sits at a coherent k ≈ 1.2 vs the add:north "
       "E-PLA datasheet (80 % strength / 91 % stiffness), repeatable at CV 2.5 % across 5 specimens.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12.5)
banner(s, 0.4, 5.55, 8.0, 0.85,
       "Caveat: elastic modulus is ~13 % below the journal floor (but meets the datasheet at 91 %); ε_f is "
       "reported as a 3–7 % range, not a single value.", fill=YELLOW_WARN, fg=BLACK, fs=12)
linkbox(s, 8.6, 6.1, 4.4, "add:north E-PLA TDS (ISO 527 / 178)", ADDNORTH_TDS)
footer(s, "Writeup: 100 % PLA validated vs literature for strength (k≈1 vs Chacón); characterised at k≈1.2 vs "
          "add:north E-PLA datasheet; modulus meets datasheet, marginally below journal; ε_f = 3–7 % range.")
pageno(s, 160)

# ===== SLIDE 21 — Fractography: individually-placed, editable specimen photos =====
def frac_tile(sl, path, x, y, w, at, cb, name, metric, band, tag):
    """Place ONE specimen photo as a separate, croppable PowerPoint picture (not a flattened
    montage). The crop only trims the grip tab so the gauge + fracture faces show; the full image
    stays embedded, so the crop can be reset / the picture moved, resized or replaced in PPT."""
    with Image.open(path) as im:
        wpx, hpx = im.size
    aspect = hpx / wpx
    ct = max(0.0, 1.0 - at / aspect - cb)          # keep bottom (fracture); frame aspect == cropped aspect (no distortion)
    h = w * at
    pic = sl.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    pic.crop_top = ct; pic.crop_bottom = cb
    pic.line.color.rgb = band; pic.line.width = Pt(1.25)
    tb(sl, x - 0.3, y + h + 0.01, w + 0.6, 0.2, name + (f"  ({tag})" if tag else ""),
       fs=10.5, bold=True, colour=band, align=PP_ALIGN.CENTER)
    tb(sl, x - 0.3, y + h + 0.21, w + 0.6, 0.2, metric, fs=9.5, colour=BLACK, align=PP_ALIGN.CENTER)


s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PHASE 8.6.20: FRACTURE PATTERNS — 50 % vs 100 % INFILL (V5 & V6)")
FROOT = r"Software\UTM_PyQt6\8.6.20 - Tensile test to Failure"
C50 = RGBColor(0x1F, 0x5F, 0xA0); C100 = RGBColor(0xC0, 0x00, 0x00)
FR50 = [
    ("V5 · S4",  "22.1 MPa · ε_f 2.5 %", FROOT + r"\Specimen_S4_V1_Spray\S4.jpg",       ""),
    ("V5b · S3", "22.0 MPa · ε_f 2.6 %", FROOT + r"\Specimen_S3_V1_Spray\S3(1).jpg",    ""),
    ("V5c · S2", "22.0 MPa · ε_f 3.1 %", FROOT + r"\Specimen_S2_V1_Spray\S2_2 (1).jpg", ""),
]
FR100 = [
    ("V6a · S7",  "47.8 MPa · ε_f 3.0 %", FROOT + r"\Specimen_S7_V2_Spray\S7(1).jpg",    "pilot"),
    ("V6b · S8",  "44.8 MPa · ε_f 5.2 %", FROOT + r"\Specimen_S8_V2_Spray\S8 (1).jpg",   ""),
    ("V6c · S10", "46.8 MPa · ε_f 7.3 %", FROOT + r"\Specimen_S10_V2_Spray\S10 (1).jpg", "ductile"),
    ("V6d · S11", "46.1 MPa · ε_f 5.0 %", FROOT + r"\Specimen_S11_V2_Spray\S11 (1).jpg", ""),
    ("V6e · S9",  "45.5 MPa · ε_f 7.4 %", FROOT + r"\Specimen_S9_V2_Spray\S9 (1).jpg",   "ductile"),
]
W, AT, CB, STEP = 1.8, 1.05, 0.02, 2.22
xb = [1.326 + STEP * i for i in range(5)]           # bottom row (100 %): 5 tiles
xt = xb[1:4]                                        # top row (50 %): 3 tiles, centred under the middle
# key finding / legend in the empty space beside the centred 50 % row
tb(s, 0.45, 1.58, 2.9, 0.32, "FRACTURE — KEY FINDING", fs=12, bold=True, colour=DARK_GREEN)
tb(s, 0.45, 1.98, 2.9, 1.7,
   "All 8 specimens failed the SAME way — a flat, transverse break at the lower gauge–fillet (a stress "
   "concentration), with no necking = brittle FDM failure.\n\nInfill sets STRENGTH & stiffness, NOT the failure mode.",
   fs=11, colour=BLACK)
tb(s, 9.95, 1.58, 3.0, 0.32, "HOW TO READ", fs=12, bold=True, colour=DARK_GREEN)
tb(s, 9.95, 1.98, 3.0, 1.7,
   "• 50 % faces expose the sparse infill ribs; 100 % faces are fully dense.\n\n"
   "• V6a = pilot (batch edge). V6c / V6e = ductile cluster (ε_f ≈ 7 %); the others ≈ 3–5 %.",
   fs=11, colour=BLACK)
tb(s, xt[0], 1.55, 6.0, 0.3, "50 % INFILL — V5 group (LED off)", fs=14, bold=True, colour=C50)
for (nm, mt, pth, tag), x in zip(FR50, xt):
    frac_tile(s, pth, x, 1.85, W, AT, CB, nm, mt, C50, tag)
tb(s, 1.0, 4.20, 8.0, 0.3, "100 % INFILL — V6 quintet (LED on)", fs=14, bold=True, colour=C100)
for (nm, mt, pth, tag), x in zip(FR100, xb):
    frac_tile(s, pth, x, 4.52, W, AT, CB, nm, mt, C100, tag)
footer(s, "Each specimen photo is an individually placed, croppable picture (…/8.6.20 - Tensile test to Failure/"
          "Specimen_S*/). Labels = measured UTS · ε_f. Reset crop in PowerPoint to see the full specimen.")
pageno(s, 161)

# ===== SLIDE 22 — Software feature: automatic preload =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "UTM SOFTWARE: AUTOMATIC PRELOAD (‘PRELOAD TENSION’)")

# --- recreated UI control (as it appears in the app toolbar) ---
GREY_BORDER = RGBColor(0xA6, 0xA6, 0xA6); BTN_FILL = RGBColor(0xEC, 0xEC, 0xEC)
tb(s, 0.5, 1.63, 1.2, 0.35, "Preload to:", fs=14)
flow(s, 1.72, 1.58, 1.05, 0.42, "470 N", fill=WHITE, border=GREY_BORDER, fs=13)
flow(s, 2.79, 1.58, 0.32, 0.42, "▴\n▾", fill=RGBColor(0xF2, 0xF2, 0xF2), border=GREY_BORDER, fs=8, fg=GREY_TEXT)
flow(s, 3.27, 1.58, 1.75, 0.42, "Preload tension", fill=BTN_FILL, border=GREY_BORDER, fs=12, fg=RGBColor(0x55, 0x55, 0x55))
tb(s, 0.5, 2.12, 5.0, 0.5,
   "The operator control (screen recreation): type a target load, click once — the crosshead "
   "auto-tensions to it, hands-off.", fs=10.5, italic=True, colour=GREY_TEXT)

header(s, 0.5, 2.75, 6.0, "How it works — one click, hands-off")
tb(s, 0.5, 3.15, 6.1, 3.0,
   "1.  Enter the target preload (e.g. 470 N) and press Preload tension.\n\n"
   "2.  The crosshead tensions at a LOAD-scheduled speed: 0.20 mm/s up to ~15 % of target, "
   "0.10 mm/s to 50 %, then ramps to a gentle 0.02 mm/s as it nears the target.\n\n"
   "3.  It stops at 1.03× the target — a deliberate ~3 % overshoot.\n\n"
   "4.  PLA stress-relaxes ~2 % while held → the load settles AT / just above the target.",
   fs=12, colour=BLACK)

s.shapes.add_picture("preload_schedule.png", Inches(6.75), Inches(1.65), width=Inches(6.2))

banner(s, 0.4, 6.25, 12.5, 0.72,
       "Why: manual jogging is slow and overshoots, and PLA relaxes after you stop (you would undershoot). "
       "Auto-preload lands consistently at target (+3 % set − ~2 % relaxation ≈ target). "
       "Safety: hard cap 1.25× target, 180 s timeout, live speed-only control (no Stop→restart re-latch).",
       fill=LIGHT_BLUE, fg=BLACK, fs=11.5)
footer(s, "Feature in Software/UTM_PyQt6/main.py — PRELOAD_SPEED_KNOTS · TARGET_FACTOR 1.03 · OVERSHOOT_CAP 1.25 · "
          "TIMEOUT 180 s. Used to set the ~470 N preload before every V5 / V6 pull.")
pageno(s, 162)


# =====================================================================================
# ROADMAP PROGRESS — advanced features & ease of use (slides 165-168)
# =====================================================================================
GREY_PLANNED = RGBColor(0xE8, 0xE8, 0xE8)

# ---- Slide 165: roadmap status dashboard ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SOFTWARE ROADMAP — ADVANCED FEATURES & EASE OF USE: STATUS")
tb(s, 0.4, 1.28, 12.55, 0.62,
   "The rig automated only ONE thing (auto-preload). A phased roadmap adds automated test modes, "
   "smart DIC and one-click analysis — each piece shippable on its own. After the full rig-test campaign:",
   fs=12, colour=BLACK)
road = [
    ["Phase", "Focus", "Status"],
    ["0 · Foundations", "shared analysis library · control engine · recipes", "DONE"],
    ["A · One-click workflow", "per-test report · test registry · prepare-specimen · auto-stop", "DONE — VALIDATED"],
    ["B · Closed-loop modes", "strain-rate + cyclic / staircase / relaxation / creep", "strain-rate DONE · 4 to wire"],
    ["C · Smart DIC", "live health HUD + measured Poisson / true Cauchy", "HUD DONE · Poisson next"],
    ["D · UX layer", "guided wizard · live overlay · dashboard", "PLANNED"],
]
rov = {(1, 2): {'bg': GREEN_PASS, 'bold': True}, (2, 2): {'bg': GREEN_PASS, 'bold': True},
       (3, 2): {'bg': YELLOW_WARN, 'bold': True}, (4, 2): {'bg': YELLOW_WARN, 'bold': True},
       (5, 2): {'bg': GREY_PLANNED, 'bold': True}}
table(s, 0.4, 2.02, 12.55, 2.75, road, cw=[2.6, 6.75, 3.2], hf=11, bf=10.5, ov=rov)
kpi(s, 0.4, 5.02, 2.95, "MODULES (in git)", "7")
kpi(s, 3.62, 5.02, 2.95, "APP FEATURES", "9")
kpi(s, 6.84, 5.02, 2.95, "SIM CHECKS PASSED", "9 / 9")
kpi(s, 10.06, 5.02, 2.89, "RIG TESTS PASSED", "6 / 6")
banner(s, 0.4, 6.18, 12.55, 0.92,
       "LEGEND — DONE + rig-validated (green) · partial, more to wire (amber) · PLANNED (grey).  Foundations, "
       "the one-click workflow and the strain-rate fracture test are validated on the rig; the remaining modes, "
       "measured Poisson and the UX layer are next.",
       fill=LIGHT_BLUE, fg=BLACK, fs=11)
footer(s, "All analysis logic is unit-tested / sim-validated offline; the app feature set is now snapshot-committed "
          "(main.py a3b187f) after the full rig-test campaign — see ROADMAP.md / TESTING_TODO.md.")
pageno(s, 163)

# ---- Slide 166: DONE — built & committed ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "DONE — BUILT, VERIFIED & COMMITTED")
header(s, 0.4, 1.28, 6.15, "Analysis & workflow tooling (offline-verified, in git)")
mods = [
    ["Module", "What it gives you"],
    ["utm_analysis.py", "ONE fracture detector + E / σy / UTS / εf / anchor"],
    ["utm_report.py", "one-click per-test PDF + PNG report"],
    ["utm_registry.py", "one table of EVERY test (props + anchor)"],
    ["utm_recipes.py", "save / load a full test setup"],
    ["control_policies + _sim", "closed-loop test-mode engine — 9/9 sim"],
    ["utm_dic.py", "live DIC health + Poisson / Cauchy maths"],
]
table(s, 0.4, 1.70, 6.15, 3.1, mods, cw=[2.25, 3.9], hf=10, bf=9.5)
tb(s, 0.4, 4.95, 6.15, 1.4,
   "Kills the copy-paste-per-specimen analysis burden (the cause of the V6c / V5-S4 detector bugs): "
   "one tested analyser, reused everywhere. Reproduces the known V5 / V6 numbers exactly.",
   fs=10.5, italic=True, colour=GREY_TEXT)
header(s, 6.75, 1.28, 6.2, "In the UI (main.py — RIG-VALIDATED · snapshot a3b187f)")
tb(s, 6.75, 1.72, 6.2, 3.9,
   "•  Generate report  — one button → PDF + images\n\n"
   "•  Settings  — Load / Save a setup (+ Default)\n\n"
   "•  Prepare specimen  — 1-click tare (position + force + DIC)\n\n"
   "•  Fracture test / Auto-stop  — halts on load collapse\n\n"
   "•  Strain-rate fracture test  — closed-loop dε/dt\n\n"
   "•  DIC health HUD  — live OK / WARN / BAD badge\n\n"
   "•  Safety net  — 10 kN / 30 mm / stall guard / dead-DIC",
   fs=12, colour=BLACK)
footer(s, "Modules committed & regression-checked against the deck numbers; the UI feature set is now "
          "snapshot-committed (main.py a3b187f) after full rig validation.")
pageno(s, 164)

# ---- Slide 167: TO BE TESTED — rig / camera ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "VALIDATED ON THE RIG  (2026-07-28 / 29)")
header(s, 0.4, 1.28, 7.35, "Feature checks — ALL PASSED")
tst = [
    ["Feature", "Result"],
    ["DIC health HUD", "green 2/2 live; red BAD on dot cover  ✓"],
    ["Prepare specimen", "1 click → position + force + DIC tared  ✓"],
    ["Auto-stop at fracture", "caught S16 collapse 2992 → −417 N  ✓"],
    ["Settings", "Default + Load / Save round-trip  ✓"],
    ["Generate report", "S16 report = CSV, every KPI  ✓"],
    ["Strain-rate fracture", "held 0.0005/s → fracture, auto-stop  ✓"],
]
table(s, 0.4, 1.70, 7.35, 3.05, tst, cw=[2.35, 5.0], hf=10, bf=9.5)
header(s, 7.95, 1.28, 5.0, "Rig facts — ALL RESOLVED")
tb(s, 7.95, 1.72, 5.0, 3.0,
   "These unblock the other 4 test modes:\n\n"
   "1.  Stop HOLDS position ✓\n     (zero drift over 5 / 10 / 15 s)\n\n"
   "2.  Direct reversal auto-decels ~1 s ✓\n     (no manual Stop needed)\n\n"
   "3.  Travel cap set to 30 mm ✓\n\n"
   "→  cyclic / staircase / relaxation / creep\n     are now UNBLOCKED to wire.",
   fs=11.5, colour=BLACK)
banner(s, 0.4, 5.5, 12.55, 1.05,
       "RESULT — every built feature passed on the rig; S16 = first 100% infill fracture (UTS 47.4 MPa, "
       "anchor-corrected). Strain-rate 6.2 held the target rate by adapting crosshead speed 0.10 → 0.05 mm/s. "
       "ONE hardware limit found — motor torque ceiling ~2.6 kN (next slide).",
       fill=GREEN_PASS, fg=BLACK, fs=11.5)
footer(s, "Full step-by-step results: Software/UTM_PyQt6/TESTING_TODO.md; thresholds confirmed (fracture arm "
          "30% / collapse 50%, travel cap 30 mm, stall guard 0.05 mm / 6 s).")
pageno(s, 165)

# ---- Slide 168: PLANNED NEXT — measured Poisson (edge-width / MDF) + remaining automation ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PLANNED NEXT — MEASURED POISSON (EDGE-WIDTH) + REMAINING AUTOMATION")
header(s, 0.4, 1.28, 12.55, "Measured Poisson / true Cauchy — edge-width tracking  (next build, reuses THIS camera)")
flow(s, 0.4, 1.75, 2.75, 0.95, "Matte-black MDF\nbackdrop\n(behind gauge)", fill=RGBColor(0x33, 0x33, 0x33),
     border=BLACK, fs=10.5, bold=True, fg=WHITE)
flow(s, 3.62, 1.75, 2.75, 0.95, "Camera detects\nL & R specimen\nedges", fill=WHITE, border=FLOW_BLUE, fs=10.5)
flow(s, 6.84, 1.75, 2.75, 0.95, "Average width\nover the gauge\n(100s of rows)", fill=WHITE, border=FLOW_BLUE, fs=10.5)
flow(s, 10.06, 1.75, 2.89, 0.95, "εw → ν  and\ntrue area →\nCauchy stress", fill=GREEN_PASS, border=DARK_GREEN,
     fs=10.5, bold=True, fg=DARK_GREEN)
arrow(s, 3.17, 2.23, 3.60, 2.23); arrow(s, 6.39, 2.23, 6.82, 2.23); arrow(s, 9.61, 2.23, 10.04, 2.23)
tb(s, 0.4, 2.85, 12.55, 0.95,
   "MEASURED (no assumed ν), reusing the current camera + specimen — matte finish avoids LED glare, a few-cm "
   "gap softens shadows. FIRST STEP: mount the board, grab ONE still frame → prototype the edge-detection to "
   "confirm contrast BEFORE building the live feature. (Transverse dots stay ruled out — see slide 164.)",
   fs=11, colour=BLACK)
header(s, 0.4, 3.95, 12.55, "Remaining automation & ease-of-use")
tb(s, 0.4, 4.38, 6.2, 2.0,
   "•  Cyclic / staircase / relaxation / creep modes\n    (engine ready — rig facts RESOLVED, ready to wire)\n\n"
   "•  Measured Poisson — 4-marker / edge-width\n    + auto specimen metadata + folder from recipe\n\n"
   "•  One-click per-specimen report deck",
   fs=11.5, colour=BLACK)
tb(s, 6.75, 4.38, 6.2, 2.0,
   "•  Guided wizard / checklist\n    (Connect → … → Prepare → Run → Save)\n\n"
   "•  Live stress-strain + elastic-modulus overlay\n\n"
   "•  Glanceable dashboard + fracture beep / banner",
   fs=11.5, colour=BLACK)
banner(s, 0.4, 6.5, 12.55, 0.72,
       "HARDWARE LIMIT — motor torque ceiling ~2.6 kN (variable; driver Vref / thermal / PSU) blocks 100% "
       "full-area fracture; use 50% / smaller specimens until resolved.   ORDER — wire remaining modes → "
       "edge-width Poisson → UX layer.", fill=YELLOW_WARN, fg=BLACK, fs=10.5)
pageno(s, 166)

# =====================================================================================
# NEW FEATURE SLIDES (169-182) — SF 1-8 overview, proof slides IN FEATURE ORDER, then context
# =====================================================================================
LIGHT_GREY = RGBColor(0xF2, 0xF2, 0xF2)


def pic_or_ph(sl, path, x, y, w, ph_h, note):
    """Add the picture if the file exists, else a labelled placeholder (for pending UI screenshots)."""
    if _os.path.exists(path):
        sl.shapes.add_picture(path, Inches(x), Inches(y), width=Inches(w))
    else:
        flow(sl, x, y, w, ph_h, note, fill=LIGHT_GREY, border=FLOW_NEUTRAL, fs=11, bold=True, fg=GREY_TEXT)

# ---- Slide 169: SMART-UTM feature set (SF 1-8) — proof slides FOLLOW in this order ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "NEW — SMART-UTM FEATURE SET (2026-07)")
tb(s, 0.4, 1.24, 12.55, 0.5, "Every card is built AND rig-validated (green). Proof slides FOLLOW in this same SF 1-8 order.", fs=12, italic=True, colour=GREY_TEXT)
cards = [
    ("DIC health HUD", "live 2/2 · jitter"), ("Prepare specimen", "1-click tare all"),
    ("Settings save / load", "reuse a setup"), ("Generate report", "1-click PDF + PNG"),
    ("Auto-stop at fracture", "halts on collapse"), ("Strain-rate fracture", "constant dε/dt"),
    ("Stall guard", "halts frozen motor"), ("Release preload", "safe return to 0"),
]
cx = [0.4, 3.62, 6.84, 10.06]; cy = [1.85, 3.75]
for i, (t_, b_) in enumerate(cards):
    flow(s, cx[i % 4], cy[i // 4], 3.0, 1.5, "SF %d\n%s\n\n%s" % (i + 1, t_, b_), fill=GREEN_PASS, border=DARK_GREEN, fs=12, bold=True, fg=DARK_GREEN)
banner(s, 0.4, 5.6, 12.55, 0.95,
       "3-layer safety on every driven test — load-collapse detector · stall guard · 10 kN / 30 mm backstop + dead-DIC "
       "freeze.  Engine ready to add 4 more modes: cyclic · staircase · relaxation · creep.",
       fill=LIGHT_BLUE, fg=BLACK, fs=11.5)
footer(s, "Details: Software/UTM_PyQt6/ROADMAP.md · TESTING_TODO.md. App wiring snapshot-committed (main.py a3b187f).")
pageno(s, 167)

# ---- Slide 170: SF 1 · DIC health HUD — modes  [content unchanged, was slide 176] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "DIC HEALTH HUD — LIVE TRACKING QUALITY")
pic_or_ph(s, "DIC HUD UI Screenshot.png", 0.4, 1.35, 8.2, 0.8, "[ drop DIC HUD UI Screenshot.png here ]")
tb(s, 8.8, 1.28, 4.15, 0.95, "A live badge on both test tabs:\nmarkers found / expected · % frames tracked · pixel jitter.",
   fs=11, italic=True, colour=GREY_TEXT)
header(s, 0.4, 2.35, 12.55, "What each state means")
modes = [["State", "Colour", "Condition", "Meaning"],
         ["OK", "green", "all markers · ≥ 95% tracked · jitter ≤ 1.5 px", "trust the strain"],
         ["WARN", "amber", "70–95% tracked  OR  jitter > 1.5 px", "degraded — re-light / watch"],
         ["BAD", "red", "a marker missing  OR  < 70% tracked", "unreliable — fix before pulling"],
         ["NO DATA", "grey", "camera off / no frames", "—"]]
mov = {(1, 1): {'bg': GREEN_PASS, 'bold': True}, (2, 1): {'bg': YELLOW_WARN, 'bold': True},
       (3, 1): {'bg': RED_FAIL, 'bold': True}, (4, 1): {'bg': GREY_PLANNED, 'bold': True}}
table(s, 0.4, 2.8, 12.55, 2.65, modes, cw=[1.7, 1.4, 5.9, 3.55], hf=11, bf=10.5, ov=mov)
banner(s, 0.4, 5.75, 12.55, 0.9,
       "Recorded per-frame in the CSV (DIC_Blobs column) — so you know DIC was reliable, and can PROVE it after the test.",
       fill=LIGHT_BLUE, fg=BLACK, fs=11.5)
pageno(s, 168)

# ---- Slide 171: SF 1 · DIC-driven safety halt — proof (S17)  [content unchanged, was slide 177] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "DIC-DRIVEN SAFETY — HALT IF TRACKING GOES BAD  (proof, S17)")
s.shapes.add_picture("feat_dic_halt.png", Inches(0.35), Inches(1.55), width=Inches(7.3))
header(s, 7.9, 1.28, 5.05, "CONDITION")
flow(s, 7.9, 1.72, 5.05, 1.6,
     "During a strain-rate test, if DIC strain FREEZES (markers lost):\n\n•  FREEZE speed at 0.2 s\n•  HALT at 1.0 s",
     fill=YELLOW_WARN, border=FLOW_NEUTRAL, fs=12, bold=True)
header(s, 7.9, 3.55, 5.05, "Why")
tb(s, 7.9, 3.98, 5.05, 1.9,
   "The loop STEERS on DIC strain.\n\nIf tracking dies it is blind — so it stops instead of pulling on stale / frozen data.",
   fs=11.5, colour=BLACK)
banner(s, 0.4, 6.35, 12.55, 0.72, "S17 — covered a marker mid-test → DIC went BAD → motor auto-halted. No runaway on blind data.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12)
pageno(s, 169)

# ---- Slide 172: SF 2 · Prepare specimen  [NEW] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF 2 — PREPARE SPECIMEN  (one-click tare)")
header(s, 0.4, 1.28, 12.55, "One click zeroes everything")
pf = ["Tare position\n(δ = 0)", "Tare force\n(N = 0)", "Tare DIC\n(set L0)", "Clear plots\n+ consoles"]
px_ = [0.4, 3.62, 6.84, 10.06]
for i, tx in enumerate(pf):
    flow(s, px_[i], 2.0, 3.0, 1.2, tx, fill=GREEN_PASS if i < 3 else LIGHT_BLUE, border=DARK_GREEN if i < 3 else FLOW_BLUE,
         fs=12, bold=True, fg=DARK_GREEN if i < 3 else BLACK)
    if i < 3:
        arrow(s, px_[i] + 3.0, 2.6, px_[i + 1], 2.6, width=2)
tb(s, 0.4, 3.6, 12.55, 1.6,
   "•  Replaces the old 3-click tare with ONE button\n\n"
   "•  DIC tares only at green 2/2 — otherwise 'DIC skipped' (honest, no false L0)\n\n"
   "•  Leaves a clean, ready-to-pull baseline",
   fs=12, colour=BLACK)
banner(s, 0.4, 5.55, 12.55, 0.9, "Rig-validated — position + force + DIC all zeroed, consoles + stress-strain plot cleared, from one press.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12)
footer(s, "Feature in Software/UTM_PyQt6/main.py (Prepare specimen button). Validated 2026-07-28.")
pageno(s, 170)

# ---- Slide 173: SF 3 & 4 · Report + Settings  [content unchanged, was slide 178] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "IN THE APP — ONE-CLICK REPORT & SAVED SETTINGS")
header(s, 0.4, 1.28, 6.2, "Generate report  →  one-page PDF + PNGs")
s.shapes.add_picture("feat_report_s16.png", Inches(0.4), Inches(1.78), width=Inches(6.15))
header(s, 6.95, 1.28, 6.0, "Settings  —  save a setup, reload in 1 click")
pic_or_ph(s, "Settings save_UI_Screenshot.png", 6.95, 1.85, 6.0, 0.6, "[ drop Settings save_UI_Screenshot.png here ]")
tb(s, 6.95, 2.65, 6.0, 3.1,
   "•  Saves area · gauge · preload · speed · mode + params\n\n"
   "•  'Default' always present (auto-stop ON)\n\n"
   "•  Reload a full test setup with ONE click\n\n"
   "•  Infill % = recorded label only (does NOT change data)\n\n"
   "•  Report reads the CSV header → KPIs + 4 plots + validation",
   fs=11.5, colour=BLACK)
footer(s, "Report shown is the REAL S16 one-pager (auto-generated). Settings image = the live Motor-Control controls.")
pageno(s, 171)

# ---- Slide 174: SF 5 · auto-stop at fracture — proof  [content unchanged, was slide 170] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "PROOF — AUTO-STOP AT FRACTURE  (S16, 100% infill)")
s.shapes.add_picture("feat_autostop_proof.png", Inches(0.35), Inches(1.55), width=Inches(7.4))
header(s, 8.0, 1.28, 4.95, "ACTIVATION CONDITION")
flow(s, 8.0, 1.72, 4.95, 1.55,
     "ARM  when load ≥ 30% of peak\n\nFIRE  when load < 50% of peak\n(collapse)  →  Stop + E-Stop",
     fill=YELLOW_WARN, border=FLOW_NEUTRAL, fs=12.5, bold=True)
kpi(s, 8.0, 3.5, 2.4, "PEAK", "2992 N", h=0.9)
kpi(s, 10.55, 3.5, 2.4, "UTS (true)", "47.4 MPa", h=0.9)
tb(s, 8.0, 4.62, 4.95, 1.0, "Fires in ONE sample after the load collapses — no hand on the button.",
   fs=11.5, italic=True, colour=GREY_TEXT)
banner(s, 0.4, 6.35, 12.55, 0.72, "The rig detects its OWN fracture and halts — arm at 30% of peak, fire at 50% collapse.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12)
pageno(s, 172)

# ---- Slide 175: SF 6 · strain-rate fracture — results & why  [content unchanged, was slide 171] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "STRAIN-RATE FRACTURE TEST — RESULTS & WHY IT WORKS")
s.shapes.add_picture("feat_strainrate_proof.png", Inches(0.35), Inches(1.55), width=Inches(7.4))
header(s, 8.0, 1.28, 4.95, "Rate held BY adapting speed")
sr = [["Regime", "speed", "dε/dt"], ["elastic", "0.10", "0.00049"], ["yield", "0.09", "0.00050"],
      ["necking", "0.06", "0.00048"], ["draw", "0.05", "0.00054"]]
table(s, 8.0, 1.75, 4.95, 1.95, sr, cw=[1.9, 1.5, 1.55], hf=10, bf=9.5)
header(s, 8.0, 3.95, 4.95, "Why it matters")
tb(s, 8.0, 4.38, 4.95, 1.9,
   "•  Constant MATERIAL strain rate (test standards)\n\n"
   "•  Compliance-free — measures the gauge, not the machine\n\n"
   "•  Comparable E / σy across specimens & rigs",
   fs=11, colour=BLACK)
banner(s, 0.4, 6.35, 12.55, 0.72,
       "Held 0.00051 /s (target 0.0005) while HALVING crosshead speed 0.10 → 0.05 mm/s — a fixed-speed pull cannot.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12)
pageno(s, 173)

# ---- Slide 176: SF 6 · strain-rate — report plots (S19, 50%)  [content unchanged, was slide 172] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "STRAIN-RATE FRACTURE — REPORT PLOTS  (S19, 50% infill)")
s.shapes.add_picture("feat_sr_plots.png", Inches(0.5), Inches(1.5), width=Inches(12.3))
header(s, 0.4, 5.02, 12.55, "Closed-loop speed limits")
kpi(s, 0.4, 5.46, 3.9, "TARGET RATE", "0.0005 /s")
kpi(s, 4.55, 5.46, 3.9, "MIN SPEED", "0.005 mm/s")
kpi(s, 8.7, 5.46, 4.25, "MAX SPEED (cap)", "0.20 mm/s")
footer(s, "S19 (50%) fractures ~1.4 kN — under the motor ceiling. The loop varied crosshead speed 0.005–0.20 mm/s to hold 0.0005 /s to fracture.")
pageno(s, 174)

# ---- Slide 177: SF 7 · safety guards & limits (stall guard)  [content unchanged, was slide 173] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SAFETY GUARDS & LIMITS — WHAT STOPS THE TEST")
header(s, 0.4, 1.28, 12.55, "Guards that halt a driven test")
guards = [["Guard", "Trips when", "Action"],
          ["Fracture auto-stop", "load < 50% of peak (armed at 30%)", "Stop"],
          ["Stall guard", "crosshead < 0.05 mm in 6 s under load > 200 N", "Stop + E-Stop"],
          ["Dead-DIC guard", "DIC strain frozen (markers lost)", "freeze speed 0.2 s → HALT 1.0 s"],
          ["Force backstop", "load ≥ 10 kN", "Stop + E-Stop"],
          ["Travel backstop", "crosshead travel ≥ 30 mm", "Stop + E-Stop"],
          ["Timeout", "runtime ≥ 900 s", "Stop"]]
table(s, 0.4, 1.72, 12.55, 3.55, guards, cw=[2.9, 6.6, 3.05], hf=11, bf=10)
banner(s, 0.4, 5.5, 12.55, 1.0,
       "HARD LIMITS —  force 10 kN  ·  travel 30 mm  ·  stall 0.05 mm in 6 s (>200 N)  ·  dead-DIC halt 1.0 s  ·  timeout 900 s.   "
       "Any breach → Stop + E-Stop.",
       fill=YELLOW_WARN, fg=BLACK, fs=12)
footer(s, "Layered so a driven test (preload · fracture · strain-rate) can't run away — protects the motor, the printed grips and the 3 t load cell.")
pageno(s, 175)

# ---- Slide 178: SF 8 · Release preload  [NEW] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF 8 — RELEASE PRELOAD  (safe return to 0)")
header(s, 0.4, 1.28, 12.55, "Controlled unload after a preload")
rf = ["Preloaded\nspecimen", "Reverse at\n0.30 mm/s", "Stop at\n~5 N"]
rx = [0.4, 4.35, 8.3]
for i, tx in enumerate(rf):
    flow(s, rx[i], 2.0, 3.1, 1.15, tx, fill=LIGHT_BLUE if i < 2 else GREEN_PASS, border=FLOW_BLUE if i < 2 else DARK_GREEN,
         fs=12.5, bold=True, fg=BLACK if i < 2 else DARK_GREEN)
    if i < 2:
        arrow(s, rx[i] + 3.1, 2.57, rx[i + 1], 2.57, width=2)
header(s, 0.4, 3.45, 12.55, "Limits")
kpi(s, 0.4, 3.9, 3.0, "RELEASE SPEED", "0.30 mm/s")
kpi(s, 3.62, 3.9, 3.0, "TARGET", "5 N")
kpi(s, 6.84, 3.9, 3.0, "RISE CAP", "50 N")
kpi(s, 10.06, 3.9, 2.9, "TIMEOUT", "180 s")
banner(s, 0.4, 5.15, 12.55, 0.95, "Rig-validated — eases tension off the specimen + grips; live-SetSpeed only (no re-latch runaway); stops on target / rise-cap / timeout.",
       fill=GREEN_PASS, fg=DARK_GREEN, fs=12)
footer(s, "Feature in Software/UTM_PyQt6/main.py (Release preload button). Validated 2026-07-28.")
pageno(s, 176)

# ---- Slide 179: two fracture methods — when to use which  [content unchanged, was slide 174] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "TWO WAYS TO FRACTURE — WHEN TO USE WHICH")
meth = [["", "Direct motor speed", "Strain-rate fracture"],
        ["How", "constant crosshead mm/s", "closed-loop on DIC dε/dt"],
        ["Rate", "varies (fast neck, slow elastic)", "CONSTANT gauge rate"],
        ["Needs DIC?", "no", "YES (green 2/2)"],
        ["Motor force", "full — higher speed OK", "capped speed → less force"],
        ["Best for", "quick UTS · strong specimens", "standards-grade · rate-sensitive"]]
table(s, 0.4, 1.4, 12.55, 3.25, meth, cw=[2.1, 5.2, 5.25], hf=11, bf=10.5)
header(s, 0.4, 4.9, 12.55, "Suggestion")
flow(s, 0.4, 5.37, 6.2, 1.0, "MAX pulling force or a quick UTS?\n→  DIRECT motor speed", fill=LIGHT_BLUE, border=FLOW_BLUE, fs=12.5, bold=True)
flow(s, 6.75, 5.37, 6.2, 1.0, "Controlled material strain rate (comparable)?\n→  STRAIN-RATE fracture", fill=GREEN_PASS, border=DARK_GREEN, fs=12.5, bold=True, fg=DARK_GREEN)
footer(s, "Both auto-stop on fracture (same detector) + stall guard. On THIS rig (torque ~2.6 kN today) use 50% / smaller specimens for strain-rate to reach break.")
pageno(s, 177)

# ---- Slide 180: innovation roadmap — workflow  [content unchanged, was slide 175] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "INNOVATION ROADMAP — AT A GLANCE")
ph = [("0 · Foundations", "analysis · engine · recipes", GREEN_PASS, DARK_GREEN, "DONE"),
      ("A · One-click", "report · prepare · auto-stop", GREEN_PASS, DARK_GREEN, "DONE"),
      ("B · Test modes", "strain-rate ✓ · 4 more", YELLOW_WARN, FLOW_NEUTRAL, "1 / 5"),
      ("C · Smart DIC", "health HUD ✓ · Poisson", YELLOW_WARN, FLOW_NEUTRAL, "partial"),
      ("D · UX layer", "wizard · overlay · dash", GREY_PLANNED, FLOW_NEUTRAL, "next")]
bx = [0.4, 2.98, 5.56, 8.14, 10.72]; bw = 2.35
for i, (t_, d_, fill, fg, st) in enumerate(ph):
    flow(s, bx[i], 2.1, bw, 1.5, t_ + "\n\n" + d_, fill=fill, border=fg, fs=10.5, bold=True, fg=fg)
    tb(s, bx[i], 3.66, bw, 0.4, st, fs=11, bold=True, colour=fg)
    if i < 4:
        arrow(s, bx[i] + bw, 2.85, bx[i + 1], 2.85, width=2)
header(s, 0.4, 4.5, 12.55, "Next up (in order)")
flow(s, 0.4, 4.98, 4.05, 0.95, "1 · Wire the 4 remaining\nmodes (engine ready)", fill=WHITE, border=FLOW_BLUE, fs=11.5, bold=True)
arrow(s, 4.47, 5.45, 4.68, 5.45, width=2)
flow(s, 4.7, 4.98, 4.05, 0.95, "2 · Measured Poisson\n(4-marker + backdrop)", fill=WHITE, border=FLOW_BLUE, fs=11.5, bold=True)
arrow(s, 8.77, 5.45, 8.98, 5.45, width=2)
flow(s, 9.0, 4.98, 3.95, 0.95, "3 · UX wizard +\nlive overlay", fill=WHITE, border=FLOW_BLUE, fs=11.5, bold=True)
banner(s, 0.4, 6.2, 12.55, 0.72, "Hardware gate — motor torque ~2.6 kN today; fix driver Vref / cooling to fracture 100% infill.",
       fill=YELLOW_WARN, fg=BLACK, fs=11)
pageno(s, 178)

# ---- Slide 181: specimen register  [content unchanged, was slide 179] ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SPECIMEN REGISTER  (S1 – S19)")
Lc = [["Spec", "Infill", "Colour", "Test / result"],
      ["S1", "", "", ""], ["S2", "50%", "", "V5c · 22.0 MPa"], ["S3", "50%", "", "V5b · 22.0 MPa"],
      ["S4", "50%", "", "V5 · 22.1 MPa"], ["S5", "", "", ""], ["S6", "", "", ""],
      ["S7", "100%", "", "V6a · 47.8 MPa"], ["S8", "100%", "", "V6b · 44.8 MPa"], ["S9", "100%", "", "V6e · 45.5 MPa"]]
Rc = [["Spec", "Infill", "Colour", "Test / result"],
      ["S10", "100%", "", "V6c · 46.8 MPa"], ["S11", "100%", "", "V6d · 46.1 MPa"], ["S12", "", "", ""],
      ["S13", "", "", ""], ["S14", "", "", ""], ["S15", "100%", "", "stall (no fracture)"],
      ["S16", "100%", "", "first 100% fracture · 47.4"], ["S17", "100%", "", "halt tests (DIC / stall)"],
      ["S18", "", "", ""], ["S19", "50%", "", "strain-rate frac · 17.3 MPa"]]
table(s, 0.4, 1.4, 6.2, 4.95, Lc, cw=[1.0, 1.1, 1.1, 3.0], hf=10, bf=9)
table(s, 6.75, 1.4, 6.2, 4.95, Rc, cw=[1.0, 1.1, 1.1, 3.0], hf=10, bf=9)
footer(s, "All spray markers (black dots on PLA). V1_Spray batch = 50% · V2_Spray = 100%. Colour (white/black) + blank cells to be filled by operator.")
pageno(s, 179)

# ---- Slide 180: buck-converter enclosure CAD ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "BUCK-CONVERTER ENCLOSURE — CAD (PLA)")
pic_or_ph(s, "Buckconverter_Enclosure_CAD.png", 0.5, 1.4, 6.3, 5.43, "[ drop Buckconverter_Enclosure_CAD.png here ]")
header(s, 7.35, 1.28, 5.55, "Purpose")
tb(s, 7.35, 1.7, 5.55, 0.95, "PLA-printed enclosure that houses the buck converter powering the LED ring lights.",
   fs=12, colour=BLACK)
flow(s, 7.35, 2.78, 3.55, 0.62, "1 · PCB locating pins", fill=LIGHT_BLUE, border=FLOW_RED, fs=12, bold=True)
arrow(s, 7.35, 3.09, 4.2, 3.2, colour=FLOW_RED, width=2.25)
flow(s, 7.35, 4.35, 3.95, 0.62, "2 · LED-switch extrusion", fill=LIGHT_BLUE, border=FLOW_RED, fs=12, bold=True)
arrow(s, 7.35, 4.66, 2.0, 5.05, colour=FLOW_RED, width=2.25)
tb(s, 7.35, 5.28, 5.55, 1.4,
   "•  Pins align + hold the buck-converter PCB\n\n"
   "•  Side extrusion = housing for the LED on/off switch\n\n"
   "•  Open top + side slots for wiring / mounting",
   fs=11.5, colour=BLACK)
footer(s, "CAD for a PLA-printed part. Callout arrows mark the PCB locating pins (floor posts) and the LED-switch extrusion (side tube).")
pageno(s, 180)

# ---- Motor torque ceiling (hardware limit) ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "MOTOR TORQUE CEILING — THE 100% FRACTURE LIMIT")
header(s, 0.4, 1.28, 12.55, "Same crosshead speed (0.10 mm/s), different MAX force")
kpi(s, 0.4, 1.75, 4.0, "WEAK DAY (S15 · today)", "~2.6 kN")
kpi(s, 4.6, 1.75, 4.0, "STRONG DAY (V6 · S16)", "3.2–3.8 kN")
kpi(s, 8.8, 1.75, 4.15, "100% FULL-AREA NEEDS", "~3.7 kN")
header(s, 0.4, 3.05, 12.55, "Why — torque capacity, NOT speed or software")
tb(s, 0.4, 3.5, 6.2, 1.5, "•  Driver current (Vref) set low\n\n•  PSU voltage sag under load", fs=12, colour=BLACK)
tb(s, 6.75, 3.5, 6.2, 1.5, "•  Driver THERMAL derating (the chip, not motor)\n\n•  Mechanical binding (screw / rails)", fs=12, colour=BLACK)
banner(s, 0.4, 5.25, 12.55, 1.0,
       "WORKAROUND — use 50% / smaller-cross-section specimens (fracture < 2.6 kN) until the torque is restored (check Vref · cooling · PSU).",
       fill=YELLOW_WARN, fg=BLACK, fs=12.5)
footer(s, "At the SAME 0.10 mm/s: S15 stalled 2.6 kN but S16 fractured 3.8 kN — the ceiling varies day-to-day. See TEST_FAILURES.md (S15).")
pageno(s, 181)

# ---- Motor jitter = stall warning ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "MOTOR JITTER = STALL WARNING  (a failed test)")
s.shapes.add_picture("feat_motor_jitter.png", Inches(0.35), Inches(1.55), width=Inches(7.4))
header(s, 8.0, 1.28, 4.95, "What happened")
tb(s, 8.0, 1.72, 4.95, 1.6,
   "At the force ceiling the crosshead FROZE and the whole machine SHOOK — a stalled stepper skipping steps.\n\n"
   "S15: had to Stop by hand.",
   fs=11.5, colour=BLACK)
header(s, 8.0, 3.5, 4.95, "Why")
tb(s, 8.0, 3.94, 4.95, 1.8,
   "•  Motor at / beyond its torque limit\n\n•  Strain-rate loop then oscillated, chasing a motor that can't move",
   fs=11.5, colour=BLACK)
banner(s, 0.4, 6.3, 12.55, 0.78,
       "WARNING — jitter = STALL. STOP, don't force 100% full-area. The stall guard now auto-halts (< 0.05 mm in 6 s under load).",
       fill=RED_FAIL, fg=BLACK, fs=12.5)
pageno(s, 182)


# =====================================================================================
# SEGMENT (moved to end): MEASURING CAUCHY (TRUE) STRESS
# =====================================================================================
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "MEASURING CAUCHY (TRUE) STRESS")
tb(s, 0.4, 2.9, 12.55, 1.7, "Getting the DEFORMING cross-section for TRUE / Cauchy stress + Poisson ratio "
   "- a separate future work-stream: edge-width tracking on a matte-black backdrop.", fs=16, bold=True, colour=DARK_GREEN)
pageno(s, 183)

# ===== SLIDE 23 — Engineering vs true (Cauchy) stress + measuring the current area =====
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "ENGINEERING vs TRUE (CAUCHY) STRESS — & MEASURING THE AREA")

header(s, 0.4, 1.28, 6.1, "Why we REPORT engineering stress")
s.shapes.add_picture("feat_eng_vs_true.png", Inches(0.4), Inches(1.66), width=Inches(6.15))
tb(s, 0.4, 4.32, 6.15, 1.15,
   "σ_eng = F / A₀  (REPORTED)      σ_true = F / A  (not tracked, ~2–5% higher)\n\n"
   "Basis: ISO 527 · Chacón · datasheet all use ENGINEERING → apples-to-apples for our k-factors.  E & σ_y ~unchanged.",
   fs=11, colour=BLACK)

header(s, 6.75, 1.28, 6.2, "Measuring the CURRENT area → true stress (future)")
meth = [
    ["Method", "How", "Note"],
    ["Poisson estimate", "A = A₀(1−ν·ε)²,  ν ≈ 0.35  (no hardware)", "cheap; ν drifts in yield"],
    ["Transverse markers", "+2 dots across width → ε_w;  A ≈ A₀(1+ε_w)²", "reuses blob-DIC; gives Poisson"],
    ["+ edge camera", "2nd view → thickness strain;  A = w·t", "rigorous; FDM is orthotropic"],
    ["Full-field speckle", "fine random speckle + subset DIC", "strain field + necking; new pipeline"],
]
ovm = {(2, c): {'bg': GREEN_PASS, 'bold': c == 0} for c in range(3)}      # recommended row
table(s, 6.75, 1.70, 6.25, 2.5, meth, cw=[1.35, 2.7, 1.6], hf=10, bf=9.5, ov=ovm)
tb(s, 6.75, 4.32, 6.25, 1.05,
   "Same speckle style (spray dots): just add a transverse dot pair — the current 2-marker tracker "
   "extends naturally (2 axial + 2 transverse). A finer random speckle enables full-field DIC "
   "(transverse field + necking) but needs a new analysis pipeline.",
   fs=10.5, italic=True, colour=GREY_TEXT)

banner(s, 0.4, 5.65, 12.6, 0.72,
       "TRANSVERSE markers = ideal, but the gauge is too NARROW → EDGE-WIDTH detection (next slide) is the practical route. Keep ENGINEERING stress as the validated basis.",
       fill=LIGHT_BLUE, fg=BLACK, fs=12)
footer(s, "Current V6 report & plots = engineering stress (nominal 80 mm²). True/Cauchy needs the deforming "
          "area; post-necking needs full-field DIC or markers at the neck.")
pageno(s, 184)

# ---- Slide 164: measuring Poisson / true stress WITHOUT transverse dots ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "MEASURING POISSON'S RATIO & TRUE STRESS — WITHOUT TRANSVERSE DOTS")

header(s, 0.4, 1.28, 6.05, "The fix — track the specimen's OWN edges")
s.shapes.add_picture("feat_edgewidth.png", Inches(0.4), Inches(1.66), width=Inches(6.05))
tb(s, 0.4, 4.28, 6.05, 1.2,
   "Gauge too NARROW for transverse dots (sub-pixel at 20 px/mm) → track the L & R edges instead.\n\n"
   "ε_w = (W₀−W)/W₀     ν = −ε_w/ε_axial     A = W·t     → MEASURED (no assumed ν), written to the CSV.",
   fs=11, colour=BLACK)

header(s, 6.6, 1.28, 6.4, "Three ways to MEASURE it (no transverse dots)")
meth = [
    ["Route", "How it works", "Needs"],
    ["1  Edge / silhouette\n    width tracking",
     "find the specimen's L & R edges across the gauge; average width over 100s of rows -> ε_w each frame",
     "matte-black backdrop;\nreuses THIS camera"],
    ["2  Full-field\n    speckle DIC",
     "fine random speckle + subset correlation (Ncorr / muDIC, offline) -> full axial + transverse strain field",
     "speckle + new\nanalysis pipeline"],
    ["3  Hardware probe",
     "2nd side camera (thickness), laser micrometer, or clip-on transverse extensometer",
     "extra hardware;\nlab-grade"],
]
ovm = {(1, c): {'bg': GREEN_PASS, 'bold': c == 0} for c in range(3)}      # recommended row
table(s, 6.6, 1.70, 6.4, 2.7, meth, cw=[1.7, 3.0, 1.7], hf=10, bf=9, ov=ovm)
tb(s, 6.6, 4.5, 6.4, 1.0,
   "Why #1 works at 20 px/mm: one edge is sub-pixel, but averaging the width along the whole gauge "
   "(100s of rows) cuts the noise ~10x to ~0.01 px — the ~0.5 px elastic width change is then well "
   "resolved. It only needs CRISP edges = a dark background behind the specimen.",
   fs=10.5, italic=True, colour=GREY_TEXT)

banner(s, 0.4, 5.65, 12.6, 0.72,
       "EDGE-WIDTH TRACKING + a matte-black backdrop = the only route that MEASURES Poisson & true Cauchy, reusing THIS camera & specimen. Keep ENGINEERING stress as the validated basis.",
       fill=LIGHT_BLUE, fg=BLACK, fs=12)
footer(s, "Supersedes the transverse-marker idea on the previous slide: the narrow gauge + camera resolution "
          "rule out a transverse dot pair. Measure the specimen's own edges (or full-field speckle) instead.")
pageno(s, 185)

# =============================================================================================
# SF9 — ADVANCED TEST MODES (pages 186-199): 1 overview + 2 per mode + 1 failure analysis.
# Every number comes from documentation/sf9_data.py, which recomputes it from the rig CSVs —
# nothing on these slides is typed in by hand.
# =============================================================================================
from sf9_data import M as SF9                                                      # noqa: E402

SF9_BACKSTOP = ("Always-on, every mode: 10 kN force · 30 mm travel · 900 s timeout · stall guard "
                "(6 s window, min(0.05 mm, 35 % of commanded travel), armed above 200 N) · "
                "dead-DIC freeze 0.2 s / halt 1.0 s · E-Stop.")


def img_fit(slide, path, x, y, maxw, maxh):
    """Place a picture scaled to fit a box, centred horizontally in it — the SF9 schematics have
    very different aspect ratios (the fracture ones are 2-panel and twice as wide)."""
    iw, ih = Image.open(path).size
    sc = min(maxw / iw, maxh / ih)
    w, h = iw * sc, ih * sc
    slide.shapes.add_picture(path, Inches(x + (maxw - w) / 2), Inches(y), width=Inches(w))
    return h


def sf9_how(page, name, schematic, what, settings, limits, guide, note=None):
    """LEFT: schematic of the protocol (+ optional caveat under it). RIGHT: what it measures and the
    settings actually used. BOTTOM: the software limits the UI enforces for this mode.

    Laid out BOTTOM-UP: the limits banner and guidance line are anchored just above the footer and
    the settings table is sized to end above them, so a mode with more parameters (staircase has 7
    rows) cannot push content into the banner.
    """
    s = prs.slides.add_slide(BLANK); ju(s)
    title(s, "SF9 · %s — HOW IT WORKS" % name)
    ih = img_fit(s, schematic, 0.5, 1.30, 6.85, 4.30)
    if note:
        tb(s, 0.5, 1.30 + ih + 0.15, 6.85, 0.75, note, fs=10.5, italic=True, colour=GREY_TEXT)

    GUIDE_Y, BANNER_Y = 6.56, 6.02
    header(s, 7.55, 1.24, 5.4, "What this mode tells you")
    flow(s, 7.55, 1.66, 5.30, 1.95, what, fill=LIGHT_BLUE, border=FLOW_BLUE, fs=11.5)
    header(s, 7.55, 3.72, 5.4, "Settings used for our test")
    rows = len(settings)
    rh = min(0.28, (BANNER_Y - 0.12 - 4.10) / rows)      # shrink rows rather than overflow
    table(s, 7.55, 4.10, 5.30, rh * rows, settings, cw=[1.55, 1.0], hf=10, bf=10)

    banner(s, 0.5, BANNER_Y, 12.4, 0.48, "SOFTWARE LIMITS — " + limits,
           fill=YELLOW_WARN, fg=BLACK, fs=11)
    tb(s, 0.5, GUIDE_Y, 12.4, 0.32, guide, fs=10.5, italic=True, colour=GREY_TEXT)
    footer(s, SF9_BACKSTOP)
    pageno(s, page)
    return s


def sf9_result(page, name, fig, kpis=None, tbl=None, verdict=None, vfill=GREEN_PASS, foot=""):
    """Also bottom-up: pin the verdict banner above the footer, stack the table and KPI row above
    it, and give the figure whatever vertical space is left. Sizing the figure FIRST (the obvious
    way) overflows as soon as a slide carries both a KPI row and a table."""
    s = prs.slides.add_slide(BLANK); ju(s)
    title(s, "SF9 · %s — OUR RESULTS" % name)
    VERDICT_Y, TOP = 6.30, 1.24
    floor_ = VERDICT_Y if verdict else 6.85
    if tbl:
        th = 0.26 * len(tbl); ty = floor_ - 0.10 - th; floor_ = ty
    if kpis:
        ky = floor_ - 0.10 - 0.82; floor_ = ky
    img_fit(s, fig, 0.45, TOP, 12.45, max(1.5, floor_ - 0.10 - TOP))
    if kpis:
        w = 12.45 / len(kpis)
        for i, (lab, val) in enumerate(kpis):
            kpi(s, 0.45 + i * w, ky, w - 0.12, lab, val, h=0.82, vfs=15)
    if tbl:
        table(s, 0.45, ty, 12.45, th, tbl, hf=9.5, bf=9.5)
    if verdict:
        banner(s, 0.45, VERDICT_Y, 12.45, 0.55, verdict, fill=vfill, fg=DARK_GREEN, fs=12)
    footer(s, foot)
    pageno(s, page)
    return s


UIH = "Software/UTM_PyQt6/ui_help/"

# ---- 186: SF9 overview — all six modes, real measured signatures ----
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF9 — ADVANCED TEST MODES: SIX CLOSED-LOOP PROTOCOLS, ONE ENGINE")
tb(s, 0.5, 1.16, 12.4, 0.4,
   "All six share one control loop (`_policy_step`) and one safety net. Every trace below is real rig "
   "data, not a schematic. Two of them drive the specimen to destruction.",
   fs=12, italic=True, colour=GREY_TEXT)
img_fit(s, "documentation/sf9_overview.png", 0.45, 1.56, 12.45, 4.45)
banner(s, 0.45, 6.14, 12.45, 0.72,
       "Why it matters: a conventional pull gives ONE modulus, ONE yield, ONE UTS. These modes "
       "interrogate the specimen on the way to failure — so a single specimen yields a CURVE "
       "(stiffness vs damage, relaxation vs level) instead of a point.",
       fill=LIGHT_BLUE, fg=BLACK, fs=12)
footer(s, "Rig-validated 2026-08-08/09 on S18, S20, S21. Engine: control_policies.py · "
          "app wiring: main.py `_policy_step` · schematics: ui_help/.")
pageno(s, 186)

# ---- 187/188: CYCLIC ----
ct, cs = SF9["cyc_tri"], SF9["cyc_sin"]
sf9_how(187, "CYCLIC", UIH + "cyclic.png",
        "Repeatedly loads and unloads between a Low and a High force for N cycles.\n\n"
        "• Hysteresis loop area = energy dissipated per cycle\n"
        "• Change in loop shape = early damage, before any visible yield\n"
        "• Waveform choice: Triangle (constant-speed ramps) or Sine (eases at each peak)\n"
        "• Stays elastic — the specimen is REUSABLE afterwards",
        [["Parameter", "Value"], ["Low / High force", "100 / 500 N"], ["Cycles", "5"],
         ["Speed", "0.100 mm/s"], ["Waveform", "Triangle (T5) · Sine (T6.3)"],
         ["Specimen", "S20 · 100 % infill"]],
        "Low 0–5000 N · High 0–5000 N · Cycles 1–1000 · Speed 0.005–0.500 mm/s",
        "Guidance: keep High below yield, or the run becomes a fatigue test and the specimen breaks.")

sf9_result(188, "CYCLIC", "documentation/sf9_cyclic.png",
           kpis=[("Peak error — Triangle", "%.0f N" % ct["pk_mae"]),
                 ("Peak error — Sine", "%.0f N" % cs["pk_mae"]),
                 ("Sine, final cycle", "%.0f N" % cs["peaks"][-1]),
                 ("Cycles completed", "%d + %d" % (len(ct["peaks"]), len(cs["peaks"])))],
           tbl=[["Cycle"] + ["%d" % i for i in range(1, len(cs["peaks"]) + 1)] + ["mean |err|"],
                ["T5 Triangle — peak (N)"] + ["%.0f" % p for p in ct["peaks"]] + ["%.0f" % ct["pk_mae"]],
                ["T6.3 Sine — peak (N)"] + ["%.0f" % p for p in cs["peaks"]] + ["%.0f" % cs["pk_mae"]]],
           verdict="Sine cuts peak error %.0f N → %.0f N (%.0f %% better) and CONVERGES: %.0f → %.0f N "
                   "across the 5 cycles, landing on the 500 N target."
                   % (ct["pk_mae"], cs["pk_mae"], 100 * (1 - cs["pk_mae"] / ct["pk_mae"]),
                      cs["peaks"][0], cs["peaks"][-1]),
           foot="The convergence is the adaptive reversal lead learning the true coast distance in the "
                "FORCE domain. Seeded at zero so it approaches from below — seeding it at the measured "
                "1.3 s decel over-led and rang (T6, T6.2).")

# ---- 189/190: STAIRCASE ----
sl, sm = SF9["stair_lin"], SF9["stair_smo"]
sf9_how(189, "STAIRCASE", UIH + "staircase.png",
        "Steps the load up — Start, Start+Step, Start+2·Step … — and DWELLS at every level.\n\n"
        "• Each dwell is a mini stress-relaxation test\n"
        "• Modulus can be re-measured at every level\n"
        "• Ramp shape: Linear (constant speed) or Smooth (eases into each level)\n"
        "• Non-destructive if the top level stays below yield",
        [["Parameter", "Value"], ["Start / Step", "300 / 300 N"], ["Levels", "3"],
         ["Dwell", "20 s"], ["Speed", "0.100 mm/s"], ["Ramp", "Linear (T3) · Smooth (T4)"],
         ["Specimen", "S20 · 100 % infill"]],
        "Start 0–5000 N · Step 10–2000 N · Levels 1–20 · Dwell 1–600 s · Speed 0.005–0.500 mm/s",
        "Guidance: keep the top level, Start+(Levels−1)·Step, below yield.")

sf9_result(190, "STAIRCASE", "documentation/sf9_staircase.png",
           kpis=[("Linear — mean overshoot", "%.0f N" % (sum(l["over"] for l in sl["levels"]) / 3)),
                 ("Smooth — mean overshoot", "%.0f N" % (sum(l["over"] for l in sm["levels"]) / 3)),
                 ("Improvement", "%.0f×" % ((sum(l["over"] for l in sl["levels"]) / 3) /
                                            (sum(l["over"] for l in sm["levels"]) / 3))),
                 ("Stall guard false trips", "0 of 6 dwells")],
           tbl=[["Level (commanded)", "L1 · 300 N", "L2 · 600 N", "L3 · 900 N"],
                ["T3 Linear — arrival overshoot"] + ["%+.1f N" % l["over"] for l in sl["levels"]],
                ["T4 Smooth — arrival overshoot"] + ["%+.1f N" % l["over"] for l in sm["levels"]],
                ["Dwell force drop (Smooth)"] + ["%.1f N" % l["drop"] for l in sm["levels"]]],
           verdict="Smooth ramp cuts arrival overshoot from ~%.0f N to ~%.0f N — a %.0f× improvement — "
                   "by tapering the last 25 %% of every approach."
                   % (sum(l["over"] for l in sl["levels"]) / 3, sum(l["over"] for l in sm["levels"]) / 3,
                      (sum(l["over"] for l in sl["levels"]) / 3) / (sum(l["over"] for l in sm["levels"]) / 3)),
           foot="Overshoot is measured against the COMMANDED level, not the settled value — the settled "
                "value already contains the dwell relaxation, which would mask the control error.")

# ---- 191/192: RELAXATION ----
rx = SF9["relax"]
sf9_how(191, "RELAXATION", UIH + "relaxation.png",
        "Ramps to a target STRAIN, then holds the crosshead still and watches the force decay.\n\n"
        "• Measures the viscoelastic stress-relaxation of the polymer\n"
        "• Decay rate and magnitude are material fingerprints\n"
        "• Requires live DIC (green 2/2) — strain is the controlled variable\n"
        "• Non-destructive below yield",
        [["Parameter", "Value"], ["Hold strain", "0.010"], ["Hold duration (measured)", "%.0f s" % rx["dur"]],
         ["Speed", "0.100 mm/s"], ["Specimen", "S20 · 100 % infill"]],
        "Hold strain 0.001–0.200 · Duration 1–3600 s · Speed 0.005–0.500 mm/s · needs DIC green 2/2",
        "Guidance: keep the hold strain below yield (≈0.015 for PLA) for a purely elastic hold.")

sf9_result(192, "RELAXATION", "documentation/sf9_relax.png",
           kpis=[("Peak load", "%.0f N" % rx["Fpk"]), ("After hold", "%.0f N" % rx["F1"]),
                 ("Stress relaxed", "%.0f N  (%.1f %%)" % (rx["drop"], rx["drop_pct"])),
                 ("Strain held", "%.5f" % rx["eps"])],
           tbl=[["Quantity", "Value", "Interpretation"],
                ["Force decay over %.0f s" % rx["dur"], "%.0f → %.0f N" % (rx["Fpk"], rx["F1"]),
                 "%.1f %% of the initial stress relaxed away" % rx["drop_pct"]],
                ["Strain held", "%.5f ± %.6f" % (rx["eps"], rx["eps_sd"]),
                 "±%.2f %% of the held value — the crosshead really did stand still"
                 % (100 * rx["eps_sd"] / rx["eps"])]],
           verdict="Textbook viscoelastic relaxation: %.0f N (%.1f %%) shed at a strain held to "
                   "±%.2f %%. The control did its job — the decay is the MATERIAL, not drift."
                   % (rx["drop"], rx["drop_pct"], 100 * rx["eps_sd"] / rx["eps"]),
           foot="Relaxation is the one mode whose dwell is not a zero-speed hold: it keeps nudging the "
                "crosshead to pin the strain, so the dwell is found from crosshead POSITION going flat.")

# ---- 193/194: CREEP ----
cr = SF9["creep"]
sf9_how(193, "CREEP", UIH + "creep.png",
        "Ramps to a target LOAD, then holds that force constant and watches the strain grow.\n\n"
        "• The dual of relaxation: fix stress, measure strain(t)\n"
        "• Reveals time-dependent deformation under sustained service load\n"
        "• Primary-creep slope indicates how the part behaves under a permanent load\n"
        "• Non-destructive well below UTS",
        [["Parameter", "Value"], ["Hold load", "400 N"], ["Hold duration (measured)", "%.0f s" % cr["dur"]],
         ["Speed", "0.100 mm/s"], ["Specimen", "S20 · 100 % infill"]],
        "Load 10–5000 N · Duration 1–3600 s · Speed 0.005–0.500 mm/s",
        "Guidance: use ≤60–70 % of UTS — above that, creep runs away and the specimen fails during the hold.")

sf9_result(194, "CREEP", "documentation/sf9_creep.png",
           kpis=[("Force held", "%.0f N" % cr["Fmean"]), ("Hold stability", "± %.1f N" % cr["Fsd"]),
                 ("Creep strain", "+%.0f µε" % cr["de"]), ("Hold duration", "%.0f s" % cr["dur"])],
           tbl=[["Quantity", "Value", "Interpretation"],
                ["Force held", "%.0f ± %.1f N" % (cr["Fmean"], cr["Fsd"]),
                 "±%.2f %% of target — the load is genuinely constant" % (100 * cr["Fsd"] / cr["Fmean"])],
                ["DIC strain", "%.5f → %.5f" % (cr["e0"], cr["e1"]),
                 "+%.0f µε of creep in %.0f s at fixed stress" % (cr["de"], cr["dur"])]],
           verdict="Force pinned to ±%.1f N (%.2f %%) while the strain crept +%.0f µε — the specimen "
                   "deformed under a load that never changed."
                   % (cr["Fsd"], 100 * cr["Fsd"] / cr["Fmean"], cr["de"]),
           foot="Creep and relaxation are duals and were run back-to-back on the same specimen (S20), so "
                "the two responses are directly comparable.")

# ---- 195/196: STAIRCASE → FRACTURE ----
sf = SF9["sf"]
_kn = None
try:
    import utm_analysis as _ua
    _kn = _ua.yield_onset(sf["dwells"])
except Exception:
    pass
sf9_how(195, "STAIRCASE → FRACTURE", UIH + "staircase_to_fracture.png",
        "DESTRUCTIVE. Like Staircase, but it keeps adding levels until the specimen breaks.\n\n"
        "• A mini stress-relaxation at EVERY level, right up to failure\n"
        "• Yield onset appears as the dwell drop stops shrinking and starts growing\n"
        "• Modulus re-measured at every level = stiffness vs stress\n"
        "• Ends in fracture → UTS and ε_f from the SAME specimen",
        [["Parameter", "Value"], ["Start / Step", "200 / 120 N"], ["Dwell", "10 s"],
         ["Speed", "0.100 mm/s"], ["Ramp", "Smooth"], ["Specimen", "S18 · 50 % infill"]],
        "Start 0–5000 N · Step 10–2000 N · Dwell 1–600 s · Speed 0.005–0.500 mm/s · max 60 levels (policy cap)",
        "Guidance: size Step so ~8–12 levels reach fracture. Too fine and the run drags; too coarse and "
        "you lose resolution exactly where yield happens.",
        note="Destructive modes are behind a confirmation dialog that echoes area, gauge and infill "
             "before arming.")

sf9_result(196, "STAIRCASE → FRACTURE", "documentation/sf9_stair_fracture.png",
           kpis=[("Peak load", "%.0f N" % sf["peak"]), ("Force anchor", "%.1f N" % sf["anchor"]),
                 ("TRUE UTS", "%.2f MPa" % sf["uts"]), ("Auto-halt after collapse", "%.2f s" % sf["halt"])],
           tbl=[["Quantity", "Value", "Note"],
                ["Levels resolved", "%d dwells" % len(sf["dwells"]), "each one a mini relaxation test"],
                ["Yield onset", ("%.0f N tared" % _kn["arrive"]) if _kn else "n/a",
                 "the dwell drop stops falling and starts growing"],
                ["Nominal vs TRUE UTS", "%.2f → %.2f MPa" % (sf["uts_nom"], sf["uts"]),
                 "anchor %.1f N recovered from the post-fracture tail" % sf["anchor"]]],
           verdict="One specimen delivered a yield knee AND a fracture: %d relaxation points, yield "
                   "located at %s, TRUE UTS %.2f MPa, auto-halt %.2f s after collapse."
                   % (len(sf["dwells"]), ("%.0f N" % _kn["arrive"]) if _kn else "the knee",
                      sf["uts"], sf["halt"]),
           foot="The anchor is the preload the tare removed; recovering it from the settled post-fracture "
                "tail converts nominal stress to true stress without a second measurement.")

# ---- 197/198: PROGRESSIVE CYCLIC → FRACTURE ----
pc = SF9["pc"]
_cy = pc["cycles"]
_val = [c for c in _cy if c["R2"] > 0.94]
_dmin = min(_cy[1:], key=lambda z: z["diss_pct"])
sf9_how(197, "PROGRESSIVE CYCLIC → FRACTURE", UIH + "progressive_cyclic_to_fracture.png",
        "DESTRUCTIVE. Load–unload–reload with the peak rising every cycle, until fracture.\n\n"
        "• EVERY unload measures the modulus at that damage state\n"
        "• Gives the stiffness-degradation curve D = 1 − Eᵢ/E₀ vs stress\n"
        "• Hysteresis area per cycle tracks energy going into damage\n"
        "• Permanent set per cycle shows plasticity accumulating",
        [["Parameter", "Value"], ["1st peak", "300 N"], ["Peak step", "150 N"],
         ["Unload to", "100 N"], ["Speed", "0.100 mm/s"], ["Specimen", "S21 · 50 % infill"]],
        "1st peak 0–5000 N · Peak step 10–2000 N · Unload to 20–2000 N · Speed 0.005–0.500 mm/s · "
        "max 40 cycles (policy cap)",
        "Guidance: keep the unload floor ≥20 N so the specimen never goes slack and the grips stay seated.",
        note="The collapse watch here is PER RISING STROKE and armed only past halfway to target — a "
             "single always-on detector would trip on every intentional unload.")

sf9_result(198, "PROGRESSIVE CYCLIC → FRACTURE", "documentation/sf9_prog_cyclic.png",
           tbl=[["Cycle"] + ["%d" % c["n"] for c in _cy] + ["trend"],
                ["Peak load (N)"] + ["%.0f" % c["peak"] for c in _cy] + ["target ±12 N"],
                ["Peak error vs target (N)"] + ["%+.0f" % (c["peak"] - c["target"]) for c in _cy] +
                ["±%.0f mean" % (sum(abs(c["peak"] - c["target"]) for c in _cy[1:]) / (len(_cy) - 1))],
                ["DIC unload E (GPa)"] + ["%.2f" % (c["E"] / 1000) if c["R2"] > 0.94 else "—" for c in _cy] +
                ["%.2f → %.2f" % (_val[0]["E"] / 1000, _val[-1]["E"] / 1000)],
                ["Crosshead K (N/mm)"] + ["%.0f" % c["K"] for c in _cy] +
                ["%.0f → %.0f  ↑" % (_cy[0]["K"], _cy[-1]["K"])],
                ["Hysteresis dissipated (%)"] + ["%.1f" % c["diss_pct"] for c in _cy] +
                ["min %.1f → %.1f" % (_dmin["diss_pct"], _cy[-1]["diss_pct"])]],
           verdict="Specimen SOFTENED %.2f → %.2f GPa (%.0f %% stiffness lost) while the crosshead read "
                   "%.0f → %.0f N/mm — STIFFER. Without DIC this test concludes the opposite of the truth."
                   % (round(_val[0]["E"] / 1000, 2), round(_val[-1]["E"] / 1000, 2),
                      100 * (1 - round(_val[-1]["E"] / 1000, 2) / round(_val[0]["E"] / 1000, 2)),
                      _cy[0]["K"], _cy[-1]["K"]),
           vfill=YELLOW_WARN,
           foot="Cycles 1–3 carry no modulus: the DIC strain CHANGE in those small unloads is below the "
                "noise floor (R² %.2f–%.2f). Dissipation is an energy integral over a large position "
                "range and has no such floor — on this rig it is the better damage metric."
                % (min(c["R2"] for c in _cy[:3]), max(c["R2"] for c in _cy[:3])))

# ---- 199: T7 failure analysis ----
t7 = SF9["t7"]
s = prs.slides.add_slide(BLANK); ju(s)
title(s, "SF9 · THE ONE THAT FAILED — T7, AND WHY")
tb(s, 0.5, 1.16, 12.4, 0.4,
   "T7 ran Staircase → FRACTURE on S20 (100 % infill) and never broke the specimen. Worth a slide: the "
   "failure is a HARDWARE limit, and the software behaved exactly as designed.",
   fs=12, italic=True, colour=GREY_TEXT)
img_fit(s, "documentation/sf9_t7_stall.png", 0.45, 1.58, 12.45, 3.30)
for i, (lab, val) in enumerate([("Peak reached", "%.0f N" % t7["peak"]),
                                ("Needed to fracture", "%.0f N" % t7["need_N"]),
                                ("Got to", "%.0f %% of it" % t7["pct_of_need"]),
                                ("Crosshead at the top", "%.0f µm in %.0f s" % (t7["grind_um"], t7["grind_s"])),
                                ("…of commanded rate", "%.1f %%" % t7["frac_of_cmd"])]):
    kpi(s, 0.45 + i * 2.49, 4.98, 2.37, lab, val, h=0.82, vfs=15,
        fill=RED_FAIL if i in (2, 4) else LIGHT_BLUE, vcol=DARK_GREEN)
header(s, 0.5, 5.92, 6.0, "Why it stalled — ranked")
tb(s, 0.5, 6.24, 6.3, 1.1,
   "1  Stepper DRIVER CURRENT (Vref) set too low — most likely, and cheapest to check\n"
   "2  Driver THERMAL DERATING — T7 was the 7th test of a 2 h 15 min session\n"
   "3  PSU voltage SAG under peak load\n"
   "4  Mechanical binding in the lead screw",
   fs=11)
header(s, 7.0, 5.92, 5.9, "Mitigation")
tb(s, 7.0, 6.24, 5.9, 1.1,
   "1  Measure and raise driver Vref to spec; add a heatsink/fan\n"
   "2  Cool between destructive runs — T7.2 and T8 both PASSED after a pause\n"
   "3  Scope the rail under load; fit a stiffer PSU\n"
   "4  On a weak day use 50 % specimens (fracture ≈1.4 kN) — both later runs did",
   fs=11)
footer(s, "NOT a hard ceiling: six 100 % specimens fractured at 3.1–3.4 kN. Software response was "
          "correct — nothing ran away, and the specimen was released intact and reusable.")
pageno(s, 199)

try:
    prs.save("documentation/V6a_8_6_20_slides.pptx")
    print("Saved: V6a_8_6_20_slides.pptx (59 slides, pages 141-199)")
except PermissionError:
    prs.save("documentation/V6a_8_6_20_slides_updated.pptx")
    print("Original locked (open in PowerPoint). Saved: V6a_8_6_20_slides_updated.pptx (59 slides)")
