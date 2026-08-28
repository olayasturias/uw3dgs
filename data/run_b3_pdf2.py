"""B.3 Tier-0 bulk, v2 -- key references on arXiv-ID / DOI, not on regex-guessed
titles.

v1 tried to carve a title out of each reference string with regexes and produced
author fragments ("Derya Akkaynak and Tali Treibitz") as its top co-cited
"papers". Open-ended title extraction from reference prose is not reliably
regexable across the layouts in this corpus.

v2 uses identifiers that cannot be misparsed -- arXiv IDs and DOIs -- as the
primary key, and for entries carrying neither, matches the entry text against a
KNOWN vocabulary of titles (everything the B.1 search surfaced, 2694 records)
by normalized substring containment. Matching against a closed vocabulary is
robust where extraction is not.
"""
import os, re, sys, json, glob, collections, unicodedata
import fitz

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))
PDFS = os.path.join(os.path.dirname(OUT), "pdfs")

HEAD_RE = re.compile(r"^\s*(?:\d+\s*\.?\s*)?(references|bibliography|reference list)\s*:?\s*$", re.I)
# A marker may be followed by the entry on the same line, OR sit alone on its own
# line with the entry starting on the next (IEEE two-column style -- RecGS does
# this, and requiring same-line text yielded 0 entries for it).
MARK_RE = re.compile(r"^\s*(?:\[(\d{1,3})\]|\((\d{1,3})\)|(\d{1,3})\.)(?:\s+|\s*$)")
BIB_START_RE = re.compile(r"^\s*(?:\[1\]|\(1\)|1\.)(?:\s|$)")
ARXIV_RE = re.compile(r"(?:arxiv[:\s]*|abs/)(\d{4}\.\d{4,5})", re.I)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def norm_ws(s):
    s = unicodedata.normalize("NFKD", s).replace("\u00ad", "")
    for a, b in (("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff"), ("’", "'"), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def tkey(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def find_ref_block(pages):
    for pi in range(len(pages) - 1, -1, -1):
        lines = pages[pi].splitlines()
        for li, ln in enumerate(lines):
            if HEAD_RE.match(norm_ws(ln)):
                return "\n".join(["\n".join(lines[li + 1:])] + pages[pi + 1:])
    # fallback 1: REFERENCES set inline / letter-spaced inside a column
    for pi in range(len(pages) - 1, -1, -1):
        m = re.search(r"\bR\s?E\s?F\s?E\s?R\s?E\s?N\s?C\s?E\s?S\b", pages[pi])
        if m:
            return "\n".join([pages[pi][m.end():]] + pages[pi + 1:])
    # fallback 2: no heading survived extraction -- find where the numbered
    # bibliography itself begins ("[1]" on its own line, late in the document)
    for pi in range(len(pages) - 1, max(len(pages) - 6, -1), -1):
        lines = pages[pi].splitlines()
        for li, ln in enumerate(lines):
            if BIB_START_RE.match(ln) and sum(
                    1 for x in lines[li:] if MARK_RE.match(x)) >= 4:
                return "\n".join(["\n".join(lines[li:])] + pages[pi + 1:])
    return ""


def split_entries(block):
    lines = block.splitlines()
    # Decide the style BEFORE splitting. A single stray "15." (a page number, a
    # section cross-reference) is not evidence of a numbered bibliography -- it
    # previously flipped DehazeGS's author-year reference list into the numbered
    # branch and discarded all 38 of its entries.
    marks = [i for i, ln in enumerate(lines) if MARK_RE.match(ln)]
    numbered = len(marks) >= 5

    if numbered:
        entries, cur = [], []
        for i, ln in enumerate(lines):
            if i in set(marks):
                if cur:
                    entries.append(norm_ws(" ".join(cur)))
                cur = [MARK_RE.sub("", ln)]
            elif cur:
                cur.append(ln)
        if cur:
            entries.append(norm_ws(" ".join(cur)))
    else:
        # author-year style: a new entry starts at "Surname, X." at line start
        entries = [norm_ws(c) for c in
                   re.split(r"\n(?=[A-Z][A-Za-z\-'À-ɏ]+,\s*[A-Z]\.)", block)]
    return [e for e in entries if 25 < len(e) < 900]


def main():
    # closed vocabulary: every title B.1 surfaced (pre-gate), plus seeds
    # Substring matching against a closed vocabulary needs the vocabulary entries
    # to be distinctive. Short/generic titles ("Artificial Intelligence", "Neural
    # Information Processing") are substrings of dozens of unrelated reference
    # strings -- they were the #5 and #9 "co-cited papers" before this filter.
    def distinctive(title):
        k = tkey(title)
        words = re.findall(r"[A-Za-z][a-z]+", title or "")
        return len(k) >= 30 and len(words) >= 4

    vocab = {}
    for f in ("pool_b2b.json",):
        for r in load_records(os.path.join(OUT, f)):
            if distinctive(r.title):
                vocab[tkey(r.title)] = r.title
    import glob as _g
    for f in _g.glob(os.path.join(OUT, "raw_*.json")):
        for r in load_records(f):
            if distinctive(r.title):
                vocab.setdefault(tkey(r.title), r.title)
    print(f"closed title vocabulary: {len(vocab)} (distinctive titles only)")

    # audit vocabulary: terms that mark a reference as topically relevant, used to
    # flag UNMATCHED reference entries -- those are papers the B.1 search missed.
    AUDIT_RE = re.compile(r"underwater|subsea|seafloor|benthic|submerged|turbid|"
                          r"gaussian splat|3d gaussian|radiance field|scattering|"
                          r"backscatter|caustic|sea-?thru|dehaz|\bhaze\b", re.I)
    missed = collections.Counter()

    tally = collections.Counter()
    seeds_of = collections.defaultdict(set)
    label, kind, arxiv_of = {}, {}, {}
    per_seed = {}

    for path in sorted(glob.glob(os.path.join(PDFS, "*.pdf"))):
        sk = os.path.basename(path)[:-4]
        doc = fitz.open(path)
        pages = [p.get_text("text") for p in doc]
        doc.close()
        block = find_ref_block(pages)
        entries = split_entries(block) if block else []

        hits = {"arxiv": 0, "doi": 0, "vocab": 0, "unmatched": 0}
        for e in entries:
            ks = set()
            for m in ARXIV_RE.finditer(e):
                k = "arxiv:" + m.group(1)
                ks.add(k); kind[k] = "arxiv"; label.setdefault(k, k)
                arxiv_of[k] = m.group(1)
            if not ks:
                for m in DOI_RE.finditer(e):
                    k = "doi:" + m.group(0).rstrip(".,;").lower()
                    ks.add(k); kind[k] = "doi"; label.setdefault(k, k)
            ek = tkey(e)
            for vk, vt in vocab.items():
                if vk in ek:
                    k = "title:" + vk
                    ks.add(k); kind[k] = "title"; label[k] = vt
            if not ks:
                hits["unmatched"] += 1
                if AUDIT_RE.search(e):
                    missed[norm_ws(e)[:170]] += 1
                continue
            for k in ks:
                tally[k] += 1
                seeds_of[k].add(sk)
                hits[kind[k] if kind[k] != "title" else "vocab"] += 1

        per_seed[sk] = {"pages": len(pages), "entries": len(entries), **hits}
        print(f'{sk:<28} entries={len(entries):>4} arxiv={hits["arxiv"]:>3} '
              f'doi={hits["doi"]:>3} vocab={hits["vocab"]:>3} miss={hits["unmatched"]:>3}')

    rows = [{"key": k, "label": label.get(k, k), "kind": kind.get(k),
             "n_seeds": len(seeds_of[k]), "n_cites": n,
             "seeds": sorted(seeds_of[k]), "arxiv": arxiv_of.get(k)}
            for k, n in tally.items()]
    rows.sort(key=lambda r: (-r["n_seeds"], -r["n_cites"]))
    json.dump({"per_seed": per_seed, "rows": rows,
               "unmatched_topical": missed.most_common()},
              open(os.path.join(OUT, "b3_cocitation.json"), "w"), indent=2)

    print(f"\nunique cited works: {len(rows)}")
    for th in (2, 3, 4, 5, 6, 7):
        print(f"  cited by >={th} seeds: {sum(1 for r in rows if r['n_seeds']>=th)}")
    print("\n--- cited by >=3 seeds ---")
    for r in rows:
        if r["n_seeds"] >= 3:
            print(f'  {r["n_seeds"]}x [{r["kind"]:<5}] {r["label"][:88]}')

    print(f"\n--- B.1 COVERAGE AUDIT: topical refs matched by nothing ({len(missed)}) ---")
    for e, n in missed.most_common(30):
        print(f"  {n}x  {e[:150]}")


if __name__ == "__main__":
    main()
