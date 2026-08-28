"""Copy the paper-relevant experiment artifacts from D:\\uw3dgs into the git
repo under experiments/. Small JSON results + docs + tools only:
 - no checkpoints/plys/renders (GB-scale),
 - no patches/ (diffs of UNLICENSED repos must not be redistributed; SETUP.md
   documents them as local-only).
Idempotent; re-run after new results land."""
import glob
import json
import os
import shutil

SRC = r"D:\uw3dgs"
DST = r"C:\Users\oat\workspace\sota-underwater-3dgs\experiments"

KEEP_RUN_FILES = ["DONE.json", "metrics.json", "geometry.json",
                  "geometry_surface.json", "geometry_s4.json",
                  "floater_mass.json"]

n = 0
for run in sorted(glob.glob(os.path.join(SRC, "runs", "*"))):
    if not os.path.isdir(run) or os.path.basename(run).startswith("_"):
        continue
    for f in KEEP_RUN_FILES:
        p = os.path.join(run, f)
        if os.path.exists(p):
            d = os.path.join(DST, "runs", os.path.basename(run))
            os.makedirs(d, exist_ok=True)
            shutil.copy2(p, d)
            n += 1
for f in ["results.jsonl", "trivial_baseline.json", "e6_delta_beta.json"]:
    p = os.path.join(SRC, "runs", f)
    if os.path.exists(p):
        os.makedirs(os.path.join(DST, "runs"), exist_ok=True)
        shutil.copy2(p, os.path.join(DST, "runs"))
        n += 1

for meta in glob.glob(os.path.join(SRC, "scenes", "*", "meta.json")):
    scene = os.path.basename(os.path.dirname(meta))
    d = os.path.join(DST, "scenes", scene)
    os.makedirs(d, exist_ok=True)
    shutil.copy2(meta, d)
    n += 1
for extra in ["scenes/s2_stereo_ref_world.json"]:
    p = os.path.join(SRC, extra)
    if os.path.exists(p):
        os.makedirs(os.path.join(DST, "scenes"), exist_ok=True)
        shutil.copy2(p, os.path.join(DST, "scenes"))
        n += 1

for doc in ["FINDINGS.md", "SETUP.md", "DATA.md", "MANIFEST.md"]:
    shutil.copy2(os.path.join(SRC, doc), os.path.join(DST, doc))
    n += 1

tooldst = os.path.join(DST, "tools")
os.makedirs(tooldst, exist_ok=True)
for t in glob.glob(os.path.join(SRC, "tools", "*.py")):
    shutil.copy2(t, tooldst)
    n += 1

readme = """# Experiment artifacts

Results, provenance and tooling behind the paper's numbers. Structure:

- `runs/<id>/` -- per-run outcome (`DONE.json`), unified photometric metrics
  (`metrics.json`), geometric evaluations (`geometry*.json`), floater-mass
  tau-sweeps (`floater_mass.json`). `runs/results.jsonl` is the append-only
  ledger; `trivial_baseline.json` and `e6_delta_beta.json` are the controls of
  Secs. IV-A and IV-E.
- `scenes/<scene>/meta.json` -- scene provenance: pose source and convention,
  measured NTU statistics, init-cloud decisions.
- `tools/` -- the full pipeline: scene builders, pose converters, the unified
  evaluator, depth/floater/chamfer metrics, the run driver, figure generation.
- `FINDINGS.md` / `SETUP.md` / `DATA.md` / `MANIFEST.md` -- the findings log,
  environment + adaptation record (incl. upstream bugs found), dataset
  decisions, and pinned commits of every method repository.

NOT included, deliberately: trained checkpoints, point clouds and renders
(GB-scale; regenerable from tools/ + MANIFEST pins), the raw datasets (see
DATA.md for sources), and source patches of the method repositories -- 13 of
20 code-available underwater methods carry no licence, so our fixes are
described in SETUP.md but not redistributed.
"""
open(os.path.join(DST, "README.md"), "w", encoding="utf-8").write(readme)
print(f"copied {n} files -> {DST}")
