# Gaussian Splatting Underwater

Code, run artifacts and the interactive project page for a controlled
cross-regime evaluation and component ablation of medium-aware 3D Gaussian
splatting on subsea survey data.

- **Paper:** [arXiv:2608.25483](https://arxiv.org/abs/2608.25483)
- **Project page (interactive point clouds):** <https://olayasturias.github.io/uw3dgs/>

## What is in this repository

| Path | Contents |
|---|---|
| `methods/` | The eight method repositories as submodules, pinned to the exact upstream commits used for the study |
| `experiments/repro/` | Bootstrap: submodule init, adaptation patches, build scripts, run queues, environment freeze |
| `experiments/tools/` | The pipeline: scene builders, pose converters, the unified evaluator, depth/floater/chamfer metrics, the run driver, and the figure generators |
| `experiments/runs/` | Per-run results: unified metrics, geometric evaluations, floater-mass τ-sweeps, the append-only ledger, and the controls (trivial predictor, replay, cross-site transfer) |
| `experiments/scenes/` | Scene provenance: pose sources and validated conventions, measured NTU statistics, initialisation decisions |
| `experiments/SETUP.md` | The shared environment (one conda env, CUDA 12.4) and every adaptation made to the method repositories, including upstream bugs found |
| `experiments/DATA.md` | The four scene regimes and exactly how each was built |
| `data/` | The literature-search pipeline: multi-source search, dedup and relevance gates, public-repo verification, clustering |
| `docs/` | The project page |

## Reproducing

1. **Method repositories.** `sh experiments/repro/bootstrap.sh` fetches all
   eight at their pinned commits and applies the local adaptations. Upstream
   source is **not** vendored here: the submodules record only a URL and a
   commit id, and the adaptations ship as diffs. Do not run
   `git submodule update --init --recursive`. See `experiments/repro/README.md`
   for why. These are non-commercial research licences (Inria/MPII, Pi-Lab).
2. **Environment.** One conda env for all eight repositories (python 3.10,
   torch 2.4.1+cu124); `experiments/repro/env/pip-freeze.txt` is the exact
   environment, `experiments/repro/build_extensions.bat` compiles the CUDA
   extensions. `experiments/SETUP.md` documents the package-rename scheme that
   lets five conflicting `diff_gaussian_rasterization` forks coexist.
3. **Data.** SeaThru-NeRF (Curaçao), [SOTRUE](https://gitlab.com/apl-ocean-engineering/public_datasets/sotrue)
   (CC BY-NC-SA 4.0), Eiffel Tower (IFREMER). `experiments/DATA.md` gives the
   scene-building commands (`build_s2_scene.py` etc.), including the validated
   pose conventions and the dot-free-filename rule. The industrial S4 scene is
   proprietary; its evaluation outputs are included, imagery is not.
4. **Runs.** `experiments/tools/run_exp.py --queue <queue.json> --gpu N`
   drives train → render → evaluate for every system; the actual queue files are
   in `experiments/repro/queues/`.
5. **Numbers.** Every reported value traces to a JSON under
   `experiments/runs/`; the figure generators (`make_fig2.py`, `make_fig_qual.py`,
   `make_web_pointclouds.py`) regenerate the figures from those artifacts.

## Citation

```bibtex
@misc{alvareztunon2026gaussian,
  title         = {Gaussian Splatting Underwater: A Controlled Cross-Regime Study},
  author        = {{\'A}lvarez-Tu{\~n}{\'o}n, Olaya and Gra{\ss}hof, Stella},
  year          = {2026},
  eprint        = {2608.25483},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CV}
}
```
