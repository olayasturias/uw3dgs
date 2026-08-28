# Gaussian Splatting Underwater — code and experiment artifacts

Code, run artifacts and the interactive project page for a controlled
cross-regime evaluation and component ablation of medium-aware 3D Gaussian
splatting on subsea survey data.

**Paper:** [arXiv:2608.25483](https://arxiv.org/abs/2608.25483)
**Project page (interactive point clouds):** https://olayasturias.github.io/uw3dgs/

## What is in this repository

| Path | Contents |
|---|---|
| `experiments/tools/` | The pipeline: scene builders, pose converters, the unified evaluator, depth/floater/chamfer metrics, the run driver, and the figure generators |
| `experiments/runs/` | Per-run results: unified metrics, geometric evaluations, floater-mass τ-sweeps, the append-only ledger, and the controls (trivial predictor, replay, cross-site transfer) |
| `experiments/scenes/` | Scene provenance: pose sources and validated conventions, measured NTU statistics, initialisation decisions |
| `experiments/SETUP.md` | The shared environment (one conda env, CUDA 12.4) and every adaptation made to the method repositories — including upstream bugs found |
| `experiments/DATA.md` | The four scene regimes and exactly how each was built |
| `data/` | The literature-search pipeline: multi-source search, dedup and relevance gates, public-repo verification, clustering |
| `docs/` | The project page |

## Reproducing

1. **Environment** — one conda env for all eight method repositories
   (python 3.10, torch 2.4.1+cu124). `experiments/SETUP.md` documents the
   package-rename scheme that lets five conflicting `diff_gaussian_rasterization`
   forks coexist, and every source fix. The method repos themselves are **not**
   vendored here — 13 of the 20 code-available underwater methods carry no
   licence, so we link and patch.
2. **Data** — SeaThru-NeRF (Curaçao), [SOTRUE](https://gitlab.com/apl-ocean-engineering/public_datasets/sotrue)
   (CC BY-NC-SA 4.0), Eiffel Tower (IFREMER). `experiments/DATA.md` gives the
   scene-building commands (`build_s2_scene.py` etc.), including the validated
   pose conventions and the dot-free-filename rule. The industrial S4 scene is
   proprietary; its evaluation outputs are included, imagery is not.
3. **Runs** — `experiments/tools/run_exp.py --queue <queue.json> --gpu N`
   drives train → render → evaluate for every system; queue files for all
   experiments are reconstructible from the ledger entries' `id`/`scene`/`extra`.
4. **Numbers** — every reported value traces to a JSON under
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
