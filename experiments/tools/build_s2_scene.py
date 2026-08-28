"""Build one SOTRUE scene (S2) in fork-ready COLMAP layout.

Steps: undistort left images (plumb_bob -> pinhole at the raw K), subsample,
write GT poses as a COLMAP model (rot_mode c2w_optical -- validated by
point_triangulator on 2026-08-22), extract/match features, triangulate the
initial point cloud with poses FIXED, and record the measured mean NTU.

Usage: build_s2_scene.py --level 0 --trial 1 [--subsample 4]
Output: D:\\uw3dgs\\scenes\\s2_turbid{level}_trial{trial}
"""
import argparse, csv, json, os, shutil, subprocess, sys

import cv2
import numpy as np

COLMAP = r"D:\uw3dgs\colmap\bin\colmap.exe"
PY = sys.executable
SOTRUE = r"D:\Datasets\SOTRUE"
TOOLS = os.path.dirname(os.path.abspath(__file__))

K = np.array([[788.57634, 0., 980.65685], [0., 787.13041, 571.03147], [0., 0., 1.]])
D = np.array([-0.016788, -0.002846, -0.003082, -0.000599, -0.000072])
W, H = 1920, 1216
CAM_PINHOLE = f"PINHOLE,{W},{H},{K[0,0]},{K[1,1]},{K[0,2]},{K[1,2]}"


def run(cmd, log):
    with open(log, "w") as f:
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True, help="turbid level dir index 0..5")
    ap.add_argument("--trial", type=int, default=1)
    ap.add_argument("--subsample", type=int, default=4)
    # Turbid images are low-contrast: default SIFT peak threshold (0.0067)
    # yields ~32 features/image at 7 NTU. Lower it for the turbid levels.
    ap.add_argument("--sift-peak", type=float, default=0.0067)
    ap.add_argument("--sift-edge", type=float, default=10.0)
    ap.add_argument("--no-triangulate", action="store_true",
                    help="eval-only scene: GT-pose model as sparse/0, no SIFT/points")
    args = ap.parse_args()

    src_img = os.path.join(SOTRUE, f"trial{args.trial}", f"turbid{args.level}", "left")
    poses = os.path.join(SOTRUE, "sotrue", "scripts", "interpolated_image_poses",
                         f"turbid{args.level}_trial{args.trial}",
                         "left_interpolated_timestamps.csv")
    out = rf"D:\uw3dgs\scenes\s2_turbid{args.level}_trial{args.trial}"
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    os.makedirs(os.path.join(out, "sparse", "0"), exist_ok=True)

    # 1. pose model (also defines the image subset)
    model_txt = os.path.join(out, "gt_model_txt")
    subprocess.run([PY, os.path.join(TOOLS, "pose2colmap.py"), "--source", "sotrue",
                    "--poses", poses, "--out", model_txt, "--rot-mode", "c2w_optical",
                    "--subsample", str(args.subsample), "--camera", CAM_PINHOLE], check=True)
    names = [l.split()[9] for l in open(os.path.join(model_txt, "images.txt")) if l.strip()]
    with open(os.path.join(out, "image_list.txt"), "w") as f:
        f.write("\n".join(names) + "\n")

    # 2. undistort selected images to pinhole at the raw K
    m1, m2 = cv2.initUndistortRectifyMap(K, D, None, K, (W, H), cv2.CV_32FC1)
    for n in names:
        dst = os.path.join(out, "images", n)
        if os.path.exists(dst):
            continue
        img = cv2.imread(os.path.join(src_img, n), cv2.IMREAD_COLOR)
        cv2.imwrite(dst, cv2.remap(img, m1, m2, cv2.INTER_LINEAR))
    print(f"undistorted {len(names)} images")

    # 3. features + matches + fixed-pose triangulation
    if args.no_triangulate:
        run([COLMAP, "model_converter", "--input_path", model_txt,
             "--output_path", os.path.join(out, "sparse", "0"),
             "--output_type", "BIN"], os.path.join(out, "convert.log"))
        _write_meta(args, out, len(names), no_points=True)
        return
    db = os.path.join(out, "db.db")
    if not os.path.exists(db):
        run([COLMAP, "feature_extractor", "--database_path", db,
             "--image_path", os.path.join(out, "images"),
             "--image_list_path", os.path.join(out, "image_list.txt"),
             "--ImageReader.single_camera", "1",
             "--ImageReader.camera_model", "PINHOLE",
             "--ImageReader.camera_params", ",".join(CAM_PINHOLE.split(",")[3:]),
             "--SiftExtraction.peak_threshold", str(args.sift_peak),
             "--SiftExtraction.edge_threshold", str(args.sift_edge)],
            os.path.join(out, "feat.log"))
        run([COLMAP, "exhaustive_matcher", "--database_path", db],
            os.path.join(out, "match.log"))
    run([COLMAP, "point_triangulator", "--database_path", db,
         "--image_path", os.path.join(out, "images"),
         "--input_path", model_txt, "--output_path", os.path.join(out, "sparse", "0")],
        os.path.join(out, "tri.log"))
    subprocess.run([COLMAP, "model_analyzer", "--path", os.path.join(out, "sparse", "0")])

    _write_meta(args, out, len(names))


def _write_meta(args, out, n_images, no_points=False):
    # measured NTU over this sequence's time span
    ts_file = os.path.join(SOTRUE, f"trial{args.trial}", f"turbid{args.level}",
                           "left_timestamps.csv")
    ts = [float(r["timestamp_sec"]) for r in csv.DictReader(open(ts_file))]
    t0, t1 = min(ts), max(ts)
    ntu = [float(r["turbidity_ntu"]) for r in
           csv.DictReader(open(os.path.join(SOTRUE, "sotrue", "turbidity.csv")))
           if t0 <= float(r["timestamp_sec"]) <= t1]
    meta = {"dataset": "SOTRUE", "level_dir": args.level, "trial": args.trial,
            "subsample": args.subsample, "n_images": n_images,
            "measured_ntu_mean": float(np.mean(ntu)) if ntu else None,
            "measured_ntu_median": float(np.median(ntu)) if ntu else None,
            "measured_ntu_std": float(np.std(ntu)) if ntu else None,
            "n_ntu_samples": len(ntu),
            "ntu_samples": ntu,
            "pose_source": "encoder GT (interpolated, c2w_optical)",
            "undistorted": "cv2 plumb_bob -> PINHOLE at raw K"}
    if no_points:
        meta["eval_only"] = "no points3D; GT-pose model only (repeatability eval)"
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
