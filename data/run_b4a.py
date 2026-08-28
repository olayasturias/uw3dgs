"""B.4a -- seed-similarity topic-relevance gate (pure-python TF-IDF).

Replaces the hand-tuned exclusion list per references/quality_filters.md: build a
TF-IDF centroid from the 12 approved seeds, score every pool paper by cosine
similarity to it, and cut below a threshold chosen from the observed
distribution rather than a magic constant.

Pure python on purpose. sklearn is installed but its numpy ABI chain is broken
in this environment (pandas/bottleneck built against numpy 1.x, runtime is
2.5.1), and a hand-rolled TF-IDF is byte-reproducible across runs, which the
skill's idempotence requirement wants anyway.
"""
import os, re, sys, json, math, collections

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records, serialize_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))

STOP = set("""a an the and or of for to in on with by from as is are was were be been being
this that these those we our it its their his her they them he she you your i at into over
under above below can may might must should would could will shall do does did done have has
had not no nor but if then than so such very more most much many few some any all each both
other another same different new novel using use used uses based approach method methods
results result show shows shown propose proposed proposes present presents presented paper
work works study studies also however thus therefore while during between among within
without via toward towards through across per due given here there when where which who whom
whose what how why about after before again further once only own too s t d et al fig figure
table section""".split())

TOK = re.compile(r"[a-z][a-z0-9\-]{1,}")


def toks(text):
    out = []
    for w in TOK.findall((text or "").lower()):
        w = w.strip("-")
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.append(w)
    # bigrams carry most of the topical signal here ("gaussian splatting",
    # "underwater image", "scattering medium"); unigrams alone conflate
    # "gaussian" in a statistics paper with "gaussian" in a splatting paper.
    return out + [f"{a}_{b}" for a, b in zip(out, out[1:])]


def build_idf(docs):
    df = collections.Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def vec(tokens, idf):
    tf = collections.Counter(tokens)
    if not tf:
        return {}
    mx = max(tf.values())
    v = {t: (0.5 + 0.5 * c / mx) * idf.get(t, 0.0) for t, c in tf.items() if t in idf}
    n = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / n for t, x in v.items()}


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def main():
    pool = load_records(os.path.join(OUT, "pool_b2b.json"))
    seeds = load_records(os.path.join(OUT, "seeds.json"))
    seed_titles = {re.sub(r"[^a-z0-9]", "", (s.title or "").lower()) for s in seeds}

    docs = {r.canonical_id: toks(f"{r.title} {r.title} {r.abstract or ''}") for r in pool}
    seed_docs = [toks(f"{s.title} {s.title} {s.abstract or ''}") for s in seeds]
    idf = build_idf(list(docs.values()) + seed_docs)

    # centroid = mean of L2-normalized seed vectors, renormalized
    cent = collections.defaultdict(float)
    for sd in seed_docs:
        for t, x in vec(sd, idf).items():
            cent[t] += x
    n = math.sqrt(sum(x * x for x in cent.values())) or 1.0
    cent = {t: x / n for t, x in cent.items()}

    scored = []
    for r in pool:
        s = cos(vec(docs[r.canonical_id], idf), cent)
        r.raw["seed_sim"] = round(s, 4)
        r.raw["is_seed"] = re.sub(r"[^a-z0-9]", "", (r.title or "").lower()) in seed_titles
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])

    sims = [s for s, _ in scored]
    q = lambda p: sims[min(len(sims) - 1, int(len(sims) * p))]
    print(f"pool={len(pool)}  sim  max={sims[0]:.3f}  p10={q(.10):.3f}  p25={q(.25):.3f}  "
          f"med={q(.50):.3f}  p75={q(.75):.3f}  min={sims[-1]:.3f}")

    print("\n--- top 15 by seed similarity ---")
    for s, r in scored[:15]:
        print(f'  {s:.3f} [{r.raw["lane"]:<7}] {r.title[:78]}')
    print("\n--- bottom 12 (sanity: these should be junk) ---")
    for s, r in scored[-12:]:
        print(f'  {s:.3f} [{r.raw["lane"]:<7}] {r.title[:78]}')

    # Threshold: keep anchors and seeds unconditionally; cut the rest at the
    # elbow. Print the neighbourhood so the cut point is auditable.
    THRESH = 0.10
    print(f"\n--- neighbourhood of THRESH={THRESH} ---")
    for s, r in scored:
        if abs(s - THRESH) < 0.022:
            print(f'  {s:.3f} [{r.raw["lane"]:<7}] {r.title[:78]}')

    kept = [r for s, r in scored
            if s >= THRESH or r.raw["lane"] == "anchor" or r.raw.get("is_seed")]
    lanes = collections.Counter(r.raw["lane"] for r in kept)
    serialize_records(kept, os.path.join(OUT, "pool_b4a.json"))
    serialize_records([r for s, r in scored if r not in kept],
                      os.path.join(OUT, "excluded_relevance.json"))
    print(f"\nkept {len(kept)}/{len(pool)}   lanes={dict(lanes)}")
    json.dump({"threshold": THRESH, "kept": len(kept), "pool": len(pool),
               "lanes": dict(lanes)},
              open(os.path.join(OUT, "b4a_summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
