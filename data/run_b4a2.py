"""B.4a v2 -- topic-relevance gate by explicit per-lane rules.

DEVIATION FROM PLAN. PLAN.md specified a seed-similarity gate (cosine >= 0.15 to
a TF-IDF seed centroid) explicitly to avoid hand-tuned exclusion lists. That gate
was implemented (run_b4a.py) and measured, and it does not discriminate on this
corpus: the 12 seeds score 0.27-0.36 and everything else collapses into a
0.03-0.12 band with no topical ordering inside it -- "AudioGS: Spectrogram-Based
Audio Gaussian Splatting" (0.057) outranks "Dehaze-then-Splat" (0.042), and a
0.10 cut would have deleted 3D-UIR, AquaGS, TUGS, Plenodium, WaterGS and
RUSplatting, i.e. most of the survey.

Cause: TF-IDF bigram cosine over ~150-word abstracts is too sparse to rank
same-field papers, and the seeds dominate their own centroid.

Replacement: per-lane rules. This IS a hand-tuned list, which the plan wanted to
avoid, but it is auditable, and every rejection is written to disk with its
reason so the cut can be reviewed. The similarity score is retained on each
record as a weak tiebreaker for composite scoring, not as a gate.
"""
import os, re, sys, json, math, collections

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canonical_record import load_records, serialize_records  # noqa
import run_b4a as TFIDF  # noqa  (reuse tokenizer / vectorizer)

OUT = os.path.dirname(os.path.abspath(__file__))

# ---- medium lane: which non-underwater media transfer to water? -----------
# Keep optically-scattering media that share water's forward model.
MED_KEEP = re.compile(r"\bfog\b|\bhaze|dehaz|\bsmoke|scatter|descatter|turbid|"
                      r"participating medi|volumetric|underwater|absorption|attenuat", re.I)
# Reject other imaging modalities that merely share the word "Gaussian".
MED_DROP = re.compile(
    r"cbct|cone-?beam|computed tomograph|\bct\b|x-?ray|radiograph|ultrasound|"
    r"colonoscop|vessel|angiograph|\bdsa\b|diffuse optical|tomograph|"
    r"\bradar\b|wireless|radio propagation|channel gain|channel knowledge|antenna|"
    r"spectrum sensing|\brf\b|audio|sound field|spectrogram|"
    r"thermal|infrared|flare removal|derain|rainy|snow|fire synthesis|"
    r"avatar|podcast|episode|photometric stereo|inverse graphics", re.I)

# ---- support lane: geometry/pose/depth infrastructure, not 2D-only work ---
SUP_KEEP = re.compile(
    r"structure from motion|structure-from-motion|\bsfm\b|colmap|refract|"
    r"camera calibration|pose estimation|visual odometry|\bslam\b|"
    r"multi-?view stereo|\bmvs\b|depth estimation|monocular depth|stereo|"
    r"dust3r|mast3r|vggt|\bmvsnet\b|3d reconstruct|point cloud|bundle adjust|"
    r"surface normal|photogrammetr|benchmark|dataset|novel view|radiance|splat", re.I)
SUP_DROP = re.compile(
    r"object detection|\byolo\b|instance segmentation|semantic segmentation|"
    r"fish species|classification of|target recognition|"
    r"biomass|carbonate budget|coral cover survey|cultural heritage documentation|"
    r"wireless communication|energy-?efficient camera|humanoid", re.I)


def main():
    pool = load_records(os.path.join(OUT, "pool_b2b.json"))
    seeds = load_records(os.path.join(OUT, "seeds.json"))
    seed_titles = {re.sub(r"[^a-z0-9]", "", (s.title or "").lower()) for s in seeds}

    docs = {r.canonical_id: TFIDF.toks(f"{r.title} {r.title} {r.abstract or ''}") for r in pool}
    sdocs = [TFIDF.toks(f"{s.title} {s.title} {s.abstract or ''}") for s in seeds]
    idf = TFIDF.build_idf(list(docs.values()) + sdocs)
    cent = collections.defaultdict(float)
    for d in sdocs:
        for t, x in TFIDF.vec(d, idf).items():
            cent[t] += x
    nrm = math.sqrt(sum(x * x for x in cent.values())) or 1.0
    cent = {t: x / nrm for t, x in cent.items()}

    kept, dropped = [], []
    for r in pool:
        blob = f"{r.title} {r.abstract or ''}"
        lane = r.raw.get("lane")
        r.raw["seed_sim"] = round(TFIDF.cos(TFIDF.vec(docs[r.canonical_id], idf), cent), 4)
        r.raw["is_seed"] = re.sub(r"[^a-z0-9]", "", (r.title or "").lower()) in seed_titles

        reason = None
        if lane == "anchor" or r.raw["is_seed"]:
            pass
        elif lane == "core":
            pass                                    # GS-term AND underwater-term: in scope by construction
        elif lane == "medium":
            if MED_DROP.search(blob):
                reason = "medium-other-modality"
            elif not MED_KEEP.search(blob):
                reason = "medium-no-scattering"
        elif lane == "support":
            if SUP_DROP.search(blob):
                reason = "support-not-geometry"
            elif not SUP_KEEP.search(blob):
                reason = "support-no-geometry-term"

        if reason:
            r.raw["exclusion"] = reason
            dropped.append(r)
        else:
            kept.append(r)

    serialize_records(kept, os.path.join(OUT, "pool_b4a.json"))
    serialize_records(dropped, os.path.join(OUT, "excluded_relevance.json"))
    lanes = collections.Counter(r.raw["lane"] for r in kept)
    dl = collections.Counter(r.raw["exclusion"] for r in dropped)
    print(f"in={len(pool)}  kept={len(kept)}  dropped={len(dropped)}")
    print("kept lanes:", dict(lanes))
    print("drop reasons:", dict(dl))
    print("\n--- dropped from medium (should be other modalities) ---")
    for r in dropped:
        if r.raw["lane"] == "medium":
            print(f"  {r.title[:88]}")
    print("\n--- dropped from support ---")
    for r in dropped:
        if r.raw["lane"] == "support":
            print(f"  {r.title[:88]}")
    json.dump({"kept": len(kept), "dropped": len(dropped), "lanes": dict(lanes),
               "drop_reasons": dict(dl), "gate": "per-lane rules (see module docstring)"},
              open(os.path.join(OUT, "b4a_summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
