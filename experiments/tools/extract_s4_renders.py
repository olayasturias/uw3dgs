"""Extract side-by-side render comparisons on plane_nose (S4).

For every selected held-out view: one strip GT | M0 | M1 | M2 | M3 with
labels, full resolution rows -> D:\\uw3dgs\\renders_planenose\\strip_<stem>.jpg,
plus a contact-sheet overview of all selected views.
M1 renders its enhanced targets (labelled with *).
"""
import glob
import os

from PIL import Image, ImageDraw, ImageFont

R = r"D:\uw3dgs\runs"
SCENE = r"D:\uw3dgs\scenes\s4_planenose"
OUT = r"D:\uw3dgs\renders_planenose"
os.makedirs(OUT, exist_ok=True)

COLS = [
    ("Ground truth", None),
    ("M0 3DGS", f"{R}/e1_s4_m0/test/ours_30000/renders"),
    ("M1 UIE->3DGS *", f"{R}/e1_s4_m1/test/ours_30000/renders"),
    ("M2 WaterSplatting", f"{R}/e1_s4_m2/ns_render/test/rgb"),
    ("M3 SeaSplat", f"{R}/e1_s4_m3/test/with_water"),
]

names = sorted(os.listdir(os.path.join(SCENE, "images")))
test = names[::8]                      # the shared held-out split
picks = list(range(0, len(test), max(1, len(test) // 10)))[:10]
H = 480
try:
    font = ImageFont.truetype("arial.ttf", 22)
    font_s = ImageFont.truetype("arial.ttf", 18)
except OSError:
    font = font_s = ImageFont.load_default()

m2files = sorted(os.listdir(COLS[3][1]))
strips = []
for k in picks:
    stem = os.path.splitext(test[k])[0]
    cells = [
        os.path.join(SCENE, "images", test[k]),
        os.path.join(COLS[1][1], f"{k:05d}.png"),
        os.path.join(COLS[2][1], f"{k:05d}.png"),
        os.path.join(COLS[3][1], m2files[k]),
        (glob.glob(os.path.join(COLS[4][1], stem + ".*")) or [None])[0],
    ]
    ims = []
    for (label, _), p in zip(COLS, cells):
        if p and os.path.exists(p):
            im = Image.open(p).convert("RGB")
            im = im.resize((int(im.width * H / im.height), H), Image.LANCZOS)
        else:
            im = Image.new("RGB", (H, H), (24, 26, 30))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.width, 34], fill=(16, 19, 24))
        d.text((10, 6), label, fill=(230, 234, 240), font=font)
        ims.append(im)
    strip = Image.new("RGB", (sum(i.width for i in ims) + 4 * (len(ims) - 1), H),
                      (255, 255, 255))
    x = 0
    for im in ims:
        strip.paste(im, (x, 0))
        x += im.width + 4
    d = ImageDraw.Draw(strip)
    d.text((10, H - 28), f"view {k+1}/{len(test)}  ({stem})",
           fill=(255, 255, 60), font=font_s)
    fp = os.path.join(OUT, f"strip_{k:03d}_{stem[:40]}.jpg")
    strip.save(fp, quality=90)
    strips.append(strip)
    print("wrote", os.path.basename(fp))

# contact sheet: all strips stacked, downscaled
W = 2200
rows = [s.resize((W, int(s.height * W / s.width)), Image.LANCZOS) for s in strips]
sheet = Image.new("RGB", (W, sum(r.height for r in rows) + 6 * (len(rows) - 1)),
                  (255, 255, 255))
y = 0
for r_ in rows:
    sheet.paste(r_, (0, y))
    y += r_.height + 6
sheet.save(os.path.join(OUT, "contact_sheet.jpg"), quality=85)
print(f"contact sheet: {len(strips)} views -> {OUT}")
