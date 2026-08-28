"""Prep the dense S3 scene for M1 (UIE variant) and M4 (mono-depth maps).
UIE pre-pass is the same parameter-free classical composite used on S1/S2/S4:
gray-world white balance + CLAHE on L.
"""
import os
import shutil

import cv2
import numpy as np

SRC = r"D:\uw3dgs\scenes\s3_eiffel2015_dense"
DST = r"D:\uw3dgs\scenes\s3_eiffel2015_dense_uie"


def uie(img):
    b, g, r = cv2.split(img.astype(np.float32))
    m = (b.mean() + g.mean() + r.mean()) / 3.0
    b *= m / max(b.mean(), 1e-6); g *= m / max(g.mean(), 1e-6); r *= m / max(r.mean(), 1e-6)
    img = np.clip(cv2.merge([b, g, r]), 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


os.makedirs(os.path.join(DST, "images"), exist_ok=True)
if not os.path.exists(os.path.join(DST, "sparse")):
    shutil.copytree(os.path.join(SRC, "sparse"), os.path.join(DST, "sparse"))
n = 0
for f in sorted(os.listdir(os.path.join(SRC, "images"))):
    if not f.lower().endswith((".png", ".jpg")):
        continue
    o = os.path.join(DST, "images", f)
    if os.path.exists(o):
        continue
    cv2.imwrite(o, uie(cv2.imread(os.path.join(SRC, "images", f), cv2.IMREAD_COLOR)))
    n += 1
print(f"s3 dense UIE: {n} images -> {DST}")
