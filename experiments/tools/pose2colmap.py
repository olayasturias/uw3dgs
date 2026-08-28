"""Convert GT camera poses to a COLMAP text model, ready for point_triangulator.

Supports the two pose sources of this study:
  --source sotrue      SOTRUE interpolated_image_poses CSV (x y z qx qy qz qw,
                       pose of the LEFT CAMERA CENTER in the tank frame)
  --source planenose   EIVA plane_nose pose_gt.txt (name tx ty tz r00..r22)

Both give a world pose of the camera; whether the stored rotation maps
camera->world or world->camera, and which axis convention the camera frame
uses, is resolved empirically via --rot-mode (test with point_triangulator,
keep the mode that triangulates).

rot modes:
  c2w_optical  stored R (from quat / matrix) is camera-to-world of a COLMAP
               optical frame (x right, y down, z forward).  COLMAP needs
               world-to-camera:  R_wc = R^T,  t = -R^T C.
  w2c_optical  stored R is already world-to-camera optical.
  c2w_ros      stored R is camera-to-world of a ROS body frame (x forward,
               z up).  Optical = body * R_BO with
               R_BO = [[0,-1,0],[0,0,-1],[1,0,0]]^T (x_b=z_o, y_b=-x_o, z_b=-y_o).
"""
import argparse, csv, os
import numpy as np


def quat_to_R(qx, qy, qz, qw):
    q = np.array([qw, qx, qy, qz], dtype=float)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def R_to_quat(R):
    # returns qw qx qy qz
    K = np.array([
        [R[0, 0] + R[1, 1] + R[2, 2], R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]],
        [R[2, 1] - R[1, 2], R[0, 0] - R[1, 1] - R[2, 2], R[1, 0] + R[0, 1], R[0, 2] + R[2, 0]],
        [R[0, 2] - R[2, 0], R[1, 0] + R[0, 1], R[1, 1] - R[0, 0] - R[2, 2], R[2, 1] + R[1, 2]],
        [R[1, 0] - R[0, 1], R[0, 2] + R[2, 0], R[2, 1] + R[1, 2], R[2, 2] - R[0, 0] - R[1, 1]],
    ]) / 3.0
    w, V = np.linalg.eigh(K)
    q = V[:, np.argmax(w)]
    if q[0] < 0:
        q = -q
    return q


# ROS body (x fwd, y left, z up) -> optical (x right, y down, z fwd)
R_BODY_OPTICAL = np.array([[0., -1., 0.], [0., 0., -1.], [1., 0., 0.]]).T


def load_sotrue(csv_path, subsample=1):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f, delimiter=" ")
        for i, r in enumerate(rd):
            if i % subsample:
                continue
            C = np.array([float(r["x"]), float(r["y"]), float(r["z"])])
            R = quat_to_R(float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"]))
            rows.append((r["image_name"], C, R))
    return rows


def load_planenose(txt_path, subsample=1):
    rows = []
    with open(txt_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            p = line.split()
            if len(p) != 13 or i % subsample:
                continue
            C = np.array([float(v) for v in p[1:4]])
            R = np.array([float(v) for v in p[4:13]]).reshape(3, 3)
            rows.append((p[0], C, R))
    return rows


FLIP_GL = np.diag([1., -1., -1.])


def convert(rows, rot_mode):
    # rows carry (name, T, R) where T is EITHER the camera center (modes that
    # end in _optical/_ros treat it as C) or the w2c translation (w2c_direct*).
    out = []
    for name, T, R in rows:
        if rot_mode == "c2w_optical":
            R_wc, t = R.T, -R.T @ T
        elif rot_mode == "w2c_optical":
            R_wc, t = R, -R @ T
        elif rot_mode == "c2w_ros":
            R_wc = (R @ R_BODY_OPTICAL).T
            t = -R_wc @ T
        elif rot_mode == "w2c_direct":
            R_wc, t = R, T
        elif rot_mode == "w2c_direct_gl":
            R_wc, t = FLIP_GL @ R, FLIP_GL @ T
        elif rot_mode == "c2w_optical_gl":
            R_wc = (R @ FLIP_GL).T
            t = -R_wc @ T
        else:
            raise ValueError(rot_mode)
        out.append((name, R_to_quat(R_wc), t))
    return out


def write_model(out_dir, cams, entries, name_map=None):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "cameras.txt"), "w") as f:
        for cid, (model, w, h, params) in cams.items():
            f.write(f"{cid} {model} {w} {h} " + " ".join(str(p) for p in params) + "\n")
    with open(os.path.join(out_dir, "images.txt"), "w") as f:
        for i, (name, q, t) in enumerate(entries, start=1):
            if name_map:
                name = name_map(name)
            f.write(f"{i} {q[0]} {q[1]} {q[2]} {q[3]} {t[0]} {t[1]} {t[2]} 1 {name}\n\n")
    open(os.path.join(out_dir, "points3D.txt"), "w").close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=["sotrue", "planenose"])
    ap.add_argument("--poses", required=True)
    ap.add_argument("--out", required=True, help="output sparse model dir")
    ap.add_argument("--rot-mode", default="c2w_optical",
                    choices=["c2w_optical", "w2c_optical", "c2w_ros", "w2c_direct", "w2c_direct_gl", "c2w_optical_gl"])
    ap.add_argument("--subsample", type=int, default=1)
    ap.add_argument("--camera", required=True,
                    help="MODEL,W,H,p1,p2,... e.g. PINHOLE,1920,1216,811.4,811.4,970.8,567.7")
    ap.add_argument("--sanitize-names", action="store_true",
                    help="replace dots in basename stems with underscores")
    args = ap.parse_args()

    parts = args.camera.split(",")
    cams = {1: (parts[0], int(parts[1]), int(parts[2]), [float(v) for v in parts[3:]])}

    rows = (load_sotrue if args.source == "sotrue" else load_planenose)(args.poses, args.subsample)
    entries = convert(rows, args.rot_mode)

    name_map = None
    if args.sanitize_names:
        def name_map(n):
            stem, ext = os.path.splitext(n)
            return stem.replace(".", "_") + ext

    write_model(args.out, cams, entries, name_map)
    print(f"wrote {len(entries)} images -> {args.out}  (rot_mode={args.rot_mode})")


if __name__ == "__main__":
    main()
