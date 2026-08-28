"""Export compact, web-ready point clouds for the GitHub Pages viewer.

From each selected model's gaussian PLY: keep opacity > 0.2, subsample to a
cap, convert SH0 -> RGB, robust-center and scale to unit-ish extent, save as
binary PLY (xyz float32 + rgb uchar, ~15 B/pt) into docs/assets/pointclouds,
plus a dark-background thumbnail for the model selector.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from plyfile import PlyData, PlyElement

SRC = r"D:\uw3dgs\viewer_exports"
DOCS = r"C:\Users\oat\workspace\sota-underwater-3dgs\docs"
PC = os.path.join(DOCS, "assets", "pointclouds")
TH = os.path.join(DOCS, "assets", "thumbs")
os.makedirs(PC, exist_ok=True)
os.makedirs(TH, exist_ok=True)

SH_C0 = 0.28209479177387814
CAP = 250_000

MODELS = [  # (file stem in viewer_exports, page label)
    ("s1_benchmark_M0_3dgs",           "S1 — M0"),
    ("s1_benchmark_M2_watersplatting", "S1 — M2"),
    ("s1_benchmark_M3_seasplat",       "S1 — M3"),
    ("s1_benchmark_M4_uwgs",           "S1 — M4"),
    ("s2_clear0NTU_M0_3dgs",           "S2 0 NTU — M0"),
    ("s2_clear0NTU_M2_watersplatting", "S2 0 NTU — M2"),
    ("s2_clear0NTU_M3_seasplat",       "S2 0 NTU — M3"),
    ("s2_turbid12NTU_M0_3dgs",         "S2 12 NTU — M0"),
    ("s2_turbid12NTU_M2_watersplatting", "S2 12 NTU — M2"),
    ("s2_turbid12NTU_M3_seasplat",     "S2 12 NTU — M3"),
    ("s3_deepvent_M0_3dgs",            "S3 — M0"),
    ("s3_deepvent_M2_watersplatting",  "S3 — M2"),
    ("s3_deepvent_M3_seasplat",        "S3 — M3"),
    ("s4_survey_M0_3dgs",              "S4 — M0"),
    ("s4_survey_M1_uie3dgs",           "S4 — M1"),
    ("s4_survey_M2_watersplatting",    "S4 — M2"),
    ("s4_survey_M3_seasplat",          "S4 — M3"),
]

for stem, label in MODELS:
    v = PlyData.read(os.path.join(SRC, stem + ".ply"))["vertex"]
    X = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    op = 1 / (1 + np.exp(-np.asarray(v["opacity"], np.float64)))
    rgb = 0.5 + SH_C0 * np.stack([v["f_dc_0"], v["f_dc_1"], v["f_dc_2"]], 1)
    m = op > 0.2
    X, rgb = X[m], np.clip(rgb[m], 0, 1)
    if len(X) > CAP:
        idx = np.random.default_rng(0).choice(len(X), CAP, replace=False)
        X, rgb = X[idx], rgb[idx]
    # robust center/scale: median center, 95th-percentile radius -> ~1.0
    C = np.median(X, 0)
    Xc = X - C
    r = np.percentile(np.linalg.norm(Xc, axis=1), 95)
    Xc /= max(r, 1e-9)
    keep = np.linalg.norm(Xc, axis=1) < 4.0   # drop extreme far-field strays
    Xc, rgb = Xc[keep], rgb[keep]

    arr = np.empty(len(Xc), dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"),
                                   ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    arr["x"], arr["y"], arr["z"] = Xc.T.astype(np.float32)
    c8 = (rgb * 255).astype(np.uint8)
    arr["red"], arr["green"], arr["blue"] = c8.T
    out = os.path.join(PC, stem + ".ply")
    PlyData([PlyElement.describe(arr, "vertex")], text=False).write(out)

    # thumbnail
    n = min(60_000, len(Xc))
    ii = np.random.default_rng(1).choice(len(Xc), n, replace=False)
    fig = plt.figure(figsize=(3.2, 2.4), facecolor="#101318")
    ax = fig.add_subplot(111, projection="3d", facecolor="#101318")
    ax.scatter(Xc[ii, 0], Xc[ii, 2], -Xc[ii, 1], s=0.3, c=rgb[ii], linewidths=0)
    ax.set_axis_off()
    ax.set_box_aspect((1, 1, 1))
    lim = 1.3
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
    ax.view_init(elev=18, azim=-60)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(os.path.join(TH, stem + ".jpg"), dpi=110, facecolor="#101318")
    plt.close(fig)
    print(f"{stem}: {len(Xc):,} pts, {os.path.getsize(out)//2**20} MB — {label}")
print("done")
