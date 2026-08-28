"""Unified photometric evaluator — ONE metrics pass for every system.

Protocol: per-repo metric code
differs in masking, resizing and colour handling, so all reported metrics come
exclusively from this script, applied identically to every system's rendered
held-out views.

Inputs are two directories of image files paired BY BASENAME STEM
(render stem == gt stem; extensions may differ). Every gt image with a
matching render is scored; missing renders are an error (systems must render
the full held-out set).

Metrics: PSNR, SSIM, LPIPS (AlexNet and VGG), on [0,1] RGB float, computed at
the GT resolution (renders are bilinearly resized if they differ; the resize
is recorded in the output). Optional border mask (SOTRUE edge distortion):
--border N crops N pixels on every side of BOTH images before scoring.

Output: JSON with per-view and aggregate values + full provenance.
"""
import argparse, json, os, sys
from pathlib import Path

import numpy as np
import torch


def load_image(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    return torch.from_numpy(np.asarray(im)).float().permute(2, 0, 1) / 255.0


def psnr(a, b):
    mse = torch.mean((a - b) ** 2)
    return float(10 * torch.log10(1.0 / mse)) if mse > 0 else float("inf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--border", type=int, default=0,
                    help="crop N px from every side before scoring")
    ap.add_argument("--names", default=None,
                    help="optional file listing gt basenames (stems) to score; "
                         "default: every gt image with a matching render")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    from pytorch_msssim import ssim as ssim_fn
    import lpips as lpips_mod
    lpips_alex = lpips_mod.LPIPS(net="alex").to(args.device)
    lpips_vgg = lpips_mod.LPIPS(net="vgg").to(args.device)

    renders = {Path(f).stem: os.path.join(args.renders, f)
               for f in os.listdir(args.renders)
               if f.lower().endswith((".png", ".jpg", ".jpeg"))}
    gts = {Path(f).stem: os.path.join(args.gt, f)
           for f in os.listdir(args.gt)
           if f.lower().endswith((".png", ".jpg", ".jpeg"))}

    if args.names:
        stems = [Path(l.strip()).stem for l in open(args.names) if l.strip()]
    else:
        stems = sorted(set(gts) & set(renders))
    missing = [s for s in stems if s not in renders]
    if missing:
        sys.exit(f"ERROR: {len(missing)} held-out views not rendered: {missing[:5]} ...")

    per_view, resized = {}, False
    with torch.no_grad():
        for s in stems:
            r, g = load_image(renders[s]), load_image(gts[s])
            if r.shape != g.shape:
                r = torch.nn.functional.interpolate(
                    r[None], size=g.shape[-2:], mode="bilinear", align_corners=False)[0]
                resized = True
            if args.border:
                b = args.border
                r, g = r[:, b:-b, b:-b], g[:, b:-b, b:-b]
            r, g = r.to(args.device), g.to(args.device)
            per_view[s] = {
                "psnr": psnr(r, g),
                "ssim": float(ssim_fn(r[None], g[None], data_range=1.0)),
                "lpips_alex": float(lpips_alex(r[None] * 2 - 1, g[None] * 2 - 1)),
                "lpips_vgg": float(lpips_vgg(r[None] * 2 - 1, g[None] * 2 - 1)),
            }

    agg = {k: float(np.mean([v[k] for v in per_view.values()]))
           for k in ["psnr", "ssim", "lpips_alex", "lpips_vgg"]}
    result = {
        "renders_dir": os.path.abspath(args.renders),
        "gt_dir": os.path.abspath(args.gt),
        "n_views": len(per_view),
        "border_crop_px": args.border,
        "renders_resized_to_gt": resized,
        "aggregate": agg,
        "per_view": per_view,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(result, open(args.out, "w"), indent=2)
    print(json.dumps({"n_views": len(per_view), **agg}, indent=2))


if __name__ == "__main__":
    main()
