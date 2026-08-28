"""Post-filter GitHub search matches before the repo gate trusts them.

run_repofind.py accepts a repo when its normalized name equals the method name,
or is contained in it alongside any domain term. Both rules produce false
positives here:

  "Don't Splat your Gaussians" -> antimatter15/splat   (a WebGL 3DGS viewer)
  "PRISM-Splat"                -> aburgasser/splat     (an astronomy toolkit)
  "BALTIC" (air/water benchmark) -> evogytis/baltic    (phylogenetics library)
  "AEGIR"                      -> ipfs/aegir           (an IPFS tool)
  "WaterGS"                    -> Water-GS.github.io   (project page, not source)

Two rules do the work.

1. CONTAINMENT DIRECTION. `method in repo_name` is good evidence -- the repo just
   carries a prefix or suffix ("3drr_Track2_SmokeGS-R"). `repo_name in method` is
   bad evidence -- it means the repo name is a short generic fragment of the
   method name, which is how `splat` matched three different papers.

2. COINED NAME or DOMAIN TERM. An exact name match is not sufficient on its own
   when the name is an ordinary word: BALTIC and AEGIR both matched exactly, to
   unrelated projects. But requiring a domain term in the description is too
   strict in the other direction, because many correct repos (dxyang/seasplat,
   WangHaoran16/UW-GS) ship with no description and no topics at all. So accept
   when the method name is clearly *coined* -- camelCase, a hyphen, or a digit,
   or a field-specific morpheme -- or when a domain term is present.
"""
import os, re, json

OUT = os.path.dirname(os.path.abspath(__file__))
CACHE_F = os.path.join(OUT, "gh_search_cache.json")

STRONG = re.compile(
    r"underwater|subsea|seafloor|seabed|benthic|submerged|marine|aquatic|ocean|"
    r"sea-?thru|turbid|backscatter|scattering|dehaz|\bhaze\b|\bfog\b|caustic|"
    r"gaussian splat|3d gaussian|3dgs|radiance field|nerf|novel view|splatting|"
    r"photogrammetr|structure.from.motion|\bsfm\b|\bslam\b|bathymetr|stereo|depth",
    re.I)
MORPHEME = re.compile(r"sea|aqua|water|hydro|ocean|marine|reef|\buw\b|uw-|splat|"
                      r"nerf|gauss|dehaz|scatter|haze|caustic|bathy|swim", re.I)


def nk(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def coined(name):
    """Does this look like a deliberately-invented system name, not a plain word?"""
    if re.search(r"\d", name) or "-" in name or "_" in name:
        return True
    if re.search(r"[a-z][A-Z]", name):          # camelCase
        return True
    if MORPHEME.search(name):
        return True
    return False


def main():
    cache = json.load(open(CACHE_F))
    kept, report_ok, report_bad = 0, [], []

    for k, v in cache.items():
        if not k.startswith("method::"):
            continue
        # re-evaluate everything, including entries a previous stricter pass
        # downgraded, so this filter is idempotent rather than cumulative
        if v.get("status") == "weak-match":
            v["status"] = "ok"
            v.pop("rejected_because", None)
        if v.get("status") != "ok":
            continue

        method = v.get("matched_method") or ""
        full = v.get("full_name") or ""
        repo_name = full.split("/")[-1]
        a, b = nk(method), nk(repo_name)
        if not a or not b:
            continue

        exact = a == b
        method_in_repo = len(a) >= 5 and a in b
        repo_in_method = b in a and not exact

        blob = f"{full} {v.get('description','')} {' '.join(v.get('topics') or [])}"
        domain = bool(STRONG.search(blob))
        # project pages come in two shapes: "<x>.github.io" and "<x>-website"
        rn = repo_name.lower()
        is_pages = (rn.endswith(".github.io") or rn.endswith("-website")
                    or rn.endswith("-page") or rn.endswith(".io"))

        why = []
        if not (exact or method_in_repo):
            why.append("repo name is only a fragment of the method name"
                       if repo_in_method else "name mismatch")
        if not (coined(method) or domain):
            why.append("plain-word name with no domain term to corroborate")
        if is_pages:
            why.append("project website (*.github.io), not source")

        if why:
            v["status"] = "weak-match"
            v["rejected_because"] = "; ".join(why)
            report_bad.append((method, full, v.get("stars"), "; ".join(why)))
        else:
            kept += 1
            report_ok.append((method, full, v.get("stars"), v.get("language")))

    json.dump(cache, open(CACHE_F, "w"), indent=2)
    print(f"confirmed: {kept}    rejected: {len(report_bad)}\n")
    print("--- ACCEPTED ---")
    for m, f, s, lang in sorted(report_ok):
        print(f"  {m:<26} -> {f:<44} *{s or 0:<5} {lang or ''}")
    print("\n--- REJECTED ---")
    for m, f, s, w in sorted(report_bad):
        print(f"  {m:<26} -> {f:<44} *{s or 0:<5} ({w})")


if __name__ == "__main__":
    main()
