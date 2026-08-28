"""Backfill n_gaussians for the nine watersplatting runs from their converted
PLYs (real artifacts, not prose). Updates DONE.json and rewrites the matching
ledger lines, then cross-checks against every M2 count quoted in FINDINGS.md /
the paper and reports agreement or disagreement.
"""
import json
import os

from plyfile import PlyData

R = r"D:\uw3dgs\runs"
RUNS = ["e1_s1_m2", "e1_s4_m2", "e5_s3dense_m2", "e2_t0_m2", "e2_t2_m2",
        "e2_t3_m2", "e2_t3_m2_r2", "e2_t3_m2_r3", "e2_t5_m2"]

derived = {}
for rid in RUNS:
    ply = os.path.join(R, rid, "point_cloud", "iteration_30000", "point_cloud.ply")
    n = PlyData.read(ply)["vertex"].count
    derived[rid] = n
    p = os.path.join(R, rid, "DONE.json")
    d = json.load(open(p))
    old = d.get("n_gaussians")
    d["n_gaussians"] = n
    d["n_gaussians_source"] = "backfilled from converted point_cloud.ply (ns ckpt); was None"
    json.dump(d, open(p, "w"), indent=2)
    print(f"{rid:16s} {old} -> {n:,}")

# rewrite ledger lines
led = os.path.join(R, "results.jsonl")
lines = open(led).read().splitlines()
out = []
for l in lines:
    try:
        d = json.loads(l)
    except json.JSONDecodeError:
        out.append(l)
        continue
    if d.get("id") in derived and d.get("status") == "OK":
        d["n_gaussians"] = derived[d["id"]]
    out.append(json.dumps(d))
open(led, "w").write("\n".join(out) + "\n")
print("ledger rewritten")

# cross-check against quoted numbers (prose claims -> derived artifacts)
print("\n--- cross-check vs quoted values ---")
checks = [
    ("S2 sweep 0 NTU '154k'",   "e2_t0_m2",   154_000, 0.02),
    ("S2 sweep 7 NTU '13k'",    "e2_t3_m2",    13_000, 0.05),
    ("S2 sweep 12 NTU '3.1k'",  "e2_t5_m2",     3_100, 0.05),
    ("repeat r2 '3.3k'",        "e2_t3_m2_r2",  3_300, 0.05),
    ("repeat r3 '26k'",         "e2_t3_m2_r3", 26_000, 0.05),
    ("Table IV S1 '1.06 M'",    "e1_s1_m2",  1_060_000, 0.02),
    ("Table IV S4 '0.09 M'",    "e1_s4_m2",     90_000, 0.10),
    ("Table IV S3 '0.03 M'",    "e5_s3dense_m2", 30_000, 0.15),
]
for label, rid, quoted, tol in checks:
    n = derived[rid]
    rel = abs(n - quoted) / quoted
    verdict = "OK" if rel <= tol else "DISAGREES"
    print(f"{verdict:9s} {label}: quoted ~{quoted:,} derived {n:,} ({rel*100:.1f}%)")
