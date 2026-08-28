"""Repo discovery + verification entirely through the GitHub SEARCH API.

Anonymous GitHub gives 60 requests/hour on the core API but 10 requests/MINUTE
(~600/hr) on the search API -- a different bucket. Search results carry the full
repository object (stars, size, language, license, pushed_at, archived), so both
discovery ("find the repo for method X") and verification ("is this repo real
source or a stub?") can run on the cheap bucket. `q=repo:owner/name` verifies a
known repo in one search call instead of one core call.

Method names are taken from the title prefix before the colon, which is how
essentially every paper in this field names its system ("SeaSplat: ...",
"UW-GS: ...", "TUGS: ..."). A repo counts as a match when its normalized name
equals the normalized method name, or the method name appears in the repo's
full_name/description alongside a domain term.
"""
import os, re, sys, json, time, urllib.request, urllib.parse, urllib.error, collections

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
CACHE_F = os.path.join(OUT, "gh_search_cache.json")
HDR = {"User-Agent": "sota-report/0.4", "Accept": "application/vnd.github+json"}
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
if TOKEN:
    HDR["Authorization"] = f"Bearer {TOKEN}"

MIN_INTERVAL = 6.5 if not TOKEN else 1.0   # 10/min anonymous
SIZE_MIN_KB = 40
_last = [0.0]

DOMAIN_RE = re.compile(r"underwater|subsea|seafloor|marine|aquatic|water|sea|"
                       r"scatter|dehaz|haze|fog|turbid|splat|gaussian|nerf|"
                       r"radiance|3d|reconstruct", re.I)


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def throttle():
    dt = time.time() - _last[0]
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last[0] = time.time()


def search(q, per_page=8, tries=3):
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q) + f"&per_page={per_page}")
    for i in range(tries):
        throttle()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=35) as r:
                return json.load(r).get("items", [])
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = int(e.headers.get("Retry-After") or 25)
                log(f"    search throttled ({e.code}); sleeping {wait}s")
                time.sleep(wait)
                continue
            return []
        except Exception:
            time.sleep(3)
    return []


def slim(d):
    size, lang = d.get("size") or 0, d.get("language")
    return {
        "url": d.get("html_url"), "full_name": d.get("full_name"),
        "stars": d.get("stargazers_count"), "forks": d.get("forks_count"),
        "size_kb": size, "language": lang,
        "pushed_at": (d.get("pushed_at") or "")[:10],
        "created_at": (d.get("created_at") or "")[:10],
        "license": ((d.get("license") or {}) or {}).get("spdx_id"),
        "archived": d.get("archived"), "fork": d.get("fork"),
        "open_issues": d.get("open_issues_count"),
        "description": (d.get("description") or "")[:200],
        "topics": d.get("topics") or [],
        "has_source": bool(lang) and size >= SIZE_MIN_KB,
        "status": "ok" if (bool(lang) and size >= SIZE_MIN_KB) else "stub",
    }


def nk(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def method_name(title):
    """System name = the token block before the first colon, when it looks like a name."""
    t = (title or "").strip()
    if ":" not in t:
        return None
    head = t.split(":", 1)[0].strip()
    if not (2 <= len(head.split()) <= 4) and len(head.split()) != 1:
        return None
    if len(head) < 3 or len(head) > 34:
        return None
    if not re.search(r"[A-Z0-9]", head):
        return None
    # reject generic descriptive prefixes that are not system names
    if re.match(r"^(a|an|the|towards?|on|from|beyond|rethinking|learning|"
                r"exploring|understanding|improving|efficient|robust|real-?time)\b",
                head, re.I):
        return None
    return head


def main():
    cache = json.load(open(CACHE_F)) if os.path.exists(CACHE_F) else {}
    pool = load_records(os.path.join(OUT, "pool_b4a.json"))
    known = json.load(open(os.path.join(OUT, "discovered_repos.json")))
    fetchres = json.load(open(os.path.join(OUT, "fetch_results.json")))

    # ---- pass 1: verify repos already harvested from PDFs -----------------
    log(f"pass 1: verifying {len(known)} PDF-harvested repos via search")
    for i, u in enumerate(known, 1):
        if u in cache:
            continue
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)", u)
        if not m:
            cache[u] = {"url": u, "status": "unverified-nongithub"}
            continue
        items = search(f"repo:{m.group(1)}/{m.group(2)}", per_page=1)
        cache[u] = slim(items[0]) if items else {"url": u, "status": "not-found"}
        log(f'  {i}/{len(known)} [{cache[u]["status"]:<10}] {u[:64]}')
        json.dump(cache, open(CACHE_F, "w"), indent=2)

    # ---- pass 2: discover repos for named methods -------------------------
    targets = []
    for r in pool:
        if r.raw.get("lane") not in ("core", "medium"):
            continue
        n = method_name(r.title)
        if n:
            targets.append((r, n))
    log(f"pass 2: {len(targets)} named methods to search")

    found = {}
    for i, (r, name) in enumerate(targets, 1):
        ck = f"method::{nk(name)}"
        if ck in cache:
            found[r.canonical_id] = cache[ck]
            continue
        items = search(f"{name} in:name,description,readme", per_page=8)
        want = nk(name)
        best = None
        for d in items:
            repo_nk = nk(d.get("name"))
            full = f'{d.get("full_name")} {d.get("description") or ""}'
            exact = repo_nk == want
            close = want in repo_nk or repo_nk in want
            domain = bool(DOMAIN_RE.search(full))
            if exact or (close and domain and len(want) >= 5):
                best = d
                break
        rec = slim(best) if best else {"status": "no-match", "query": name}
        rec["matched_method"] = name
        cache[ck] = rec
        found[r.canonical_id] = rec
        if best:
            log(f'  {i}/{len(targets)} FOUND {name:<24} -> {rec["full_name"]:<40} '
                f'*{rec["stars"]} {rec["status"]}')
        else:
            log(f"  {i}/{len(targets)} ----- {name}")
        json.dump(cache, open(CACHE_F, "w"), indent=2)

    # ---- assemble per-paper repo assignment -------------------------------
    assign = {}
    for r in pool:
        cands = []
        fr = fetchres.get(r.canonical_id) or {}
        for u in (fr.get("repos") or []) + (r.raw.get("code_urls") or []):
            c = cache.get(u)
            if c and c.get("status") == "ok":
                cands.append(c)
        m = found.get(r.canonical_id)
        if m and m.get("status") == "ok":
            cands.append(m)
        # prefer a repo whose name matches the method name
        nm = nk(method_name(r.title) or "")
        cands.sort(key=lambda c: (nk(c.get("full_name", "").split("/")[-1]) != nm,
                                  -(c.get("stars") or 0)))
        assign[r.canonical_id] = {
            "title": r.title, "lane": r.raw.get("lane"),
            "repo": cands[0] if cands else None,
            "n_candidates": len(cands),
        }

    json.dump(assign, open(os.path.join(OUT, "repo_assign.json"), "w"), indent=2)
    json.dump(cache, open(CACHE_F, "w"), indent=2)
    n_ok = sum(1 for v in assign.values() if v["repo"])
    lanes = collections.Counter(v["lane"] for v in assign.values() if v["repo"])
    log(f"\npapers with a verified public repo: {n_ok}/{len(assign)}  by lane {dict(lanes)}")


if __name__ == "__main__":
    main()
