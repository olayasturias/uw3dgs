"""Repo discovery + verification for the strict-present repo gate.

Three discovery channels, cheapest first:
  1. regex code URLs straight out of abstracts   -- free, no API
  2. awesome-list READMEs via raw.githubusercontent -- free, no API quota
  3. GitHub search API by method name             -- costs quota

Then one /repos/{owner}/{repo} call per unique repo to verify it is real
(size, language, pushed_at, license, stars) rather than a README stub.
"""
import os, re, sys, json, time, urllib.request, urllib.error

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
OUT = os.path.dirname(os.path.abspath(__file__))

TOKEN = os.environ.get("GITHUB_TOKEN") or ""
if not TOKEN:
    try:
        import subprocess
        TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True,
                               text=True, timeout=15).stdout.strip()
        if "no oauth" in TOKEN.lower() or " " in TOKEN:
            TOKEN = ""
    except Exception:
        TOKEN = ""

HDR = {"User-Agent": "sota-report/0.4", "Accept": "application/vnd.github+json"}
if TOKEN:
    HDR["Authorization"] = f"Bearer {TOKEN}"

REPO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(github\.com|gitlab\.com|bitbucket\.org)/"
    r"([A-Za-z0-9][\w.-]*)/([\w.-]+?)(?=[\s,;)\]}>\"']|\.git|/|$)",
    re.I,
)
BAD_OWNERS = {"sponsors", "features", "about", "topics", "collections", "orgs",
              "settings", "marketplace", "apps", "site", "readme"}

AWESOME_LISTS = [
    "MrNeRF/awesome-3D-gaussian-splatting",
    "xinzhichao/awesome-underwater-datasets",
    "wangyanckxx/Single-Underwater-Image-Enhancement-and-Color-Restoration",
    "yzrobot/awesome-underwater-robotics",
    "awesome-NeRF/awesome-NeRF",
]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def _get(url, timeout=30, raw=False):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return data.decode("utf-8", "replace") if raw else json.loads(data)


def extract_repos(text):
    """Pull normalized host/owner/name triples out of free text."""
    out = set()
    if not text:
        return out
    for host, owner, name in REPO_RE.findall(text):
        owner, name = owner.strip("."), name.strip(".").removesuffix(".git")
        if owner.lower() in BAD_OWNERS or not name or len(name) < 2:
            continue
        out.add((host.lower(), owner, name))
    return out


def fetch_awesome(slug):
    for branch in ("main", "master"):
        for fn in ("README.md", "readme.md"):
            try:
                return _get(f"https://raw.githubusercontent.com/{slug}/{branch}/{fn}",
                            raw=True)
            except urllib.error.HTTPError:
                continue
            except Exception:
                continue
    return ""


def gh_search_repos(q, per_page=20):
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q) + f"&sort=stars&order=desc&per_page={per_page}")
    try:
        return _get(url).get("items", [])
    except Exception as e:
        log(f"  search fail '{q[:40]}': {e}")
        return []


def verify_repo(host, owner, name):
    """One API call. Returns dict with the gate decision."""
    rec = {"host": host, "owner": owner, "name": name,
           "url": f"https://{host}/{owner}/{name}", "status": None}
    if host != "github.com":
        rec["status"] = "unverified-nongithub"
        return rec
    try:
        d = _get(f"https://api.github.com/repos/{owner}/{name}")
    except urllib.error.HTTPError as e:
        rec["status"] = "404" if e.code == 404 else f"http-{e.code}"
        return rec
    except Exception as e:
        rec["status"] = f"err-{type(e).__name__}"
        return rec

    rec.update({
        "full_name": d.get("full_name"),
        "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"),
        "size_kb": d.get("size"),
        "language": d.get("language"),
        "pushed_at": (d.get("pushed_at") or "")[:10],
        "created_at": (d.get("created_at") or "")[:10],
        "license": ((d.get("license") or {}) or {}).get("spdx_id"),
        "archived": d.get("archived"),
        "description": (d.get("description") or "")[:200],
        "homepage": d.get("homepage"),
        "topics": d.get("topics", []),
    })
    # strict-present gate: real source, not a README stub / "code coming soon"
    size = rec.get("size_kb") or 0
    lang = rec.get("language")
    rec["has_source"] = bool(lang) and size >= 40
    rec["status"] = "ok" if rec["has_source"] else "stub"
    return rec


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    log(f"GITHUB_TOKEN present: {bool(TOKEN)}")
    try:
        rl = _get("https://api.github.com/rate_limit")
        core = rl["resources"]["core"]
        log(f"rate limit: {core['remaining']}/{core['limit']} core, "
            f"search {rl['resources']['search']['remaining']}/{rl['resources']['search']['limit']}")
    except Exception as e:
        log(f"rate_limit probe failed: {e}")

    if mode in ("awesome", "all"):
        found = {}
        for slug in AWESOME_LISTS:
            md = fetch_awesome(slug)
            if not md:
                log(f"awesome MISS {slug}")
                continue
            # keep only lines mentioning the domain, to avoid pulling in 1000s of
            # unrelated splatting repos from awesome-3D-gaussian-splatting
            keep = [ln for ln in md.splitlines()
                    if re.search(r"underwater|subsea|seafloor|benthic|marine|aquatic|"
                                 r"submerged|turbid|scatter|fog|haze|dehaz|caustic|water",
                                 ln, re.I)]
            repos = set()
            for ln in keep:
                repos |= extract_repos(ln)
            found[slug] = sorted(repos)
            log(f"awesome HIT  {slug}: {len(keep)} domain lines -> {len(repos)} repos")
        with open(os.path.join(OUT, "awesome_repos.json"), "w") as f:
            json.dump({k: [list(t) for t in v] for k, v in found.items()}, f, indent=2)


if __name__ == "__main__":
    import urllib.parse  # noqa
    main()
