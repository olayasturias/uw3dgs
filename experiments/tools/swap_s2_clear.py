import os
import shutil

# 1) stage the 0-NTU M2/M3 models into viewer_exports
R = r"D:\uw3dgs\runs"
VE = r"D:\uw3dgs\viewer_exports"
for stem, run in [("s2_clear0NTU_M2_watersplatting", "e2_t0_m2"),
                  ("s2_clear0NTU_M3_seasplat", "e2_t0_m3")]:
    dst = os.path.join(VE, stem + ".ply")
    if not os.path.exists(dst):
        shutil.copy2(os.path.join(R, run, "point_cloud", "iteration_30000",
                                  "point_cloud.ply"), dst)
    print(stem, os.path.getsize(dst) // 2**20, "MB")

# 2) add to the web export list
p = r"D:\uw3dgs\tools\make_web_pointclouds.py"
s = open(p, encoding="utf-8").read()
old = '    ("s2_clear0NTU_M0_3dgs",           "S2 0 NTU — M0"),'
new = ('    ("s2_clear0NTU_M0_3dgs",           "S2 0 NTU — M0"),\n'
       '    ("s2_clear0NTU_M2_watersplatting", "S2 0 NTU — M2"),\n'
       '    ("s2_clear0NTU_M3_seasplat",       "S2 0 NTU — M3"),')
if new not in s:
    assert s.count(old) == 1
    s = s.replace(old, new)
    open(p, "w", encoding="utf-8").write(s)
print("web export list updated")

# 3) S2 tab: clear-water models only
p = r"C:\Users\oat\workspace\sota-underwater-3dgs\docs\index.html"
s = open(p, encoding="utf-8").read()
old = """  { name: 'S2 · SOTRUE tank (measured turbidity)', methods: [
      ['M0 · 3DGS — clear (0 NTU)', 's2_clear0NTU_M0_3dgs'],
      ['M0 · 3DGS — 12 NTU',        's2_turbid12NTU_M0_3dgs'],
      ['M2 · WaterSplatting — 12 NTU', 's2_turbid12NTU_M2_watersplatting'],
      ['M3 · SeaSplat — 12 NTU',    's2_turbid12NTU_M3_seasplat'] ], start: 1 },"""
new = """  { name: 'S2 · SOTRUE tank (clear water)', methods: [
      ['M0 · 3DGS',           's2_clear0NTU_M0_3dgs'],
      ['M2 · WaterSplatting', 's2_clear0NTU_M2_watersplatting'],
      ['M3 · SeaSplat',       's2_clear0NTU_M3_seasplat'] ], start: 0 },"""
assert s.count(old) == 1
s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("S2 tab switched to clear-water models")
