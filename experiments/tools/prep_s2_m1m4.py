"""Prep for M1/M4 on the SOTRUE sweep (Fig. 2 extension).

M1: UIE-enhanced copies of the four S2 scenes (same classical pre-pass as
S1/S4: gray-world WB — a no-op on grey-replicated frames — plus CLAHE on L).
M4: nothing here; its DA-V2 depth maps are generated separately (dggt env).
"""
import os
import shutil

import cv2
import numpy as np


def uie(img):
    b, g, r = cv2.split(img.astype(np.float32))
    m = (b.mean() + g.mean() + r.mean()) / 3.0
    b *= m / max(b.mean(), 1e-6); g *= m / max(g.mean(), 1e-6); r *= m / max(r.mean(), 1e-6)
    img = np.clip(cv2.merge([b, g, r]), 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


for lvl in [0, 2, 3, 5]:
    src = rf"D:\uw3dgs\scenes\s2_turbid{lvl}_trial1"
    dst = rf"D:\uw3dgs\scenes\s2_turbid{lvl}_uie"
    os.makedirs(os.path.join(dst, "images"), exist_ok=True)
    if not os.path.exists(os.path.join(dst, "sparse")):
        shutil.copytree(os.path.join(src, "sparse"), os.path.join(dst, "sparse"))
    n = 0
    for f in sorted(os.listdir(os.path.join(src, "images"))):
        if not f.endswith(".png"):
            continue
        o = os.path.join(dst, "images", f)
        if os.path.exists(o):
            continue
        cv2.imwrite(o, uie(cv2.imread(os.path.join(src, "images", f), cv2.IMREAD_COLOR)))
        n += 1
    print(f"s2_turbid{lvl}_uie: {n} images enhanced")
print("done")
