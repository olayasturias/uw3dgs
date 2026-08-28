"""B.2b -- title hygiene + RGB-only sensor gate + near-duplicate detection.

Sensor gate is deliberately two-tier. A hard reject fires only on TITLE evidence,
because a title is an authorial commitment to what the method is. Abstract-level
evidence produces a `review` flag instead: papers routinely mention sonar or IMU
in a related-work sentence without depending on either, and auto-rejecting on
that would silently delete valid RGB-only work.
"""
import os, re, sys, json, html, collections, itertools, difflib

SCRIPTS = r"C:\Users\oat\.claude\skills\sota-report\scripts"
sys.path.insert(0, SCRIPTS)
from canonical_record import load_records, serialize_records  # noqa

OUT = os.path.dirname(os.path.abspath(__file__))

TAG_RE = re.compile(r"<[^>]{1,40}>")
WS_RE = re.compile(r"\s+")

# --- hard reject: the method IS an acoustic / non-visual method -------------
# NOTE: "bathymetry" is deliberately NOT here. It names an output (depth of the
# seabed), not a sensor. Through-water photogrammetry / refraction-aware splatting
# from UAV or diver imagery is squarely visual-only and must survive this gate.
# Only acoustic bathymetry instruments are rejected.
SONAR_TITLE = re.compile(
    r"\bsonar\b|\bacoustic\b|\bfls\b|forward[- ]scan|forward[- ]looking sonar|"
    r"side[- ]scan|multi-?beam|\bmbes\b|\becho ?sounder\b|acoustic bathymetr", re.I)
NONVIS_TITLE = re.compile(
    r"\blidar\b|\brgb-?d\b|\bdvl\b|doppler velocity log|structured light|"
    r"time[- ]of[- ]flight|\btof camera\b|inertial|\bimu\b|\bins\b|pressure sensor", re.I)

# --- soft flag: abstract suggests a required non-visual input ---------------
SONAR_ABS = re.compile(
    r"camera[- ]sonar|sonar[- ]camera|acoustic[- ]optical|optical[- ]acoustic|"
    r"sonar image|sonar measurement|sonar data|imaging sonar|acoustic sensor|"
    r"visual[- ]acoustic|acousto[- ]optic", re.I)
NONVIS_ABS = re.compile(
    r"visual[- ]inertial|inertial measurement|\bimu\b|\bdvl\b|depth sensor|"
    r"pressure sensor|rgb-?d|lidar|structured light|multi[- ]?beam", re.I)

# --- soft flag: not a splatting/radiance method at all ----------------------
NOT_NVS = re.compile(r"gaussian splat|3dgs|3d gaussian|radiance field|nerf\b|"
                     r"novel view synthesis|neural rendering|splatting", re.I)


def clean_title(t):
    t = html.unescape(TAG_RE.sub("", t or ""))
    return WS_RE.sub(" ", t).strip()


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower())


def main():
    recs = load_records(os.path.join(OUT, "pool_b2.json"))
    for r in recs:
        r.title = clean_title(r.title)
        r.abstract = clean_title(r.abstract) if r.abstract else r.abstract

    kept, hard = [], []
    counts = collections.Counter()
    for r in recs:
        t, a = r.title or "", r.abstract or ""
        lane = r.raw.get("lane")
        reasons = []

        if lane != "anchor":
            if SONAR_TITLE.search(t):
                reasons.append("sonar-in-title")
            if NONVIS_TITLE.search(t):
                reasons.append("nonvisual-sensor-in-title")
        if reasons:
            r.raw["exclusion"] = ",".join(reasons)
            counts["HARD:" + reasons[0]] += 1
            hard.append(r)
            continue

        flags = []
        if SONAR_ABS.search(a):
            flags.append("sonar-in-abstract")
        if NONVIS_ABS.search(a):
            flags.append("nonvisual-in-abstract")
        if lane in ("core", "medium") and not NOT_NVS.search(t + " " + a):
            flags.append("no-nvs-term")
        r.raw["sensor_flags"] = flags
        r.raw["needs_sensor_review"] = bool(flags)
        if flags:
            counts["FLAG:" + flags[0]] += 1
        kept.append(r)

    # near-duplicate detection: arXiv preprint vs later journal version often get
    # reworded titles ("Gaussian Splashing: Direct Volumetric Rendering Underwater"
    # vs "Gaussian splashing enables direct volumetric rendering underwater").
    pairs = []
    byyear = sorted(kept, key=lambda r: r.title or "")
    for a, b in itertools.combinations(byyear, 2):
        na, nb = norm(a.title), norm(b.title)
        if abs(len(na) - len(nb)) > 25:
            continue
        ratio = difflib.SequenceMatcher(None, na, nb).ratio()
        if ratio >= 0.80:
            pairs.append((round(ratio, 3), a.title, a.year, b.title, b.year))
    pairs.sort(reverse=True)

    serialize_records(kept, os.path.join(OUT, "pool_b2b.json"))
    serialize_records(hard, os.path.join(OUT, "excluded_sensor.json"))

    lanes = collections.Counter(r.raw.get("lane") for r in kept)
    print(f"in  : {len(recs)}")
    print(f"hard-excluded (non-visual sensor in title): {len(hard)}")
    print(f"kept: {len(kept)}   lanes={dict(lanes)}")
    print("counts:", dict(counts))
    print(f"needing manual sensor review: {sum(1 for r in kept if r.raw['needs_sensor_review'])}")
    print(f"\nnear-duplicate pairs (>=0.80): {len(pairs)}")
    for p in pairs[:25]:
        print(f'  {p[0]}  [{p[2]}] {p[1][:60]}\n         [{p[4]}] {p[3][:60]}')

    print("\n--- HARD EXCLUDED ---")
    for r in sorted(hard, key=lambda r: r.title or ""):
        print(f'  {r.raw["exclusion"]:<28} {r.year} {(r.title or "")[:72]}')

    json.dump({"in": len(recs), "hard_excluded": len(hard), "kept": len(kept),
               "lanes": dict(lanes), "counts": dict(counts),
               "near_dup_pairs": len(pairs)},
              open(os.path.join(OUT, "b2b_summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
