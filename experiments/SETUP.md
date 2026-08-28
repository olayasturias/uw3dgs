# uw3dgs shared environment — setup record

Goal: host all 8 underwater-3DGS method repos in ONE conda env on the locally
installed toolchain (CUDA 12.4, VS 2022, RTX 3090 / sm_86), adapting repo code
where upstream pins conflict. Companion to the paper
[arXiv:2608.25483](https://arxiv.org/abs/2608.25483).

## Environment

- Env: `D:\envs\uw3dgs` — python 3.10, torch 2.4.1+cu124, numpy 1.26.4,
  nerfstudio 1.1.5, gsplat 1.4.0 (SeaFree-GS vendored fork), tiny-cuda-nn (source, arch 86),
  setuptools 69.5.1.
- Build env for every CUDA extension: VS2022 x64 tools, `DISTUTILS_USE_SDK=1`,
  `TORCH_CUDA_ARCH_LIST=8.6`, `TCNN_CUDA_ARCHITECTURES=86`.

## Rasterizer package map (Collision A resolution)

Five repos install `diff_gaussian_rasterization` upstream — four incompatible ABIs.
Each variant is installed once under a unique package name; repo imports patched.

| Package installed | Kernel source | Consumers |
|---|---|---|
| `diff_gaussian_rasterization` | upstream `dr_aa` (gaussian-splatting submodule) | gaussian-splatting |
| `dgr_uir` | 3D-UIR vendored (dr_aa + modified backward: 4-comp means2D grad) | 3D-UIR |
| `dgr_main` | upstream `main` (recgs submodule) | recgs |
| `dgr_seasplat` | dxyang fork (seasplat submodule) | seasplat |
| `dgr_uwgs` | UW-GS vendored fork | UW-GS |
| `dgr_rus` | RUSplatting vendored (kernels == UW-GS; python wrapper differs: clamp 0.1 vs 0.01) | RUSplatting |
| `simple_knn` | Inria (identical in all repos) | all forks |
| `fused_ssim` | rahul-goel/fused-ssim (3D-UIR's vendored copy identical) | gaussian-splatting, 3D-UIR |

Deviation from the original plan: inspection claimed 3D-UIR == upstream dr_aa and
RUSplatting == UW-GS. Local diffs showed 3D-UIR's kernels ARE modified and
RUSplatting's python wrapper carries a different clamp constant → six variants
instead of four, every fork gets its own package. All eight extensions compiled
first-try on CUDA 12.4 + MSVC 2022 (no source fixes needed).

## Per-repo status (2026-08-22)

Smoke test = truncated training run (500 iters, or 1000+100 for recgs) on
`D:\uw3dgs\smoke_scene` (40 EiffelTower frames), GPU 1.

| Repo | Cloned | Deps | Extension | Import | Smoke train | Notes |
|---|---|---|---|---|---|---|
| gaussian-splatting | ✓ | ✓ | ✓ | ✓ | **PASS** (34 it/s) | |
| seasplat | ✓ | ✓ | ✓ | ✓ | **PASS** incl. seathru path + full metrics pass | no licence — patches stay local |
| UW-GS | ✓ | ✓ | ✓ | ✓ | **PASS** after 2 bug fixes (log #5, #11) | no licence — patches stay local |
| 3D-UIR | ✓ | ✓ | ✓ | ✓ | **PASS** | no licence — patches stay local |
| recgs | ✓ | ✓ | ✓ | ✓ | **PASS** both stages (stage 2 ran full 69k iters to completion) | no licence — patches stay local |
| RUSplatting | ✓ | ✓ | ✓ | ✓ | **PASS** (with depthmaps) | no licence; NEVER run submodule init here |
| water-splatting | ✓ | ✓ | ✓ | ✓ | **PASS** (ns-train, 500 iters) | Apache-2.0; runs on ns 1.1.5 despite 1.1.4 README pin |
| SeaFree-GS | ✓ | ✓ | ✓ | ✓ | **PASS** (ns-train, 500 iters; depth maps optional) | MIT |

Run rule: concurrent fork runs need unique `--port` (network_gui binds 6009).

## Environment (as installed, 2026-08-21)

python 3.10.19 · torch 2.4.1+cu124 · torchvision 0.19.1+cu124 · numpy 1.26.4 ·
nerfstudio 1.1.5 · gsplat 1.4.0 (SeaFree-GS vendored build, replaces PyPI wheel) ·
tinycudann 2.0 (source, sm_86) · setuptools 69.5.1 · opencv-python 4.11 · open3d 0.19 ·
kornia 0.8.2 · lpips 0.1.4 · dearpygui 2.3 · rawpy 0.27 · splines 0.3.0.
`ns-train` registry contains `water-splatting`, `water-splatting-big`, `seafree-gs`.

## Adaptations log

(chronological; every source edit also exists as a commit on branch `cu124-shared-env`
in the local clone and as a diff in `patches/`)

1. **Rasterizer package renames** (all repos, commit "Rename rasterizer package for
   shared cu124 env"): `git mv diff_gaussian_rasterization <new>` in each vendored/
   submodule rasterizer + 3-token sed in its `setup.py` + sed of the repo's import
   sites (`gaussian_renderer/__init__.py`; 3D-UIR additionally `render.py`,
   `render_video.py`, `scene/gaussian_model.py`, `train.py`, `utils/loss_utils.py`).
   RUSplatting: also deleted a stray prebuilt linux `_C.cpython-38-*.so`.
2. **seasplat**: `requirements.txt` deliberately NOT installed (broken cu118 pip
   freeze that would clobber torch); curated deps installed instead.
3. **UW-GS / RUSplatting `environment.yml`**: ignored (Windows conda exports with
   conflicting pins).
4. **Smoke-test scene**: `D:\uw3dgs\smoke_scene` — 40 consecutive EiffelTower/2015
   frames, RADIAL camera cast to PINHOLE (distortion dropped — smoke test only,
   NOT valid for experiments), points3D filtered to visible tracks
   (`make_smoke_scene.py`).
5. **UW-GS bug fix** (`gaussian_renderer/__init__.py`): published code never passes
   `colors_precomp_clean` to the rasterizer → kernel reads `features_clean` off a
   NULL pointer → CUDA illegal memory access on the default code path
   (`convert_SHs_python=True`). Diagnosed with compute-sanitizer
   (`renderCUDA<3>` invalid global read at near-null address). Fix: pass the clean
   colors the renderer already computes — matching RUSplatting, which is derived
   from UW-GS and DOES pass it. This is a genuine upstream bug worth reporting.
6. **seasplat fix** (`metrics.py`): `fname.split('.')[0]` truncates image names
   containing dots (e.g. `20150418T033014.000Z.png`) → FileNotFoundError in the
   end-of-training metrics pass. Fix: `os.path.splitext(fname)[0]`.
7. **UW-GS + RUSplatting require mono-depth maps** in `<scene>/depthmap/` (same
   filenames as images); `viewpoint_cam.original_depth` is used unconditionally in
   both train loops, and cameras.py min-max normalises → a CONSTANT depth map
   yields NaN. Smoke test uses vertical-gradient placeholders; **experiments need
   real mono-depth (e.g. DepthAnything) here**.
8. **recgs protocol constraint** (no patch): `train_recgs.py` computes `freq_diffs`
   only when `iteration % 1000 == 1`, so the stage-1 checkpoint MUST land on a
   multiple of 1000 (authors use 30000) or stage 2 crashes with UnboundLocalError.
9. **seasplat side effect**: writes `experiments/<date>/<exp>/` AND caches
   `depths.npy` inside the SCENE directory (`images/depths.npy`). Keep scene dirs
   disposable copies for seasplat runs.
10. **DATA RULE — no dots in image basenames.** The whole 3DGS-fork family
    truncates image names at the FIRST dot (`split('.')[0]`) in dataset readers,
    render naming, and metrics gt lookup. Filenames like `20150418T033014.000Z.png`
    (EiffelTower) silently break the render→gt pairing. Sanitize every scene at
    prep time: `stem.replace('.', '_') + ext`, applied to both the files and
    `images.txt` (see `make_smoke_scene.py`). Applies to ALL future scene prep
    (SOTRUE, SeaThru-NeRF, EIVA).
11. **UW-GS second fix** (`train.py` training_report): `Ll1.item()` on the
    elementwise (unreduced) l1 tensor crashes whenever tensorboard IS installed —
    the authors evidently ran without it. Fix: `Ll1.mean().item()`.
12. **recgs stage-2 length**: `--iterations` does NOT control `train_recgs.py`;
    its loop runs to `opt.rec_iterations` (default 69000). Use `--rec_iterations`
    to bound it.
