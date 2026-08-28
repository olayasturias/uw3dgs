"""E6 headline number: do the estimated medium coefficients shift when the
input is linearised? Compare the saved medium networks of e1_s1_m3 (gamma
input, A0) and e6_lin_s1_m3 (linearised input): B_inf directly, and the
attenuation transmittance each net predicts on a fixed depth ramp (the nets
are depth-conditioned, so we compare their function values, then convert to an
effective wideband beta via t(z) = exp(-beta z))."""
import sys

import numpy as np
import torch

sys.path.insert(0, r"D:\uw3dgs\repos\seasplat")
from deepseecolor.models import AttenuateNetV3, BackscatterNetV2  # noqa

RUNS = {"gamma": r"D:\uw3dgs\runs\e1_s1_m3", "linear": r"D:\uw3dgs\runs\e6_lin_s1_m3"}
out = {}
for tag, run in RUNS.items():
    bs = BackscatterNetV2(use_residual=False, scale=5.0, do_sigmoid=False)
    bs.load_state_dict(torch.load(run + r"\backscatter_30000.pth", map_location="cpu"))
    at = AttenuateNetV3(scale=5.0, do_sigmoid=False, init_vals=True)
    at.load_state_dict(torch.load(run + r"\attenuate_30000.pth", map_location="cpu"))
    binf = torch.sigmoid(bs.B_inf.detach()).flatten().numpy()
    # transmittance on a fixed metric depth ramp
    z = torch.linspace(0.5, 6.0, 12).reshape(1, 1, 12, 1).repeat(1, 1, 1, 2)
    with torch.no_grad():
        t = at(z).squeeze().numpy()  # (3, 12, 2) channels x depths
    t = t.mean(axis=-1)
    zs = z.squeeze().numpy().mean(axis=-1)
    beta_eff = -np.log(np.clip(t, 1e-6, 1)) / zs  # per channel per depth
    out[tag] = {"B_inf": binf, "beta_mid": beta_eff[:, 5], "beta_curve": beta_eff}
    print(f"{tag:7s} B_inf = {np.round(binf, 4)}   beta_eff(z~3m) = {np.round(beta_eff[:, 5], 4)}")

db = out["linear"]["B_inf"] - out["gamma"]["B_inf"]
dbeta = out["linear"]["beta_mid"] - out["gamma"]["beta_mid"]
rel = dbeta / np.maximum(np.abs(out["gamma"]["beta_mid"]), 1e-6) * 100
print("\nDelta B_inf (lin - gamma):", np.round(db, 4))
print("Delta beta_eff @3m:", np.round(dbeta, 4), " relative:", np.round(rel, 1), "%")
import json
json.dump({k: {kk: vv.tolist() for kk, vv in v.items()} for k, v in out.items()},
          open(r"D:\uw3dgs\runs\e6_delta_beta.json", "w"), indent=2)
