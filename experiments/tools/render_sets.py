"""Master render-strip extractor for every sequence. Idempotent: re-run as new
results land and each set is rebuilt with whatever columns now exist.

Output per sequence -> D:\\uw3dgs\\renders_<name>\\
  strip_<view>_<stem>.jpg   full-resolution side-by-side, labelled
  contact_sheet.jpg         all selected views stacked

Column labels carry their caveats: * = renders its own enhanced targets
(M1, not comparable to GT); (7k) = truncated run, qualitative only.
"""
import glob
import os

from PIL import Image, ImageDraw, ImageFont

R = r"D:\uw3dgs\runs"
S = r"D:\uw3dgs\scenes"

# (label, render dir, filename mode)
def cols(*items):
    return [i for i in items if i]


SETS = [
    dict(name="s1_curacao", scene=rf"{S}\s1_curacao", n=3, cols=cols(
        ("Ground truth", None, "gt"),
        ("M0 3DGS", rf"{R}\e1_s1_m0\test\ours_30000\renders", "idx"),
        ("M1 UIE->3DGS *", rf"{R}\e1_s1_m1\test\ours_30000\renders", "idx"),
        ("M2 WaterSplatting", rf"{R}\e1_s1_m2\ns_render\test\rgb", "sorted"),
        ("M3 SeaSplat", rf"{R}\e1_s1_m3\test\with_water", "stem"),
        ("M4 UW-GS", rf"{R}\e1_s1_m4_retry\test\ours_30000\renders", "idx"))),
    dict(name="s2_clear0NTU", scene=rf"{S}\s2_turbid0_trial1", n=10, cols=cols(
        ("Ground truth", None, "gt"),
        ("M0 3DGS", rf"{R}\e2_t0_m0\test\ours_30000\renders", "idx"),
        ("M1 UIE->3DGS *", rf"{R}\e2_t0_m1\test\ours_30000\renders", "idx"),
        ("M2 WaterSplatting", rf"{R}\e2_t0_m2\ns_render\test\rgb", "sorted"),
        ("M3 SeaSplat", rf"{R}\e2_t0_m3\test\with_water", "stem"))),
    dict(name="s2_turbid12NTU", scene=rf"{S}\s2_turbid5_trial1", n=10, cols=cols(
        ("Ground truth", None, "gt"),
        ("M0 3DGS", rf"{R}\e2_t5_m0\test\ours_30000\renders", "idx"),
        ("M1 UIE->3DGS *", rf"{R}\e2_t5_m1\test\ours_30000\renders", "idx"),
        ("M2 WaterSplatting", rf"{R}\e2_t5_m2\ns_render\test\rgb", "sorted"),
        ("M3 SeaSplat", rf"{R}\e2_t5_m3\test\with_water", "stem"),
        ("M4 UW-GS (7k)", rf"{R}\e2_t5_m4_7k\test\ours_7000\renders", "idx"))),
    dict(name="s3_eiffel", scene=rf"{S}\s3_eiffel2015_dense", n=10, cols=cols(
        ("Ground truth", None, "gt"),
        ("M0 3DGS", rf"{R}\e5_s3dense_m0\test\ours_30000\renders", "idx"),
        ("M1 UIE->3DGS *", rf"{R}\e5_s3dense_m1\test\ours_30000\renders", "idx"),
        ("M2 WaterSplatting", rf"{R}\e5_s3dense_m2\ns_render\test\rgb", "sorted"),
        ("M3 SeaSplat", rf"{R}\e5_s3_m3\test\with_water", "stem"),
        ("M4 UW-GS (7k)", rf"{R}\e5_s3dense_m4_7k\test\ours_7000\renders", "idx"))),
    dict(name="planenose", scene=rf"{S}\s4_planenose", n=10, cols=cols(
        ("Ground truth", None, "gt"),
        ("M0 3DGS", rf"{R}\e1_s4_m0\test\ours_30000\renders", "idx"),
        ("M1 UIE->3DGS *", rf"{R}\e1_s4_m1\test\ours_30000\renders", "idx"),
        ("M2 WaterSplatting", rf"{R}\e1_s4_m2\ns_render\test\rgb", "sorted"),
        ("M3 SeaSplat", rf"{R}\e1_s4_m3\test\with_water", "stem"),
        ("M4 UW-GS (7k)", rf"{R}\e1_s4_m4_7k\test\ours_7000\renders", "idx"))),
]

H = 480
try:
    font = ImageFont.truetype("arial.ttf", 22)
    font_s = ImageFont.truetype("arial.ttf", 18)
except OSError:
    font = font_s = ImageFont.load_default()

for st in SETS:
    # keep only columns whose renders exist (GT always kept)
    live = [c for c in st["cols"] if c[2] == "gt" or (c[1] and os.path.isdir(c[1]))]
    skipped = [c[0] for c in st["cols"] if c not in live]
    out = rf"D:\uw3dgs\renders_{st['name']}"
    os.makedirs(out, exist_ok=True)
    names = [n for n in sorted(os.listdir(os.path.join(st["scene"], "images")))
             if n.lower().endswith((".png", ".jpg"))]
    test = names[::8]
    step = max(1, len(test) // st["n"])
    picks = list(range(0, len(test), step))[:st["n"]]
    cache, strips = {}, []
    for k in picks:
        stem = os.path.splitext(test[k])[0]
        ims = []
        for label, d, mode in live:
            p = None
            if mode == "gt":
                p = os.path.join(st["scene"], "images", test[k])
            elif mode == "idx":
                p = os.path.join(d, f"{k:05d}.png")
            elif mode == "sorted":
                cache.setdefault(d, sorted(os.listdir(d)))
                if k < len(cache[d]):
                    p = os.path.join(d, cache[d][k])
            elif mode == "stem":
                p = (glob.glob(os.path.join(d, stem + ".*")) or [None])[0]
            if p and os.path.exists(p):
                im = Image.open(p).convert("RGB")
                im = im.resize((int(im.width * H / im.height), H), Image.LANCZOS)
            else:
                im = Image.new("RGB", (int(H * 1.5), H), (24, 26, 30))
                ImageDraw.Draw(im).text((14, H // 2), "missing view",
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
    note = f"  (pending: {', '.join(skipped)})" if skipped else ""
    print(f"{st['name']}: {len(strips)} strips x {len(live)} cols -> {out}{note}")
