"""B.5 helper -- condense each working-set PDF into the fields the synthesis needs.

references/text_analysis_policy.md puts assistant `Read` on the PDF first and
PyMuPDF text second, with the text path reserved for bulk work. A ~50-paper
working set at 8-30 pages each is bulk: rendering every page as an image to read
visually would cost more context than the whole synthesis. So this script pulls
targeted regions -- abstract, section headers, method opening, evaluation
sentences, limitation sentences, metric-bearing lines -- and the assistant reads
the condensed digest instead. Papers whose digest looks thin get a full visual
`Read` pass individually.
"""
import os, re, sys, json, glob, unicodedata
import fitz

OUT = os.path.dirname(os.path.abspath(__file__))
PDFS = os.path.join(os.path.dirname(OUT), "pdfs")

HDR_RE = re.compile(
    r"^\s*(?:(?:[IVXLC]+|\d+)[.\)]?\s*)?"
    r"(abstract|introduction|related work|background|preliminaries|method(?:s|ology)?|"
    r"approach|our method|proposed method|experiments?|experimental setup|"
    r"evaluation|results|ablation|discussion|limitations?|conclusions?|"
    r"implementation details|datasets?)\b\s*:?\s*$", re.I)

METRIC_RE = re.compile(r"\b(PSNR|SSIM|LPIPS|RMSE|MAE|Chamfer|F1|IoU|FPS|UIQM|UCIQE|"
                       r"AbsRel|delta1|δ1)\b", re.I)
DATASET_RE = re.compile(
    r"\b(SeaThru-?NeRF|SeaThru|UIEB|EUVP|LSUI|SQUID|Atlantis|FLSea|VAROS|"
    r"USOD|RUIE|UWBundle|Tank dataset|Neural[- ]Sea|Mip-?NeRF ?360|LLFF|"
    r"Tanks and Temples|DeepFish|CoralNet|HoloOcean|UNav-?Sim|Aqualoc|"
    r"SubPipe|MIMIR|Eiffel Tower|Kelp|Curacao|Panama|IUI3|Red ?Sea)\b", re.I)
LIMIT_RE = re.compile(
    r"\b(limitation|fails? to|cannot|do(?:es)? not (?:handle|generalize|account)|"
    r"struggles?|remains? (?:an )?open|future work|is limited to|assumes? that|"
    r"we do not|drawback|bottleneck)\b", re.I)
CODE_RE = re.compile(r"(?:github\.com|gitlab\.com)/[\w.\-]+/[\w.\-]+", re.I)


def norm(s):
    s = unicodedata.normalize("NFKD", s).replace("­", "")
    for a, b in (("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff"), ("’", "'")):
        s = s.replace(a, b)
    return re.sub(r"[ \t]+", " ", s)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text) if 30 < len(s.strip()) < 420]


def digest(path, max_pages=40):
    d = fitz.open(path)
    n = min(len(d), max_pages)
    pages = [norm(d[i].get_text("text")) for i in range(n)]
    total_pages = len(d)
    d.close()
    full = "\n".join(pages)

    headers = []
    for p in pages:
        for ln in p.splitlines():
            m = HDR_RE.match(ln.strip())
            if m:
                h = m.group(1).lower()
                if not headers or headers[-1] != h:
                    headers.append(h)

    # abstract: text between "Abstract" and the next header / "Introduction"
    abstract = ""
    m = re.search(r"\bAbstract\b[\s:—-]*(.{200,2600}?)(?=\n\s*(?:\d+\.?\s*)?"
                  r"(?:Introduction|I\.\s|Keywords|Index Terms)\b)", full, re.S | re.I)
    if m:
        abstract = re.sub(r"\s+", " ", m.group(1)).strip()
    if not abstract:
        abstract = re.sub(r"\s+", " ", pages[0])[:1600]

    sents = sentences(re.sub(r"\s+", " ", full))
    limits = [s for s in sents if LIMIT_RE.search(s)][:8]
    metrics = [s for s in sents if METRIC_RE.search(s)][:8]
    datasets = sorted({m.group(0) for m in DATASET_RE.finditer(full)})
    codes = sorted({("https://" + c) for c in CODE_RE.findall(full)})

    # method opening: first ~1200 chars after a method-ish header
    method = ""
    mm = re.search(r"\n\s*(?:(?:[IVX]+|\d+)[.\)]?\s*)?"
                   r"(?:Method(?:s|ology)?|Approach|Our Method|Proposed Method)\b[^\n]*\n",
                   full, re.I)
    if mm:
        method = re.sub(r"\s+", " ", full[mm.end():mm.end() + 1800]).strip()

    return {
        "pages": total_pages, "headers": headers[:24],
        "abstract": abstract[:2400], "method_opening": method[:1800],
        "limitation_sentences": limits, "metric_sentences": metrics,
        "datasets_mentioned": datasets, "code_urls": codes,
        "chars": len(full),
    }


def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(glob.glob(os.path.join(PDFS, "*.pdf")))
    if sel:
        keys = set(json.load(open(sel)))
        files = [f for f in files if os.path.basename(f)[:-4] in keys]
    out = {}
    for p in files:
        k = os.path.basename(p)[:-4]
        try:
            out[k] = digest(p)
            d = out[k]
            print(f'{k:<52} pg={d["pages"]:>3} hdrs={len(d["headers"]):>2} '
                  f'abs={len(d["abstract"]):>4} meth={len(d["method_opening"]):>4} '
                  f'lim={len(d["limitation_sentences"])} ds={len(d["datasets_mentioned"])}')
        except Exception as e:
            print(f"{k:<52} FAIL {type(e).__name__}: {e}")
    json.dump(out, open(os.path.join(OUT, "digests.json"), "w"), indent=2)
    print(f"\nwrote digests for {len(out)} papers")


if __name__ == "__main__":
    main()
