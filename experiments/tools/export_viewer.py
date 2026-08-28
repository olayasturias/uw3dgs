"""Stage descriptively-named 3DGS .ply files for browser viewing (SuperSplat).

Copies each model's point_cloud.ply to D:\\uw3dgs\\viewer_exports\\<name>.ply.
For models over ~150 MB an additional *_lite.ply is written with the f_rest_*
(view-dependent SH) properties stripped: colours are kept (SH0), size drops
~4x, and the geometry/floater structure - the thing worth screenshotting - is
unchanged.
"""
import os
import shutil

import numpy as np
from plyfile import PlyData, PlyElement

R = r"D:\uw3dgs\runs"
OUT = r"D:\uw3dgs\viewer_exports"
os.makedirs(OUT, exist_ok=True)

MODELS = {
    # S1 benchmark
    "s1_benchmark_M0_3dgs":          "e1_s1_m0",
    "s1_benchmark_M2_watersplatting": "e1_s1_m2",
    "s1_benchmark_M3_seasplat":      "e1_s1_m3",
    "s1_benchmark_M4_uwgs":          "e1_s1_m4_retry",
    "s1_ablation_A2_no_depth_sup":   "e4_a2_s1",
    # S2 tank
    "s2_clear0NTU_M0_3dgs":          "e2_t0_m0",
    "s2_turbid12NTU_M0_3dgs":        "e2_t5_m0",
    "s2_turbid12NTU_M2_watersplatting": "e2_t5_m2",
    "s2_turbid12NTU_M3_seasplat":    "e2_t5_m3",
    # S3 deep vent
    "s3_deepvent_M0_3dgs":           "e5_s3dense_m0",
    "s3_deepvent_M2_watersplatting": "e5_s3dense_m2",
    "s3_deepvent_M3_seasplat":       "e5_s3_m3",
    # S4 industrial survey
    "s4_survey_M0_3dgs":             "e1_s4_m0",
    "s4_survey_M1_uie3dgs":          "e1_s4_m1",
    "s4_survey_M2_watersplatting":   "e1_s4_m2",
    "s4_survey_M3_seasplat":         "e1_s4_m3",
}
LITE_THRESHOLD = 150 * 1024 * 1024


def strip_sh(src, dst):
    v = PlyData.read(src)["vertex"]
    keep = [p.name for p in v.properties if not p.name.startswith("f_rest")]
    arr = np.empty(v.count, dtype=[(k, v.data.dtype[k]) for k in keep])
    for k in keep:
        arr[k] = v[k]
    PlyData([PlyElement.describe(arr, "vertex")]).write(dst)


total = 0
for name, run in MODELS.items():
    src = os.path.join(R, run, "point_cloud", "iteration_30000", "point_cloud.ply")
    if not os.path.exists(src):
        print("MISSING", run)
        continue
    dst = os.path.join(OUT, name + ".ply")
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    total += 1
    if os.path.getsize(src) > LITE_THRESHOLD:
        lite = os.path.join(OUT, name + "_lite.ply")
        if not os.path.exists(lite):
            strip_sh(src, lite)
        print(f"{name}: {os.path.getsize(dst)//2**20} MB (+lite "
              f"{os.path.getsize(lite)//2**20} MB)")
    else:
        print(f"{name}: {os.path.getsize(dst)//2**20} MB")

open(os.path.join(OUT, "README.txt"), "w").write("""3DGS models for browser viewing
================================
Open https://superspl.at/editor (or https://playcanvas.com/supersplat) and
drag any .ply here into the page. Orbit: left-drag; pan: right-drag; zoom:
wheel. Screenshot: the camera icon in the toolbar (renders at canvas size).

*_lite.ply = same model with view-dependent colour (SH bands) stripped:
4x smaller, identical geometry/floaters, ambient colours only.

Suggested screenshots for the paper (Fig. 3 / failure gallery):
- s2_turbid12NTU_M0_3dgs: orbit sideways -> the "haze wall" reconstructed as
  solid geometry between camera trajectory and tank wall.
- s1_benchmark_M3_seasplat(_lite): tilt to grazing angle -> the floating
  translucent veil over the reef (floater mass 0.37).
- s3_deepvent_M2_watersplatting: 27k-gaussian residue after the medium field
  absorbed the scene.
- s2_turbid12NTU_M2_watersplatting: 3k gaussians - the scene dissolved.
- s4_survey_M3_seasplat vs s4_survey_M0_3dgs: misplaced opaque geometry.
NOTE: tank-scene models (s2_*) are metric (metres); others are in their
scene's SfM scale.
""")
print(f"\n{total} models staged -> {OUT}")
