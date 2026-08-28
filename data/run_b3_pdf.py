"""B.3 Tier-0 (bulk half) -- parse reference lists straight out of the seed PDFs.

OpenAlex returned referenced_works=0 for 10/12 seeds (no Crossref-deposited
reference lists for arXiv preprints), so the citation graph has to be recovered
from the papers themselves. This is the bulk/structured half of Tier 0 and runs
through PyMuPDF per references/text_analysis_policy.md; the sentiment half is a
separate targeted `Read` pass over related-work prose.
"""
import os, re, sys, json, glob, collections, unicodedata

import fitz  # PyMuPDF

OUT = os.path.dirname(os.path.abspath(__file__))
PDFS = os.path.join(os.path.dirname(OUT), "pdfs")

HEAD_RE = re.compile(r"^\s*(?:\d+\s*\.?\s*)?(references|bibliography|reference list)\s*$", re.I)
# a numbered-entry marker: [12]  or  12.  at line start
MARK_RE = re.compile(r"^\s*(?:\[(\d{1,3})\]|\((\d{1,3})\)|(\d{1,3})\.)\s+")
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")
ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})", re.I)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)


def norm_ws(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", s).strip()


def get_text(path):
    doc = fitz.open(path)
    pages = [p.get_text("text") for p in doc]
    doc.close()
    return pages


def find_ref_block(pages):
    """Return the raw text of the reference section, searching from the back."""
    joined = []
    start_pg, start_ln = None, None
    for pi in range(len(pages) - 1, -1, -1):
        lines = pages[pi].splitlines()
        for li, ln in enumerate(lines):
            if HEAD_RE.match(norm_ws(ln)):
                start_pg, start_ln = pi, li
                break
        if start_pg is not None:
            break
    if start_pg is None:
        return ""
    joined.append("\n".join(pages[start_pg].splitlines()[start_ln + 1:]))
    for pi in range(start_pg + 1, len(pages)):
        joined.append(pages[pi])
    return "\n".join(joined)


def split_entries(block):
    """Split a reference block into individual entries on [N] / N. markers."""
    lines = block.splitlines()
    entries, cur, seen_any = [], [], False
    for ln in lines:
        if MARK_RE.match(ln):
            seen_any = True
            if cur:
                entries.append(norm_ws(" ".join(cur)))
            cur = [MARK_RE.sub("", ln)]
        elif cur:
            cur.append(ln)
    if cur:
        entries.append(norm_ws(" ".join(cur)))
    if not seen_any:
        # unnumbered (author-year) style: split on blank-ish boundaries
        chunks = re.split(r"\n(?=[A-Z][A-Za-z\-']+,\s)", block)
        entries = [norm_ws(c) for c in chunks if len(norm_ws(c)) > 40]
    return [e for e in entries if 25 < len(e) < 700]


def entry_title(e):
    """Best-effort title extraction from a reference string."""
    s = re.sub(r"^\s*(?:\[\d+\]|\(\d+\))\s*", "", e)
    s = ARXIV_RE.sub(" ", s)
    s = re.sub(r"\bdoi:\s*\S+", " ", s, flags=re.I)
    # drop a leading author block: sequences of "X. Surname," / "Surname, X.,"
    s = re.sub(r"^(?:[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][A-Za-z\-']+,?\s*(?:and\s+)?){1,14}", "", s)
    s = re.sub(r"^(?:[A-Z][A-Za-z\-']+,\s*[A-Z]\.(?:\s*[A-Z]\.)?,?\s*(?:and\s+)?){1,14}", "", s)
    s = re.sub(r"^[^A-Za-z]*", "", s)
    # title usually ends at the first period followed by a capitalised venue/In
    m = re.match(r"(.{12,180}?)[\.\?](?=\s+(?:In\b|Proc|IEEE|ACM|arXiv|Adv|Conf|Journal|"
                 r"Trans|Comput|Int\b|Springer|CVPR|ICCV|ECCV|NeurIPS|SIGGRAPH|\d{4}|[A-Z]))", s)
    t = (m.group(1) if m else s[:150]).strip(" .,;:")
    t = re.sub(r"\s+", " ", t)
    return t if len(t) >= 12 else None


def key(t):
    t = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def main():
    seed_meta = {r["key"]: r for r in json.load(open(os.path.join(OUT, "seed_fetch.json")))}
    tally = collections.Counter()
    bykey = collections.defaultdict(set)
    display = {}
    arxiv_of = {}
    per_seed = {}

    for path in sorted(glob.glob(os.path.join(PDFS, "*.pdf"))):
        sk = os.path.basename(path)[:-4]
        try:
            pages = get_text(path)
        except Exception as e:
            print(f"  PDF FAIL {sk}: {e}"); continue
        block = find_ref_block(pages)
        entries = split_entries(block) if block else []
        titles = []
        for e in entries:
            t = entry_title(e)
            if not t:
                continue
            k = key(t)
            if len(k.split()) < 3:
                continue
            titles.append(t)
            tally[k] += 1
            bykey[k].add(sk)
            display.setdefault(k, t)
            m = ARXIV_RE.search(e)
            if m:
                arxiv_of.setdefault(k, m.group(1))
        per_seed[sk] = {"pages": len(pages), "ref_block_chars": len(block),
                        "entries": len(entries), "titles": len(titles)}
        print(f"{sk:<28} pages={len(pages):>3} entries={len(entries):>4} titles={len(titles):>4}")

    rows = []
    for k, n in tally.items():
        rows.append({"key": k, "title": display[k], "n_seeds": n,
                     "seeds": sorted(bykey[k]), "arxiv": arxiv_of.get(k)})
    rows.sort(key=lambda r: -r["n_seeds"])

    json.dump({"per_seed": per_seed, "rows": rows},
              open(os.path.join(OUT, "b3_pdf_cocitation.json"), "w"), indent=2)

    tot = len(rows)
    print(f"\nunique cited titles: {tot}")
    for th in (2, 3, 4, 5, 6):
        print(f"  cited by >={th} seeds: {sum(1 for r in rows if r['n_seeds']>=th)}")
    print("\n--- cited by >=4 seeds ---")
    for r in rows:
        if r["n_seeds"] >= 4:
            print(f'  {r["n_seeds"]}x  {r["title"][:92]}')


if __name__ == "__main__":
    main()
