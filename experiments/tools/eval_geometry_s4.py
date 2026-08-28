"""S4 geometric evaluation: gaussian centers vs the plane_nose reference cloud.

Protocol (outline §7.4): export = gaussian means with opacity > 0.5 ("chosen
once and applied to all"); fine-align with point-to-point ICP (same nominal
frame — report the alignment residual, never hide it); evaluate on the
CO-VISIBLE region only (reference points that project into >=1 training
camera); report accuracy (model->ref), completeness (ref->model), chamfer;
all in mm. The reference is a CONSISTENCY reference, not ground truth (Q2).
"""
import argparse, json, os
import numpy as np


def load_gaussians(ply_path, min_op=0.5):
    from plyfile import PlyData
    v = PlyData.read(ply_path)["vertex"]
    X = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    op = 1 / (1 + np.exp(-np.asarray(v["opacity"], np.float64)))
    return X[op > min_op]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--iters", type=int, default=30000)
    ap.add_argument("--scene", default=r"D:\uw3dgs\scenes\s4_planenose")
    ap.add_argument("--ref", default=r"D:\Datasets\EIVA\vobster_quay\plane_nose\pointcloud_gt.ply")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import open3d as o3d

    model_pts = load_gaussians(os.path.join(
        args.run, "point_cloud", f"iteration_{args.iters}", "point_cloud.ply"))
    ref = o3d.io.read_point_cloud(args.ref)
    ref = ref.voxel_down_sample(0.01)
    ref_pts = np.asarray(ref.points)
    print(f"model {len(model_pts):,} pts (op>0.5); ref {len(ref_pts):,} pts (1cm voxel)")

    # co-visible region: reference points that project into >=1 camera
    K = np.array([[923.7952710373842, 0, 695.65], [0, 923.7952710373842, 703.5885],
                  [0, 0, 1.]])  # 1408^2 scene intrinsics
    W = H = 1408
    poses = []
    for l in open(os.path.join(os.path.dirname(args.scene), "s4_planenose", "gt_model_txt", "images.txt")):
        p = l.split()
        if len(p) < 10:
            continue
        qw, qx, qy, qz = map(float, p[1:5])
        t = np.array(list(map(float, p[5:8])))
        n = np.linalg.norm([qw, qx, qy, qz])
        qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
        R = np.array([
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy)],
            [2 * (qx * qy + qw * qz), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qw * qx)],
            [2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx * qx + qy * qy)]])
        poses.append((R, t))
    vis = np.zeros(len(ref_pts), bool)
    for R, t in poses[::4]:  # every 4th camera is plenty for coverage
        Xc = ref_pts @ R.T + t
        z = Xc[:, 2]
        m = z > 0.1
        u = K[0, 0] * Xc[m, 0] / z[m] + K[0, 2]
        v = K[1, 1] * Xc[m, 1] / z[m] + K[1, 2]
        mi = np.where(m)[0][(u >= 0) & (u < W) & (v >= 0) & (v < H) & (z[m] < 12)]
        vis[mi] = True
    ref_vis = ref_pts[vis]
    print(f"co-visible reference: {len(ref_vis):,} / {len(ref_pts):,}")

    # ICP fine alignment (model -> reference), init identity
    src = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(model_pts))
    dst = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(ref_vis))
    icp = o3d.pipelines.registration.registration_icp(
        src, dst, 0.2, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPoint())
    T = icp.transformation
    model_al = model_pts @ T[:3, :3].T + T[:3, 3]
    align_shift_mm = float(np.linalg.norm(T[:3, 3]) * 1000)

    from scipy.spatial import cKDTree
    d_ref = cKDTree(ref_vis)
    d_mod = cKDTree(model_al)
    acc = d_ref.query(model_al, k=1)[0]        # model -> ref
    comp = d_mod.query(ref_vis, k=1)[0]        # ref -> model
    res = {
        "n_model_pts": int(len(model_pts)), "n_ref_covisible": int(len(ref_vis)),
        "icp_fitness": float(icp.fitness), "icp_rmse_mm": float(icp.inlier_rmse * 1000),
        "icp_translation_mm": align_shift_mm,
        "accuracy_mm": {"mean": float(acc.mean() * 1000), "median": float(np.median(acc) * 1000)},
        "completeness_mm": {"mean": float(comp.mean() * 1000), "median": float(np.median(comp) * 1000)},
        "chamfer_mm": float((acc.mean() + comp.mean()) / 2 * 1000),
    }
    out = args.out or os.path.join(args.run, "geometry_s4.json")
    json.dump(res, open(out, "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
