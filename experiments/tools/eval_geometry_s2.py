"""S2 geometric evaluation: rendered depth vs the 0-NTU world-frame stereo
reference (see FINDINGS.md F8 for why the reference is level-0 only).

For each held-out view: project reference points (tank frame) into the camera
(GT pose c2w_optical, raw K), keep the nearest reference z per pixel bucket,
sample the model's rendered depth there, report absolute error statistics in
millimetres. Metric scale is real (testbed kinematics).
"""
import argparse, csv, json, os
import numpy as np

KL = np.array([[788.57634, 0., 980.65685], [0., 787.13041, 571.03147], [0., 0., 1.]])
W, H = 1920, 1216
REF = r"D:\uw3dgs\scenes\s2_stereo_ref_world.npz"
POSES_TPL = (r"D:\Datasets\SOTRUE\sotrue\scripts\interpolated_image_poses"
             r"\turbid{level}_trial{trial}\left_interpolated_timestamps.csv")


def quat_to_R(qx, qy, qz, qw):
    q = np.array([qw, qx, qy, qz], float)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depths", required=True, help="dir of <stem>_depth.npy renders")
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pts_w = np.load(REF)["points"]  # (N,3) tank frame
    poses = {}
    for r in csv.DictReader(open(POSES_TPL.format(level=args.level, trial=args.trial)),
                            delimiter=" "):
        poses[os.path.splitext(r["image_name"])[0]] = (
            np.array([float(r["x"]), float(r["y"]), float(r["z"])]),
            quat_to_R(float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"])))

    per_view, all_err = {}, []
    for f in sorted(os.listdir(args.depths)):
        if not f.endswith("_depth.npy"):
            continue
        stem = f[:-len("_depth.npy")]
        if stem.lower().endswith((".png", ".jpg")):
            stem = os.path.splitext(stem)[0]
        C, R_c2w = poses[stem]
        X_c = (pts_w - C) @ R_c2w  # world->cam: R^T (x - C); row-vector form
        z = X_c[:, 2]
        front = z > 0.05
        u = KL[0, 0] * X_c[front, 0] / z[front] + KL[0, 2]
        v = KL[1, 1] * X_c[front, 1] / z[front] + KL[1, 2]
        zf = z[front]
        inb = (u >= 0) & (u < W - 1) & (v >= 0) & (v < H - 1)
        ui, vi, zf = u[inb].astype(int), v[inb].astype(int), zf[inb]
        # occlusion handling: keep the NEAREST reference point per pixel
        lin = vi * W + ui
        order = np.argsort(zf)
        lin_o, z_o = lin[order], zf[order]
        first = np.unique(lin_o, return_index=True)[1]
        lin_u, z_u = lin_o[first], z_o[first]

        depth = np.load(os.path.join(args.depths, f))
        d = depth.reshape(-1)[lin_u]
        valid = (d > 0.05) & (d < 10)
        alpha_f = os.path.join(args.depths, f.replace("_depth.npy", "_alpha.npy"))
        if os.path.exists(alpha_f):
            a = np.load(alpha_f).reshape(-1)[lin_u]
            valid &= a > 0.5
        err = np.abs(d[valid] - z_u[valid]) * 1000.0  # mm
        per_view[stem] = {"n": int(valid.sum()),
                          "mae_mm": float(err.mean()),
                          "medae_mm": float(np.median(err)),
                          "rmse_mm": float(np.sqrt((err ** 2).mean()))}
        all_err.append(err)

    allc = np.concatenate(all_err)
    agg = {"n_views": len(per_view), "n_samples": int(len(allc)),
           "mae_mm": float(allc.mean()), "medae_mm": float(np.median(allc)),
           "rmse_mm": float(np.sqrt((allc ** 2).mean()))}
    json.dump({"aggregate": agg, "per_view": per_view,
               "reference": REF, "level": args.level, "trial": args.trial},
              open(args.out, "w"), indent=2)
    print(json.dumps(agg, indent=2))


if __name__ == "__main__":
    main()
