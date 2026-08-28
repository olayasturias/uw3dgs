"""Lift the 0-NTU stereo depth reference into the shared tank (world) frame.

Rationale (FINDINGS.md F8): at 7-12 NTU SGBM locks onto the particulate field,
so per-level stereo references are invalid. The tank scene is static and all
levels/trials share one world origin, so the 0-NTU test-frame stereo points,
transformed camera->world with the 0-NTU GT poses, serve every level.

Output: one npz of world-frame points (metres) + per-source-frame provenance.
At eval time: project into any level's camera (GT pose, raw K), compare
rendered depth at those pixels.
"""
import csv, json, os
import numpy as np

SCENE = r"D:\uw3dgs\scenes\s2_turbid0_trial1"
POSES = (r"D:\Datasets\SOTRUE\sotrue\scripts\interpolated_image_poses"
         r"\turbid0_trial1\left_interpolated_timestamps.csv")
OUT = r"D:\uw3dgs\scenes\s2_stereo_ref_world.npz"

KL = np.array([[788.57634, 0., 980.65685], [0., 787.13041, 571.03147], [0., 0., 1.]])


def quat_to_R(qx, qy, qz, qw):
    q = np.array([qw, qx, qy, qz], float)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


poses = {}
for r in csv.DictReader(open(POSES), delimiter=" "):
    poses[r["image_name"]] = (
        np.array([float(r["x"]), float(r["y"]), float(r["z"])]),
        quat_to_R(float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"])))

ref_dir = os.path.join(SCENE, "stereo_ref")
pts_w, prov = [], []
rng = np.random.default_rng(0)
for f in sorted(os.listdir(ref_dir)):
    if not f.endswith(".npz"):
        continue
    name = f.replace(".npz", ".png")
    if name not in poses:
        print("no pose for", name)
        continue
    d = np.load(os.path.join(ref_dir, f))
    u, v, z = d["u"], d["v"], d["z"]
    # subsample to keep the reference tractable (~100k/frame)
    if len(z) > 100_000:
        idx = rng.choice(len(z), 100_000, replace=False)
        u, v, z = u[idx], v[idx], z[idx]
    x = (u - KL[0, 2]) / KL[0, 0] * z
    y = (v - KL[1, 2]) / KL[1, 1] * z
    X_cam = np.stack([x, y, z], axis=0)
    C, R_c2w = poses[name]  # camera-to-world optical (validated)
    X_w = (R_c2w @ X_cam).T + C
    pts_w.append(X_w.astype(np.float32))
    prov.append((name, len(z)))

allpts = np.concatenate(pts_w, axis=0)
np.savez_compressed(OUT, points=allpts)
json.dump({"frames": prov, "n_points": int(len(allpts)),
           "source": "turbid0 trial1 test frames (every 8th), SGBM stereo",
           "frame": "tank/world (SOTRUE origin), metres"},
          open(OUT.replace(".npz", ".json"), "w"), indent=2)
print(f"world-frame stereo reference: {len(allpts):,} points from {len(prov)} frames -> {OUT}")
