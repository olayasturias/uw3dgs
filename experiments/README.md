# Experiment artifacts

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
- `SETUP.md` / `DATA.md` / `MANIFEST.md` -- the
  environment + adaptation record (incl. upstream bugs found), dataset
  decisions, and pinned commits of every method repository.

NOT included, deliberately: trained checkpoints, point clouds and renders
(GB-scale; regenerable from tools/ + MANIFEST pins), the raw datasets (see
DATA.md for sources), and source patches of the method repositories -- 13 of
20 code-available underwater methods carry no licence, so our fixes are
described in SETUP.md but not redistributed.
