"""Re-crop extracted figures at full column width.

The skill's auto region detection tightens to the union of embedded image rects,
which clips figure elements drawn as vector art or laid out in a text block
(Swimm3R lost its left-hand input column and half its caption; Aquatic-GS lost
its caption's right margin). Here the horizontal extent is taken from the page
text/image content box rather than from the raster rects alone, and the vertical
extent runs from the top of the figure content to the bottom of its own caption
block -- so the crop still contains no neighbouring body text.
"""
import os, re, sys, json
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = os.path.join(ROOT, "figures")
PDFS = os.path.join(ROOT, "pdfs")

# key, page (0-indexed), caption prefix regex, output figure number
JOBS = [
    ("li2024watersplatting",    3, r"Figure\s*2[.:]", 2),
    ("yang2024seasplat",        2, r"Fig(?:ure)?\.?\s*2[.:]", 2),
    ("wang2024uwgs",            3, r"Figure\s*2[.:]", 2),
    ("li2024gaussiansplashing", 4, r"Fig\.?\s*3[.:]", 3),
    ("liu2024aquaticgs",        3, r"Fig\.?\s*2[.:]", 2),
    ("zhang2024recgs",          2, r"Fig\.?\s*3[.:]", 3),
    ("wang2026swimm3r",         2, r"Fig\.?\s*2[.:]", 2),
    ("levy2023seathrunerf",     4, r"Figure\s*3[.:]", 3),
]


def main():
    for key, pno, cappat, fignum in JOBS:
        path = os.path.join(PDFS, key + ".pdf")
        if not os.path.exists(path):
            print(f"MISSING {key}")
            continue
        d = fitz.open(path)
        p = d[pno]
        blocks = p.get_text("blocks")
        cap = None
        for b in blocks:
            if re.match(cappat, b[4].strip()):
                cap = b
                break
        rects = []
        for xref, *_ in p.get_images(full=True):
            try:
                rects += list(p.get_image_rects(xref))
            except Exception:
                pass
        # vector-drawn diagram parts count too
        for dr in p.get_drawings():
            r = dr.get("rect")
            if r and r.width > 8 and r.height > 8:
                rects.append(r)

        if cap is None:
            print(f"{key}: caption not found on pg{pno}; skipped")
            d.close()
            continue

        above = [r for r in rects if r.y1 <= cap[1] + 2]
        if above:
            top = min(r.y0 for r in above)
            # ignore stray marks far above (headers, page numbers)
            body = [r for r in above if r.y0 > cap[1] - 420]
            if body:
                top = min(r.y0 for r in body)
        else:
            top = max(0, cap[1] - 260)

        x0 = min([r.x0 for r in above] + [cap[0]]) if above else cap[0]
        x1 = max([r.x1 for r in above] + [cap[2]]) if above else cap[2]
        x0 = max(p.rect.x0, x0 - 6)
        x1 = min(p.rect.x1, x1 + 6)
        clip = fitz.Rect(x0, max(p.rect.y0, top - 6), x1, min(p.rect.y1, cap[3] + 5))

        pm = p.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), clip=clip)
        out = os.path.join(FIGS, f"{key}_fig{fignum:02d}.png")
        pm.save(out)
        print(f"{key:<26} pg{pno} clip={tuple(round(v) for v in clip)} "
              f"-> {pm.width}x{pm.height}  {os.path.getsize(out)//1024}KB")
        d.close()


if __name__ == "__main__":
    main()
