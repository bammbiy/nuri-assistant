"""Rebuild a character's expression frames from two AI-generated reference sheets.

    pip install pillow numpy scipy rembg onnxruntime
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
        # Full-body figure on the left of the base sheet: cut box, figure top/bottom, eyes.
        full=dict(crop=(100, 0, 680, 1116), top=131, bottom=1089, mid=(369.5, 195), dist=59,
                  # Shy's mouth sits lower and its sleeve cuffs reach the mouth corners: use a
                  # lower, wider mouth area and paint the cuff lace/outlines in it with skin.
                  # Polygons are in eye-distance units relative to the eye midpoint.
                  mouth={"shy": (0.34, 0.36, 0.88)},
                  cover={"shy": [
                      [(-0.42, 0.58), (-0.15, 0.6), (-0.15, 0.76), (-0.06, 0.9), (-0.42, 0.9)],
                      [(0.27, 0.6), (0.42, 0.6), (0.42, 0.9), (0.12, 0.9), (0.2, 0.79), (0.27, 0.74)],
                      [(-0.42, 0.82), (0.42, 0.82), (0.42, 0.95), (-0.42, 0.95)],
                  ]}),
        expressions=dict(
            sheet="reference_expressions.webp", dist=89,
            columns=((0, 690), (690, 1300), (1300, 2000)), rows=((0, 560), (560, 1116)),
            mids=dict(happy=(396, 248), thinking=(999, 247), surprised=(1597.5, 251.75),
                      sad=(388, 778), angry=(1000, 779), shy=(1600, 775.5)),
            # Closed mouths get a talking frame (center in sheet px, size in output px);
            # open ones (happy, surprised, shy) already read as speech.
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
        full=dict(crop=(120, 0, 620, 1116), top=52, bottom=1096, mid=(372, 189), dist=52),
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
            talk=dict(thinking=((1008.8, 263.6), (12, 9)), sad=((343.8, 826.0), (12, 9))),
        ),
    ),
    "yuki": dict(
        eye_px=0.767 * 89,
        base=dict(
            sheet="reference_sheet.webp", crop=(1040, 0, 1960, 1116), mid=(1467.5, 346.5), dist=125,
            talk=((1472, 437), (21, 15.6)),
            blink=((1358, 1442, 328, 368), (1498, 1584, 322, 362)), skin="lerp", lash=3.0, feather=1.5,
        ),
        # erase: sheet boxes where semi-transparent leftovers of the background (a sticky note
        # and the board edge beside the hair) are dropped; the opaque hair stays.
        full=dict(crop=(170, 60, 580, 1116), top=87, bottom=1099, mid=(371.5, 182), dist=47,
                  erase=((420, 60, 580, 240),), mouth_shift=(0.15, 0.05),
                  mouth={e: (0.42, 0.34, 0.92) for e in ("neutral", "happy", "thinking", "surprised", "sad", "angry", "shy")}),
        expressions=dict(
            sheet="reference_expressions.webp",
            # Rows stop above the Korean/English labels printed under each face.
            columns=((60, 690), (700, 1320), (1330, 1960)), rows=((40, 470), (590, 965)),
            mids=dict(happy=(397, 219), thinking=(1001.5, 220.5), surprised=(1602.5, 228),
                      sad=(387.5, 770), angry=(1001, 772), shy=(1596, 772)),
            # The panels are not drawn at one scale (and closed or narrowed eyes sit wider apart),
            # so each has its own eye distance, calibrated by head height against the neutral.
            dist=dict(happy=77, thinking=79, surprised=81, sad=90, angry=91, shy=90),
            talk=dict(thinking=((1001, 278), (11, 8)), sad=((390, 830), (11, 8)), angry=((1000, 833), (11, 8))),
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

    Faces are scaled by eye distance and aligned on the eyes, then blended through a
    feathered oval that covers brows to chin, so expressions, talking and blinking carry
    over. Hand gestures exist only in the bust art and are left out.
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
    # Brows+eyes band plus a small mouth oval: wide enough for the expression, but it
    # stops short of the chin and cheeks where bust poses put hands and sleeves.
    d, (ex, ey) = config["eye_px"], EYE_OUT

    def cover(frame, polygons, oval):
        """Paint the given regions with the median skin tone found in the mouth oval."""
        a = np.array(frame).copy()
        region = Image.new("L", (W, H), 0)
        draw = ImageDraw.Draw(region)
        for polygon in polygons:
            draw.polygon([(ex + x * d, ey + y * d) for x, y in polygon], fill=255)
        covered = np.array(region) > 0
        rgb = a[..., :3].astype(int)
        saturation, lum = rgb.max(-1) - rgb.min(-1), rgb.mean(-1)
        skin = (np.array(oval) > 0) & ~covered & (saturation >= 33) & (saturation < 90) & (lum > 185)
        if skin.any():
            a[covered, :3] = np.median(rgb[skin], axis=0).astype(np.uint8)
            a[covered, 3] = 255
        return Image.fromarray(a)

    def face_mask(frame_name, frame):
        expression = frame_name.split("_")[0]
        half, top, bottom = full.get("mouth", {}).get(expression, (0.36, 0.32, 0.86))
        band = Image.new("L", (W, H), 0)
        ImageDraw.Draw(band).ellipse([ex - 1.0 * d, ey - 0.6 * d, ex + 1.0 * d, ey + 0.5 * d], fill=255)
        mouth = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mouth).ellipse([ex - half * d, ey + top * d, ex + half * d, ey + bottom * d], fill=255)
        blur = ImageFilter.GaussianBlur(d * 0.07)
        return band.filter(blur), mouth.filter(blur)

    def masked(img, mask):
        img = img.copy()
        img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", img.size, 0), mask))
        return img

    out = out / "full"
    out.mkdir(parents=True, exist_ok=True)
    for frame_name, frame in frames.items():
        face = frame.copy()
        expression = frame_name.split("_")[0]
        if expression in full.get("cover", {}):
            half, top, bottom = full["mouth"][expression]
            oval = Image.new("L", (W, H), 0)
            ImageDraw.Draw(oval).ellipse([ex - half * d, ey + top * d, ex + half * d, ey + bottom * d], fill=255)
            face = cover(face, full["cover"][expression], oval)
        band, mouth = face_mask(frame_name, frame)
        if "mouth_shift" in full:
            # The full-body face is turned slightly, so its mouth sits off the eye midline:
            # move the bust mouth there (eye-distance units) so it replaces the drawn one.
            dx, dy = (round(v * d) for v in full["mouth_shift"])
            shifted = Image.new("RGBA", face.size, (0, 0, 0, 0))
            shifted.alpha_composite(masked(face, mouth), (max(dx, 0), max(dy, 0)), (max(-dx, 0), max(-dy, 0)))
            face = masked(face, band)
            face.alpha_composite(shifted)
        else:
            face = masked(face, Image.fromarray(np.maximum(np.array(band), np.array(mouth))))
        size = (round(W * face_k), round(H * face_k))
        small = face.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
        result = base.copy()
        result.alpha_composite(small, (round(eye_full[0] - EYE_OUT[0] * face_k), round(eye_full[1] - EYE_OUT[1] * face_k)))
        result.save(out / f"{frame_name}.png", optimize=True)


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
        frames[expression] = place(panel, mid, k)
        if expression in exp["talk"]:
            (mx, my), size = exp["talk"][expression]
            frames[f"{expression}_talk"] = talk(frames[expression], to_out((mx - x0, my - y0), mid, k), size)

    out.mkdir(parents=True, exist_ok=True)
    cleaned = {frame: clean(img, alpha_fix=config.get("alpha")) for frame, img in frames.items()}
    for frame, img in cleaned.items():
        img.save(out / f"{frame}.png", optimize=True)
    if "full" in config:
        build_full(config, folder, session, cleaned, out)
    return sorted(frames)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CHARACTERS:
        sys.exit(f"usage: python tools/build_frames.py {{{'|'.join(CHARACTERS)}}} [output folder]")
    character = sys.argv[1]
    print(build(character, Path(sys.argv[2]) if len(sys.argv) > 2 else ASSETS / character))
