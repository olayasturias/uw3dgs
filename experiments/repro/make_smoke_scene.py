"""Build a small COLMAP-format smoke-test scene from EiffelTower/2015.

Picks 40 consecutive (by filename) registered images, writes sparse/0 text
model with the RADIAL camera cast to PINHOLE (distortion dropped -- fine for a
toolchain smoke test, NOT for experiments), copies the images, and filters
points3D to tracks visible in the subset.
"""
import os, shutil

SRC = r"D:\Datasets\EiffelTower\2015"
DST = r"D:\uw3dgs\smoke_scene"
N = 40

sfm = os.path.join(SRC, "sfm")
os.makedirs(os.path.join(DST, "sparse", "0"), exist_ok=True)
os.makedirs(os.path.join(DST, "images"), exist_ok=True)

# --- images.txt: two lines per image ---
entries = []  # (name, id_line, pts_line)
with open(os.path.join(sfm, "images.txt"), encoding="utf-8") as f:
    lines = [l for l in f if not l.startswith("#")]
for i in range(0, len(lines) - 1, 2):
    head = lines[i].split()
    entries.append((head[9], lines[i], lines[i + 1]))
entries.sort(key=lambda e: e[0])
mid = len(entries) // 2
subset = entries[mid:mid + N]
sel_ids = {e[1].split()[0] for e in subset}
print(f"selected {len(subset)} images: {subset[0][0]} .. {subset[-1][0]}")

# The 3DGS-family code truncates image names at the FIRST dot everywhere
# (dataset readers, render naming, metrics gt lookup), so basenames must be
# dot-free apart from the extension. Sanitize: 'a.000Z.png' -> 'a_000Z.png'.
def sanitize(name):
    stem, ext = os.path.splitext(name)
    return stem.replace(".", "_") + ext

with open(os.path.join(DST, "sparse", "0", "images.txt"), "w", encoding="utf-8") as f:
    f.write("# subset for smoke test\n")
    for name, h, p in subset:
        parts = h.split()
        parts[9] = sanitize(parts[9])
        f.write(" ".join(parts) + "\n")
        f.write(p)

# --- cameras.txt: RADIAL -> PINHOLE (fx=fy=f, drop k1,k2) ---
with open(os.path.join(sfm, "cameras.txt"), encoding="utf-8") as f:
    cam = [l for l in f if not l.startswith("#")][0].split()
cid, _, w, h_, f_, cx, cy = cam[0], cam[1], cam[2], cam[3], cam[4], cam[5], cam[6]
with open(os.path.join(DST, "sparse", "0", "cameras.txt"), "w", encoding="utf-8") as f:
    f.write(f"{cid} PINHOLE {w} {h_} {f_} {f_} {cx} {cy}\n")

# --- points3D.txt: keep points observed by any selected image ---
kept = 0
with open(os.path.join(sfm, "points3D.txt"), encoding="utf-8") as fin, \
     open(os.path.join(DST, "sparse", "0", "points3D.txt"), "w", encoding="utf-8") as fout:
    for l in fin:
        if l.startswith("#"):
            continue
        parts = l.split()
        track_imgs = parts[8::2]
        if any(t in sel_ids for t in track_imgs):
            fout.write(l)
            kept += 1
print(f"kept {kept} points")

for name, _, _ in subset:
    shutil.copy2(os.path.join(SRC, "images", name), os.path.join(DST, "images", sanitize(name)))
print("done ->", DST)
