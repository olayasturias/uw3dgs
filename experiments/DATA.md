# Experiment scenes — provenance and conventions

Built 2026-08-22 by `tools/build_s2_scene.py`, `tools/build_s4_scene.py`,
COLMAP 3.11.1 (`D:\uw3dgs\colmap`). All scenes are fork-ready COLMAP layouts:
`images/` + `sparse/0/{cameras,images,points3D}.bin`, PINHOLE cameras,
dot-free image basenames.

## Sources (user-provided, all local)

| Paper scene | Source | Path |
|---|---|---|
| S1 Curaçao | SeaThru-NeRF dataset | `D:\Datasets\SeathruNeRF_dataset\SeathruNeRF_dataset\Curasao` |
| S2 turbidity | SOTRUE (APL-UW) | `D:\Datasets\SOTRUE` |
| S3 Eiffel Tower | IFREMER | `D:\Datasets\EiffelTower` (2015/2016/2018/2020) |
| S4 EIVA survey | plane_nose | `D:\Datasets\EIVA\vobster_quay\plane_nose` |

## Pose conventions (validated empirically via fixed-pose point_triangulator)

- **SOTRUE** interpolated CSV (x y z qx qy qz qw): pose of the LEFT camera
  center in a consistent tank frame; quaternion = **camera-to-world of the
  optical frame** (`c2w_optical`). Winner: 8852 pts / track 4.29 vs ≤2185 pts,
  track 2.0 for the alternatives. Left and right CSVs carry the same pose
  (left camera center) — right camera needs the stereo baseline applied.
- **plane_nose** `pose_gt.txt` (name tx ty tz r00..r22): identical to the XMP
  `<extrinsics>` sidecars = **direct world-to-camera [R|t]** (`w2c_direct`).
  Winner: 561 pts / 0.69 px vs 3–8 pts for five alternatives.

## Built scenes (`D:\uw3dgs\scenes\`)

| Scene | Images | Camera | Init cloud | Measured NTU (median) | Notes |
|---|---|---|---|---|---|
| `s1_curacao` | 21 @ 1794×1188 | PINHOLE (image_undistorter from authors' OPENCV model) | authors' model, 25.8k pts, 0.52 px | — | |
| `s2_turbid0_trial1` | 193 @ 1920×1216 | PINHOLE (cv2 undistort at raw K) | own triangulation, 17,348 pts, track 5.7, 1.77 px | **0.0** | |
| `s2_turbid3_trial1` | 193 | " | **turbid0 cloud** (own: 367 pts — too sparse) | **7.0** | needed SIFT peak 0.001 to match at all |
| `s2_turbid5_trial1` | 193 | " | **turbid0 cloud** (own: 0 — see below) | **12.0** | |
| `s3_eiffel2015` | 308 @ ~1794×1080 | PINHOLE (image_undistorter of provided RADIAL model) | provided model, 200k pts, 1.45 px | — | every 16th of 4914 — SPARSE coverage; kept only as the coverage-sensitivity data point (M0: PSNR 16.5) |
| `s3_eiffel2015_dense` | 350 consecutive @ ~1794×1080 | " | provided model, best-tracked contiguous window | — | **the S3 scene used for E5** (user decision 2026-08-22: feasible subset over full-site subsampling) |
| `s4_planenose` | 566 @ 1408×1408 | PINHOLE (0.5× resize of distortion-free rectified) | own triangulation, 172,653 pts, track 5.2, **0.34 px** | — | + `depthmap/` from IGEV; reference = `pointcloud_gt.ply` (7.5M pts) |

**Constant-init decision (E2):** all three S2 levels share turbid0's triangulated
cloud (identical tank frame). At 7 NTU SIFT needed peak_threshold 0.001 and still
triangulated only 367 weak points; at 13 NTU (measured 12) permissive SIFT extracts
~10,208 features/image but **0 survive geometric verification** — the features are
backscatter noise. Constant init removes init quality as a confound in the
dose-response; the per-level SIFT collapse (8k+ → 367 → 0 usable) is itself data
for the registration-vs-NTU story (C5, Table III's last line).

SOTRUE level-dir → nominal NTU mapping: turbid0→0, turbid1→2, turbid2→5,
turbid3→7, turbid4→10, turbid5→13. trial1 local levels: 0,2,3,4,5 (turbid1
not downloaded; not needed). trial2 available for the repeatability check.

## Protocol decisions

- **Init clouds are triangulated with poses fixed — never seeded from the
  evaluation reference** (`pointcloud_gt.ply` stays evaluation-only).
- S2 subsample: every 4th frame (10 Hz → 2.5 Hz, ~193 views). S4: all 566.
- SOTRUE images ship RGB-replicated mono (3-channel PNGs) — Q5's per-channel
  coefficient check applies unchanged.
- SOTRUE images are undistorted at the RAW camera matrix (plumb_bob coeffs are
  small); border masking per protocol still applies at evaluation.
- Train left camera only (runbook); right camera reserved as the stereo depth
  reference (never trained on).

## Still TODO for experiments

- `depthmap/` for S1 (UW-GS/RUSplatting need it; only S4 has IGEV). Mono-depth
  (DepthAnything — DA3 weights cached in `D:\hf_home`) required for E1's M4 row
  on S1. S2 does not need it (E2 runs M0/M2/M3 only).
- SeaFree-GS optional inputs (white-balanced images / u16 depths) if it is used
  beyond fallback.
- E3 COLMAP-pose variants of S2 scenes (free SfM instead of GT poses) — expect
  registration failure at 12 NTU; that failure rate is a Table III line.
- Trial-2 pose models for the repeatability evaluation (no retraining).
- ns-train runs must pin the SAME eval split as the forks: `colmap` dataparser
  with `--eval-mode interval --eval-interval 8` (forks use llffhold=8).
