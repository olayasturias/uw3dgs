"""Convert a nerfstudio gaussian checkpoint (water-splatting / seafree-gs) to
an Inria-format point_cloud.ply IN THE ORIGINAL COLMAP/tank frame, so the
uniform depth renderer + geometric evaluator apply unchanged.

nerfstudio trains in an auto-oriented, auto-scaled frame:
  x_ns = scale * (T_3x4 @ [x_orig; 1])
We invert: x_orig = R^T (x_ns / scale - t);  log-scales -= log(scale).
Colors are written as DC-only placeholders (depth evaluation ignores them).
"""
import argparse, json, os
import numpy as np
import torch
from plyfile import PlyData, PlyElement


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--transforms", required=True, help="dataparser_transforms.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sd = torch.load(args.ckpt, map_location="cpu")["pipeline"]
    g = {k.split("gauss_params.")[1]: sd[k].numpy()
         for k in sd if "gauss_params." in k}
    tr = json.load(open(args.transforms))
    T = np.array(tr["transform"])  # 3x4
    R, t = T[:, :3], T[:, 3]
    s = tr["scale"]

    means = (g["means"] / s - t) @ R  # R^T applied on the right for row vectors
    scales = g["scales"] - np.log(s)
    N = means.shape[0]

    dtype = [("x", "f4"), ("y", "f4"), ("z", "f4"),
             ("nx", "f4"), ("ny", "f4"), ("nz", "f4"),
             ("f_dc_0", "f4"), ("f_dc_1", "f4"), ("f_dc_2", "f4"),
             ("opacity", "f4"),
             ("scale_0", "f4"), ("scale_1", "f4"), ("scale_2", "f4"),
             ("rot_0", "f4"), ("rot_1", "f4"), ("rot_2", "f4"), ("rot_3", "f4")]
    el = np.empty(N, dtype=dtype)
    el["x"], el["y"], el["z"] = means.T.astype(np.float32)
    el["nx"] = el["ny"] = el["nz"] = 0
    fdc = g["features_dc"].astype(np.float32)
    el["f_dc_0"], el["f_dc_1"], el["f_dc_2"] = fdc.T
    el["opacity"] = g["opacities"].squeeze().astype(np.float32)
    el["scale_0"], el["scale_1"], el["scale_2"] = scales.T.astype(np.float32)
    el["rot_0"], el["rot_1"], el["rot_2"], el["rot_3"] = g["quats"].T.astype(np.float32)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    PlyData([PlyElement.describe(el, "vertex")]).write(args.out)
    print(f"wrote {N} gaussians -> {args.out} (frame: original COLMAP/tank)")


if __name__ == "__main__":
    main()
