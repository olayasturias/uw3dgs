"""Deterministic pure-python spherical k-means over TF-IDF vectors.

Used for the B.3.5 diversity audit and again for the B.6 data-driven taxonomy.
HDBSCAN (the skill's first choice) is unavailable -- the installed sklearn stack
has a broken numpy ABI -- so this is the documented k-means fallback with k
picked by the elbow heuristic over k=3..8.

Determinism matters for the skill's idempotence requirement, so initialization
is k-means++ driven by a fixed integer stream seeded from the sorted document
ids, never by Math.random-style entropy.
"""
import math, hashlib, collections


def _seedstream(ids):
    h = hashlib.sha256("|".join(sorted(ids)).encode()).digest()
    state = int.from_bytes(h[:8], "big") or 1

    def nxt():
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        return (state >> 11) / float(1 << 53)
    return nxt


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def _centroid(vecs):
    c = collections.defaultdict(float)
    for v in vecs:
        for k, x in v.items():
            c[k] += x
    n = math.sqrt(sum(x * x for x in c.values())) or 1.0
    return {k: x / n for k, x in c.items()}


def kmeans(ids, vecs, k, iters=40):
    rnd = _seedstream(ids)
    n = len(vecs)
    # k-means++ on cosine distance
    first = int(rnd() * n) % n
    cents = [vecs[first]]
    while len(cents) < k:
        d2 = []
        for v in vecs:
            best = max((cos(v, c) for c in cents), default=0.0)
            d = max(0.0, 1.0 - best)
            d2.append(d * d)
        tot = sum(d2) or 1.0
        r = rnd() * tot
        acc = 0.0
        pick = n - 1
        for i, x in enumerate(d2):
            acc += x
            if acc >= r:
                pick = i
                break
        cents.append(vecs[pick])

    assign = [0] * n
    for _ in range(iters):
        changed = False
        for i, v in enumerate(vecs):
            best, bi = -1.0, 0
            for j, c in enumerate(cents):
                s = cos(v, c)
                if s > best:
                    best, bi = s, j
            if assign[i] != bi:
                assign[i] = bi
                changed = True
        groups = collections.defaultdict(list)
        for i, a in enumerate(assign):
            groups[a].append(vecs[i])
        cents = [_centroid(groups[j]) if groups[j] else cents[j] for j in range(k)]
        if not changed:
            break

    inertia = sum(1.0 - cos(vecs[i], cents[assign[i]]) for i in range(n))
    return assign, cents, inertia


def choose_k(ids, vecs, kmin=3, kmax=8):
    """Elbow: pick k maximising the drop-off in marginal inertia reduction."""
    res = {}
    for k in range(kmin, min(kmax, len(vecs) - 1) + 1):
        res[k] = kmeans(ids, vecs, k)
    ks = sorted(res)
    iner = [res[k][2] for k in ks]
    best_k, best_gain = ks[0], -1.0
    for i in range(1, len(ks) - 1):
        gain = (iner[i - 1] - iner[i]) - (iner[i] - iner[i + 1])
        if gain > best_gain:
            best_gain, best_k = gain, ks[i]
    return best_k, res, dict(zip(ks, iner))


def top_terms(vecs, assign, j, n=12):
    c = collections.defaultdict(float)
    cnt = 0
    for v, a in zip(vecs, assign):
        if a == j:
            cnt += 1
            for k, x in v.items():
                c[k] += x
    return [t for t, _ in sorted(c.items(), key=lambda kv: -kv[1])[:n]], cnt
