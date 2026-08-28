"""Experiment runner: one process per GPU works through a JSON queue.

Each run: train -> render held-out views -> unified evaluator -> results row.
Every number for the paper comes from tools/evaluate.py, never from a repo's
own metrics code.

Queue entry:
  {"id": "e2_t0_m0", "system": "3dgs|seasplat|watersplatting",
   "scene": "D:/uw3dgs/scenes/s2_turbid0_trial1", "port": 6021,
   "iters": 30000, "extra": ["--flag", ...]}

Usage: run_exp.py --queue q_gpu0.json --gpu 0
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

PY = sys.executable
REPOS = r"D:\uw3dgs\repos"
RUNS = r"D:\uw3dgs\runs"
TOOLS = os.path.dirname(os.path.abspath(__file__))
NS_TRAIN = r"D:\envs\uw3dgs\Scripts\ns-train.exe"
NS_RENDER = r"D:\envs\uw3dgs\Scripts\ns-render.exe"


def sh(cmd, log, cwd=None, env=None):
    t0 = time.time()
    with open(log, "a", encoding="utf-8") as f:
        f.write("\n$ " + " ".join(str(c) for c in cmd) + "\n")
        f.flush()
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env,
                           stdout=f, stderr=subprocess.STDOUT)
    return r.returncode, time.time() - t0


def gaussian_count(ply_path):
    try:
        from plyfile import PlyData
        return len(PlyData.read(str(ply_path))["vertex"].data)
    except Exception:
        return None


def find_one(base, patterns):
    for p in patterns:
        hits = sorted(Path(base).glob(p))
        if hits:
            return hits[-1]
    return None


def run_one(run, gpu):
    out = os.path.join(RUNS, run["id"])
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "run.log")
    iters = run.get("iters", 30000)
    scene = run["scene"]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), WANDB_MODE="disabled",
               PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    result = {"id": run["id"], "system": run["system"], "scene": scene,
              "gpu": gpu, "iters": iters, "extra": run.get("extra", [])}

    if run["system"] == "uwgs":
        repo = os.path.join(REPOS, "UW-GS")
        rc, dt = sh([PY, "train.py", "-s", scene, "-m", out, "--eval", "-r", "1",
                     "--iterations", iters, "--save_iterations", iters,
                     "--port", run.get("port", 6100 + gpu)] + run.get("extra", []),
                    log, cwd=repo, env=env)
        result["train_s"] = dt
        if rc != 0:
            result["status"] = "TRAIN_FAILED"
            return result
        rc, _ = sh([PY, "render.py", "-m", out, "-s", scene, "--skip_train",
                    "--iteration", iters], log, cwd=repo, env=env)
        renders = os.path.join(out, "test", f"ours_{iters}", "renders")
        gt = os.path.join(out, "test", f"ours_{iters}", "gt")

    elif run["system"] == "3dgs":
        repo = os.path.join(REPOS, run.get("repo", "gaussian-splatting"))
        rc, dt = sh([PY, "train.py", "-s", scene, "-m", out, "--eval", "-r", "1",
                     "--iterations", iters, "--save_iterations", iters,
                     "--port", run.get("port", 6100 + gpu)] + run.get("extra", []),
                    log, cwd=repo, env=env)
        result["train_s"] = dt
        if rc != 0:
            result["status"] = "TRAIN_FAILED"
            return result
        rc, _ = sh([PY, "render.py", "-m", out, "-s", scene, "--skip_train"],
                   log, cwd=repo, env=env)
        renders = os.path.join(out, "test", f"ours_{iters}", "renders")
        gt = os.path.join(out, "test", f"ours_{iters}", "gt")

    elif run["system"] == "seasplat":
        repo = os.path.join(REPOS, "seasplat")
        rc, dt = sh([PY, "train.py", "-s", scene, "-m", out, "--exp", run["id"],
                     "--eval", "-r", "1", "--iterations", iters,
                     "--do_seathru", "--seathru_from_iter",
                     run.get("seathru_from", 10000),
                     "--save_iterations", iters, "--checkpoint_iterations", iters,
                     "--test_iterations", iters,
                     "--port", run.get("port", 6100 + gpu)] + run.get("extra", []),
                    log, cwd=repo, env=env)
        result["train_s"] = dt
        if rc != 0:
            result["status"] = "TRAIN_FAILED"
            return result
        renders = os.path.join(out, "test", "with_water")
        gt = os.path.join(scene, "images")

    elif run["system"] == "watersplatting":
        # nerfstudio/tyro: model-level extras must precede the dataparser
        # subcommand ("colmap"), or they are rejected as misplaced
        rc, dt = sh([NS_TRAIN, "water-splatting", "--data", scene,
                     "--output-dir", out, "--experiment-name", run["id"],
                     "--timestamp", "run", "--max-num-iterations", iters,
                     "--vis", "tensorboard"] + run.get("extra", []) +
                    ["colmap", "--colmap-path", "sparse/0", "--images-path", "images",
                     "--downscale-factor", "1",
                     "--eval-mode", "interval", "--eval-interval", "8"],
                    log, env=env)
        result["train_s"] = dt
        if rc != 0:
            result["status"] = "TRAIN_FAILED"
            return result
        cfg = find_one(out, [f"{run['id']}/water-splatting/run/config.yml",
                             "**/config.yml"])
        if cfg is None:
            result["status"] = "NO_CONFIG"
            return result
        rc, _ = sh([NS_RENDER, "dataset", "--load-config", cfg,
                    "--split", "test", "--output-path", os.path.join(out, "ns_render"),
                    "--rendered-output-names", "rgb", "gt-rgb"], log, env=env)
        renders = os.path.join(out, "ns_render", "test", "rgb")
        gt = os.path.join(out, "ns_render", "test", "gt-rgb")
    else:
        result["status"] = f"UNKNOWN_SYSTEM {run['system']}"
        return result

    if not os.path.isdir(renders):
        result["status"] = "NO_RENDERS"
        result["renders_expected"] = str(renders)
        return result

    metrics_json = os.path.join(out, "metrics.json")
    cmd = [PY, os.path.join(TOOLS, "evaluate.py"), "--renders", renders,
           "--gt", gt, "--out", metrics_json]
    if run.get("border"):
        cmd += ["--border", run["border"]]
    rc, _ = sh(cmd, log, env=env)
    if rc != 0 or not os.path.exists(metrics_json):
        result["status"] = "EVAL_FAILED"
        return result
    result["metrics"] = json.load(open(metrics_json))["aggregate"]

    ply = find_one(out, [f"point_cloud/iteration_{iters}/point_cloud.ply",
                         "**/point_cloud.ply"])
    result["n_gaussians"] = gaussian_count(ply) if ply else None
    if result["n_gaussians"] is None:
        # nerfstudio systems write a checkpoint, not a PLY: count the means
        # tensor directly so the field never silently falls back to None
        ckpt = find_one(out, ["**/nerfstudio_models/step-*.ckpt"])
        if ckpt:
            import torch
            sd = torch.load(str(ckpt), map_location="cpu")["pipeline"]
            k = [x for x in sd if x.endswith("gauss_params.means")]
            if k:
                result["n_gaussians"] = int(sd[k[0]].shape[0])
    result["status"] = "OK"
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--gpu", type=int, required=True)
    args = ap.parse_args()

    queue = json.load(open(args.queue))
    ledger = os.path.join(RUNS, "results.jsonl")
    os.makedirs(RUNS, exist_ok=True)
    for run in queue:
        done_marker = os.path.join(RUNS, run["id"], "DONE.json")
        if os.path.exists(done_marker):
            print(f"[skip] {run['id']} already done", flush=True)
            continue
        print(f"[start] {run['id']} on gpu{args.gpu}", flush=True)
        try:
            result = run_one(run, args.gpu)
        except Exception as e:  # never kill the queue
            result = {"id": run["id"], "status": f"DRIVER_ERROR {e}"}
        result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        json.dump(result, open(done_marker, "w"), indent=2)
        with open(ledger, "a") as f:
            f.write(json.dumps(result) + "\n")
        print(f"[done] {run['id']}: {result.get('status')} "
              f"{result.get('metrics', '')}", flush=True)
    print("QUEUE_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
