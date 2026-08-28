"""Trivial-predictor control for the 'PSNR rewards the failure' claim (R2 Major 2).

Predictor: per-pixel MEDIAN of the training images (every frame NOT in the
held-out set). No geometry, no model. Evaluated exactly like the systems:
PSNR on the held-out views, 32 px border mask, per S2 level.

If trivial PSNR rises with turbidity as much as the systems', the headline is
about PSNR dynamic range; if the model-minus-trivial margin holds or grows,
the claim strengthens. Either way it goes in Table III.
"""
import json
import os

import numpy as np
from PIL import Image

OUT = {}
for level, ntu in [(0, 0.0), (3, 7.0), (5, 12.0)]:
    scene = rf"D:\uw3dgs\scenes\s2_turbid{level}_trial1\images"
    names = sorted(os.listdir(scene))
    test = set(names[::8])
    train = [n for n in names if n not in test]
    # median over training frames (single channel; images are grey-replicated)
    stack = np.stack([np.asarray(Image.open(os.path.join(scene, n)).convert("L"),
                                 dtype=np.uint8) for n in train])
    med = np.median(stack, axis=0).astype(np.float64)

    b = 32
    psnrs = []
    for n in sorted(test):
        gt = np.asarray(Image.open(os.path.join(scene, n)).convert("L"), np.float64)
        d = (med - gt)[b:-b, b:-b] / 255.0
        mse = (d ** 2).mean()
        psnrs.append(10 * np.log10(1.0 / mse))
    OUT[f"ntu_{ntu}"] = {"trivial_median_psnr_mean": float(np.mean(psnrs)),
                         "n_test": len(psnrs), "n_train": len(train)}
    print(f"NTU {ntu}: trivial median-image PSNR = {np.mean(psnrs):.2f} dB "
          f"(min {min(psnrs):.2f}, max {max(psnrs):.2f})")

json.dump(OUT, open(r"D:\uw3dgs\runs\trivial_baseline.json", "w"), indent=2)
