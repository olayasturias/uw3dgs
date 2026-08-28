"""B.7 -- assemble the working set and every machine-readable spoke.

Produces: working_set.json, papers_table.csv, excluded.csv, references.bib,
code_availability.md, MANIFEST.json.

Working-set definition for this run (see PLAN.md Risk 3): the survey has two
tiers, because a strict code-only rule would make it impossible to cite Sea-thru
or SeaThru-NeRF.
  * METHOD SET  -- code-available methods. These are the survey's subject and the
                   only papers allowed into the §11 comparison matrices.
  * CONTEXT SET -- papers cited for background, datasets, evaluation or lineage.
                   No repo requirement. Never in the matrices.
Anchors are context by construction.
"""
import os, re, sys, csv, json, glob, hashlib, collections, datetime

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records, serialize_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)
TAX = json.load(open(os.path.join(OUT, "taxonomy.json"), encoding="utf-8"))

EXCL_TITLES = {re.sub(r"[^a-z0-9]", "", e["title"].lower()): e["reason"]
               for e in TAX["excluded_manually"]}


def nk(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def bibkey(r, used):
    a = (r.authors[0].split(",")[0] if r.authors else "anon")
    a = re.sub(r"[^A-Za-z]", "", a).lower() or "anon"
    # method name if the title has one, else first content word
    head = (r.title or "").split(":")[0]
    tok = re.sub(r"[^A-Za-z0-9]", "", head).lower()[:16] or "paper"
    k = f"{a}{r.year or 0}{tok}"
    n, base = 1, k
    while k in used:
        n += 1
        k = f"{base}{chr(ord('a') + n - 1)}"
    used.add(k)
    return k


# Fallback family assignment for papers whose system name is not enumerated in
# taxonomy.json. Ordered: the first rule that fires wins, so the more specific
# families are tested before the catch-all F1.
FALLBACK = [
    # F6 must be title-driven only. Matching "dataset"/"benchmark" anywhere in an
    # abstract swept in ordinary method papers -- RUSplatting and
    # ScatteringSplatting both landed in F6 because their abstracts name the
    # datasets they evaluate on.
    ("F6", "datasets-and-evaluation",
     r"^[^.]*(\bbenchmark\b|\bdataset\b|comparative (analysis|study)|"
     r"experimental compar|systematic evaluation|\bsurvey\b|\ba review\b)"),
    ("F5", "online-slam", r"\bslam\b|real-?time (localization|mapping)|"
     r"incremental mapping|online reconstruction|odometry"),
    # scattering media before restoration: "Smoke Restoration" is F7, not F2
    ("F7", "transferable-scattering",
     r"\bfog\b|\bhaze\b|dehaz|smoke|participating medi"),
    ("F3", "nuisance-and-dynamics",
     r"caustic|distractor|marine snow|transient|dynamic|flicker|"
     r"spatiotemporal|moving object|floater"),
    ("F4", "geometry-and-pose",
     r"structure.from.motion|\bsfm\b|colmap|refract|camera pose|pose estimation|"
     r"calibrat|multi-?view stereo|\bmvs\b|depth estimation|monocular depth|"
     r"stereo|feed-?forward|dust3r|mast3r|panoram|omnidirectional|trinocular|"
     r"sparse-?view|bathymetr|\bsdf\b|point cloud"),
    ("F2", "restoration-coupled",
     r"restorat|restor\w+|enhance\w*|color correct|colour correct|retinex|"
     r"true color|true appearance|degradation-aware"),
    ("F8", "applications",
     r"compress|teleoperat|archaeolog|heritage|shipwreck|coral reef monitor|"
     r"digital twin|inspection|test (image )?generat"),
]
UW_RE_F = re.compile(r"underwater|subsea|seafloor|benthic|marine|aquatic|submerged|sea", re.I)


def family_of(title, abstract="", lane=None):
    """Map a paper to a taxonomy family: named-method match first, rules second."""
    t = nk(title)
    best = None
    for fam in TAX["families"]:
        subs = fam.get("subfamilies") or [{"id": fam["id"], "name": fam["name"],
                                           "members": fam.get("members", [])}]
        for sf in subs:
            for m in sf["members"]:
                mk = nk(re.sub(r"\(.*?\)", "", m))
                # short coined names (UW-GS -> "uwgs", TUGS) only ever appear as a
                # title prefix, so allow them there; longer names may appear anywhere
                hit = (len(mk) >= 5 and mk in t) or (len(mk) >= 3 and t.startswith(mk))
                if hit:
                    cand = (fam["id"], fam["anchor"], sf["id"], sf["name"], len(mk))
                    if best is None or cand[4] > best[4]:
                        best = cand
    if best:
        return best[:4]

    blob = f"{title} {abstract}"
    for fid, anchor, pat in FALLBACK:
        if re.search(pat, blob, re.I):
            # a scattering-media rule only means F7 when the paper is NOT underwater
            if fid == "F7" and UW_RE_F.search(blob):
                continue
            return (fid, anchor, None, "(rule-assigned)")
    if lane in ("core", "medium"):
        return ("F1", "medium-aware-splatting", None, "(rule-assigned)")
    return (None, None, None, None)


def esc(s):
    return (s or "").replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


MORPHEME = re.compile(r"sea|aqua|water|hydro|ocean|marine|reef|uw|splat|nerf|"
                      r"gauss|dehaz|scatter|haze|caustic|bathy|swim", re.I)


def method_name(title):
    t = (title or "").strip()
    if ":" not in t:
        return None
    head = t.split(":", 1)[0].strip()
    return head if 3 <= len(head) <= 34 and re.search(r"[A-Z0-9]", head) else None


def repo_relates(title, repo):
    """Does this repository plausibly BELONG to this paper?

    Repo URLs harvested from a PDF's front matter are as often dependencies as
    the paper's own code: AquaNeRF's PDF links google-research/multinerf,
    ReefMapGS links MichaelGrupp/evo, NeRF-To-Real Tester links
    magicleap/SuperPointPretrainedNetwork. All three are tools the paper uses,
    and all three were being credited as the paper's implementation. Require the
    repository name to actually correspond to the paper's system name.
    """
    if not repo or not repo.get("full_name"):
        return False
    rn = repo["full_name"].split("/")[-1]
    b = nk(rn)
    mn = method_name(title)
    if mn:
        a = nk(mn)
        if a and (a == b or (len(a) >= 5 and a in b) or (len(b) >= 5 and b in a
                                                         and len(b) / len(a) >= 0.6)):
            return True
    # Acronym: "Underwater Variable Zoom" -> UVZ (WindySprint/UVZ),
    # "Style-Decoupled Adaptive Routing Network" -> SDARN ~ SDAR-Net.
    # the acronym is formed from the leading capitalised run only: for
    # "Style-Decoupled Adaptive Routing Network for Underwater Image Enhancement"
    # the acronym is SDARN, not SDARNFUIE
    lead = re.match(r"([A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)*)", (title or "").strip())
    for src in (mn, lead.group(1) if lead else None, title):
        if not src:
            continue
        initials = nk("".join(w[0] for w in re.findall(r"[A-Za-z][a-z]+|[A-Z]{2,}", src)))
        if len(initials) >= 3 and (initials == b or initials in b):
            return True

    # Repo name as a token set drawn from the title:
    # facebookresearch/volumetric_primitives <- "... Volumetric Ray-Traced
    # Primitives for Modeling and Rendering ...". The tokens are in the title but
    # not adjacent, so substring matching alone misses it.
    toks = [t for t in re.split(r"[^A-Za-z0-9]+", rn) if len(t) >= 5]
    if len(toks) >= 2:
        tl = (title or "").lower()
        if all(t.lower() in tl for t in toks):
            return True

    words = [nk(w) for w in re.findall(r"[A-Za-z][A-Za-z\-]{4,}", title or "")]
    return any(w and w in b and MORPHEME.search(w) for w in words)


def main():
    pool = load_records(os.path.join(OUT, "pool_b4a.json"))
    assign = json.load(open(os.path.join(OUT, "repo_assign.json"))) \
        if os.path.exists(os.path.join(OUT, "repo_assign.json")) else {}
    digests = json.load(open(os.path.join(OUT, "digests.json")))
    fetch = json.load(open(os.path.join(OUT, "fetch_results.json")))

    # Digest lookup by pdf slug. Also index by normalized title: title-dedup can
    # keep the record whose canonical_id never had a fetch attempt while its
    # collapsed twin did (RecGS was reported as pdf_fetched=no despite the PDF
    # sitting on disk under the twin's id).
    slug_of, slug_by_title = {}, {}
    for cid, v in fetch.items():
        s = os.path.basename(v["file"])[:-4] if v.get("file") else None
        slug_of[cid] = s
        if s and v.get("title"):
            slug_by_title.setdefault(nk(v["title"]), s)
    # seed PDFs are named by seed key, not by the pool slug
    for sf in glob.glob(os.path.join(OUT, "seed_fetch.json")):
        for e in json.load(open(sf)):
            if e.get("status") in ("ok", "cached") and e.get("title"):
                slug_by_title.setdefault(nk(e["title"]), e["key"])

    used, method_set, context_set, excluded = set(), [], [], []
    seen_titles = {}
    for r in sorted(pool, key=lambda x: x.canonical_id):
        tkey = nk(r.title)
        # belt-and-braces title dedup: two RecGS records survived the B.2 merge
        # (they differ only by "With"/"with" in a field the merge did not key on)
        if tkey in seen_titles:
            continue
        seen_titles[tkey] = True
        if tkey in EXCL_TITLES:
            r.raw["exclusion"] = EXCL_TITLES[tkey]
            excluded.append(r)
            continue
        lane = r.raw.get("lane")
        fam, anchor, sfid, sfname = family_of(r.title, r.abstract or "", lane)
        a = assign.get(r.canonical_id) or {}
        repo = a.get("repo")
        if repo and not repo_relates(r.title, repo):
            r.raw["rejected_repo"] = repo.get("full_name")
            repo = None
        sl = slug_of.get(r.canonical_id) or slug_by_title.get(tkey)
        dg = digests.get(sl) if sl else None

        r.raw.update({
            "bibkey": bibkey(r, used),
            "family": fam, "family_anchor": anchor,
            "subfamily": sfid, "subfamily_name": sfname,
            "repo": repo,
            "has_code": bool(repo and repo.get("status") == "ok"),
            "pdf": sl,
            "datasets": (dg or {}).get("datasets_mentioned", []),
            "out_of_window_anchor": lane == "anchor",
        })

        if lane == "anchor":
            context_set.append(r)
        elif r.raw["has_code"] and lane in ("core", "medium"):
            method_set.append(r)
        else:
            context_set.append(r)

    # ---- outputs ----------------------------------------------------------
    serialize_records(method_set, os.path.join(OUT, "method_set.json"))
    serialize_records(context_set, os.path.join(OUT, "context_set.json"))

    cols = ["bibkey", "title", "year", "venue", "family", "subfamily", "lane",
            "arxiv_id", "doi", "repo_url", "repo_stars", "repo_language",
            "repo_license", "repo_last_push", "repo_size_kb", "datasets",
            "citations", "pdf_fetched", "set"]
    with open(os.path.join(ROOT, "papers_table.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for tag, group in (("method", method_set), ("context", context_set)):
            for r in group:
                rp = r.raw.get("repo") or {}
                w.writerow([
                    r.raw["bibkey"], r.title, r.year, r.venue or "",
                    r.raw.get("family") or "", r.raw.get("subfamily") or "",
                    r.raw.get("lane"), r.arxiv_id or "", r.doi or "",
                    rp.get("url", ""), rp.get("stars", ""), rp.get("language", ""),
                    rp.get("license", ""), rp.get("pushed_at", ""), rp.get("size_kb", ""),
                    "; ".join(sorted({d.lower() for d in r.raw.get("datasets", [])}))[:180],
                    r.citation_count if r.citation_count is not None else "",
                    "yes" if r.raw.get("pdf") else "no", tag,
                ])

    with open(os.path.join(ROOT, "excluded.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "year", "lane", "reason", "stage"])
        for r in excluded:
            w.writerow([r.title, r.year, r.raw.get("lane"), r.raw.get("exclusion"), "B.6-manual"])
        for fn, stage in (("excluded_sensor.json", "B.2b-sensor-gate"),
                          ("excluded_relevance.json", "B.4a-relevance-gate")):
            p = os.path.join(OUT, fn)
            if os.path.exists(p):
                for r in load_records(p):
                    w.writerow([r.title, r.year, r.raw.get("lane"),
                                r.raw.get("exclusion", "gate"), stage])

    with open(os.path.join(ROOT, "references.bib"), "w", encoding="utf-8") as f:
        for r in sorted(method_set + context_set, key=lambda x: x.raw["bibkey"]):
            typ = "article" if (r.venue and "arxiv" not in (r.venue or "").lower()) else "misc"
            f.write(f"@{typ}{{{r.raw['bibkey']},\n")
            f.write(f"  title  = {{{esc(r.title)}}},\n")
            if r.authors:
                f.write(f"  author = {{{esc(' and '.join(r.authors))}}},\n")
            if r.year:
                f.write(f"  year   = {{{r.year}}},\n")
            if r.venue:
                f.write(f"  journal= {{{esc(r.venue)}}},\n")
            if r.doi:
                f.write(f"  doi    = {{{r.doi}}},\n")
            if r.arxiv_id:
                f.write(f"  eprint = {{{r.arxiv_id}}},\n  archivePrefix = {{arXiv}},\n")
            rp = r.raw.get("repo") or {}
            if rp.get("url"):
                f.write(f"  note   = {{Code: \\url{{{rp['url']}}}}},\n")
            f.write("}\n\n")

    # code availability spoke
    fam_stat = collections.defaultdict(lambda: [0, 0])
    for r in method_set + context_set:
        if r.raw.get("lane") in ("core", "medium"):
            fam = r.raw.get("family") or "unassigned"
            fam_stat[fam][1] += 1
            if r.raw["has_code"]:
                fam_stat[fam][0] += 1
    with open(os.path.join(ROOT, "code_availability.md"), "w", encoding="utf-8") as f:
        f.write("# Code availability\n\n")
        f.write("Every repository below was resolved and verified through the GitHub API. "
                "`ok` means the repository exists, reports a primary language, and holds more "
                "than a README's worth of content (>40 KB). `stub` means it resolves but "
                "carries no real source — an announced-but-unpublished release.\n\n")
        f.write("## Rate by method family\n\n| Family | With code | Candidates | Rate |\n|---|---:|---:|---:|\n")
        for fam in sorted(fam_stat):
            a, b = fam_stat[fam]
            f.write(f"| {fam} | {a} | {b} | {100*a//max(1,b)}% |\n")
        f.write("\n## Verified repositories\n\n"
                "| Method | Repo | Stars | Lang | License | Last push | Size (KB) |\n"
                "|---|---|---:|---|---|---|---:|\n")
        for r in sorted(method_set, key=lambda x: -( (x.raw['repo'] or {}).get('stars') or 0)):
            rp = r.raw["repo"]
            nm = (r.title or "").split(":")[0][:40]
            f.write(f"| {nm} | [{rp['full_name']}]({rp['url']}) | {rp.get('stars',0)} | "
                    f"{rp.get('language') or '—'} | {rp.get('license') or 'none'} | "
                    f"{rp.get('pushed_at') or '—'} | {rp.get('size_kb') or '—'} |\n")

    man = {
        "generated": datetime.date.today().isoformat(),
        "topic": "Gaussian splatting for underwater scenes (visual-only, code-available)",
        "tier": "academic (degraded: see PLAN.md source health)",
        "counts": {"pool_b4a": len(pool), "method_set": len(method_set),
                   "context_set": len(context_set), "manually_excluded": len(excluded)},
        "families": {f["id"]: f["anchor"] for f in TAX["families"]},
        "reproducibility": {
            "python_version": sys.version.split()[0],
            "pymupdf_version": __import__("fitz").__doc__ or "",
            "cite_extract_version": "not-installed",
            "cite_critic_version": "disabled (skill not installed)",
            "sentiment_multipliers": "n/a (Tier-0 sentiment classification not run)",
            "query_seed_strings_hash": hashlib.sha256(
                open(os.path.join(OUT, "run_b1.py"), "rb").read()).hexdigest()[:16],
        },
        "papers": [
            {"bibkey": r.raw["bibkey"], "title": r.title, "year": r.year,
             "family": r.raw.get("family"), "subfamily": r.raw.get("subfamily"),
             "set": ("method" if r in method_set else "context"),
             "has_code": r.raw["has_code"],
             "repo": (r.raw.get("repo") or {}).get("url"),
             "out_of_window_anchor": r.raw["out_of_window_anchor"],
             "canonical_id": r.canonical_id}
            for r in sorted(method_set + context_set, key=lambda x: x.raw["bibkey"])
        ],
    }
    json.dump(man, open(os.path.join(ROOT, "MANIFEST.json"), "w"), indent=2)

    print(f"method_set  = {len(method_set)}")
    print(f"context_set = {len(context_set)}")
    print(f"excluded    = {len(excluded)} (manual) + gates")
    print("\ncode-availability by family:")
    for fam in sorted(fam_stat):
        a, b = fam_stat[fam]
        print(f"  {fam or 'unassigned':<28} {a}/{b}")
    unassigned = [r.title for r in method_set if not r.raw.get("family")]
    print(f"\nmethod-set papers with no family: {len(unassigned)}")
    for t in unassigned[:20]:
        print("   ", t[:88])


if __name__ == "__main__":
    main()
