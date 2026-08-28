"""Resolve the 12 approved seeds to canonical records + fetch their PDFs."""
import os, re, sys, json, time, urllib.request, urllib.error

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records, serialize_records  # noqa
import arxiv_search  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
PDFS = os.path.join(os.path.dirname(OUT), "pdfs")
os.makedirs(PDFS, exist_ok=True)
_m = os.environ.get("SOTA_REPORT_MAILTO", "")
UA = {"User-Agent": "Mozilla/5.0 (sota-report/0.4"
                    + (f"; {_m}" if _m else "") + ")"}

# (bibtex_key, title fragment to match in pool, fallback arxiv id)
SEEDS = [
    ("li2024watersplatting",   "WaterSplatting: Fast Underwater 3D Scene Reconstruction",       "2408.08206"),
    ("yang2024seasplat",       "SeaSplat: Representing Underwater Scenes",                      "2409.17345"),
    ("wang2024uwgs",           "UW-GS: Distractor-Aware 3D Gaussian Splatting",                 "2410.01517"),
    ("zhang2024recgs",         "RecGS: Removing Water Caustic",                                 "2407.10318"),
    ("li2024gaussiansplashing","Gaussian Splashing: Direct Volumetric Rendering Underwater",    "2411.19588"),
    ("liu2024aquaticgs",       "Aquatic-GS: A Hybrid 3D Representation",                        "2411.00239"),
    ("zhang2024bayesian",      "Bayesian uncertainty analysis for underwater 3D reconstruction","2407.08154"),
    ("levy2023seathrunerf",    "SeaThru-NeRF: Neural Radiance Fields in Scattering Media",      "2304.07743"),
    ("chen2026review",         "Visual enhancement and 3D representation for underwater scenes","2505.01869"),
    ("yu2025dehazegs",         "DehazeGS: Seeing Through Fog with 3D Gaussian Splatting",       "2501.03659"),
    ("song2024refractivecolmap","Refractive COLMAP: Refractive Structure-from-Motion",          "2403.08640"),
    ("wang2026swimm3r",        "Swimm3R: Splatting with Medium-aware SfM",                      "2608.00950"),
]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch_pdf(url, dest, timeout=60):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if not data.startswith(b"%PDF"):
            return False, f"not-a-pdf ({data[:16]!r})"
        with open(dest, "wb") as f:
            f.write(data)
        return True, f"{len(data)//1024} KB"
    except urllib.error.HTTPError as e:
        return False, f"http-{e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}"


def main():
    pool = load_records(os.path.join(OUT, "pool_b2b.json"))
    idx = {norm(r.title): r for r in pool}

    resolved, results = [], []
    for key, frag, axid in SEEDS:
        nf = norm(frag)
        rec = next((r for k, r in idx.items() if nf in k or k in nf), None)
        if rec is None:
            # not in pool (e.g. SeaThru-NeRF was merged, or title drifted) -> arXiv
            hits = arxiv_search.search(frag, max_results=3)
            rec = hits[0] if hits else None
            time.sleep(3.2)
        if rec is None:
            log(f"UNRESOLVED {key}  ({frag[:50]})")
            results.append({"key": key, "status": "unresolved"})
            continue

        aid = rec.arxiv_id or axid
        rec.raw = dict(rec.raw or {})
        rec.raw.update({"seed_key": key, "is_seed": True})
        if not rec.arxiv_id and axid:
            rec.arxiv_id = axid
        resolved.append(rec)

        dest = os.path.join(PDFS, f"{key}.pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 20000:
            log(f"CACHED     {key:<26} {os.path.getsize(dest)//1024} KB")
            results.append({"key": key, "status": "cached", "path": dest,
                            "title": rec.title, "arxiv": aid})
            continue

        ok, detail = (False, "no-arxiv-id")
        tried = []
        if aid:
            for u in (f"https://arxiv.org/pdf/{aid}", f"https://arxiv.org/pdf/{aid}v1"):
                ok, detail = fetch_pdf(u, dest)
                tried.append(f"{u.rsplit('/',1)[-1]}:{detail}")
                if ok:
                    break
                time.sleep(2)
        if not ok and rec.pdf_url:
            ok, detail = fetch_pdf(rec.pdf_url, dest)
            tried.append(f"oa:{detail}")
        log(f'{"OK  " if ok else "FAIL"}       {key:<26} {detail:<12} {(rec.title or "")[:52]}')
        results.append({"key": key, "status": "ok" if ok else "fail",
                        "detail": detail, "tried": tried, "path": dest if ok else None,
                        "title": rec.title, "arxiv": aid, "year": rec.year})
        time.sleep(1.5)

    serialize_records(resolved, os.path.join(OUT, "seeds.json"))
    json.dump(results, open(os.path.join(OUT, "seed_fetch.json"), "w"), indent=2)
    got = sum(1 for r in results if r["status"] in ("ok", "cached"))
    log(f"seeds resolved={len(resolved)}/12  pdfs={got}/12")


if __name__ == "__main__":
    main()
