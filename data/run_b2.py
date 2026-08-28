"""B.2 -- deduplicate across sources, apply window + coarse topic gates,
and harvest code URLs out of abstracts (free, no API quota).

Coarse gate assigns each surviving record a `lane`:
  core     GS-family term AND underwater-family term      -> the survey's spine
  medium   GS-family term AND scattering-medium term       -> Branch 3 transferable
  support  underwater term AND geometry/SLAM/SfM term,
           no GS term                                      -> Branch 4/7 context
  anchor   pre-2024 but matches a designated anchor title
Everything else is rejected here with a logged reason. The fine-grained
seed-similarity gate and the repo gate run later, in B.4.
"""
import os, re, sys, json, glob, collections

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import CanonicalRecord, load_records, serialize_records  # noqa
from deduplicate import deduplicate  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
WINDOW_YEAR = 2024

GS_RE = re.compile(r"gaussian splat|3dgs|3-d gaussian|3d gaussian|gaussian splat|"
                   r"radiance field|novel view synthesis|neural rendering|nerf\b|"
                   r"differentiable rasteriz|splatting", re.I)
UW_RE = re.compile(r"underwater|under-water|subsea|sub-sea|seafloor|sea floor|seabed|"
                   r"benthic|submerged|marine|ocean|aquatic|coral|shipwreck|"
                   r"in-water|turbid", re.I)
MED_RE = re.compile(r"scattering medi|participating medi|volumetric scatter|"
                    r"\bfog\b|\bhaze\b|\bhazy\b|dehaz|smoke|turbid|attenuat|backscatter|"
                    r"veiling light|absorption", re.I)
GEO_RE = re.compile(r"structure from motion|structure-from-motion|\bsfm\b|\bslam\b|"
                    r"3d reconstruction|photogrammetr|pose estimation|visual odometry|"
                    r"depth estimation|multi-view stereo|\bmvs\b|bundle adjust|mapping", re.I)

# marine-biology / oceanography false friends that UW_RE happily matches
NOISE_RE = re.compile(r"fish stock|aquaculture feed|fishery|fisheries management|"
                      r"phytoplankton bloom|water quality index|desalinat|"
                      r"marine spatial planning|maritime law|shipping emission|"
                      r"antifoul|corrosion|marine biolog(?!.*imag)|"
                      r"sediment core|ocean acidif|sea surface temperature", re.I)

# Anchors are matched on the NORMALIZED FULL TITLE, not by substring. Substring
# matching pulled in derivative papers ("Enhancing SeaThru-NeRF with ...",
# "... using Instant-NGP") and mislabelled them as the 2023/2018 originals.
ANCHOR_TITLES = {
    "3dgaussiansplattingforrealtimeradiancefieldrendering": "kerbl2023_3dgs",
    "seathrunerfneuralradiancefieldsinscatteringmedia": "levy2023_seathrunerf",
    "seathruamethodforremovingwaterfromunderwaterimages": "akkaynak2019_seathru",
    "arevisedunderwaterimageformationmodel": "akkaynak2018_revised",
    "nerfrepresentingscenesasneuralradiancefieldsforviewsynthesis": "mildenhall2020_nerf",
    "whatisthespaceofattenuationcoefficientsinunderwatercomputervision": "akkaynak2017_attenuation",
}


def title_key(t):
    """Aggressive normalization for exact-title matching and dedup."""
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())

CODE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(github\.com|gitlab\.com|bitbucket\.org|huggingface\.co)/"
    r"([A-Za-z0-9][\w.-]{0,38})/([\w.-]{1,60}?)(?=[\s,;)\]}>\"'\\]|\.git\b|/|$)", re.I)
BAD_OWNERS = {"sponsors", "features", "about", "topics", "collections", "orgs", "apps",
              "settings", "marketplace", "site", "readme", "datasets", "spaces"}


def code_urls(text):
    out = []
    for host, owner, name in CODE_RE.findall(text or ""):
        owner = owner.strip("."); name = name.strip(".").removesuffix(".git")
        if owner.lower() in BAD_OWNERS or len(name) < 2:
            continue
        out.append(f"https://{host.lower()}/{owner}/{name}")
    return sorted(set(out))


def main():
    files = sorted(glob.glob(os.path.join(OUT, "raw_*.json")))
    allrecs, per_branch = [], {}
    for f in files:
        rs = load_records(f)
        b = os.path.basename(f)[4:-5]
        for r in rs:
            r.raw = dict(r.raw or {}); r.raw["branch"] = b
        per_branch[b] = len(rs)
        allrecs += rs
    print(f"loaded {len(allrecs)} raw from {len(files)} branch files")

    uniq = deduplicate(allrecs)
    print(f"deduplicated (canonical-id) -> {len(uniq)} unique")

    # Second pass: the canonical-id dedup leaves duplicates whenever the same work
    # appears with different identifiers (arXiv preprint vs DOI'd version vs an
    # OpenAlex record with no DOI). Merge on normalized title, keeping the record
    # with the richest metadata and unioning provenance + identifiers.
    def richness(r):
        return (bool(r.doi), bool(r.arxiv_id), bool(r.abstract),
                r.citation_count or 0, len(r.source_provenance))

    groups = collections.defaultdict(list)
    for r in uniq:
        groups[title_key(r.title)].append(r)
    merged = []
    collapsed = 0
    for k, g in groups.items():
        if len(g) == 1:
            merged.append(g[0]); continue
        collapsed += len(g) - 1
        g.sort(key=richness, reverse=True)
        best = g[0]
        for other in g[1:]:
            best.doi = best.doi or other.doi
            best.arxiv_id = best.arxiv_id or other.arxiv_id
            best.openalex_id = best.openalex_id or other.openalex_id
            best.abstract = best.abstract or other.abstract
            best.venue = best.venue or other.venue
            best.pdf_url = best.pdf_url or other.pdf_url
            best.citation_count = max(best.citation_count or 0, other.citation_count or 0)
            best.source_provenance = list(best.source_provenance) + list(other.source_provenance)
            # earliest year wins: the preprint date is the right one for a young field
            if other.year and best.year:
                best.year = min(best.year, other.year)
            best.year = best.year or other.year
        merged.append(best)
    uniq = merged
    print(f"deduplicated (title merge) -> {len(uniq)} unique "
          f"({collapsed} extra collapsed, {len(allrecs)-len(uniq)} total merged away)")

    kept, rejected = [], collections.Counter()
    for r in uniq:
        blob = f"{r.title or ''} {r.abstract or ''}"
        anchor = ANCHOR_TITLES.get(title_key(r.title))

        gs, uw, med, geo = (bool(GS_RE.search(blob)), bool(UW_RE.search(blob)),
                            bool(MED_RE.search(blob)), bool(GEO_RE.search(blob)))
        noise = bool(NOISE_RE.search(blob)) and not gs

        if anchor:
            lane = "anchor"
        elif (r.year or 0) < WINDOW_YEAR:
            rejected["pre-window"] += 1; continue
        elif noise:
            rejected["domain-noise"] += 1; continue
        elif gs and uw:
            lane = "core"
        elif gs and med:
            lane = "medium"
        elif uw and geo:
            lane = "support"
        else:
            rejected["no-topic-match"] += 1; continue

        r.raw["lane"] = lane
        r.raw["anchor_key"] = anchor
        r.raw["code_urls"] = code_urls(blob)
        r.raw["flags"] = {"gs": gs, "uw": uw, "med": med, "geo": geo}
        kept.append(r)

    serialize_records(kept, os.path.join(OUT, "pool_b2.json"))
    lanes = collections.Counter(r.raw["lane"] for r in kept)
    yrs = collections.Counter(r.year for r in kept)
    withcode = sum(1 for r in kept if r.raw["code_urls"])

    print("\n--- B.2 pool ---")
    print("lanes:", dict(lanes))
    print("years:", dict(sorted((y, c) for y, c in yrs.items() if y)))
    print(f"records carrying a code URL in the abstract: {withcode}")
    print("rejected:", dict(rejected))
    print("\nanchors found:")
    for r in kept:
        if r.raw["lane"] == "anchor":
            print(f'  {r.raw["anchor_key"]:<28} {r.year} {(r.title or "")[:70]}')

    json.dump({"raw_per_branch": per_branch, "raw_total": len(allrecs),
               "unique": len(uniq), "kept": len(kept), "lanes": dict(lanes),
               "rejected": dict(rejected), "with_code_url": withcode},
              open(os.path.join(OUT, "b2_summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
