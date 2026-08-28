"""B.7.5 -- tiered PDF fetch for the candidate pool, then harvest code URLs from
the fetched PDFs' front matter.

Harvesting repo links out of the papers themselves costs zero GitHub API quota,
which matters here: GITHUB_TOKEN is unset and anonymous GitHub allows 60 req/hr,
while the repo gate is the defining constraint of this run. Doing discovery via
GitHub search would have burned the whole hourly budget before verifying a
single repository.
"""
import os, re, sys, json, time, urllib.request, urllib.error, concurrent.futures as cf
import fitz

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
PDFS = os.path.join(os.path.dirname(OUT), "pdfs")
os.makedirs(PDFS, exist_ok=True)
_m = os.environ.get("SOTA_REPORT_MAILTO", "")
UA = {"User-Agent": "Mozilla/5.0 (compatible; sota-report/0.4"
                    + (f"; +mailto:{_m}" if _m else "") + ")"}

CODE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(github\.com|gitlab\.com|bitbucket\.org|codeberg\.org)/"
    r"([A-Za-z0-9][\w.\-]{0,38})/([\w.\-]{1,64})", re.I)
PAGE_RE = re.compile(r"(?:https?://)([\w\-]+\.github\.io/[\w\-./]*)", re.I)
BAD = {"sponsors", "features", "about", "topics", "collections", "orgs", "apps",
       "settings", "marketplace", "site", "readme", "login", "join", "pricing",
       "explore", "notifications", "search", "blog", "security"}


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def slug(r):
    a = (r.authors[0].split(",")[0] if r.authors else "anon")
    a = re.sub(r"[^A-Za-z]", "", a).lower() or "anon"
    t = re.sub(r"[^a-z0-9]+", "", (r.title or "")[:26].lower())
    return f"{a}{r.year or 0}_{t}"[:58]


def fetch(url, dest, timeout=50):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as h:
            data = h.read()
    except urllib.error.HTTPError as e:
        return False, f"http-{e.code}"
    except Exception as e:
        return False, type(e).__name__
    if not data.startswith(b"%PDF"):
        return False, "not-pdf"
    if len(data) < 20000:
        return False, "too-small"
    with open(dest, "wb") as f:
        f.write(data)
    return True, f"{len(data)//1024}KB"


def candidates(r):
    """Tiered URL list: arXiv -> OA url -> DOI resolver."""
    urls = []
    if r.arxiv_id:
        urls.append(f"https://arxiv.org/pdf/{r.arxiv_id}")
    if r.pdf_url and r.pdf_url not in urls:
        urls.append(r.pdf_url)
    return urls


def one(r):
    dest = os.path.join(PDFS, slug(r) + ".pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 20000:
        return {"id": r.canonical_id, "file": dest, "status": "cached"}
    tried = []
    for u in candidates(r):
        ok, d = fetch(u, dest)
        tried.append(f"{u[:48]}:{d}")
        if ok:
            return {"id": r.canonical_id, "file": dest, "status": "ok",
                    "detail": d, "tried": tried}
        time.sleep(0.8)
    return {"id": r.canonical_id, "file": None, "status": "fail", "tried": tried}


def harvest(path):
    """Code URLs + project pages from the first 2 and last 1 pages."""
    try:
        d = fitz.open(path)
    except Exception:
        return [], []
    pages = list(range(min(2, len(d)))) + ([len(d) - 1] if len(d) > 2 else [])
    txt = ""
    for i in pages:
        txt += d[i].get_text("text") + "\n"
        for lnk in d[i].get_links():
            if lnk.get("uri"):
                txt += lnk["uri"] + "\n"
    d.close()
    txt = txt.replace("\u00ad", "").replace("\n", " ")
    repos, sites = set(), set()
    for host, owner, name in CODE_RE.findall(txt):
        owner, name = owner.strip("."), name.strip(".").removesuffix(".git")
        if owner.lower() in BAD or len(name) < 2 or name.lower() in BAD:
            continue
        repos.add(f"https://{host.lower()}/{owner}/{name}")
    for s in PAGE_RE.findall(txt):
        sites.add("https://" + s.rstrip("./"))
    return sorted(repos), sorted(sites)


def main():
    pool = load_records(os.path.join(OUT, "pool_b4a.json"))
    want = [r for r in pool if r.raw.get("lane") in ("core", "medium", "anchor", "support")]
    have_url = [r for r in want if candidates(r)]
    log(f"pool={len(pool)} fetchable(with arXiv/OA url)={len(have_url)} "
        f"no-url={len(want)-len(have_url)}")

    results = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(one, r): r for r in have_url}
        for i, f in enumerate(cf.as_completed(futs), 1):
            r = futs[f]
            try:
                res = f.result()
            except Exception as e:
                res = {"id": r.canonical_id, "file": None, "status": "err", "detail": str(e)[:60]}
            res["title"] = r.title
            res["lane"] = r.raw.get("lane")
            results[r.canonical_id] = res
            if i % 15 == 0 or res["status"] == "fail":
                ok = sum(1 for v in results.values() if v["status"] in ("ok", "cached"))
                log(f"  {i}/{len(have_url)} ok={ok} {time.time()-t0:.0f}s  "
                    f"[{res['status']}] {(r.title or '')[:52]}")

    ok = [v for v in results.values() if v["status"] in ("ok", "cached")]
    log(f"PDF fetch: {len(ok)}/{len(have_url)} ({100*len(ok)//max(1,len(have_url))}%), "
        f"{time.time()-t0:.0f}s")

    log("harvesting code URLs from PDFs ...")
    nrepo = 0
    for cid, v in results.items():
        if not v.get("file") or not os.path.exists(v["file"]):
            continue
        repos, sites = harvest(v["file"])
        v["repos"], v["project_pages"] = repos, sites
        nrepo += bool(repos)
    log(f"papers with >=1 code URL in PDF: {nrepo}/{len(ok)}")

    # also fold in URLs already found in abstracts at B.2
    for r in pool:
        v = results.get(r.canonical_id)
        au = r.raw.get("code_urls") or []
        if v is None and au:
            results[r.canonical_id] = {"id": r.canonical_id, "title": r.title,
                                       "lane": r.raw.get("lane"), "status": "no-pdf",
                                       "repos": au, "project_pages": []}
        elif v is not None and au:
            v["repos"] = sorted(set((v.get("repos") or []) + au))

    json.dump(results, open(os.path.join(OUT, "fetch_results.json"), "w"), indent=2)
    allrepos = sorted({u for v in results.values() for u in (v.get("repos") or [])})
    json.dump(allrepos, open(os.path.join(OUT, "discovered_repos.json"), "w"), indent=2)
    log(f"unique repo URLs discovered: {len(allrepos)}")


if __name__ == "__main__":
    main()
