"""Closing eval batch: surface-depth renders + floater masses for the S3/S4
runs that lack them (Table IV floater column). GPU1."""
import json
import os
import subprocess
import sys

PY = sys.executable
T = r"D:\uw3dgs\tools"
JOBS = [
    ("e1_s4_m0", r"D:\uw3dgs\scenes\s4_planenose"),
    ("e1_s4_m2", r"D:\uw3dgs\scenes\s4_planenose"),
    ("e1_s4_m3", r"D:\uw3dgs\scenes\s4_planenose"),
    ("e1_s4_m1", r"D:\uw3dgs\scenes\s4_planenose_uie"),
    ("e5_s3dense_m0", r"D:\uw3dgs\scenes\s3_eiffel2015_dense"),
    ("e5_s3_m3", r"D:\uw3dgs\scenes\s3_eiffel2015_dense"),
    ("e6_lin_s1_m3", r"D:\uw3dgs\scenes\s1_curacao_linear"),
]
env = dict(os.environ, CUDA_VISIBLE_DEVICES="1")
out = {}
for rid, scene in JOBS:
    run = rf"D:\uw3dgs\runs\{rid}"
    ply = os.path.join(run, "point_cloud", "iteration_30000", "point_cloud.ply")
    dd = os.path.join(run, "depths_surf")
    fm = os.path.join(run, "floater_mass.json")
    if not os.path.exists(ply):
        print(rid, "NO PLY"); continue
    if not os.path.exists(fm):
        if not os.path.isdir(dd):
            r = subprocess.run([PY, os.path.join(T, "render_depth_3dgs.py"),
                                "--ply", ply, "--scene", scene, "--out", dd,
                                "--min-opacity", "0.5"],
                               env=env, capture_output=True, text=True)
            if r.returncode:
                print(rid, "RENDER FAILED:", r.stdout[-200:], r.stderr[-200:]); continue
        r = subprocess.run([PY, os.path.join(T, "floater_mass.py"), "--run", run,
                            "--scene", scene], env=env, capture_output=True, text=True)
        if r.returncode:
            print(rid, "FLOATER FAILED:", r.stderr[-200:]); continue
    out[rid] = json.load(open(fm))["floater_mass"]
    print(rid, "floater@0.1 =", round(out[rid]["0.1"], 3), flush=True)
print("BATCH DONE")
