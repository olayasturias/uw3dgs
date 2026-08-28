import os

os.chdir(r"C:\Users\oat\workspace\sota-underwater-3dgs\docs")
s = open("index.html", encoding="utf-8").read()

# 1) generation note under the heading
old = """    <h2 class="title is-4">Interactive Gaussian point clouds</h2>
    <div class="tabs is-toggle is-centered is-small mb-3">"""
new = """    <h2 class="title is-4">Interactive Gaussian point clouds</h2>
    <p class="teaser-caption mb-4" style="margin-top:-0.25rem;">
      Each cloud is extracted directly from a trained 3DGS model: every Gaussian
      contributes one point at its centre, coloured by its base (SH degree-0)
      colour. Gaussians with opacity below 0.2 are dropped, clouds larger than
      250&thinsp;k points are randomly subsampled, and each cloud is centred and
      scaled by its robust (95th-percentile) radius for viewing. What you see is
      therefore the model's <em>geometry</em> as the optimiser committed it &mdash;
      including floaters and fabricated medium &mdash; not a rendered image.
    </p>
    <div class="tabs is-toggle is-centered is-small mb-3">"""
assert s.count(old) == 1
s = s.replace(old, new)

# 2) comment panel under the chips
old = """    <div id="model-buttons" class="is-flex is-flex-wrap-wrap is-justify-content-center mt-3" style="gap:8px;"></div>
    <p class="teaser-caption">
      Gaussian centres (opacity &gt; 0.2) of trained models, straight from the runs behind the paper's tables.
      Compare <em>S1 reef &mdash; M2</em> against <em>M3</em> to see the floating veil that buys the benchmark's best PSNR;
      open <em>S2 tank 12&thinsp;NTU</em> to see haze reconstructed as solid geometry; open <em>S3 &mdash; M2</em> to see
      what remains after a medium field absorbs the scene.
    </p>"""
new = """    <div id="model-buttons" class="is-flex is-flex-wrap-wrap is-justify-content-center mt-3" style="gap:8px;"></div>
    <div id="model-comment" class="teaser-caption" style="min-height:3.2em;"></div>"""
assert s.count(old) == 1
s = s.replace(old, new)

# 3) data: blurbs + per-method comments; wire into the JS
old = """const DATASETS = [
  { name: 'S1 · SeaThru-NeRF (Curaçao reef)', methods: [
      ['M0 · 3DGS',            's1_benchmark_M0_3dgs'],
      ['M2 · WaterSplatting',  's1_benchmark_M2_watersplatting'],
      ['M3 · SeaSplat',        's1_benchmark_M3_seasplat'],
      ['M4 · UW-GS',           's1_benchmark_M4_uwgs'] ], start: 2 },
  { name: 'S2 · SOTRUE tank (clear water)', methods: [
      ['M0 · 3DGS',           's2_clear0NTU_M0_3dgs'],
      ['M2 · WaterSplatting', 's2_clear0NTU_M2_watersplatting'],
      ['M3 · SeaSplat',       's2_clear0NTU_M3_seasplat'] ], start: 0 },
  { name: 'S3 · Eiffel Tower vent (IFREMER)', methods: [
      ['M0 · 3DGS',            's3_deepvent_M0_3dgs'],
      ['M2 · WaterSplatting',  's3_deepvent_M2_watersplatting'],
      ['M3 · SeaSplat',        's3_deepvent_M3_seasplat'] ], start: 0 },
  { name: 'S4 · EIVA industrial survey', methods: [
      ['M0 · 3DGS',            's4_survey_M0_3dgs'],
      ['M1 · UIE\\u21923DGS',  's4_survey_M1_uie3dgs'],
      ['M2 · WaterSplatting',  's4_survey_M2_watersplatting'],
      ['M3 · SeaSplat',        's4_survey_M3_seasplat'] ], start: 0 },
];"""
new = """const DATASETS = [
  { name: 'S1 · SeaThru-NeRF (Curaçao reef)',
    blurb: 'The field\\u2019s default benchmark: shallow, sunlit, clear tropical water. All four systems land within 1.3 dB of each other photometrically \\u2014 their point clouds do not.',
    methods: [
      ['M0 · 3DGS',           's1_benchmark_M0_3dgs',
       '29.3 dB. A fifth of its opacity floats off-surface (floater mass 0.21): the blue veil is explained by a translucent halo around the reef.'],
      ['M2 · WaterSplatting', 's1_benchmark_M2_watersplatting',
       '29.5 dB and the cleanest field of the study (floater mass 0.077): the separate volumetric medium field absorbs the veil, so almost nothing floats.'],
      ['M3 · SeaSplat',       's1_benchmark_M3_seasplat',
       '30.2 dB from 3.35 M Gaussians \\u2014 a third of whose opacity floats (0.37). The photometric lead is bought with the floating translucent mass you can see wrapped around the scene.'],
      ['M4 · UW-GS',          's1_benchmark_M4_uwgs',
       '30.6 dB, the benchmark\\u2019s best PSNR \\u2014 and the dirtiest geometry of the study: over half its opacity mass floats (0.551). Benchmark rank rewards contamination.'] ],
    start: 2 },
  { name: 'S2 · SOTRUE tank (clear water)',
    blurb: 'Controlled testbed, encoder ground-truth poses, metric scale. In clear water every system reconstructs the tank; the differences are in surface accuracy against an independent stereo reference.',
    methods: [
      ['M0 · 3DGS',           's2_clear0NTU_M0_3dgs',
       '32.0 dB and the best surface of the study: 99 mm median depth error. The opaque core sits on the stereo reference to ~2 cm.'],
      ['M2 · WaterSplatting', 's2_clear0NTU_M2_watersplatting',
       '32.9 dB, 289 mm surface error, near-zero floaters (0.001) \\u2014 clean but less accurate than the medium-blind baseline where there is no medium to model.'],
      ['M3 · SeaSplat',       's2_clear0NTU_M3_seasplat',
       '28.2 dB, 438 mm surface error: the medium networks and depth losses push structure around even though the water is clear.'] ],
    start: 0 },
  { name: 'S3 · Eiffel Tower vent (IFREMER)',
    blurb: 'Deep hydrothermal vent under co-moving ROV light \\u2014 the regime that violates the uniform-veiling-light assumption every medium model bakes in. Vanilla 3DGS beats both medium-aware systems here.',
    methods: [
      ['M0 · 3DGS',           's3_deepvent_M0_3dgs',
       '27.0 dB, best on the scene, 1.9 M Gaussians: with no medium model to mislead, the structure survives the moving light.'],
      ['M2 · WaterSplatting', 's3_deepvent_M2_watersplatting',
       '23.2 dB from only 27 k Gaussians: the direction-conditioned medium field absorbed the co-moving light pattern and most of the scene with it. This cloud is what remained.'],
      ['M3 · SeaSplat',       's3_deepvent_M3_seasplat',
       '25.9 dB, 2.0 M Gaussians: survives better than M2 but still loses to the medium-blind baseline once its lighting assumption is violated.'] ],
    start: 0 },
  { name: 'S4 · EIVA industrial survey',
    blurb: 'Operational survey imagery with a metric photogrammetric reference (chamfer in mm). The benchmark\\u2019s ranking inverts here \\u2014 and the naive baseline wins the geometry.',
    methods: [
      ['M0 · 3DGS',           's4_survey_M0_3dgs',
       '25.9 dB, 58 mm chamfer, median accuracy 7 mm: on a well-overlapped survey below the turbidity cliff, vanilla splatting geometry is genuinely good.'],
      ['M1 · UIE\\u21923DGS', 's4_survey_M1_uie3dgs',
       'Best geometry of ALL systems: 45 mm chamfer in 27 minutes, from a fixed 2D restoration pre-pass in front of stock 3DGS. The cheapest underwater adaptation beats every medium-aware architecture on the axis a surveyor cares about.'],
      ['M2 · WaterSplatting', 's4_survey_M2_watersplatting',
       '25.7 dB, 46 mm chamfer, near-zero floaters: accurate and clean \\u2014 statistically tied with the baseline photometrically.'],
      ['M3 · SeaSplat',       's4_survey_M3_seasplat',
       'The S1 benchmark leader comes last on both axes here: 24.7 dB and 369 mm chamfer, with 29% of its committed opacity nowhere near the reference \\u2014 misplaced opaque geometry, not a translucent veil.'] ],
    start: 0 },
];"""
assert s.count(old) == 1
s = s.replace(old, new)

# 4) JS: update the comment panel on selection
old = """function renderMethods() {
  btns.innerHTML = '';
  const ds = DATASETS[activeDs];
  ds.methods.forEach(([label, stem], i) => {
    const fig = document.createElement('figure');
    fig.className = 'model-btn' + (i === ds.start ? ' active' : '');
    fig.innerHTML = `<img src="assets/thumbs/${stem}.jpg" alt="${label}"
                       onerror="this.style.display='none'"><figcaption>${label}</figcaption>`;
    fig.onclick = () => {
      btns.querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'));
      fig.classList.add('active');
      show(stem);
    };
    btns.appendChild(fig);
  });
  show(ds.methods[ds.start][1]);
}"""
new = """const commentEl = document.getElementById('model-comment');
function setComment(ds, comment) {
  commentEl.innerHTML = `<strong>${ds.name}.</strong> ${ds.blurb}<br><em>${comment}</em>`;
}
function renderMethods() {
  btns.innerHTML = '';
  const ds = DATASETS[activeDs];
  ds.methods.forEach(([label, stem, comment], i) => {
    const fig = document.createElement('figure');
    fig.className = 'model-btn' + (i === ds.start ? ' active' : '');
    fig.innerHTML = `<img src="assets/thumbs/${stem}.jpg" alt="${label}"
                       onerror="this.style.display='none'"><figcaption>${label}</figcaption>`;
    fig.onclick = () => {
      btns.querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'));
      fig.classList.add('active');
      show(stem);
      setComment(ds, comment);
    };
    btns.appendChild(fig);
  });
  show(ds.methods[ds.start][1]);
  setComment(ds, ds.methods[ds.start][2]);
}"""
assert s.count(old) == 1
s = s.replace(old, new)

open("index.html", "w", encoding="utf-8").write(s)
print("generation note + per-selection comments added")
