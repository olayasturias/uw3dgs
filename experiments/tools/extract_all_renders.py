"""Side-by-side render strips + contact sheet for every remaining sequence
(S1, S2 clear, S2 12 NTU, S3), same format as the plane_nose set.
M1 renders enhanced targets (*); columns absent for a scene are omitted.
"""
import glob
import os

from PIL import Image, ImageDraw, ImageFont

R = r"D:\uw3dgs\runs"

SCENES = [
    dict(name="s1_curacao", scene=r"D:\uw3dgs\scenes\s1_curacao", n=3,
         cols=[("Ground truth", None, "gt"),
               ("M0 3DGS", f"{R}/e1_s1_m0/test/ours_30000/renders", "idx"),
               ("M1 UIE->3DGS *", f"{R}/e1_s1_m1/test/ours_30000/renders", "idx"),
               ("M2 WaterSplatting", f"{R}/e1_s1_m2/ns_render/test/rgb", "sorted"),
               ("M3 SeaSplat", f"{R}/e1_s1_m3/test/with_water", "stem"),
               ("M4 UW-GS", f"{R}/e1_s1_m4_retry/test/ours_30000/renders", "idx")]),
    dict(name="s2_clear0NTU", scene=r"D:\uw3dgs\scenes\s2_turbid0_trial1", n=10,
         cols=[("Ground truth", None, "gt"),
               ("M0 3DGS", f"{R}/e2_t0_m0/test/ours_30000/renders", "idx"),
               ("M1 UIE->3DGS *", f"{R}/e2_t0_m1/test/ours_30000/renders", "idx"),
               ("M2 WaterSplatting", f"{R}/e2_t0_m2/ns_render/test/rgb", "sorted"),
               ("M3 SeaSplat", f"{R}/e2_t0_m3/test/with_water", "stem")]),
    dict(name="s2_turbid12NTU", scene=r"D:\uw3dgs\scenes\s2_turbid5_trial1", n=10,
         cols=[("Ground truth", None, "gt"),
               ("M0 3DGS", f"{R}/e2_t5_m0/test/ours_30000/renders", "idx"),
               ("M1 UIE->3DGS *", f"{R}/e2_t5_m1/test/ours_30000/renders", "idx"),
               ("M2 WaterSplatting", f"{R}/e2_t5_m2/ns_render/test/rgb", "sorted"),
               ("M3 SeaSplat", f"{R}/e2_t5_m3/test/with_water", "stem")]),
    dict(name="s3_eiffel", scene=r"D:\uw3dgs\scenes\s3_eiffel2015_dense", n=10,
         cols=[("Ground truth", None, "gt"),
               ("M0 3DGS", f"{R}/e5_s3dense_m0/test/ours_30000/renders", "idx"),
               ("M2 WaterSplatting", f"{R}/e5_s3dense_m2/ns_render/test/rgb", "sorted"),
               ("M3 SeaSplat", f"{R}/e5_s3_m3/test/with_water", "stem")]),
]

H = 480
try:
    font = ImageFont.truetype("arial.ttf", 22)
    font_s = ImageFont.truetype("arial.ttf", 18)
except OSError:
    font = font_s = ImageFont.load_default()

for sc in SCENES:
    out = rf"D:\uw3dgs\renders_{sc['name']}"
    os.makedirs(out, exist_ok=True)
    names = sorted(os.listdir(os.path.join(sc["scene"], "images")))
    names = [n for n in names if n.lower().endswith((".png", ".jpg"))]
    test = names[::8]
    step = max(1, len(test) // sc["n"])
    picks = list(range(0, len(test), step))[:sc["n"]]
    sorted_cache = {}
    strips = []
    for k in picks:
        stem = os.path.splitext(test[k])[0]
        ims = []
        for label, d, mode in sc["cols"]:
            p = None
            if mode == "gt":
                p = os.path.join(sc["scene"], "images", test[k])
            elif d and mode == "idx":
                p = os.path.join(d, f"{k:05d}.png")
            elif d and mode == "sorted":
                if d not in sorted_cache:
                    sorted_cache[d] = sorted(os.listdir(d))
                if k < len(sorted_cache[d]):
                    p = os.path.join(d, sorted_cache[d][k])
            elif d and mode == "stem":
                hit = glob.glob(os.path.join(d, stem + ".*"))
                p = hit[0] if hit else None
            if p and os.path.exists(p):
                im = Image.open(p).convert("RGB")
                im = im.resize((int(im.width * H / im.height), H), Image.LANCZOS)
            else:
                im = Image.new("RGB", (int(H * 1.5), H), (24, 26, 30))
                ImageDraw.Draw(im).text((14, H // 2), "missing",
                                        fill=(120, 120, 120), font=font)
            dd = ImageDraw.Draw(im)
            dd.rectangle([0, 0, im.width, 34], fill=(16, 19, 24))
            dd.text((10, 6), label, fill=(230, 234, 240), font=font)
            ims.append(im)
        strip = Image.new("RGB", (sum(i.width for i in ims) + 4 * (len(ims) - 1), H),
                          (255, 255, 255))
        x = 0
        for im in ims:
            strip.paste(im, (x, 0))
            x += im.width + 4
        ImageDraw.Draw(strip).text((10, H - 28),
                                   f"view {k+1}/{len(test)}  ({stem[:44]})",
                                   fill=(255, 255, 60), font=font_s)
        strip.save(os.path.join(out, f"strip_{k:03d}_{stem[:40]}.jpg"), quality=90)
        strips.append(strip)
    W = 2200
    rows = [s.resize((W, int(s.height * W / s.width)), Image.LANCZOS) for s in strips]
    sheet = Image.new("RGB", (W, sum(r.height for r in rows) + 6 * (len(rows) - 1)),
                      (255, 255, 255))
    y = 0
    for r_ in rows:
        sheet.paste(r_, (0, y))
        y += r_.height + 6
    sheet.save(os.path.join(out, "contact_sheet.jpg"), quality=85)
    print(f"{sc['name']}: {len(strips)} strips -> {out}")
