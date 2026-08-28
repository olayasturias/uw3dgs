import sys, os, re
SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
lane = sys.argv[1] if len(sys.argv) > 1 else "core"
recs = [r for r in load_records(os.path.join(OUT, "pool_b2.json"))
        if r.raw.get("lane") == lane]
recs.sort(key=lambda r: (-(r.citation_count or 0), -(r.year or 0)))
print(f"lane={lane}  n={len(recs)}\n")
for r in recs:
    src = "".join(sorted({p.source[0] for p in r.source_provenance}))
    code = "C" if r.raw.get("code_urls") else "-"
    ax = r.arxiv_id or ""
    print(f'{r.year} c={r.citation_count or 0:>4} {src:<3} {code} {ax:<12} {(r.title or "")[:88]}')
