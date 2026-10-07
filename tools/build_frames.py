"""Rebuild a character's expression frames from two AI-generated reference sheets.

    pip install -r tools/requirements-frames.txt
    python tools/build_frames.py nuri            # writes assets/characters/nuri/
    python tools/build_frames.py sera /tmp/out   # or any output folder

Each character has a base sheet (large bust-up figure for the neutral face) and
an expression sheet (3x2 grid: happy, thinking, surprised / sad, angry, shy).
Every frame is aligned on the midpoint between the eyes and scaled by eye
distance, so switching expressions does not make the character jump.

All coordinates below are in sheet pixels, measured by hand on a zoomed
coordinate grid. If you regenerate a sheet, re-measure them before running.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from rembg import new_session, remove
from scipy import ndimage

from key_alpha import FADE_ROWS, key_alpha

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "characters"
W, H = 405, 344                   # output frame size
EYE_OUT = (202.5, 187.5)          # where the midpoint between the eyes lands
SS = 6                            # supersampling for hand-drawn edits
EXPRESSION_ORDER = ("happy", "thinking", "surprised", "sad", "angry", "shy")
FULL_W, FULL_H = 405, 480          # full-body frames (same width as the bust frames)
FULL_FIGURE_H = 462                # figure height inside a full-body frame

CHARACTERS = {
    "nuri": dict(
        eye_px=0.767 * 89,  # output eye distance; every character uses this to share one scale
        base=dict(
            # 2000x1116 upscale of the original 1024x572 sheet; coordinates scaled by ~1.953.
            sheet="reference_sheet.webp", crop=(1016, 0, 1953, 1116), mid=(1468.8, 360.0), dist=125,
            talk=((1473.6, 437.0), (19.5, 15.6)),  # mouth center and size in sheet px
            blink=((1363.3, 1439.5, 335.6, 386.3), (1500.0, 1582.0, 335.6, 386.3)), skin=(1471, 363),
        ),
        # Full-body figure on the left of the base sheet: cut box, figure top/bottom, eyes
        # (iris centers, measured at 10x; nose, mouth and chin must sit at the same multiples
        # of the eye distance as on the bust, or the pasted face will not line up).
        # face: oval bounding the pasted face, in eye-distance units (half width, top, bottom);
        # per-expression bottoms stop above a hand at the chin (Nuri's pen).
        full=dict(crop=(100, 0, 680, 1116), top=131, bottom=1089, mid=(369.5, 195), dist=59,
                  face=dict(oval=(0.9, -0.55, 0.98), bottom={"thinking": 0.85})),
        expressions=dict(
            sheet="reference_expressions.webp", dist=89,
            columns=((0, 690), (690, 1300), (1300, 2000)), rows=((0, 560), (560, 1116)),
            mids=dict(happy=(396, 248), thinking=(999, 247), surprised=(1597.5, 251.75),
                      sad=(388, 778), angry=(1000, 779), shy=(1600, 775.5)),
            # Closed mouths get a talking frame (center in sheet px, size in output px);
            # open ones (happy, surprised, shy) already read as speech.
            # Head size/position fix after eye alignment: (scale, dx, dy) in output px, found by
            # overlaying each frame's hair silhouette and face skin on neutral (best IoU).
            adjust=dict(happy=(1.045, 0, -2), thinking=(1.055, 4.5, 0), surprised=(1.03, 1.5, 0),
                        sad=(0.97, 1.5, -2), angry=(0.96, 1.5, -0.5), shy=(0.955, -1.5, -4.5)),
            talk=dict(thinking=((1001.5, 297), (10, 8)), sad=((388, 835.5), (10, 8))),
        ),
    ),
    "sera": dict(
        eye_px=0.767 * 89,
        base=dict(
            # Eye distance calibrated by head width against the expression panels (raw: 125).
            sheet="reference_sheet.webp", crop=(1040, 0, 1960, 1116), mid=(1473.5, 352.5), dist=137,
            talk=((1472.5, 434), (19.5, 15.6)),
            blink=((1366, 1442, 330, 374), (1505, 1584, 330, 374)), skin="ring", lash=3.4, feather=2.4,
        ),
        # Iris centers measured at 10x; dist fits nose, mouth and chin to the bust proportions.
        full=dict(crop=(120, 0, 620, 1116), top=52, bottom=1096, mid=(371.5, 190), dist=50,
                  face=dict(oval=(0.9, -0.55, 1.0), bottom={"thinking": 0.9, "angry": 0.95})),
        # Background removal left a faint gray haze around the dark hair (ahoge tip):
        # drop alpha below the floor and stretch the rest so edges end crisply.
        # Semi-transparent pixels brighter than haze_lum are background haze (the hair's real
        # edges are dark), so they are dropped too.
        alpha=dict(floor=60, gain=1.35, haze_lum=75),
        expressions=dict(
            # 2000x1117 upscale of the original 1024x572 sheet; coordinates scaled by ~1.953.
            sheet="reference_expressions.webp", dist=82,
            columns=((8, 664), (671, 1329), (1337, 1992)), rows=((4, 556), (562, 1113)),
            mids=dict(happy=(347.7, 212.9), thinking=(1014.8, 213.3), surprised=(1665.2, 213.3),
                      sad=(338.9, 773.3), angry=(1008.8, 773.3), shy=(1676.3, 773.3)),
            # Head size/position fix after eye alignment: (scale, dx, dy) in output px, found by
            # overlaying each frame's hair silhouette and face skin on neutral (best IoU).
            adjust=dict(happy=(1.0, 2, 2), thinking=(1.02, 5.5, 2.5), surprised=(1.005, -1.5, 2),
                        sad=(1.005, -2.5, 2), angry=(1.005, 0, 0), shy=(1.0, 3.5, 0)),
            talk=dict(thinking=((1008.8, 263.6), (12, 9)), sad=((343.8, 826.0), (12, 9))),
        ),
    ),
    "yuki": dict(
        # Second sheet set (2026-10-07), redrawn in the shared style; the first set was semi-real.
        eye_px=0.767 * 89,
        base=dict(
            sheet="reference_sheet.webp", crop=(1080, 0, 1960, 1116), mid=(1497.5, 362), dist=137,
            talk=((1505, 458), (21, 15)),
            blink=((1388, 1470, 343, 392), (1525, 1610, 343, 392)), skin=(1500, 385), lash=3.0, feather=2.0,
        ),
        # Sheet background decorations (calendar, notes) are separate blobs and get dropped.
        full=dict(crop=(180, 40, 570, 1116), top=72, bottom=1098, mid=(374.5, 191), dist=59,
                  face=dict(oval=(0.95, -0.55, 1.05))),
        expressions=dict(
            # Each panel has a white frame line: crop inside it. Rows also stop above the labels.
            sheet="reference_expressions.webp",
            columns=((90, 664), (712, 1290), (1336, 1914)), rows=((50, 506), (608, 1022)),
            mids=dict(happy=(375.5, 240), thinking=(1005, 233), surprised=(1625, 237),
                      sad=(376.5, 810), angry=(997.5, 810), shy=(1618.5, 810)),
            dist=dict(happy=91, thinking=84, surprised=80, sad=97, angry=95, shy=93),
            # Happy's closed eyes sit wider than open ones would, so its eye distance overstates the size.
            adjust=dict(happy=(1.12, 2.5, 7), thinking=(1.035, 7, 2), surprised=(0.99, 2.5, 5.5),
                        sad=(1.03, 2.5, 0.5), angry=(1.005, 2.5, 0.5), shy=(0.985, 2, 0.5)),
            talk=dict(happy=((377, 287), (10, 7)), thinking=((1002, 286), (10, 7)), sad=((377, 870), (10, 7)),
                      shy=((1620, 872), (10, 7))),
        ),
    ),
    "akane": dict(
        eye_px=0.767 * 89,
        base=dict(
            sheet="reference_sheet.webp", crop=(1060, 0, 1960, 1116), mid=(1487.5, 364), dist=125,
            talk=((1490, 440), (19.5, 15.6)),
            blink=((1395, 1450, 341, 381), (1526, 1580, 341, 381)), skin="lerp", lash=3.0, feather=1.5,
        ),
        full=dict(crop=(150, 20, 620, 1116), top=51, bottom=1095, mid=(379, 194), dist=52,
                  face=dict(oval=(0.9, -0.55, 1.0), bottom={"thinking": 0.85, "shy": 0.85})),
        expressions=dict(
            # Rows stop above the name labels; a stray check mark in the thinking panel is a
            # separate blob and is dropped by the cleanup.
            sheet="reference_expressions.webp",
            columns=((100, 690), (700, 1300), (1310, 1950)), rows=((15, 455), (555, 1000)),
            mids=dict(happy=(400, 245), thinking=(1002, 247), surprised=(1596, 248),
                      sad=(388, 773), angry=(998, 773), shy=(1604, 776)),
            dist=dict(happy=80, thinking=82, surprised=78, sad=90, angry=83, shy=95),
            # Hair silhouette weighs more than skin here: angry's puffed cheeks widen the face.
            adjust=dict(happy=(1.01, 0, -6), thinking=(1.03, 3.5, -3.5), surprised=(0.98, -0.5, -2.5),
                        sad=(1.08, -2, -8), angry=(0.99, 0, -8), shy=(1.135, 3.5, -6)),
            talk=dict(happy=((400, 300), (10, 7)), thinking=((998, 298), (10, 7)), sad=((390, 830), (10, 7))),
        ),
    ),
    "shizuku": dict(
        eye_px=0.767 * 89,
        base=dict(
            sheet="reference_sheet.webp", crop=(1080, 0, 1960, 1116), mid=(1495.5, 370), dist=139,
            talk=((1497.5, 459), (21, 15)),
            blink=((1390, 1460, 345, 390), (1534, 1602, 345, 390)), skin=(1497, 372), lash=3.0, feather=2.0,
        ),
        # The sheet background has sticky notes and a calendar; they are separate blobs and
        # are dropped with everything else that does not touch the figure.
        full=dict(crop=(226, 40, 560, 1116), top=76, bottom=1093, mid=(375.25, 189), dist=55.5,
                  face=dict(oval=(0.9, -0.55, 1.0))),
        expressions=dict(
            sheet="reference_expressions.webp",
            columns=((100, 700), (720, 1320), (1340, 1960)), rows=((20, 470), (570, 1005)),
            mids=dict(happy=(355, 238), thinking=(997.5, 243), surprised=(1647, 245),
                      sad=(352.5, 778), angry=(1001, 771), shy=(1652.5, 772)),
            dist=dict(happy=97, thinking=95, surprised=91.5, sad=98, angry=92, shy=95),
            adjust=dict(happy=(0.995, 0, -4.5), thinking=(0.97, -2.5, -1), surprised=(0.93, -0.5, 1),
                        sad=(1.01, -0.5, -1.5), angry=(0.955, 0.5, -6.5), shy=(0.995, 0, -4.5)),
            talk=dict(happy=((357, 304), (10, 7)), thinking=((1001, 306), (10, 7)), sad=((353, 840), (10, 7)),
                      shy=((1650, 838), (10, 7))),
        ),
    ),
    "hinata": dict(
        eye_px=0.767 * 89,
        base=dict(
            # Neutral is already an open-mouthed grin, so it gets no talking frame (talk=None).
            # The sheet background (window frame, calendar, icons) does not touch the figure.
            sheet="reference_sheet.webp", crop=(1060, 0, 1960, 1116), mid=(1497.5, 367.5), dist=139, talk=None,
            blink=((1382, 1457, 340, 392), (1537, 1622, 338, 390)), skin=(1520, 383), lash=3.0, feather=2.0,
        ),
        # Background removal leaves a faint gray haze in the gap between the jaw and the hair;
        # the hair's real edges are dark outlines, so bright semi-transparent pixels are haze.
        alpha=dict(floor=60, gain=1.35, haze_lum=90),
        full=dict(crop=(185, 40, 610, 1116), top=72, bottom=1098, mid=(378, 191), dist=57,
                  face=dict(oval=(0.9, -0.55, 1.0))),
        expressions=dict(
            sheet="reference_expressions.webp",
            columns=((100, 700), (700, 1335), (1335, 1960)), rows=((10, 512), (565, 1070)),
            # Thinking rolls the irises up and aside: its mid is the eye shapes' center.
            mids=dict(happy=(345, 249), thinking=(995, 247), surprised=(1620.5, 248),
                      sad=(351, 788), angry=(990, 793), shy=(1628, 792)),
            dist=dict(happy=90, thinking=95, surprised=85, sad=92, angry=90, shy=90),
            # Thinking's panel is drawn 8% smaller; found by the silhouette overlay (onion skin).
            adjust=dict(happy=(1.02, 1, -1), thinking=(1.08, 4.5, -2), surprised=(0.9625, 1, -2),
                        sad=(1.015, 1, -5), angry=(0.9925, -0.5, -1), shy=(0.9925, -0.5, -3)),
            talk=dict(thinking=((990, 305), (10, 7)), sad=((352, 850), (10, 7))),
        ),
    ),
    "sakura": dict(
        eye_px=0.767 * 89,
        base=dict(
            sheet="reference_sheet.webp", crop=(1060, 0, 1960, 1116), mid=(1485, 370), dist=140,
            talk=((1487, 454), (21, 15)),
            blink=((1370, 1448, 337, 387), (1522, 1610, 337, 387)), skin=(1470, 390), lash=3.0, feather=2.0,
        ),
        # The tea tray in the full-body figure's hand stays (it is part of the same blob).
        full=dict(crop=(130, 40, 670, 1116), top=88, bottom=1095, mid=(374.5, 193), dist=56,
                  face=dict(oval=(0.9, -0.55, 1.0))),
        expressions=dict(
            sheet="reference_expressions.webp",
            columns=((80, 685), (685, 1315), (1315, 1960)), rows=((20, 516), (590, 1056)),
            # Happy has closed eyes and thinking looks aside: their mids are the eye shapes' centers.
            mids=dict(happy=(365, 240), thinking=(999, 245), surprised=(1628, 242),
                      sad=(362.5, 813), angry=(1000, 812), shy=(1637.5, 812)),
            dist=dict(happy=96, thinking=98, surprised=90, sad=95, angry=94, shy=95),
            # Happy and thinking panels are drawn about 10% smaller (silhouette and face skin agree).
            adjust=dict(happy=(1.095, 3, -4.5), thinking=(1.135, 6.5, 1.5), surprised=(1.02, -1.5, -4),
                        sad=(1.0075, 0.5, -2.5), angry=(1.0, 0.5, -3), shy=(1.0075, 1.5, -2.5)),
            talk=dict(happy=((365, 295), (10, 7)), thinking=((1010, 300), (10, 7)), sad=((365, 875), (10, 7)),
                      shy=((1638, 873), (10, 7))),
        ),
    ),

    "reika": dict(
        eye_px=0.767 * 89,
        base=dict(
            # The sheet background (window frames, sticky notes, calendars, gears) does not touch
            # the bust and is dropped as separate blobs.
            sheet="reference_sheet.webp", crop=(1060, 0, 1960, 1116), mid=(1500, 368), dist=140,
            talk=((1502, 458), (21, 15)),
            blink=((1368, 1460, 340, 390), (1540, 1637, 340, 390)), skin=(1500, 388), lash=3.0, feather=2.0,
        ),
        full=dict(crop=(200, 40, 640, 1116), top=88, bottom=1095, mid=(378.25, 192.25), dist=56.5,
                  face=dict(oval=(0.9, -0.55, 1.0))),
        expressions=dict(
            sheet="reference_expressions.webp",
            columns=((80, 685), (685, 1318), (1318, 1960)), rows=((15, 512), (580, 1060)),
            # Happy has closed eyes and thinking looks aside: their mids are the eye shapes' centers.
            mids=dict(happy=(373, 220), thinking=(1003, 230), surprised=(1627.5, 230),
                      sad=(375, 788), angry=(1001.5, 790), shy=(1635, 790)),
            dist=dict(happy=103, thinking=102, surprised=89, sad=94, angry=97, shy=94),
            # Happy and thinking panels are drawn about 15% smaller; shy looks aside, so its eye
            # mid sits left of the face center.
            adjust=dict(happy=(1.15, -2.5, -6.5), thinking=(1.155, 2.5, 3), surprised=(1.0, 2, 1.5),
                        sad=(0.985, -1, 0.5), angry=(1.03, 1.5, 3.5), shy=(0.9925, 6, 2.5)),
            talk=dict(thinking=((1003, 285), (10, 7)), sad=((378, 850), (10, 7)), angry=((1002, 850), (10, 7)),
                      shy=((1630, 850), (10, 7))),
        ),
    ),

}

def place(img, mid, k):
    """Scale by k and move `mid` to EYE_OUT, in premultiplied alpha to avoid dark fringes.

    LANCZOS with a float source box keeps sub-pixel eye alignment and stays crisp when
    shrinking HD sheets. The source is padded first because the box may reach past it.
    """
    pad = int(max(W, H) / k) + 2
    padded = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    padded.paste(img, (pad, pad))
    left, top = mid[0] + pad - EYE_OUT[0] / k, mid[1] + pad - EYE_OUT[1] / k
    box = (left, top, left + W / k, top + H / k)
    return padded.convert("RGBa").resize((W, H), Image.LANCZOS, box=box).convert("RGBA")

def to_out(p, mid, k):
    return ((p[0] - mid[0]) * k + EYE_OUT[0], (p[1] - mid[1]) * k + EYE_OUT[1])

def harden(img, floor, gain, haze_lum=None):
    a = np.array(img)
    alpha = a[..., 3].astype(float)
    if haze_lum is not None:
        haze = (alpha < 200) & (a[..., :3].mean(-1) > haze_lum)
        alpha[haze] = 0
    a[..., 3] = np.clip((alpha - floor) * gain * 255 / (255 - floor), 0, 255).astype(np.uint8)
    return Image.fromarray(a)

def largest(img):
    """Keep only the biggest opaque blob (drops sheet decorations rembg left behind)."""
    a = np.array(img)
    alpha = a[..., 3]
    labels, n = ndimage.label(alpha > 40)
    if n:
        sizes = ndimage.sum(np.ones_like(alpha), labels, range(1, n + 1))
        keep = ndimage.binary_dilation(labels == (np.argmax(sizes) + 1), iterations=4)
        alpha[~keep] = 0
    return Image.fromarray(a)

def clean(img, fade=40, alpha_fix=None):
    if alpha_fix:
        img = harden(img, **alpha_fix)
    a = np.array(largest(img))
    alpha = a[..., 3]
    ramp = np.linspace(1, 0, fade) ** 1.5
    alpha[H - fade:] = (alpha[H - fade:] * ramp[:, None]).astype(np.uint8)
    a[..., 3] = alpha
    return Image.fromarray(a)

def edit(img, box, draw_fn, soft_mask=False, feather=1.2):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    region = img.crop((x0, y0, x1, y1)).resize(((x1 - x0) * SS, (y1 - y0) * SS), Image.LANCZOS)
    draw_fn(ImageDraw.Draw(region), lambda x, y: ((x - x0) * SS, (y - y0) * SS))
    region = region.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    if soft_mask:
        mask = Image.new("L", region.size, 0)
        ImageDraw.Draw(mask).ellipse([1, 1, region.width - 2, region.height - 2], fill=255)
        region.putalpha(Image.composite(region.getchannel("A"), Image.new("L", region.size, 0), mask.filter(ImageFilter.GaussianBlur(feather))))
    out = img.copy(); out.alpha_composite(region, (x0, y0)); return out

def talk(img, center, size):
    cx, cy = center; w, h = size
    def fn(d, p):
        d.ellipse([*p(cx - w / 2, cy - h / 2), *p(cx + w / 2, cy + h / 2)], fill=(150, 62, 78, 255),
                  outline=(90, 40, 50, 255), width=int(0.9 * SS))
        d.chord([*p(cx - w * 0.3, cy), *p(cx + w * 0.3, cy + h / 2)], 180, 360, fill=(235, 130, 140, 255))
    return edit(img, (cx - w, cy - h, cx + w, cy + h), fn)

def blink(img, eyes, skin, lash=2.2, feather=1.2):
    """Paint each eye over with skin and draw a closed lash line.

    skin is one RGBA color, or "ring": the median skin tone just around each eye,
    which blends better with eyelid shading.
    """
    out = img
    if skin == "lerp":
        return lerp_blink(img, eyes, lash, feather)
    for (ex0, ex1, ytop, ybot) in eyes:
        color = skin if skin != "ring" else ring_color(img, (ex0, ytop, ex1, ybot))
        def fn(d, p, ex0=ex0, ex1=ex1, ytop=ytop, ybot=ybot, color=color):
            d.ellipse([*p(ex0 + 1, ytop + 2), *p(ex1 - 1, ybot + 1)], fill=color)
            d.arc([*p(ex0 + 1, ytop + 1), *p(ex1 - 1, ybot - 1)], 20, 160, fill=(70, 45, 60, 255), width=int(lash * SS))
        out = edit(out, (ex0 - 2, ytop - 2, ex1 + 2, ybot + 4), fn, soft_mask=True, feather=feather)
    return out

def lerp_blink(img, eyes, lash, feather):
    """Close the eyes by filling each eye oval row by row with a blend of the skin just left
    and right of it. Follows blush and shading gradients that a flat color would not."""
    a = np.array(img).astype(float)
    for (ex0, ex1, ytop, ybot) in eyes:
        cx, cy, rx, ry = (ex0 + ex1) / 2, (ytop + ybot) / 2 + 1, (ex1 - ex0) / 2 + 1, (ybot - ytop) / 2 + 2
        fill = a.copy()
        rows = []
        for y in range(int(cy - ry), int(cy + ry) + 2):
            half = rx * np.sqrt(max(0.0, 1 - ((y - cy) / ry) ** 2))
            if half >= 1:
                xl, xr = int(np.floor(cx - half)) - 2, int(np.ceil(cx + half)) + 2
                rows.append((y, xl, xr, a[y, xl - 2:xl + 1, :3].mean(0), a[y, xr:xr + 3, :3].mean(0)))
        # Lash wings and hair also sit beside the eye: a sample that is not light, warm skin
        # (dark lashes, gray-white hair) takes the nearest skin row's.
        for side in (3, 4):
            good = [i for i, row in enumerate(rows) if row[side].mean() > 200 and row[side][0] - row[side][2] > 6]
            for i, row in enumerate(rows):
                if good and i not in good:
                    nearest = min(good, key=lambda j: abs(j - i))
                    rows[i] = row[:side] + (rows[nearest][side],) + row[side + 1:]
        for y, xl, xr, left, right in rows:
            t = np.linspace(0, 1, xr - xl + 1)[:, None]
            fill[y, xl:xr + 1, :3] = left * (1 - t) + right * t
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
        m = np.array(mask.filter(ImageFilter.GaussianBlur(feather)))[..., None] / 255
        a = a * (1 - m) + fill * m
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    for (ex0, ex1, ytop, ybot) in eyes:
        def fn(d, p, ex0=ex0, ex1=ex1, ytop=ytop, ybot=ybot):
            d.arc([*p(ex0 + 1, ytop + 1), *p(ex1 - 1, ybot - 1)], 20, 160, fill=(70, 45, 60, 255), width=int(lash * SS))
        out = edit(out, (ex0 - 2, ytop - 2, ex1 + 2, ybot + 4), fn)
    return out

def ring_color(img, box):
    """Median of light skin pixels in a band around an eye box (output px)."""
    a = np.array(img).astype(int)
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    band = (d > 1.1) & (d < 2.2) & (a[..., 3] > 240) & (a[..., :3].sum(-1) > 620)
    return tuple(int(v) for v in np.median(a[band][:, :3], axis=0)) + (255,)


def build_full(config, folder, session, frames, out):
    """Full-body frames: the sheet's full-body figure with each bust frame's face pasted on.

    The full-body face has the bust face's proportions, so each bust frame's whole face
    (bangs and eyes, then the skin with eyes, nose, mouth and blush) is scaled by eye
    distance and aligned on the eyes. Talking and blinking carry over; hair, headset arms,
    hands and sleeves around the face come from the full-body figure.
    """
    full = config["full"]
    sheet = Image.open(folder / config["base"]["sheet"]).convert("RGB")
    ox, oy = full["crop"][:2]
    figure = remove(sheet.crop(full["crop"]), session=session).convert("RGBA")
    if config.get("alpha"):
        figure = harden(figure, **config["alpha"])
    if full.get("erase"):
        a = np.array(figure)
        for x0, y0, x1, y1 in full["erase"]:
            box = a[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
            box[box[..., 3] < 200] = 0
        figure = Image.fromarray(a)
    figure = largest(figure)
    k = FULL_FIGURE_H / (full["bottom"] - full["top"])
    eye = ((full["mid"][0] - ox) * k, (full["mid"][1] - oy) * k)
    # Center horizontally on the eyes, feet a few pixels above the frame bottom.
    left = eye[0] - FULL_W / 2
    top = (full["bottom"] - oy) * k - (FULL_H - 6)
    scaled = figure.convert("RGBa").resize((round(figure.width * k), round(figure.height * k)), Image.LANCZOS).convert("RGBA")
    base = Image.new("RGBA", (FULL_W, FULL_H), (0, 0, 0, 0))
    base.alpha_composite(scaled, (round(-left), round(-top)))
    eye_full = (eye[0] - round(left), eye[1] - round(top))

    face_k = full["dist"] * k / config["eye_px"]
    d, (ex, ey) = config["eye_px"], EYE_OUT

    def face_shape(frame, oval):
        """The face itself inside the oval: bangs and eyes above the cheekbones, below that only
        the skin blob with its holes (eyes, mouth, tears) filled. Hair, headset arms, sleeves
        and hands that reach in from the edge stay out, so the full-body figure's own show."""
        a = np.array(frame).astype(int)
        r, g, b, alpha = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
        # Warm and light, but not yellowish cream (Nuri's shy sleeves reach the mouth).
        cream = (g - b >= 12) & (r - g < 18)
        skin = (alpha > 200) & (r - b > 6) & (r >= g) & ((r + g + b) / 3 > 150) & ~cream & oval
        skin = ndimage.binary_opening(skin, iterations=1)
        labels, _ = ndimage.label(skin)
        seed = labels[int(ey + 0.45 * d), int(ex)]
        if seed:
            skin = labels == seed
        skin = ndimage.binary_fill_holes(ndimage.binary_closing(skin, iterations=2))
        yy = np.arange(H)[:, None]
        upper = oval & (yy < ey + 0.3 * d)
        # Shrunk a little so outlines along the edge (sleeve cuffs, the jaw) come from the
        # full-body figure, which draws the jaw in the same place.
        return ndimage.binary_erosion(skin, iterations=2) | upper

    def masked(img, mask):
        img = img.copy()
        img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", img.size, 0), mask))
        return img

    out = out / "full"
    out.mkdir(parents=True, exist_ok=True)
    for frame_name, frame in frames.items():
        expression = frame_name.split("_")[0]
        half, top, bottom = full["face"]["oval"]
        bottom = full["face"].get("bottom", {}).get(expression, bottom)
        oval = Image.new("L", (W, H), 0)
        ImageDraw.Draw(oval).ellipse([ex - half * d, ey + top * d, ex + half * d, ey + bottom * d], fill=255)
        mask = Image.fromarray(face_shape(frame, np.array(oval) > 0).astype(np.uint8) * 255)
        face = masked(frame, mask.filter(ImageFilter.GaussianBlur(1.2)))
        result = base.copy()
        size = (round(W * face_k), round(H * face_k))
        small = face.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
        result.alpha_composite(small, (round(eye_full[0] - EYE_OUT[0] * face_k), round(eye_full[1] - EYE_OUT[1] * face_k)))
        key_alpha(result).save(out / f"{frame_name}.png", optimize=True)


def build(name, out):
    config = CHARACTERS[name]
    folder = ASSETS / name
    session = new_session("isnet-anime")
    frames = {}

    # Neutral: the large bust-up figure on the base sheet.
    base = config["base"]
    sheet = Image.open(folder / base["sheet"]).convert("RGB")
    ox, oy = base["crop"][:2]
    rgb = sheet.crop(base["crop"])
    shift = lambda p: (p[0] - ox, p[1] - oy)
    mid = shift(base["mid"])
    k = config["eye_px"] / base["dist"]
    neutral = place(remove(rgb, session=session).convert("RGBA"), mid, k)
    frames["neutral"] = neutral
    if base["talk"]:
        (mouth, (mw, mh)) = base["talk"]
        frames["neutral_talk"] = talk(neutral, to_out(shift(mouth), mid, k), (mw * k, mh * k))
    if base["skin"] in ("ring", "lerp"):
        skin = base["skin"]
    else:
        sx, sy = shift(base["skin"])
        skin = tuple(int(v) for v in np.array(rgb)[sy, sx]) + (255,)
    eyes = []
    for ex0, ex1, ytop, ybot in base["blink"]:
        (a0, b0), (a1, b1) = to_out(shift((ex0, ytop)), mid, k), to_out(shift((ex1, ybot)), mid, k)
        eyes.append((a0, a1, b0, b1))
    frames["neutral_blink"] = blink(neutral, eyes, skin, base.get("lash", 2.2), base.get("feather", 1.2))

    # Expressions: one panel each from the 3x2 expression sheet.
    exp = config["expressions"]
    sheet = Image.open(folder / exp["sheet"]).convert("RGB")
    for index, expression in enumerate(EXPRESSION_ORDER):
        dist = exp["dist"][expression] if isinstance(exp["dist"], dict) else exp["dist"]
        k = config["eye_px"] / dist
        (x0, x1), (y0, y1) = exp["columns"][index % 3], exp["rows"][index // 3]
        panel = remove(sheet.crop((x0, y0, x1, y1)), session=session).convert("RGBA")
        mid = (exp["mids"][expression][0] - x0, exp["mids"][expression][1] - y0)
        scale, dx, dy = exp.get("adjust", {}).get(expression, (1, 0, 0))
        k *= scale
        mid = (mid[0] - dx / k, mid[1] - dy / k)
        frames[expression] = place(panel, mid, k)
        if expression in exp["talk"]:
            (mx, my), size = exp["talk"][expression]
            frames[f"{expression}_talk"] = talk(frames[expression], to_out((mx - x0, my - y0), mid, k), size)

    out.mkdir(parents=True, exist_ok=True)
    cleaned = {frame: clean(img, alpha_fix=config.get("alpha")) for frame, img in frames.items()}
    for frame, img in cleaned.items():
        key_alpha(img, FADE_ROWS).save(out / f"{frame}.png", optimize=True)
    if "full" in config:
        build_full(config, folder, session, cleaned, out)
    return sorted(frames)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CHARACTERS:
        sys.exit(f"usage: python tools/build_frames.py {{{'|'.join(CHARACTERS)}}} [output folder]")
    character = sys.argv[1]
    print(build(character, Path(sys.argv[2]) if len(sys.argv) > 2 else ASSETS / character))
