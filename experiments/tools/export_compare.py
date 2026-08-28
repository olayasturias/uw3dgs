"""Export per-view ground-truth/render pairs for the project page's comparison slider.

render_sets.py builds labelled side-by-side strips for inspection. The web slider
needs the opposite: each image on its own, GT and every method at identical pixel
dimensions so a wipe divider lines up.

The scene/run mapping is NOT duplicated here. It is read from render_sets.py, which
stays the single source of truth; if that file's structure changes this exits loudly
rather than drifting.

Output -> docs/assets/compare/<scene>/<view>_<method>.jpg  + manifest.json
"""
import json
import os
import glob

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "assets", "compare")

WIDTH = 1100      # displayed at ~900 css px, so this covers hi-dpi
QUALITY = 82
N_VIEWS = 3       # per scene; keeps the page under a sane download

# Scene keys -> the label and blurb the page shows.
SCENE_META = {
    "s1_curacao":     ("S1 · SeaThru-NeRF (Curaçao)", "The field's default shallow benchmark: clear, naturally lit water."),
    "s2_clear0NTU":   ("S2 · SOTRUE 0 NTU",           "Turbidity-controlled stereo tank, clear water, encoder ground-truth poses."),
    "s2_turbid12NTU": ("S2 · SOTRUE 12 NTU",          "The same tank and trajectory at 12 NTU, where SfM registers 0 % of frames."),
    "s3_eiffel":      ("S3 · Eiffel Tower vent",      "Deep hydrothermal vent under a light that moves with the ROV."),
    "planenose":      ("S4 · EIVA survey",            "Industrial survey scene with a metric photogrammetric reference."),
}

# Column label -> short web key. M1 renders its own enhanced targets, so it is
# marked and must not be read as a like-for-like match against GT.
def method_key(label):
    if label.lower().startswith("ground"):
        return "gt"
    return label.split()[0].lower()


def web_label(label):
    """render_sets.py writes ASCII labels for PIL; the page can show the real arrow."""
    return label.replace("->", "→").replace(" *", "*")


def load_sets():
    p = os.path.join(ROOT, "experiments", "tools", "render_sets.py")
    src = open(p, encoding="utf-8").read()
    head = src.split("H = 480")[0]
    if "SETS" not in head:
        raise SystemExit("render_sets.py structure changed: could not read SETS")
    ns = {}
    exec(head.replace("from PIL import Image, ImageDraw, ImageFont", ""), ns)
    return ns["SETS"]


def main():
    manifest = {"width": WIDTH, "scenes": []}
    total = 0
    for st in load_sets():
        name = st["name"]
        scene_dir = os.path.join(st["scene"], "images")
        names = [n for n in sorted(os.listdir(scene_dir)) if n.lower().endswith((".png", ".jpg"))]
        test = names[::8]
        live = [c for c in st["cols"] if c[2] == "gt" or (c[1] and os.path.isdir(c[1]))]

        step = max(1, len(test) // N_VIEWS)
        picks = list(range(0, len(test), step))[:N_VIEWS]

        outdir = os.path.join(OUT, name)
        os.makedirs(outdir, exist_ok=True)

        label, blurb = SCENE_META.get(name, (name, ""))
        entry = {"key": name, "label": label, "blurb": blurb, "views": [], "methods": []}
        entry["methods"] = [{"key": method_key(l), "label": web_label(l)} for l, _, _ in live]

        cache = {}
        for k in picks:
            stem = os.path.splitext(test[k])[0]
            view = f"v{k:03d}"
            size = None
            wrote = []
            for lab, d, mode in live:
                p = None
                if mode == "gt":
                    p = os.path.join(scene_dir, test[k])
                elif mode == "idx":
                    p = os.path.join(d, f"{k:05d}.png")
                elif mode == "sorted":
                    cache.setdefault(d, sorted(os.listdir(d)))
                    if k < len(cache[d]):
                        p = os.path.join(d, cache[d][k])
                elif mode == "stem":
                    p = (glob.glob(os.path.join(d, stem + ".*")) or [None])[0]
                if not (p and os.path.exists(p)):
                    continue
                im = Image.open(p).convert("RGB")
                if size is None:                      # GT comes first and sets the geometry
                    size = (WIDTH, round(im.height * WIDTH / im.width))
                im = im.resize(size, Image.LANCZOS)   # every method matched to GT exactly
                fn = f"{view}_{method_key(lab)}.jpg"
                im.save(os.path.join(outdir, fn), quality=QUALITY, optimize=True)
                wrote.append(method_key(lab))
                total += 1
            if wrote:
                entry["views"].append({"key": view, "stem": stem,
                                       "w": size[0], "h": size[1], "have": wrote})
        manifest["scenes"].append(entry)
        print(f"  {name:16} {len(entry['views'])} views x {len(entry['methods'])} cols")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    mb = sum(os.path.getsize(os.path.join(dp, f))
             for dp, _, fs in os.walk(OUT) for f in fs) / 1048576
    print(f"  wrote {total} images, {mb:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
