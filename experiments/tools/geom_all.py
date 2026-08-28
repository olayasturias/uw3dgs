"""Geometric evaluation sweep: for every finished S2 run, render depth (both
estimators) and score against the world stereo reference. Idempotent."""
import json, os, re, subprocess, sys

PY = sys.executable
RUNS = r"D:\uw3dgs\runs"
TOOLS = os.path.dirname(os.path.abspath(__file__))


def main():
    for rid in sorted(os.listdir(RUNS)):
        done = os.path.join(RUNS, rid, "DONE.json")
        if not os.path.exists(done) or rid.startswith("_"):
            continue
        d = json.load(open(done))
        m = re.search(r"s2_turbid(\d)", d.get("scene", ""))
        if d.get("status") != "OK" or not m:
            continue
        level = int(m.group(1))
        out = os.path.join(RUNS, rid)
        ply = os.path.join(out, "point_cloud", f"iteration_{d['iters']}", "point_cloud.ply")
        if not os.path.exists(ply):
            print(f"[{rid}] no ply (nerfstudio system?) — skipping fork depth path")
            continue
        for tag, minop in [("", 0.0), ("_surface", 0.5)]:
            gj = os.path.join(out, f"geometry{tag}.json")
            if os.path.exists(gj):
                continue
            dd = os.path.join(out, "depths" + ("_surf" if tag else ""))
            cmd = [PY, os.path.join(TOOLS, "render_depth_3dgs.py"), "--ply", ply,
                   "--scene", d["scene"], "--out", dd]
            if minop:
                cmd += ["--min-opacity", str(minop)]
            subprocess.run(cmd, check=True, capture_output=True)
            subprocess.run([PY, os.path.join(TOOLS, "eval_geometry_s2.py"),
                            "--depths", dd, "--level", str(level), "--trial", "1",
                            "--out", gj], check=True, capture_output=True)
            agg = json.load(open(gj))["aggregate"]
            print(f"[{rid}] geometry{tag}: medae {agg['medae_mm']:.0f} mm "
                  f"(mae {agg['mae_mm']:.0f})")


if __name__ == "__main__":
    main()
