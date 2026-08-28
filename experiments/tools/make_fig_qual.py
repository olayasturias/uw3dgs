"""Qualitative comparison grid (paper hero figure): rows = regimes, columns =
ground truth | M0 | M2 | M3, one held-out view per row. M2's nerfstudio split
is offset by one frame from the forks' split; its column shows the adjacent
held-out frame (stated in the caption)."""
import glob
import os

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42   # TrueType, not Type 3 (IEEE PDF compliance)
matplotlib.rcParams["ps.fonttype"] = 42
import matplotlib.pyplot as plt
from PIL import Image

R = r"D:\uw3dgs\runs"
ROWS = [
    dict(label="S1 benchmark\n(shallow, sunlit)",
         scene=r"D:\uw3dgs\scenes\s1_curacao", k=1,
         m0=f"{R}/e1_s1_m0/test/ours_30000/renders",
         m2=f"{R}/e1_s1_m2/ns_render/test/rgb",
         m3=f"{R}/e1_s1_m3/test/with_water"),
    dict(label="S2 tank\n(12 NTU measured)",
         scene=r"D:\uw3dgs\scenes\s2_turbid5_trial1", k=12,
         m0=f"{R}/e2_t5_m0/test/ours_30000/renders",
         m2=f"{R}/e2_t5_m2/ns_render/test/rgb",
         m3=f"{R}/e2_t5_m3/test/with_water"),
    dict(label="S3 deep vent\n(co-moving light)",
         scene=r"D:\uw3dgs\scenes\s3_eiffel2015_dense", k=22,
         m0=f"{R}/e5_s3dense_m0/test/ours_30000/renders",
         m2=f"{R}/e5_s3dense_m2/ns_render/test/rgb",
         m3=f"{R}/e5_s3_m3/test/with_water"),
    dict(label="S4 industrial\nsurvey",
         scene=r"D:\uw3dgs\scenes\s4_planenose", k=35,
         m0=f"{R}/e1_s4_m0/test/ours_30000/renders",
         m2=f"{R}/e1_s4_m2/ns_render/test/rgb",
         m3=f"{R}/e1_s4_m3/test/with_water"),
]
COLS = ["Ground truth", "M0 3DGS", "M2 WaterSplatting", "M3 SeaSplat"]


def load(path, target_h=240):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.resize((int(w * target_h / h), target_h), Image.LANCZOS)
    # center-crop to exactly 4:3 so all rows align regardless of source aspect
    tw = int(target_h * 4 / 3)
    if im.width > tw:
        x0 = (im.width - tw) // 2
        im = im.crop((x0, 0, x0 + tw, target_h))
    elif im.width < tw:  # narrower than 4:3 (e.g. square): crop height instead
        th = int(im.width * 3 / 4)
        y0 = (im.height - th) // 2
        im = im.crop((0, y0, im.width, y0 + th)).resize((tw, target_h), Image.LANCZOS)
    return im


fig, axes = plt.subplots(len(ROWS), 4, figsize=(7.16, 5.6))
plt.rcParams.update({"font.size": 8, "font.family": "sans-serif"})
for r, row in enumerate(ROWS):
    stems = sorted(os.listdir(os.path.join(row["scene"], "images")))
    test = stems[::8]
    stem = os.path.splitext(test[row["k"]])[0]
    cells = []
    cells.append(os.path.join(row["scene"], "images", test[row["k"]]))       # GT
    cells.append(os.path.join(row["m0"], f"{row['k']:05d}.png"))             # M0
    if row["m2"]:
        m2files = sorted(os.listdir(row["m2"]))
        cells.append(os.path.join(row["m2"], m2files[row["k"]]))             # M2 (adjacent)
    else:
        cells.append(None)
    m3hit = glob.glob(os.path.join(row["m3"], stem + ".*"))                  # M3
    cells.append(m3hit[0] if m3hit else None)

    for c, path in enumerate(cells):
        ax = axes[r, c]
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        if path and os.path.exists(path):
            ax.imshow(load(path))
        else:
            ax.text(0.5, 0.5, "not run", ha="center", va="center",
                    fontsize=8, color="0.45", transform=ax.transAxes)
        if r == 0:
            ax.set_title(COLS[c], fontsize=8.5)
        if c == 0:
            ax.set_ylabel(row["label"], fontsize=7.5)

plt.subplots_adjust(wspace=0.02, hspace=0.02, left=0.06, right=0.995,
                    top=0.95, bottom=0.005)
for ext in ("pdf", "png"):
    fig.savefig(rf"C:\Users\oat\workspace\sota-underwater-3dgs\paper\figures\fig_qual.{ext}",
                dpi=300)
print("wrote fig_qual.pdf/.png")
