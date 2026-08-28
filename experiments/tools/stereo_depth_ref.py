"""Stereo depth reference for S2 held-out views (metric, in the TRAINING frame).

The right camera is never trained on, so SGBM stereo depth is an independent
geometric check on every S2 run (mm-scale is
meaningful because testbed kinematics give metric scale).

Pipeline per held-out frame:
  raw L/R -> rectify (ROS calib R,P) -> SGBM disparity -> Z = fx*B/d (rectified)
  -> 3D in rectified-left frame -> rotate by R_rect^T into raw-left camera frame
  -> project with the raw K (the training scenes' PINHOLE camera)
  -> save sparse (u, v, Z) samples as npz.

Held-out stems = sorted(scene image names)[::8]  (matches the forks' llffhold=8
and nerfstudio's --eval-mode interval 8 on the same sorted list).
"""
import argparse, json, os
import numpy as np
import cv2

SOTRUE = r"D:\Datasets\SOTRUE"

KL = np.array([[788.57634, 0., 980.65685], [0., 787.13041, 571.03147], [0., 0., 1.]])
DL = np.array([-0.016788, -0.002846, -0.003082, -0.000599, -0.000072])
RL = np.array([[0.99988556, 0.00259775, 0.0149037],
               [-0.00255624, 0.9999928, -0.002804],
               [-0.01491087, 0.00276558, 0.999885]])
PL = np.array([[811.45719, 0., 970.80426, 0.],
               [0., 811.45719, 567.69419, 0.],
               [0., 0., 1., 0.]])
KR = np.array([[777.55213, 0., 969.34359], [0., 775.88695, 588.76049], [0., 0., 1.]])
DR = np.array([-0.021041, 0.010499, -0.003923, -0.000324, -0.007830])
RR = np.array([[0.99988738, 0.00211514, 0.01485785],
               [-0.00215651, 0.99999384, 0.00276892],
               [-0.0148519, -0.00280065, 0.99988578]])
PR = np.array([[811.45719, 0., 970.80426, -61.5084],
               [0., 811.45719, 567.69419, 0.],
               [0., 0., 1., 0.]])
W, H = 1920, 1216
FX_RECT = PL[0, 0]
BASELINE = -PR[0, 3] / PR[0, 0]  # 0.0758 m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--scene", required=True, help="training scene dir (for the image list)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    names = sorted(os.listdir(os.path.join(args.scene, "images")))
    test = names[::8]
    os.makedirs(args.out, exist_ok=True)

    mapLx, mapLy = cv2.initUndistortRectifyMap(KL, DL, RL, PL, (W, H), cv2.CV_32FC1)
    mapRx, mapRy = cv2.initUndistortRectifyMap(KR, DR, RR, PR, (W, H), cv2.CV_32FC1)
    sgbm = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=160, blockSize=7,
        P1=8 * 3 * 49, P2=32 * 3 * 49, uniquenessRatio=8,
        speckleWindowSize=120, speckleRange=2, disp12MaxDiff=1,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)

    src = os.path.join(SOTRUE, f"trial{args.trial}", f"turbid{args.level}")
    stats = []
    for n in test:
        L = cv2.imread(os.path.join(src, "left", n))
        R = cv2.imread(os.path.join(src, "right", n.replace("left", "right")))
        if L is None or R is None:
            print("MISSING pair for", n)
            continue
        Lr = cv2.remap(L, mapLx, mapLy, cv2.INTER_LINEAR)
        Rr = cv2.remap(R, mapRx, mapRy, cv2.INTER_LINEAR)
        disp = sgbm.compute(cv2.cvtColor(Lr, cv2.COLOR_BGR2GRAY),
                            cv2.cvtColor(Rr, cv2.COLOR_BGR2GRAY)).astype(np.float32) / 16.0
        valid = disp > 1.0
        Z = np.where(valid, FX_RECT * BASELINE / np.maximum(disp, 1e-6), 0)
        # rectified pixels -> 3D (rectified-left frame)
        vs, us = np.nonzero(valid)
        z = Z[vs, us]
        keep = (z > 0.2) & (z < 5.0)  # tank scale
        us, vs, z = us[keep], vs[keep], z[keep]
        x = (us - PL[0, 2]) / FX_RECT * z
        y = (vs - PL[1, 2]) / PL[1, 1] * z
        X_rect = np.stack([x, y, z], axis=0)
        X_cam = RL.T @ X_rect                     # into raw-left camera frame
        # project with raw K (training frame is undistorted at raw K)
        u2 = KL[0, 0] * X_cam[0] / X_cam[2] + KL[0, 2]
        v2 = KL[1, 1] * X_cam[1] / X_cam[2] + KL[1, 2]
        inb = (u2 >= 0) & (u2 < W) & (v2 >= 0) & (v2 < H)
        np.savez_compressed(os.path.join(args.out, os.path.splitext(n)[0] + ".npz"),
                            u=u2[inb].astype(np.float32), v=v2[inb].astype(np.float32),
                            z=X_cam[2][inb].astype(np.float32))
        stats.append((n, int(inb.sum()), float(np.median(X_cam[2][inb])) if inb.any() else None))
        print(n, "samples:", int(inb.sum()))
    json.dump({"frames": stats, "baseline_m": BASELINE,
               "note": "z in metres, raw-left camera frame; project with raw K"},
              open(os.path.join(args.out, "stats.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
