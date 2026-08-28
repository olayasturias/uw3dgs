"""B.1 multi-source search driver: arXiv (boolean) + OpenAlex, 8 branches.

The skill's arxiv_search.search() wraps every query as all:"<phrase>" (exact
phrase only), which is too tight for this topic -- "Gaussian splatting for
underwater scenes" would not match all:"underwater gaussian splatting".
So arXiv is driven here with a proper boolean search_query. OpenAlex uses the
skill's module unchanged.
"""
import sys, os, time, json, urllib.request, urllib.parse, re
from datetime import date

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)

from canonical_record import CanonicalRecord, Provenance, make_canonical_id, serialize_records  # noqa
import openalex  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_GAP = 3.1   # arXiv asks for >=3s between calls
NS = {"a": "http://www.w3.org/2005/Atom"}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- arXiv ----
def arxiv_boolean(search_query, max_results=100, timeout=45):
    import xml.etree.ElementTree as ET
    params = urllib.parse.urlencode({
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "sota-report/0.4 (oat@eiva.com)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        root = ET.fromstring(r.read())

    recs = []
    for rank, e in enumerate(root.findall("a:entry", NS)):
        aid_url = e.findtext("a:id", "", NS)
        m = re.search(r"abs/([^v]+)v?(\d*)", aid_url)
        if not m:
            continue
        arxiv_id = m.group(1)
        title = " ".join((e.findtext("a:title", "", NS) or "").split())
        summary = " ".join((e.findtext("a:summary", "", NS) or "").split())
        pub = e.findtext("a:published", "", NS)
        year = int(pub[:4]) if pub[:4].isdigit() else None
        authors = []
        for a in e.findall("a:author", NS):
            n = (a.findtext("a:name", "", NS) or "").strip()
            if not n:
                continue
            parts = n.split()
            authors.append(f"{parts[-1]}, {' '.join(p[0] + '.' for p in parts[:-1])}" if len(parts) > 1 else n)
        doi = e.findtext("{http://arxiv.org/schemas/atom}doi", None, NS)
        cats = [c.get("term") for c in e.findall("a:category", NS)]
        recs.append(CanonicalRecord(
            canonical_id=make_canonical_id(doi=doi, arxiv_id=arxiv_id, title=title,
                                           first_author=authors[0] if authors else None, year=year),
            title=title, authors=authors, year=year,
            venue="arXiv", abstract=summary, doi=doi, arxiv_id=arxiv_id,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf", is_open_access=True,
            concepts=cats, paper_type="preprint",
            source_provenance=[Provenance(source="arxiv", query=search_query, rank=rank)],
            raw={"published": pub},
        ))
    return recs


# ------------------------------------------------------------- branches ----
GS = '(abs:"Gaussian Splatting" OR abs:"Gaussian splatting" OR abs:"3D Gaussian" OR abs:"Gaussian Splats")'
UW = '(abs:underwater OR abs:subsea OR abs:seafloor OR abs:benthic OR abs:marine OR abs:aquatic OR abs:submerged)'

BRANCHES = {
    "b1_underwater_native_3dgs": {
        "arxiv": [
            f'{GS} AND {UW}',
            f'{GS} AND (abs:"scattering medium" OR abs:turbid OR abs:turbidity) AND (abs:water OR abs:underwater)',
            'abs:"underwater" AND (abs:"novel view synthesis" OR abs:"radiance field")',
        ],
        "openalex": [
            '"gaussian splatting" AND underwater',
            '("gaussian splatting" OR "3d gaussian") AND (subsea OR seafloor OR benthic OR marine)',
            'underwater AND ("novel view synthesis" OR "radiance field")',
        ],
    },
    "b2_image_formation_restoration": {
        "arxiv": [
            'abs:"underwater image formation" AND (abs:"radiance field" OR abs:"Gaussian Splatting" OR abs:"3D reconstruction")',
            '(abs:backscatter OR abs:"veiling light" OR abs:attenuation) AND (abs:"novel view synthesis" OR abs:"neural rendering" OR abs:"Gaussian Splatting")',
            'abs:"underwater image restoration" AND (abs:"3D" OR abs:depth OR abs:geometry)',
        ],
        "openalex": [
            'underwater AND (backscatter OR attenuation OR "veiling light") AND (rendering OR "radiance field" OR "gaussian splatting")',
            '"underwater image formation model"',
            '"underwater image restoration" AND ("3d reconstruction" OR depth)',
        ],
    },
    "b3_scattering_media_transfer": {
        "arxiv": [
            f'{GS} AND (abs:"participating media" OR abs:"scattering media" OR abs:"scattering medium")',
            f'{GS} AND (abs:fog OR abs:haze OR abs:dehazing OR abs:smoke OR abs:"volumetric scattering")',
            '(abs:"radiance field" OR abs:NeRF) AND (abs:"participating media" OR abs:dehazing OR abs:fog)',
        ],
        "openalex": [
            '"gaussian splatting" AND ("participating media" OR "scattering media" OR fog OR haze)',
            '("radiance field" OR nerf) AND (dehazing OR "scattering media")',
        ],
    },
    "b4_pose_and_sfm": {
        "arxiv": [
            'abs:"structure from motion" AND abs:underwater',
            f'{GS} AND (abs:"pose-free" OR abs:"COLMAP-free" OR abs:"unposed" OR abs:"camera pose estimation")',
            f'{GS} AND (abs:DUSt3R OR abs:MASt3R OR abs:VGGT OR abs:"feed-forward 3D")',
            '(abs:underwater OR abs:subsea) AND (abs:"visual odometry" OR abs:"pose estimation") AND (abs:refraction OR abs:turbid OR abs:"low texture")',
        ],
        "openalex": [
            'underwater AND "structure from motion"',
            '"gaussian splatting" AND ("pose-free" OR "colmap-free" OR unposed)',
        ],
    },
    "b5_gs_slam_online": {
        "arxiv": [
            f'{GS} AND abs:SLAM AND {UW}',
            f'{GS} AND abs:SLAM AND (abs:monocular OR abs:"RGB-only" OR abs:"real-time")',
            f'{GS} AND (abs:"incremental mapping" OR abs:"online reconstruction") AND {UW}',
        ],
        "openalex": [
            '"gaussian splatting" AND slam AND (underwater OR marine OR subsea)',
            '"gaussian splatting slam" AND monocular',
        ],
    },
    "b6_nuisance_caustics_snow_dynamic": {
        "arxiv": [
            '(abs:caustics OR abs:"caustic") AND (abs:"Gaussian Splatting" OR abs:"neural rendering" OR abs:"3D reconstruction" OR abs:underwater)',
            'abs:"marine snow" OR (abs:"floating particles" AND abs:underwater)',
            f'{GS} AND (abs:distractor OR abs:transient OR abs:dynamic) AND {UW}',
        ],
        "openalex": [
            'underwater AND (caustics OR "marine snow")',
            '"gaussian splatting" AND underwater AND (dynamic OR distractor OR transient)',
        ],
    },
    "b7_datasets_benchmarks": {
        "arxiv": [
            'abs:underwater AND abs:dataset AND (abs:"3D reconstruction" OR abs:"novel view synthesis" OR abs:photogrammetry)',
            'abs:underwater AND abs:benchmark AND (abs:vision OR abs:reconstruction OR abs:SLAM)',
            '(abs:"coral reef" OR abs:"shipwreck" OR abs:"seafloor mapping") AND (abs:"3D reconstruction" OR abs:"Gaussian Splatting" OR abs:photogrammetry)',
        ],
        "openalex": [
            'underwater AND dataset AND ("3d reconstruction" OR "novel view synthesis")',
            'underwater AND benchmark AND (reconstruction OR slam OR "view synthesis")',
        ],
    },
    "b0_anchors": {
        "arxiv": [
            'ti:"3D Gaussian Splatting for Real-Time Radiance Field Rendering"',
            'ti:"SeaThru-NeRF"',
        ],
        "openalex": [
            '"3d gaussian splatting for real-time radiance field rendering"',
            '"seathru-nerf"',
            '"sea-thru" AND underwater',
        ],
    },
}


def main():
    t0 = time.time()
    summary = {}
    total = 0
    for bname, spec in BRANCHES.items():
        recs = []
        for q in spec["arxiv"]:
            try:
                r = arxiv_boolean(q, max_results=100)
                log(f"B.1 {bname} arxiv  <- {len(r):>3} | {q[:75]}")
                recs += r
            except Exception as e:
                log(f"B.1 {bname} arxiv  !! {type(e).__name__}: {e} | {q[:60]}")
            time.sleep(ARXIV_GAP)
        for q in spec["openalex"]:
            try:
                r = openalex.search(q, limit=200, since=None)
                for i, rec in enumerate(r):
                    rec.source_provenance = [Provenance(source="openalex", query=q, rank=i)]
                log(f"B.1 {bname} oalex  <- {len(r):>3} | {q[:75]}")
                recs += r
            except Exception as e:
                log(f"B.1 {bname} oalex  !! {type(e).__name__}: {e} | {q[:60]}")
            time.sleep(0.4)
        path = os.path.join(OUT, f"raw_{bname}.json")
        serialize_records(recs, path)
        summary[bname] = len(recs)
        total += len(recs)
        log(f"B.1 {bname} DONE: {len(recs)} raw records -> {os.path.basename(path)}  "
            f"(cum {total}, {time.time()-t0:.0f}s)")

    with open(os.path.join(OUT, "b1_summary.json"), "w") as f:
        json.dump({"branches": summary, "total_raw": total,
                   "elapsed_s": round(time.time() - t0, 1)}, f, indent=2)
    log(f"B.1 ALL DONE: {total} raw records across {len(BRANCHES)} branches, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
