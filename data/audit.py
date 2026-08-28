"""B.7.6 -- pre-commit sanity audit. Blocks the bundle if any check fails."""
import os, re, sys, csv, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails, warns = [], []


def check(name, ok, detail=""):
    (fails if not ok else warns if detail.startswith("WARN") else []).append(
        f"{name}: {detail}") if (not ok or detail.startswith("WARN")) else None
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


report = open(os.path.join(ROOT, "REPORT.md"), encoding="utf-8").read()
man = json.load(open(os.path.join(ROOT, "MANIFEST.json"), encoding="utf-8"))
bib = open(os.path.join(ROOT, "references.bib"), encoding="utf-8").read()
rows = list(csv.DictReader(open(os.path.join(ROOT, "papers_table.csv"), encoding="utf-8")))

print("B.7.6 sanity audit\n")

# 1 — anchors present and correctly flagged
anchors = [p for p in man["papers"] if p["out_of_window_anchor"]]
check("1a anchors present in MANIFEST", len(anchors) == 4, f"{len(anchors)} anchors")

# 2 — no anchor leaked into the method set or the comparison matrices
leaked = [p for p in anchors if p["set"] == "method"]
check("1b no anchor in method set", not leaked, f"leaked: {[p['bibkey'] for p in leaked]}")
matrix = report.split("### 11.2")[1].split("### 11.3")[0] if "### 11.2" in report else ""
anchor_titles = ["Sea-Thru", "Revised Underwater Image Formation", "SeaThru-NeRF:"]
in_matrix = [t for t in anchor_titles if re.search(r"^\|\s*\*\*[^|]*" + re.escape(t),
                                                   matrix, re.M)]
check("1c no anchor row in §11.2 matrix", not in_matrix, f"found: {in_matrix}")

# 3 — every [@key] in REPORT.md resolves in references.bib
cites = set(re.findall(r"\[@([A-Za-z0-9_\-]+)\]", report))
bibkeys = set(re.findall(r"@\w+\{([^,]+),", bib))
missing = sorted(cites - bibkeys)
check("2 citations resolve in references.bib", not missing,
      f"unresolved: {missing}" if missing else f"{len(cites)} cite keys, {len(bibkeys)} bib entries")

# 4 — every figure referenced by REPORT.md exists on disk
figs = re.findall(r"\]\((figures/[^)]+)\)", report)
absent = [f for f in figs if not os.path.exists(os.path.join(ROOT, f))]
check("3 figure files exist", not absent, f"{len(figs)} refs; missing: {absent}")

# 5 — every manifest paper has a bib entry and vice versa
mankeys = {p["bibkey"] for p in man["papers"]}
check("4a manifest ⊆ bib", not (mankeys - bibkeys), f"{len(mankeys - bibkeys)} missing")
check("4b bib ⊆ manifest", not (bibkeys - mankeys), f"{len(bibkeys - mankeys)} extra")

# 6 — csv and manifest agree
csvkeys = {r["bibkey"] for r in rows}
check("4c csv == manifest", csvkeys == mankeys,
      f"csv={len(csvkeys)} manifest={len(mankeys)}")

# 7 — every method-set paper actually has a repo URL
nourl = [r["bibkey"] for r in rows if r["set"] == "method" and not r["repo_url"]]
check("5 method set all have repo URLs", not nourl, f"{nourl}")

# 8 — section anchors declared in REPORT.md are unique
decl = re.findall(r"\{#([a-z0-9\-]+)\}", report)
check("6 section anchors unique", len(decl) == len(set(decl)),
      f"{len(decl)} anchors: {decl}")

# 9 — internal §-references point at sections that exist, at BOTH levels.
# The first version only checked top-level numbers, so "§4.4" passed because
# §4 exists — while §4 actually stops at 4.3 (the refraction discussion is §7.4).
secnums = set(re.findall(r"^## (\d+)\.", report, re.M))
subnums = set(re.findall(r"^### (\d+\.\d+)", report, re.M))
refs = set(re.findall(r"§(\d+(?:\.\d+)?)", report))
bad = sorted(r for r in refs
             if ("." in r and r not in subnums) or ("." not in r and r not in secnums))
check("7 internal section refs valid", not bad,
      f"dangling: {bad}" if bad else f"{len(refs)} refs, all resolve")

# 10 — extraction populated for method set
digests = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "digests.json"), encoding="utf-8"))
nopdf = [r["bibkey"] for r in rows if r["set"] == "method" and r["pdf_fetched"] == "no"]
print(f"  [INFO] method-set papers without a fetched PDF: {len(nopdf)} {nopdf}")

print()
if fails:
    print("AUDIT FAILED:")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("AUDIT PASSED")
