import os
import re

os.chdir(r"C:\Users\oat\workspace\sota-underwater-3dgs\docs")
s = open("index.html", encoding="utf-8").read()

# Replace the DATASETS block's blurbs/comments with qualitative descriptions.
start = s.find("const DATASETS = [")
end = s.find("];", start) + 2
assert start > 0 and end > start
new_block = """const DATASETS = [
  { name: 'S1 · SeaThru-NeRF (Curaçao reef)',
    blurb: 'Shallow sunlit reef, clear tropical water. The rendered views of all four systems look almost identical \\u2014 the point clouds show where they actually differ.',
    methods: [
      ['M0 · 3DGS',           's1_benchmark_M0_3dgs',
       'The reef itself is well-formed, but tilt to a grazing angle and a loose halo of drifting points hangs above the seabed \\u2014 the blue veil, explained as translucent matter parked in the water column.'],
      ['M2 · WaterSplatting', 's1_benchmark_M2_watersplatting',
       'The cleanest cloud on this scene: the water lives in a separate volumetric field, so nearly every point sits on coral or sand. Rotate around it \\u2014 the space above the reef is genuinely empty.'],
      ['M3 · SeaSplat',       's1_benchmark_M3_seasplat',
       'A dense reef wrapped in a shell of floating points. Orbit sideways and the wrapping becomes obvious: much of what this model committed to space is veil, not scene \\u2014 and it is exactly what makes its renders look so good.'],
      ['M4 · UW-GS',          's1_benchmark_M4_uwgs',
       'The best-looking renders of the benchmark come from this cloud \\u2014 in which more than half of the committed matter floats free of any surface. Look between the camera side and the reef: the fog is part of the model.'] ],
    start: 2 },
  { name: 'S2 · SOTRUE tank (clear water)',
    blurb: 'A controlled testbed tank scanned along a servo-driven trajectory. In clear water every system recovers the tank \\u2014 compare how crisply each one commits to the actual surfaces.',
    methods: [
      ['M0 · 3DGS',           's2_clear0NTU_M0_3dgs',
       'Sparse but sharply placed: points hug the tank structure with almost nothing in between. This is the crispest surface any system produced in the study.'],
      ['M2 · WaterSplatting', 's2_clear0NTU_M2_watersplatting',
       'Denser and softer than M0: surfaces are all there, but edges blur slightly where the medium field and the splats negotiate who explains what.'],
      ['M3 · SeaSplat',       's2_clear0NTU_M3_seasplat',
       'The tank emerges, but with structure smeared along the viewing directions \\u2014 the depth losses pull points into compromise positions even with no water to model.'] ],
    start: 0 },
  { name: 'S3 · Eiffel Tower vent (IFREMER)',
    blurb: 'A deep hydrothermal vent lit only by the ROV\\u2019s own lamps \\u2014 the light moves with the camera, which breaks the \\u201cuniform water glow\\u201d assumption every medium model relies on.',
    methods: [
      ['M0 · 3DGS',           's3_deepvent_M0_3dgs',
       'The chimney and talus slope come through intact, with the darkness simply left empty. Having no medium model turns out to be an advantage when the \\u201cmedium\\u201d is a moving lamp.'],
      ['M2 · WaterSplatting', 's3_deepvent_M2_watersplatting',
       'A skeleton. The medium field decided the co-moving light pattern WAS the water and swallowed most of the scene with it \\u2014 this sparse residue is everything that survived. The most instructive cloud on the page.'],
      ['M3 · SeaSplat',       's3_deepvent_M3_seasplat',
       'Structurally complete but with a dimmer, muddier surface than M0: the analytic water terms keep trying to explain the lamp falloff and leave their fingerprints on the geometry.'] ],
    start: 0 },
  { name: 'S4 · EIVA industrial survey',
    blurb: 'A real inspection pass over a submerged structure, with operational lighting and mild turbidity. This is the scene the methods exist for.',
    methods: [
      ['M0 · 3DGS',           's4_survey_M0_3dgs',
       'A clean, coherent hull: on a well-overlapped survey trajectory in mild water, plain splatting places its points on the structure and little else.'],
      ['M1 · UIE\\u21923DGS', 's4_survey_M1_uie3dgs',
       'Visually the tightest surface of the four \\u2014 produced by nothing more than a classical 2D restoration pass in front of stock 3DGS. Simplicity wins the geometry here.'],
      ['M2 · WaterSplatting', 's4_survey_M2_watersplatting',
       'Sparse but faithful: the medium field soaks up the green cast and the splats concentrate on the hull. Very little floats.'],
      ['M3 · SeaSplat',       's4_survey_M3_seasplat',
       'Look around the hull\\u2019s silhouette: solid clumps sit displaced from the structure. These are not translucent floaters \\u2014 the model committed opaque geometry in the wrong places, which its good-looking renders never reveal.'] ],
    start: 0 },
];"""
s = s[:start] + new_block + s[end:]

# Comment footer: refer to the paper for numbers
old = """function setComment(ds, comment) {
  commentEl.innerHTML = `<strong>${ds.name}.</strong> ${ds.blurb}<br><em>${comment}</em>`;
}"""
new = """function setComment(ds, comment) {
  commentEl.innerHTML = `<strong>${ds.name}.</strong> ${ds.blurb}<br><em>${comment}</em>` +
    '<br><span style="color:#7a7a7a;">Quantitative comparisons (PSNR, surface error, floater mass) are in the paper\\u2019s Tables II\\u2013IV.</span>';
}"""
assert s.count(old) == 1
s = s.replace(old, new)

open("index.html", "w", encoding="utf-8").write(s)
# sanity
assert s.count("<script") == s.count("</script>")
assert len(re.findall(r"blurb:", s)) == 4
print("qualitative comments in place")
