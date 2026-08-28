"""B.4b -- verify every discovered repo and apply the strict-present repo gate.

One GET /repos/{owner}/{repo} per repository. With GITHUB_TOKEN unset the
anonymous ceiling is 60 requests/hour, so the runner checks the live rate-limit
headers and sleeps against the real reset timestamp instead of guessing. Results
are cached to disk per repo, so re-runs cost nothing and an interrupted run
resumes where it stopped.

Gate ("strict-present", per PLAN.md): the repo must exist, be non-empty, expose a
detected language, and carry more than a README's worth of content. A repo that
is only a landing README ("code coming soon") fails.
"""
import os, re, sys, json, time, subprocess, urllib.request, urllib.error

OUT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(OUT, "repo_cache.json")

TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
if not TOKEN:
    try:
        t = subprocess.run(["gh", "auth", "token"], capture_output=True,
                           text=True, timeout=15).stdout.strip()
        if re.match(r"^gh[pousr]_[A-Za-z0-9]+$", t):
            TOKEN = t
    except Exception:
        pass

HDR = {"User-Agent": "sota-report/0.4", "Accept": "application/vnd.github+json"}
if TOKEN:
    HDR["Authorization"] = f"Bearer {TOKEN}"

SIZE_MIN_KB = 40      # a README-only repo is typically < 20 KB


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def api(url):
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.load(r), dict(r.headers), None
    except urllib.error.HTTPError as e:
        return None, dict(e.headers), e.code
    except Exception as e:
        return None, {}, type(e).__name__


def wait_if_needed(hdrs):
    rem = hdrs.get("X-RateLimit-Remaining")
    rst = hdrs.get("X-RateLimit-Reset")
    if rem is None:
        return
    if int(rem) <= 1 and rst:
        delay = max(0, int(rst) - int(time.time())) + 3
        log(f"  rate limit exhausted; sleeping {delay}s until reset")
        time.sleep(delay)


def verify(url, cache):
    if url in cache and cache[url].get("status") not in (None, "err-timeout"):
        return cache[url]
    m = re.match(r"https://(github\.com|gitlab\.com|bitbucket\.org|codeberg\.org)/([^/]+)/([^/]+)", url)
    if not m:
        rec = {"url": url, "status": "unparseable"}
        cache[url] = rec
        return rec
    host, owner, name = m.groups()
    if host != "github.com":
        rec = {"url": url, "host": host, "owner": owner, "name": name,
               "status": "unverified-nongithub"}
        cache[url] = rec
        return rec

    d, hdrs, err = api(f"https://api.github.com/repos/{owner}/{name}")
    if err == 403 and "rate limit" in json.dumps(hdrs).lower() + str(err):
        wait_if_needed(hdrs)
        d, hdrs, err = api(f"https://api.github.com/repos/{owner}/{name}")
    if d is None:
        rec = {"url": url, "owner": owner, "name": name,
               "status": {404: "not-found", 403: "forbidden-or-ratelimited",
                          451: "dmca"}.get(err, f"err-{err}")}
        cache[url] = rec
        wait_if_needed(hdrs)
        return rec

    size = d.get("size") or 0
    lang = d.get("language")
    has_source = bool(lang) and size >= SIZE_MIN_KB
    rec = {
        "url": d.get("html_url") or url, "owner": owner, "name": name,
        "full_name": d.get("full_name"), "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"), "size_kb": size, "language": lang,
        "pushed_at": (d.get("pushed_at") or "")[:10],
        "created_at": (d.get("created_at") or "")[:10],
        "license": ((d.get("license") or {}) or {}).get("spdx_id"),
        "archived": d.get("archived"), "fork": d.get("fork"),
        "open_issues": d.get("open_issues_count"),
        "description": (d.get("description") or "")[:180],
        "topics": d.get("topics") or [],
        "has_source": has_source,
        "status": "ok" if has_source else "stub",
    }
    cache[url] = rec
    wait_if_needed(hdrs)
    return rec


def main():
    repos = json.load(open(os.path.join(OUT, "discovered_repos.json")))
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    log(f"token={'yes' if TOKEN else 'NO (anonymous, 60/hr)'}  repos={len(repos)}  "
        f"cached={sum(1 for r in repos if r in cache)}")

    d, hdrs, _ = api("https://api.github.com/rate_limit")
    if d:
        c = d["resources"]["core"]
        log(f"rate limit: {c['remaining']}/{c['limit']}")

    for i, u in enumerate(repos, 1):
        was = u in cache
        rec = verify(u, cache)
        if not was:
            log(f"  {i}/{len(repos)} [{rec['status']:<12}] "
                f"{'*' + str(rec.get('stars')) if rec.get('stars') is not None else '':>6} "
                f"{rec.get('language') or '':<12} {u[:62]}")
            json.dump(cache, open(CACHE, "w"), indent=2)

    json.dump(cache, open(CACHE, "w"), indent=2)
    import collections
    st = collections.Counter(v["status"] for v in cache.values())
    log(f"done. statuses: {dict(st)}")


if __name__ == "__main__":
    main()
