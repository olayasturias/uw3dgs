"""Build the EIVA plane_nose scene (S4) in fork-ready COLMAP layout.

- Images: processed/left, resized 2816^2 -> 1408^2 (all systems then train at
  identical native resolution, below the forks' 1.6K auto-rescale threshold),
  names sanitized (dots -> underscores; the 3DGS family truncates at the first
  dot).
- Poses: pose_gt.txt = XMP extrinsics = direct world-to-camera [R|t]
  (rot_mode w2c_direct, validated by point_triangulator 2026-08-22).
- Init cloud: COLMAP triangulation with poses fixed. Deliberately NOT seeded
  from pointcloud_gt.ply -- that is the evaluation reference.
- depthmap/: IGEV metric depth (float32 npy) -> 8-bit PNG (min-max per image),
  as required by UW-GS / RUSplatting loaders.
"""
import json, os, subprocess, sys

import cv2
import numpy as np

COLMAP = r"D:\uw3dgs\colmap\bin\colmap.exe"
PY = sys.executable
SRC = r"D:\Datasets\EIVA\vobster_quay\plane_nose"
OUT = r"D:\uw3dgs\scenes\s4_planenose"
TOOLS = os.path.dirname(os.path.abspath(__file__))

SCALE = 0.5
FX = FY = 1847.5905420747683 * SCALE
CX, CY = 1391.3 * SCALE, 1407.177 * SCALE
W = H = 1408
CAM = f"PINHOLE,{W},{H},{FX},{FY},{CX},{CY}"


def sanitize(name):
    stem, ext = os.path.splitext(name)
    return stem.replace(".", "_") + ext


def run(cmd, log):
    with open(log, "w") as f:
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)


def main():
    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "depthmap"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "sparse", "0"), exist_ok=True)

    names = [l.split()[0] for l in open(os.path.join(SRC, "pose_gt.txt")) if len(l.split()) == 13]
    print(f"{len(names)} posed images")

    # 1. GT-pose COLMAP model with sanitized names
    model_txt = os.path.join(OUT, "gt_model_txt")
    subprocess.run([PY, os.path.join(TOOLS, "pose2colmap.py"), "--source", "planenose",
                    "--poses", os.path.join(SRC, "pose_gt.txt"), "--out", model_txt,
                    "--rot-mode", "w2c_direct", "--camera", CAM, "--sanitize-names"],
                   check=True)

    # 2. resize images + depth maps
    for n in names:
        dst = os.path.join(OUT, "images", sanitize(n))
        if not os.path.exists(dst):
            img = cv2.imread(os.path.join(SRC, "processed", "left", n), cv2.IMREAD_COLOR)
            cv2.imwrite(dst, cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 97])
        stem = os.path.splitext(n)[0]
        ddst = os.path.join(OUT, "depthmap", sanitize(n))
        if not os.path.exists(ddst):
            d = np.load(os.path.join(SRC, "processed", "igev_plusplus_depth", stem + "_depth.npy"))
            d = cv2.resize(d, (W, H), interpolation=cv2.INTER_NEAREST)
            lo, hi = np.percentile(d, 1), np.percentile(d, 99)
            d8 = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1) * 255
            cv2.imwrite(ddst, d8.astype(np.uint8))
    print("images + depthmaps written")

    with open(os.path.join(OUT, "image_list.txt"), "w") as f:
        f.write("\n".join(sanitize(n) for n in names) + "\n")

    # 3. features + matches + fixed-pose triangulation
    db = os.path.join(OUT, "db.db")
    if not os.path.exists(db):
        run([COLMAP, "feature_extractor", "--database_path", db,
             "--image_path", os.path.join(OUT, "images"),
             "--image_list_path", os.path.join(OUT, "image_list.txt"),
             "--ImageReader.single_camera", "1",
             "--ImageReader.camera_model", "PINHOLE",
             "--ImageReader.camera_params", f"{FX},{FY},{CX},{CY}",
             "--SiftExtraction.max_num_features", "16384"],
            os.path.join(OUT, "feat.log"))
        run([COLMAP, "sequential_matcher", "--database_path", db,
             "--SequentialMatching.overlap", "20",
             "--SequentialMatching.loop_detection", "0"],
            os.path.join(OUT, "match.log"))
    run([COLMAP, "point_triangulator", "--database_path", db,
         "--image_path", os.path.join(OUT, "images"),
         "--input_path", model_txt, "--output_path", os.path.join(OUT, "sparse", "0")],
        os.path.join(OUT, "tri.log"))
    subprocess.run([COLMAP, "model_analyzer", "--path", os.path.join(OUT, "sparse", "0")])

    json.dump({"dataset": "EIVA plane_nose", "n_images": len(names),
               "resolution": [W, H], "scale_from_native": SCALE,
               "pose_source": "pose_gt.txt (XMP extrinsics, w2c_direct)",
               "reference_cloud": os.path.join(SRC, "pointcloud_gt.ply"),
               "note": "init cloud triangulated, NOT seeded from reference"},
              open(os.path.join(OUT, "meta.json"), "w"), indent=2)
    print("done ->", OUT)


if __name__ == "__main__":
    main()
