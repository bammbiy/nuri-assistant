"""Rebuild Nuri's expression frames from the two AI-generated reference sheets.

    pip install pillow numpy scipy rembg onnxruntime
    python tools/build_nuri_frames.py

Reads assets/characters/nuri/reference_sheet.webp (neutral, 1024x572) and
reference_expressions.jpg (six expressions, 3x2 grid). The crop boxes and eye
positions below were measured on those exact sheets; if you regenerate a sheet,
re-measure them (eye midpoint and eye distance) before running.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from rembg import new_session, remove
from scipy import ndimage

NURI = Path(__file__).resolve().parents[1] / "assets" / "characters" / "nuri"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else NURI
PANEL_K = 1.5                     # output px per expression-sheet px
W, H = 405, 344                   # 270 x ~229 sheet px
EYE_OUT = (202.5, 187.5)          # where the midpoint between the eyes lands
SS = 6                            # supersampling for hand-drawn edits

session = new_session("isnet-anime")
sheet = Image.open(NURI / "reference_sheet.webp").convert("RGB")
neutral_rgb = sheet.crop((520, 0, 1000, 572))  # bust-up figure on the right
neutral_cut = remove(neutral_rgb, session=session)
expressions = Image.open(NURI / "reference_expressions.jpg").convert("RGB")

# (eye midpoint, eye distance) measured by hand on a coordinate grid
NEUTRAL = dict(mid=(232, 184.5), dist=64)
PANEL_DIST = 45.5  # same sheet, same scale: use one value for every panel
PANELS = {
    "happy": (202, 126), "thinking": (170.5, 127), "surprised": (136, 127.5),
    "sad": (198, 114), "angry": (169.5, 114.5), "shy": (137.5, 115),
}

def place(img, mid, k):
    """Scale by k and move `mid` to EYE_OUT, in premultiplied alpha to avoid dark fringes."""
    left, top = mid[0] - EYE_OUT[0] / k, mid[1] - EYE_OUT[1] / k
    box = (left, top, left + W / k, top + H / k)
    return img.convert("RGBa").transform((W, H), Image.EXTENT, box, Image.BICUBIC).convert("RGBA")

def to_out(p, mid, k):
    return ((p[0] - mid[0]) * k + EYE_OUT[0], (p[1] - mid[1]) * k + EYE_OUT[1])

def clean(img, fade=40):
    a = np.array(img)
    alpha = a[..., 3]
    labels, n = ndimage.label(alpha > 40)
    if n:
        sizes = ndimage.sum(np.ones_like(alpha), labels, range(1, n + 1))
        keep = ndimage.binary_dilation(labels == (np.argmax(sizes) + 1), iterations=2)
        alpha[~keep] = 0
    ramp = np.linspace(1, 0, fade) ** 1.5
    alpha[H - fade:] = (alpha[H - fade:] * ramp[:, None]).astype(np.uint8)
    a[..., 3] = alpha
    return Image.fromarray(a)

def edit(img, box, draw_fn, soft_mask=False):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    region = img.crop((x0, y0, x1, y1)).resize(((x1 - x0) * SS, (y1 - y0) * SS), Image.LANCZOS)
    draw_fn(ImageDraw.Draw(region), lambda x, y: ((x - x0) * SS, (y - y0) * SS))
    region = region.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    if soft_mask:
        mask = Image.new("L", region.size, 0)
        ImageDraw.Draw(mask).ellipse([1, 1, region.width - 2, region.height - 2], fill=255)
        region.putalpha(Image.composite(region.getchannel("A"), Image.new("L", region.size, 0), mask.filter(ImageFilter.GaussianBlur(1.2))))
    out = img.copy(); out.alpha_composite(region, (x0, y0)); return out

def talk(img, center, size):
    cx, cy = center; w, h = size
    def fn(d, p):
        d.ellipse([*p(cx - w / 2, cy - h / 2), *p(cx + w / 2, cy + h / 2)], fill=(150, 62, 78, 255),
                  outline=(90, 40, 50, 255), width=int(0.9 * SS))
        d.chord([*p(cx - w * 0.3, cy), *p(cx + w * 0.3, cy + h / 2)], 180, 360, fill=(235, 130, 140, 255))
    return edit(img, (cx - w, cy - h, cx + w, cy + h), fn)

def blink(img, eyes, skin):
    out = img
    for (ex0, ex1, ytop, ybot) in eyes:
        def fn(d, p, ex0=ex0, ex1=ex1, ytop=ytop, ybot=ybot):
            d.ellipse([*p(ex0 + 1, ytop + 2), *p(ex1 - 1, ybot + 1)], fill=skin)
            d.arc([*p(ex0 + 1, ytop + 1), *p(ex1 - 1, ybot - 1)], 20, 160, fill=(70, 45, 60, 255), width=int(2.2 * SS))
        out = edit(out, (ex0 - 2, ytop - 2, ex1 + 2, ybot + 4), fn, soft_mask=True)
    return out

frames = {}
# Neutral: from the first sheet, re-framed to match the expression sheet.
k = PANEL_K * PANEL_DIST / NEUTRAL["dist"]
mid = NEUTRAL["mid"]
neutral_src = neutral_cut.convert("RGBA")
skin = tuple(int(v) for v in np.array(neutral_rgb)[186, 233]) + (255,)
neutral = place(neutral_src, mid, k)
frames["neutral"] = neutral
frames["neutral_talk"] = talk(neutral, to_out((234.5, 224), mid, k), (10 * k, 8 * k))
eyes = []
for ex0, ex1, ytop, ybot in ((178, 217, 172, 198), (248, 290, 172, 198)):
    (a0, b0), (a1, b1) = to_out((ex0, ytop), mid, k), to_out((ex1, ybot), mid, k)
    eyes.append((a0, a1, b0, b1))
frames["neutral_blink"] = blink(neutral, eyes, skin)

# Expressions: one panel each from the expression sheet.
for name, pmid in PANELS.items():
    index = list(PANELS).index(name)
    col, row = index % 3, index // 3
    box = (col * 341, row * 286, min((col + 1) * 341 + 1, 1024), (row + 1) * 286)
    panel = remove(expressions.crop(box), session=session).convert("RGBA")
    frames[name] = place(panel, pmid, PANEL_K)
# Mouths that are closed in the art get a talking frame; open ones already read as speech.
frames["thinking_talk"] = talk(frames["thinking"], to_out((170, 149), PANELS["thinking"], PANEL_K), (9, 7))
frames["sad_talk"] = talk(frames["sad"], to_out((196.5, 141.5), PANELS["sad"], PANEL_K), (9, 7))

OUT.mkdir(parents=True, exist_ok=True)
for name, img in frames.items():
    clean(img).save(OUT / f"{name}.png", optimize=True)
print(sorted(frames))
