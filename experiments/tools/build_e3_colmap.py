"""E3 pose-ablation scenes: COLMAP free SfM on the SAME undistorted images the
GT-pose scenes use. Intrinsics are fixed to the known calibration (generous to
COLMAP); SIFT settings are the tuned best-effort ones from the GT-pose
triangulation attempts. Registration rate = images in largest model / total —
a first-class result for Table III.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

COLMAP = r"D:\uw3dgs\colmap\bin\colmap.exe"
FX, FY, CX, CY = 788.57634, 787.13041, 980.65685, 571.03147


def sh(cmd, log):
    with open(log, "a") as f:
        f.write("\n$ " + " ".join(str(c) for c in cmd) + "\n")
        f.flush()
        return subprocess.run([str(c) for c in cmd], stdout=f,
                              stderr=subprocess.STDOUT).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--sift-peak", type=float, default=0.0067)
    ap.add_argument("--sift-edge", type=float, default=10.0)
    args = ap.parse_args()

    src = rf"D:\uw3dgs\scenes\s2_turbid{args.level}_trial1"
    out = rf"D:\uw3dgs\scenes\s2_turbid{args.level}_colmap"
    os.makedirs(os.path.join(out, "sparse"), exist_ok=True)
    log = os.path.join(out, "sfm.log")
    images = os.path.join(src, "images")
    n_total = len(os.listdir(images))

    db = os.path.join(out, "db.db")
    if not os.path.exists(db):
        sh([COLMAP, "feature_extractor", "--database_path", db, "--image_path", images,
            "--ImageReader.single_camera", "1", "--ImageReader.camera_model", "PINHOLE",
            "--ImageReader.camera_params", f"{FX},{FY},{CX},{CY}",
            "--SiftExtraction.peak_threshold", args.sift_peak,
            "--SiftExtraction.edge_threshold", args.sift_edge], log)
        sh([COLMAP, "exhaustive_matcher", "--database_path", db], log)
    rc = sh([COLMAP, "mapper", "--database_path", db, "--image_path", images,
             "--output_path", os.path.join(out, "sparse"),
             "--Mapper.ba_refine_focal_length", "0",
             "--Mapper.ba_refine_extra_params", "0"], log)

    # find largest sub-model
    best, best_n = None, 0
    for sub in sorted(Path(out, "sparse").glob("*")):
        if not (sub / "images.bin").exists():
            continue
        p = subprocess.run([COLMAP, "model_analyzer", "--path", str(sub)],
                           capture_output=True, text=True)
        txt = p.stdout + p.stderr
        n = 0
        for line in txt.splitlines():
            if "Registered images" in line:
                n = int(line.split()[-1])
        if n > best_n:
            best, best_n = sub, n
    meta = {"level_dir": args.level, "images_total": n_total,
            "registered": best_n, "registration_rate": best_n / n_total,
            "largest_model": str(best), "mapper_rc": rc,
            "sift_peak": args.sift_peak, "sift_edge": args.sift_edge,
            "note": "free SfM on identical undistorted images; intrinsics fixed to calibration"}
    # promote largest model to sparse/0 for training use
    if best is not None and best.name != "0":
        import shutil
        dst = Path(out, "sparse", "0")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(best), str(dst))
        meta["largest_model"] = str(dst)
    # scene images: reuse the trial scene's (relative junction not portable; copy list)
    meta["images_dir"] = images
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
