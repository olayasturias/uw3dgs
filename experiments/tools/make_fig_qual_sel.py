"""Composite figure from four hand-picked held-out views (one per sequence),
built from the source renders so the grid has one header row, aligned columns
and vector text. IEEE-compliant: TrueType (fonttype 42), never Type 3.

Views requested:
  S1 Curacao        view  1  MTN_1296
  S2 tank 12 NTU    view  2  left_000065
  S3 Eiffel vent    view  0  20150418T024020_000Z
  S4 survey         view 21  image_left_processed_..._CAL_796
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42   # TrueType, not Type 3 (IEEE)
matplotlib.rcParams["ps.fonttype"] = 42
# Times New Roman to match IEEEtran body text; stix for maths (Times-metric)
matplotlib.rcParams["font.family"] = "serif"
matplotlib.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif"]
matplotlib.rcParams["mathtext.fontset"] = "stix"
import matplotlib.pyplot as plt
from PIL import Image

R = r"D:\uw3dgs\runs"
S = r"D:\uw3dgs\scenes"

ROWS = [
    dict(label="S1 Cura\u00e7ao\n(shallow, sunlit)", scene=rf"{S}\s1_curacao", k=1,
         m0=rf"{R}\e1_s1_m0\test\ours_30000\renders",
         m1=rf"{R}\e1_s1_m1\test\ours_30000\renders",
         m2=rf"{R}\e1_s1_m2\ns_render\test\rgb",
         m3=rf"{R}\e1_s1_m3\test\with_water",
         m4=rf"{R}\e1_s1_m4_retry\test\ours_30000\renders"),
    dict(label="S2 tank\n(0 NTU, clear)", scene=rf"{S}\s2_turbid0_trial1", k=2,
         m0=rf"{R}\e2_t0_m0\test\ours_30000\renders",
         m1=rf"{R}\e2_t0_m1\test\ours_30000\renders",
         m2=rf"{R}\e2_t0_m2\ns_render\test\rgb",
         m3=rf"{R}\e2_t0_m3\test\with_water",
         m4=None),
    dict(label="S3 Eiffel vent\n(co-moving light)", scene=rf"{S}\s3_eiffel2015_dense", k=0,
         m0=rf"{R}\e5_s3dense_m0\test\ours_30000\renders",
         m1=rf"{R}\e5_s3dense_m1\test\ours_30000\renders",
         m2=rf"{R}\e5_s3dense_m2\ns_render\test\rgb",
         m3=rf"{R}\e5_s3_m3\test\with_water",
         m4=None),
    dict(label="S4 survey\n(operational)", scene=rf"{S}\s4_planenose", k=21,
         m0=rf"{R}\e1_s4_m0\test\ours_30000\renders",
         m1=rf"{R}\e1_s4_m1\test\ours_30000\renders",
         m2=rf"{R}\e1_s4_m2\ns_render\test\rgb",
         m3=rf"{R}\e1_s4_m3\test\with_water",
         m4=None),
]
COLS = ["Ground truth", "M0 3DGS", "M1 UIE$\\rightarrow$3DGS$^{*}$",
        "M2 WaterSplatting", "M3 SeaSplat", "M4 UW-GS"]
TH = 260


def load(path):
    im = Image.open(path).convert("RGB")
    im = im.resize((int(im.width * TH / im.height), TH), Image.LANCZOS)
    tw = int(TH * 4 / 3)
    if im.width > tw:
        x0 = (im.width - tw) // 2
        im = im.crop((x0, 0, x0 + tw, TH))
    elif im.width < tw:
        th = int(im.width * 3 / 4)
        y0 = (im.height - th) // 2
        im = im.crop((0, y0, im.width, y0 + th)).resize((tw, TH), Image.LANCZOS)
    return im


fig, axes = plt.subplots(len(ROWS), 6, figsize=(7.16, 3.55))
for r, row in enumerate(ROWS):
    names = [n for n in sorted(os.listdir(os.path.join(row["scene"], "images")))
             if n.lower().endswith((".png", ".jpg"))]
    test = names[::8]
    k = row["k"]
    stem = os.path.splitext(test[k])[0]
    m2dir = row["m2"]
    m2files = sorted(os.listdir(m2dir)) if m2dir else []
    cells = [
        os.path.join(row["scene"], "images", test[k]),
        os.path.join(row["m0"], f"{k:05d}.png"),
        os.path.join(row["m1"], f"{k:05d}.png"),
        os.path.join(m2dir, m2files[k]) if m2files and k < len(m2files) else None,
        (glob.glob(os.path.join(row["m3"], stem + ".*")) or [None])[0],
        os.path.join(row["m4"], f"{k:05d}.png") if row["m4"] else None,
    ]
    for c, p in enumerate(cells):
        ax = axes[r, c]
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        if p and os.path.exists(p):
            ax.imshow(load(p))
        else:
            ax.text(0.5, 0.5, "did not\ncomplete", ha="center", va="center",
                    fontsize=6, color="0.5", transform=ax.transAxes)
        if r == 0:
            ax.set_title(COLS[c], fontsize=6.6, pad=3)
        if c == 0:
            ax.set_ylabel(row["label"], fontsize=6.2)

plt.subplots_adjust(wspace=0.03, hspace=0.03, left=0.055, right=0.998,
                    top=0.93, bottom=0.004)
out = r"C:\Users\oat\workspace\sota-underwater-3dgs\paper\figures\fig_qual_sel"
for ext in ("pdf", "png"):
    fig.savefig(f"{out}.{ext}", dpi=400)
print("wrote fig_qual_sel.pdf/.png")
