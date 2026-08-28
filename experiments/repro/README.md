# Reproducing the runs

Everything needed to go from a clean checkout to the trained models behind the
results in `experiments/runs/`.

```sh
sh experiments/repro/bootstrap.sh        # method repos at pinned commits + adaptations
experiments/repro/build_extensions.bat   # compile the CUDA extensions (VS2022 x64)
python experiments/tools/run_exp.py --queue experiments/repro/queues/q_gpu0.json --gpu 0
```

`../SETUP.md` documents the environment and every adaptation in prose;
`../DATA.md` covers scene construction. This directory holds the machine-usable
form of both.

## How the method repositories are traced

The eight upstream repositories are **git submodules** pinned to the exact
commits used for the study. A submodule stores only a URL and a commit id, so
no upstream source is copied into this repository — you fetch it from the
original authors, at the revision we ran.

| Repo | Upstream | Pinned commit | Licence | Local adaptation |
|---|---|---|---|---|
| gaussian-splatting | graphdeco-inria/gaussian-splatting | `54c035f7` | Inria/MPII GS (non-commercial) | none |
| seasplat | dxyang/seasplat | `ddc6259d` | Inria/MPII GS (inherited) | rasterizer → `dgr_seasplat`; `metrics.py` dotted-filename fix |
| recgs | tyz1030/recgs | `73500100` | Inria/MPII GS (inherited) | rasterizer → `dgr_main` |
| water-splatting | water-splatting/water-splatting | `0c2d9438` | Apache-2.0 | none |
| UW-GS | WangHaoran16/UW-GS | `104d1c07` | Inria/MPII GS (inherited) | rasterizer → `dgr_uwgs`; two upstream bug fixes |
| 3D-UIR | bilityniu/3D-UIR | `49459baa` | Pi-Lab 1.0 (non-commercial) | rasterizer → `dgr_uir` |
| RUSplatting | theflash987/RUSplatting | `33e2a620` | Inria/MPII GS (inherited) | rasterizer → `dgr_rus`; drop prebuilt linux `.so` |
| SeaFree-GS | deng-ai-lab/SeaFree-GS | `7797e97d` | MIT | none |

Rasterizer submodule commits, where applicable, are recorded in
`../MANIFEST.md`.

### Do not run `git submodule update --init --recursive`

`bootstrap.sh` initialises submodules selectively, and it matters:

- Several repos vendor or reference **SIBR_viewers** — thousands of files that
  are not needed to train or evaluate, and which contain paths longer than
  Windows `MAX_PATH`. `bootstrap.sh` sets `core.longpaths` for this repository.
- **RUSplatting's `.gitmodules` is wrong**; its rasterizer is vendored in the
  parent tree. Initialising it recursively fails.
- UW-GS, 3D-UIR, RUSplatting and SeaFree-GS all vendor their rasterizers.

## Adaptations, and why they are diffs

Five repos needed source changes to coexist in one CUDA 12.4 environment. They
are distributed here as patches in `patches/<repo>/`, applied by `bootstrap.sh`
on top of the pinned commit. Two kinds:

1. **Rasterizer package renames.** Five repos install a package called
   `diff_gaussian_rasterization`, with four mutually incompatible ABIs. Each is
   renamed so all can be installed side by side. Mechanical, no behaviour change.
2. **Genuine upstream bug fixes** — worth reporting to the authors:
   - **UW-GS** never passes `colors_precomp_clean` to the rasterizer, so the
     kernel reads `features_clean` off a null pointer: CUDA illegal memory
     access on the default `convert_SHs_python=True` path. RUSplatting, derived
     from UW-GS, does pass it.
   - **UW-GS** calls `.item()` on an unreduced elementwise L1 tensor, which
     crashes whenever tensorboard is installed.
   - **seasplat** truncates image names at the first dot, so filenames like
     `20150418T033014.000Z.png` break the end-of-training metrics pass.

Constraints that are *protocol*, not patches — recgs' stage-1 checkpoint must
land on a multiple of 1000, and its stage 2 is bounded by `--rec_iterations`,
not `--iterations` — are described in `../SETUP.md`.

### Licensing of the patches

Each `patches/<repo>/` directory carries a copy of that repository's licence.
The five Inria/MPII-licensed repos grant the right to prepare and distribute
derivative works (§3), provided distribution is under the same licence, ships a
complete copy of it, and retains attribution notices (§4.1) — which is what the
per-directory licence copies are for. 3D-UIR's Pi-Lab 1.0 permits redistribution
with modification under equivalent conditions.

**These are non-commercial research licences.** The Inria licence covers
research users "both academic and industrial" for research and evaluation only;
Pi-Lab 1.0 is non-commercial. Anyone reusing this pipeline inherits those terms
from the upstream repositories.

## Contents

| Path | What |
|---|---|
| `bootstrap.sh` | Selective submodule init + patch application |
| `patches/<repo>/` | Adaptation diffs against the pinned commit, plus that repo's licence |
| `build_extensions.bat` | Compiles the eight CUDA extensions (VS2022 x64, `TORCH_CUDA_ARCH_LIST=8.6`) |
| `build_scenes.bat`, `build_wave2.bat` | Scene construction drivers |
| `make_smoke_scene.py` | 40-frame EiffelTower smoke-test scene |
| `queues/*.json` | The actual run queues consumed by `run_exp.py` |
| `env/pip-freeze.txt` | The 277-package environment as installed |
| `env/python-version.txt` | Interpreter version |

## Environment

`env/pip-freeze.txt` is a literal freeze of the environment that produced the
results, not a curated install list — it pins transitive dependencies exactly.
The load-bearing versions are python 3.10, torch 2.4.1+cu124, numpy 1.26.4,
nerfstudio 1.1.5, gsplat 1.4.0 (SeaFree-GS's vendored build, which replaces the
PyPI wheel) and tiny-cuda-nn built from source for sm_86. Installing the freeze
verbatim into a fresh conda env will not rebuild the CUDA extensions; run
`build_extensions.bat` after.

Note that `seasplat/requirements.txt` is deliberately **not** installed — it is
a broken cu118 pip freeze that would downgrade torch. See `../SETUP.md`.
