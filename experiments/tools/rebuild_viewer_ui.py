import os

os.chdir(r"C:\Users\oat\workspace\sota-underwater-3dgs\docs")
s = open("index.html", encoding="utf-8").read()

# --- HTML: dataset tabs above the viewer, method chips below ---
old_html = """    <div id="viewer-wrap">
      <canvas id="viewer"></canvas>
      <div id="viewer-hint">drag to rotate &middot; scroll to zoom &middot; right-drag to pan</div>
      <div id="viewer-stats"></div>
    </div>
    <div id="model-buttons" class="is-flex is-flex-wrap-wrap is-justify-content-center mt-3" style="gap:8px;"></div>"""
new_html = """    <div class="tabs is-toggle is-centered is-small mb-3">
      <ul id="dataset-tabs"></ul>
    </div>
    <div id="viewer-wrap">
      <canvas id="viewer"></canvas>
      <div id="viewer-hint">drag to rotate &middot; scroll to zoom &middot; right-drag to pan</div>
      <div id="viewer-stats"></div>
    </div>
    <div id="model-buttons" class="is-flex is-flex-wrap-wrap is-justify-content-center mt-3" style="gap:8px;"></div>"""
assert s.count(old_html) == 1
s = s.replace(old_html, new_html)

# --- JS: two-level selection + real error reporting ---
old_js_start = "const MODELS = ["
old_js_end = "show(MODELS[1][0]);   // start on the floating-veil model"
i = s.find(old_js_start)
j = s.find(old_js_end)
assert i > 0 and j > i
new_js = """const DATASETS = [
  { name: 'S1 · SeaThru-NeRF (Curaçao reef)', methods: [
      ['M0 · 3DGS',            's1_benchmark_M0_3dgs'],
      ['M2 · WaterSplatting',  's1_benchmark_M2_watersplatting'],
      ['M3 · SeaSplat',        's1_benchmark_M3_seasplat'],
      ['M4 · UW-GS',           's1_benchmark_M4_uwgs'] ], start: 2 },
  { name: 'S2 · SOTRUE tank (measured turbidity)', methods: [
      ['M0 · 3DGS — clear (0 NTU)', 's2_clear0NTU_M0_3dgs'],
      ['M0 · 3DGS — 12 NTU',        's2_turbid12NTU_M0_3dgs'],
      ['M2 · WaterSplatting — 12 NTU', 's2_turbid12NTU_M2_watersplatting'],
      ['M3 · SeaSplat — 12 NTU',    's2_turbid12NTU_M3_seasplat'] ], start: 1 },
  { name: 'S3 · Eiffel Tower vent (IFREMER)', methods: [
      ['M0 · 3DGS',            's3_deepvent_M0_3dgs'],
      ['M2 · WaterSplatting',  's3_deepvent_M2_watersplatting'],
      ['M3 · SeaSplat',        's3_deepvent_M3_seasplat'] ], start: 0 },
  { name: 'S4 · EIVA industrial survey', methods: [
      ['M0 · 3DGS',            's4_survey_M0_3dgs'],
      ['M1 · UIE\\u21923DGS',  's4_survey_M1_uie3dgs'],
      ['M2 · WaterSplatting',  's4_survey_M2_watersplatting'],
      ['M3 · SeaSplat',        's4_survey_M3_seasplat'] ], start: 0 },
];

const canvas = document.getElementById('viewer');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101318);
const camera = new THREE.PerspectiveCamera(50, 16 / 9, 0.01, 100);
camera.position.set(1.6, 1.0, 1.6);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w || canvas.height !== h) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

let cloud = null;
const loader = new PLYLoader();
const stats = document.getElementById('viewer-stats');
function show(stem) {
  stats.textContent = 'loading\\u2026';
  loader.load(`assets/pointclouds/${stem}.ply`, geo => {
    try {
      if (cloud) { scene.remove(cloud); cloud.geometry.dispose(); cloud.material.dispose(); }
      geo.rotateX(Math.PI);
      const mat = new THREE.PointsMaterial({ size: 0.008, vertexColors: true });
      cloud = new THREE.Points(geo, mat);
      scene.add(cloud);
      controls.target.set(0, 0, 0);
      stats.textContent = `${geo.getAttribute('position').count.toLocaleString()} points`;
    } catch (e) { stats.textContent = 'render error: ' + e.message; }
  }, undefined, err => {
    const detail = err && err.target && err.target.status !== undefined
      ? `HTTP ${err.target.status}` : (err && err.message ? err.message : String(err));
    stats.textContent = `failed to load ${stem}.ply (${detail})`;
    console.error('pointcloud load failed', stem, err);
  });
}

const tabs = document.getElementById('dataset-tabs');
const btns = document.getElementById('model-buttons');
let activeDs = 0;

function renderMethods() {
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
}

DATASETS.forEach((ds, i) => {
  const li = document.createElement('li');
  if (i === 0) li.className = 'is-active';
  li.innerHTML = `<a>${ds.name}</a>`;
  li.onclick = () => {
    tabs.querySelectorAll('li').forEach(x => x.classList.remove('is-active'));
    li.classList.add('is-active');
    activeDs = i;
    renderMethods();
  };
  tabs.appendChild(li);
});
renderMethods();
"""
s = s[:i] + new_js + s[j + len(old_js_end):]
open("index.html", "w", encoding="utf-8").write(s)
print("viewer UI rebuilt")
