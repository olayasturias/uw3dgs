"""Uniform depth renderer: load ANY fork's exported point_cloud.ply and render
per-test-view depth with the upstream (dr_aa) rasterizer.

Protocol: geometry export is "chosen once and applied to all" systems
every 3DGS-fork system's geometry is its gaussian set,
rendered by ONE renderer, so depth differences reflect the learned geometry and
never per-repo rendering code. (water-splatting is nerfstudio-based and gets
depth via ns-render; documented exception.)

Outputs <out>/<stem>_depth.npy (metres, camera z) + <stem>_alpha.npy per
held-out view (sorted names [::8]).
"""
import argparse, os, sys
import numpy as np
import torch

REPO = r"D:\uw3dgs\repos\gaussian-splatting"
sys.path.insert(0, REPO)

from scene.dataset_readers import readColmapSceneInfo  # noqa
from scene.gaussian_model import GaussianModel  # noqa
from utils.camera_utils import cameraList_from_camInfos  # noqa
from gaussian_renderer import render  # noqa


class A:  # minimal args namespace for camera loading
    resolution = 1
    data_device = "cuda"
    train_test_exp = False


class Pipe:
    convert_SHs_python = False
    compute_cov3D_python = False
    debug = False
    antialiasing = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ply", required=True)
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sh-degree", type=int, default=3)
    ap.add_argument("--min-opacity", type=float, default=0.0,
                    help="surface-depth mode: drop gaussians below this opacity "
                         "before rendering (translucent floater veil corrupts "
                         "blended depth by metres; see FINDINGS F10)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    info = readColmapSceneInfo(args.scene, "images", "", eval=True, train_test_exp=False)
    test_cams = cameraList_from_camInfos(info.test_cameras, 1.0, A(), False, False)

    # auto-detect SH degree from the ply (forks export different degrees;
    # seasplat saves DC-only)
    from plyfile import PlyData
    nrest = len([pr.name for pr in PlyData.read(args.ply)["vertex"].properties
                 if pr.name.startswith("f_rest")])
    sh_deg = {0: 0, 9: 1, 24: 2, 45: 3}[nrest]
    gaussians = GaussianModel(sh_deg)
    gaussians.load_ply(args.ply)
    n0 = gaussians.get_xyz.shape[0]
    if args.min_opacity > 0:
        m = (gaussians.get_opacity.squeeze() > args.min_opacity)
        for attr in ["_xyz", "_features_dc", "_features_rest", "_opacity",
                     "_scaling", "_rotation"]:
            setattr(gaussians, attr, getattr(gaussians, attr)[m])
        print(f"opacity>{args.min_opacity}: kept {int(m.sum())}/{n0} gaussians")
    print(f"{gaussians.get_xyz.shape[0]} gaussians from {args.ply}")

    bg = torch.zeros(3, device="cuda")
    ones = None
    with torch.no_grad():
        for cam in test_cams:
            pkg = render(cam, gaussians, Pipe(), bg)
            # dr_aa "depth" is the alpha-blended INVERSE depth: sum(w_i / z_i).
            # Recover alpha by rendering constant-1 colours on a black bg, then
            # alpha-normalise: depth = alpha / sum(w_i/z_i). One estimator for
            # every system (per-repo 'depth' outputs are not comparable).
            if ones is None or ones.shape[0] != gaussians.get_xyz.shape[0]:
                ones = torch.ones_like(gaussians.get_xyz)
            alpha = render(cam, gaussians, Pipe(), bg,
                           override_color=ones)["render"][0].squeeze()
            inv = pkg["depth"].squeeze().clamp(min=1e-12)
            depth = (alpha.clamp(min=1e-6) / inv).cpu().numpy()
            np.save(os.path.join(args.out, cam.image_name + "_depth.npy"), depth)
            np.save(os.path.join(args.out, cam.image_name + "_alpha.npy"),
                    alpha.cpu().numpy())
    print(f"rendered {len(test_cams)} test depth maps -> {args.out}")


if __name__ == "__main__":
    main()
