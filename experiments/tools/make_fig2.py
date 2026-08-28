"""Figure 2: turbidity dose-response on SOTRUE (E2).

Two stacked panels, shared x = measured NTU (two measures -> two charts, never
a dual axis). Top: held-out PSNR. Bottom: surface depth error [mm], log scale.
Series colors: dataviz reference categorical slots 1-3 in fixed order, with
marker/linestyle secondary encoding for grayscale print. Data from the run
ledger (runs/e2_*/DONE.json + geometry_surface.json), hardcoded here with
provenance so the figure is regenerable and auditable.
"""
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42   # TrueType, not Type 3 (IEEE PDF compliance)
matplotlib.rcParams["ps.fonttype"] = 42
import matplotlib.pyplot as plt

X = [0.0, 6.0, 7.0, 12.0]  # measured NTU (median), scenes s2_turbid{0,2,3,5}_trial1

SERIES = {
    "M0 3DGS":           dict(color="#2a78d6", marker="o", ls="-",
                              psnr=[31.97, 35.54, 35.94, 35.11], surf=[99, 845, 848, 847]),
    "M2 WaterSplatting": dict(color="#eb6834", marker="s", ls="--",
                              psnr=[32.87, 35.59, 35.90, 36.38], surf=[289, 456, 660, 809]),
    "M3 SeaSplat":       dict(color="#1baf7a", marker="^", ls=":",
                              psnr=[28.17, None, 28.67, 28.13], surf=[438, None, 934, 917]),
}
CROSS_NTU = 3.3  # interp. of the M0/M2 crossing; MEASURED bracket: (0, 6) NTU

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "axes.linewidth": 0.6,
    "font.family": "sans-serif",
})

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.5, 4.0), sharex=True,
                               gridspec_kw=dict(hspace=0.12))

def plot(ax, key):
    for name, s in SERIES.items():
        xs = [x for x, v in zip(X, s[key]) if v is not None]
        ys = [v for v in s[key] if v is not None]
        gap = len(xs) < len(X)  # missing cell: fade the connector so the line
        ax.plot(xs, ys, color=s["color"], ls=s["ls"],  # does not imply a value
                lw=1.4, alpha=0.35 if gap else 1.0, zorder=2)
        ax.plot(xs, ys, color=s["color"], marker=s["marker"], ls="none",
                ms=4.5, markerfacecolor="white",
                markeredgewidth=1.1, markeredgecolor=s["color"],
                clip_on=False, zorder=3)
    ax.grid(axis="y", color="0.88", lw=0.5, zorder=0)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

plot(ax1, "psnr")
ax1.set_ylabel("PSNR [dB] $\\uparrow$")
ax1.set_ylim(27, 37.5)
# direct labels at right end
ax1.annotate("M2", (12, 36.38), xytext=(4, 2), textcoords="offset points",
             color="#52514e", fontsize=7.5)
ax1.annotate("M0", (12, 35.11), xytext=(4, -8), textcoords="offset points",
             color="#52514e", fontsize=7.5)
ax1.annotate("M3", (12, 28.13), xytext=(4, -2), textcoords="offset points",
             color="#52514e", fontsize=7.5)

plot(ax2, "surf")
ax2.set_yscale("log")
ax2.set_ylabel("surface depth error [mm] $\\downarrow$")
ax2.set_xlabel("measured turbidity [NTU]")
ax2.set_ylim(80, 1200)
ax2.set_yticks([100, 300, 1000])
ax2.set_yticklabels(["100", "300", "1000"])
ax2.set_xticks([0, 6, 7, 12])

# crossing annotation (both panels share x, rule on the geometric panel)
for ax in (ax1, ax2):
    ax.axvline(CROSS_NTU, color="0.55", lw=0.8, ls=(0, (2, 2)), zorder=1)
ax2.annotate("M0/M2 cross\nin (0,6) NTU (measured)", (CROSS_NTU, 95),
             xytext=(6, 2), textcoords="offset points", fontsize=7,
             color="#52514e")

# shared legend (identity never color-alone: markers differ too)
from matplotlib.lines import Line2D
handles = [Line2D([], [], color=s["color"], marker=s["marker"], ls=s["ls"],
                  lw=1.4, ms=4.5, markerfacecolor="white",
                  markeredgecolor=s["color"], label=n)
           for n, s in SERIES.items()]
ax1.legend(handles=handles, loc="lower right", fontsize=7,
           frameon=False, handlelength=2.2, borderaxespad=0.1)

for ext in ("pdf", "png"):
    fig.savefig(rf"C:\Users\oat\workspace\sota-underwater-3dgs\paper\figures\fig2_dose_response.{ext}",
                bbox_inches="tight", dpi=300)
print("wrote fig2_dose_response.pdf/.png")
