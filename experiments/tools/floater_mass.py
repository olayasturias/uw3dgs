"""Floater mass (C3, GT-free): per held-out view, project every gaussian
center; where a gaussian sits more than tau NEARER the camera than the
opacity-gated surface depth at its pixel, accumulate its opacity. Normalise by
the total opacity of in-frustum gaussians. Sweep tau; never report one value
(protocol). Uses the SAME surface depth maps as the geometric evaluation.

Needs: run dir with point_cloud.ply + depths_surf/ (from geom_all), and the
scene for cameras. Works for any system whose gaussians are exported to ply.
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, r"D:\uw3dgs\repos\gaussian-splatting")

TAUS = [0.05, 0.1, 0.2, 0.3, 0.5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--scene", required=True)
    ap.add_argument("--iters", type=int, default=30000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from plyfile import PlyData
    from scene.dataset_readers import readColmapSceneInfo
    from utils.camera_utils import cameraList_from_camInfos

    class A:
        resolution = 1
        data_device = "cuda"
        train_test_exp = False

    ply = os.path.join(args.run, "point_cloud", f"iteration_{args.iters}",
                       "point_cloud.ply")
    v = PlyData.read(ply)["vertex"]
    X = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    op = 1.0 / (1.0 + np.exp(-np.asarray(v["opacity"], dtype=np.float64)))

    info = readColmapSceneInfo(args.scene, "images", "", eval=True, train_test_exp=False)
    depth_dir = os.path.join(args.run, "depths_surf")
    per_tau = {t: [] for t in TAUS}
    n_views = 0
    for c in info.test_cameras:
        stem = c.image_name
        dfile = None
        for cand in (stem + "_depth.npy", os.path.splitext(stem)[0] + "_depth.npy",
                     stem + ".png_depth.npy"):
            p = os.path.join(depth_dir, cand)
            if os.path.exists(p):
                dfile = p
                break
        if dfile is None:
            continue
        D = np.load(dfile)
        H, W = D.shape
        # fork readers store R = R_wc^T (c2w rotation) and T = w2c translation:
        # x_cam = R_wc x_w + T  ==  x_w @ R + T in row-vector form
        Xc = X @ c.R + c.T
        z = Xc[:, 2]
        fx = W / (2 * np.tan(c.FovX / 2))
        fy = H / (2 * np.tan(c.FovY / 2))
        u = fx * Xc[:, 0] / z + W / 2
        vv = fy * Xc[:, 1] / z + H / 2
        m = (z > 0.05) & (u >= 0) & (u < W) & (vv >= 0) & (vv < H)
        ui, vi, zi, oi = u[m].astype(int), vv[m].astype(int), z[m], op[m]
        Ds = D[vi, ui]
        total = oi.sum()
        if total <= 0:
            continue
        for t in TAUS:
            fl = (Ds - zi) > t
            per_tau[t].append(float(oi[fl].sum() / total))
        n_views += 1

    result = {"n_views": n_views,
              "floater_mass": {str(t): float(np.mean(per_tau[t])) for t in TAUS}}
    out = args.out or os.path.join(args.run, "floater_mass.json")
    json.dump(result, open(out, "w"), indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
