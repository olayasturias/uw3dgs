"""B.3.3 / B.3.4 -- co-citation expansion via OpenAlex.

Semantic Scholar is unstable in this environment (1/5 probe success, HTTP 429),
so OpenAlex substitutes: `referenced_works` gives the backward bibliography and
`cited_by_api_url` gives the forward citers. Neither carries sentiment, so every
citation enters the tally at multiplier 1.0; the sentiment layer is applied
separately from Tier-0 PDF reads.
"""
import os, re, sys, json, time, collections, urllib.request, urllib.parse, urllib.error

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
API = "https://api.openalex.org"
# Contact for API "polite pool" rate limits (OpenAlex/Crossref/unpaywall).
# Set SOTA_REPORT_MAILTO to your own address; left unset the requests still
# work, just on the anonymous rate limit.
MAILTO = os.environ.get("SOTA_REPORT_MAILTO", "")
SEL = ("id,doi,title,display_name,publication_year,cited_by_count,type,"
       "primary_location,authorships,referenced_works,abstract_inverted_index,"
       "best_oa_location,open_access")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"sota-report/0.4 (mailto:{MAILTO})"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(3 * (i + 1)); continue
            raise
        except Exception:
            if i < tries - 1:
                time.sleep(2 * (i + 1)); continue
            raise


def unabstract(inv):
    if not inv:
        return None
    pos = {}
    for w, ii in inv.items():
        for i in ii:
            pos[i] = w
    return " ".join(pos[k] for k in sorted(pos))[:1800]


def find_work(rec):
    """Resolve a seed CanonicalRecord to an OpenAlex work."""
    if rec.doi:
        try:
            return get(f"{API}/works/doi:{rec.doi}?select={SEL}&mailto={MAILTO}")
        except Exception:
            pass
    if rec.arxiv_id:
        for f in (f"locations.landing_page_url:https://arxiv.org/abs/{rec.arxiv_id}",):
            try:
                d = get(f"{API}/works?filter={urllib.parse.quote(f)}&select={SEL}&mailto={MAILTO}")
                if d.get("results"):
                    return d["results"][0]
            except Exception:
                pass
    t = re.sub(r"[^A-Za-z0-9 ]", " ", rec.title or "")[:120]
    try:
        d = get(f"{API}/works?filter=title.search:{urllib.parse.quote(t)}"
                f"&select={SEL}&per-page=5&mailto={MAILTO}")
        for w in d.get("results", []):
            a = re.sub(r"[^a-z0-9]", "", (w.get("display_name") or "").lower())
            b = re.sub(r"[^a-z0-9]", "", (rec.title or "").lower())
            if a[:60] == b[:60]:
                return w
    except Exception:
        pass
    return None


def batch_works(ids):
    out = []
    ids = [i.rsplit("/", 1)[-1] for i in ids]
    for i in range(0, len(ids), 50):
        chunk = "|".join(ids[i:i + 50])
        try:
            d = get(f"{API}/works?filter=ids.openalex:{chunk}&select={SEL}"
                    f"&per-page=50&mailto={MAILTO}")
            out += d.get("results", [])
        except Exception as e:
            log(f"  batch fail: {e}")
        time.sleep(0.35)
    return out


def slim(w):
    loc = w.get("primary_location") or {}
    src = (loc.get("source") or {}) or {}
    oa = (w.get("best_oa_location") or {}) or {}
    return {
        "oa_id": w.get("id"), "doi": w.get("doi"),
        "title": w.get("display_name"), "year": w.get("publication_year"),
        "cited_by": w.get("cited_by_count"), "type": w.get("type"),
        "venue": src.get("display_name"),
        "authors": [a["author"]["display_name"]
                    for a in (w.get("authorships") or [])[:8] if a.get("author")],
        "abstract": unabstract(w.get("abstract_inverted_index")),
        "pdf_url": oa.get("pdf_url"),
        "landing": loc.get("landing_page_url"),
    }


def main():
    seeds = load_records(os.path.join(OUT, "seeds.json"))
    back = collections.Counter()
    back_seeds = collections.defaultdict(set)
    fwd = collections.Counter()
    fwd_seeds = collections.defaultdict(set)
    meta = {}
    seedmap = {}

    for rec in seeds:
        key = rec.raw.get("seed_key")
        w = find_work(rec)
        if not w:
            log(f"NO-OA  {key}  {(rec.title or '')[:55]}")
            continue
        oaid = w["id"].rsplit("/", 1)[-1]
        seedmap[key] = {"oa_id": oaid, "title": w.get("display_name"),
                        "refs": len(w.get("referenced_works") or []),
                        "cited_by": w.get("cited_by_count")}
        refs = w.get("referenced_works") or []
        for r in refs:
            rid = r.rsplit("/", 1)[-1]
            back[rid] += 1
            back_seeds[rid].add(key)

        # forward citers
        n = 0
        cursor = "*"
        while cursor and n < 300:
            d = get(f"{API}/works?filter=cites:{oaid}&select={SEL}"
                    f"&per-page=100&cursor={urllib.parse.quote(cursor)}&mailto={MAILTO}")
            for c in d.get("results", []):
                cid = c["id"].rsplit("/", 1)[-1]
                fwd[cid] += 1
                fwd_seeds[cid].add(key)
                meta.setdefault(cid, slim(c))
                n += 1
            cursor = (d.get("meta") or {}).get("next_cursor")
            time.sleep(0.3)
        log(f"seed {key:<26} refs={len(refs):<4} citers={n}")
        time.sleep(0.3)

    # hydrate backward refs cited by >=2 seeds (the ones that matter)
    want = [k for k, v in back.items() if v >= 2 and k not in meta]
    log(f"hydrating {len(want)} backward refs cited by >=2 seeds")
    for w in batch_works(want):
        meta[w["id"].rsplit("/", 1)[-1]] = slim(w)

    rows = []
    for oid in set(back) | set(fwd):
        m = meta.get(oid)
        if not m:
            continue
        rows.append({
            **m, "oaid_short": oid,
            "back_count": back.get(oid, 0), "fwd_count": fwd.get(oid, 0),
            "back_seeds": sorted(back_seeds.get(oid, [])),
            "fwd_seeds": sorted(fwd_seeds.get(oid, [])),
            "dual_signal": bool(back.get(oid) and fwd.get(oid)),
        })
    rows.sort(key=lambda r: (-(r["back_count"] + r["fwd_count"]), -(r["cited_by"] or 0)))

    json.dump({"seedmap": seedmap, "rows": rows},
              open(os.path.join(OUT, "b3_expansion.json"), "w"), indent=2)

    log(f"\nB.3 done: {len(seedmap)}/12 seeds resolved on OpenAlex")
    log(f"  backward refs seen: {len(back)} unique; >=2 seeds: {sum(1 for v in back.values() if v>=2)}; "
        f">=3 seeds: {sum(1 for v in back.values() if v>=3)}")
    log(f"  forward citers: {len(fwd)} unique; >=2 seeds: {sum(1 for v in fwd.values() if v>=2)}")
    log(f"  dual-signal: {sum(1 for r in rows if r['dual_signal'])}")
    print("\n--- top 40 expansion candidates ---")
    for r in rows[:40]:
        print(f'  b={r["back_count"]} f={r["fwd_count"]} {"D" if r["dual_signal"] else " "} '
              f'{r["year"]} c={r["cited_by"] or 0:>4} {(r["title"] or "")[:76]}')


if __name__ == "__main__":
    main()
