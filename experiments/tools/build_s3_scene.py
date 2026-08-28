"""Build the Eiffel Tower 2015 scene (S3) for E5 (artificial-light probe).

The IFREMER dataset ships a full COLMAP TEXT model (RADIAL camera, 4914
images, 525k points). We: subsample every Nth image (default 16 -> ~307
views), sanitize dotted basenames (copying the subset to a staging dir),
filter points to visible tracks, then run image_undistorter to get the
fork-ready PINHOLE scene. No feature matching needed.
"""
import argparse, os, shutil, subprocess

COLMAP = r"D:\uw3dgs\colmap\bin\colmap.exe"
SRC = r"D:\Datasets\EiffelTower\2015"
OUT = r"D:\uw3dgs\scenes\s3_eiffel2015"


def sanitize(name):
    stem, ext = os.path.splitext(name)
    return stem.replace(".", "_") + ext


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--subsample", type=int, default=16)
    ap.add_argument("--contiguous", type=int, default=0,
                    help="instead of global subsampling, take this many CONSECUTIVE "
                         "frames from the best-tracked window (dense overlap)")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    OUT = args.out

    sfm = os.path.join(SRC, "sfm")
    stage = os.path.join(OUT, "_stage")
    os.makedirs(os.path.join(stage, "images"), exist_ok=True)
    os.makedirs(os.path.join(stage, "model"), exist_ok=True)

    lines = [l for l in open(os.path.join(sfm, "images.txt"), encoding="utf-8")
             if not l.startswith("#")]
    entries = [(lines[i].split()[9], lines[i], lines[i + 1])
               for i in range(0, len(lines) - 1, 2)]
    entries.sort(key=lambda e: e[0])
    if args.contiguous:
        # observations per image = POINTS2D triplets with a valid POINT3D_ID
        obs = [sum(1 for t in p.split()[2::3] if t != "-1") for _, _, p in entries]
        n = args.contiguous
        csum = [0]
        for o in obs:
            csum.append(csum[-1] + o)
        best = max(range(len(entries) - n),
                   key=lambda i: csum[i + n] - csum[i])
        subset = entries[best:best + n]
        print(f"contiguous window [{best}:{best+n}] "
              f"({subset[0][0]} .. {subset[-1][0]}), "
              f"mean tracked obs/img {(csum[best+n]-csum[best])/n:.0f}")
    else:
        subset = entries[::args.subsample]
    sel_ids = {e[1].split()[0] for e in subset}
    print(f"{len(subset)} / {len(entries)} images selected")

    with open(os.path.join(stage, "model", "images.txt"), "w", encoding="utf-8") as f:
        for name, h, p in subset:
            parts = h.split()
            parts[9] = sanitize(parts[9])
            f.write(" ".join(parts) + "\n")
            f.write(p)
    shutil.copyfile(os.path.join(sfm, "cameras.txt"),
                    os.path.join(stage, "model", "cameras.txt"))
    kept = 0
    with open(os.path.join(sfm, "points3D.txt"), encoding="utf-8") as fin, \
         open(os.path.join(stage, "model", "points3D.txt"), "w", encoding="utf-8") as fout:
        for l in fin:
            if l.startswith("#"):
                continue
            if any(t in sel_ids for t in l.split()[8::2]):
                fout.write(l)
                kept += 1
    print(f"{kept} points kept")

    for name, _, _ in subset:
        dst = os.path.join(stage, "images", sanitize(name))
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(SRC, "images", name), dst)

    subprocess.run([COLMAP, "image_undistorter",
                    "--image_path", os.path.join(stage, "images"),
                    "--input_path", os.path.join(stage, "model"),
                    "--output_path", OUT, "--output_type", "COLMAP"], check=True)
    os.makedirs(os.path.join(OUT, "sparse", "0"), exist_ok=True)
    for f in ("cameras.bin", "images.bin", "points3D.bin"):
        src = os.path.join(OUT, "sparse", f)
        if os.path.exists(src):
            shutil.move(src, os.path.join(OUT, "sparse", "0", f))
    shutil.rmtree(stage)
    for junk in ("stereo", "run-colmap-geometric.sh", "run-colmap-photometric.sh"):
        p = os.path.join(OUT, junk)
        (shutil.rmtree if os.path.isdir(p) else os.remove)(p) if os.path.exists(p) else None
    subprocess.run([COLMAP, "model_analyzer", "--path", os.path.join(OUT, "sparse", "0")])
    print("done ->", OUT)


if __name__ == "__main__":
    main()
