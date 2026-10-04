"""Draws the README banner (images/banner.png): a water-themed header with the project title.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\make_banner.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

OUT = Path(__file__).resolve().parents[1] / "images" / "banner.png"
W, H = 16, 4


def droplet(cx, cy, size):
    """A water-drop outline: pointed top, round bottom."""
    t = np.linspace(0, 2 * np.pi, 120)
    x = cx + size * 0.62 * np.sin(t) * (1 - np.cos(t)) / 2 * 1.6
    y = cy + size * np.cos(t)
    verts = np.column_stack([x, y])
    return MplPath(verts, [MplPath.MOVETO] + [MplPath.LINETO] * (len(verts) - 1))


def main():
    fig = plt.figure(figsize=(W, H), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    # deep-sea to shallow-water gradient
    cmap = LinearSegmentedColormap.from_list("water", ["#052f4a", "#0b6fa4", "#1aa3b8"])
    grad = np.linspace(0, 1, 512).reshape(1, -1)
    ax.imshow(grad, extent=[0, W, 0, H], cmap=cmap, aspect="auto", zorder=0)

    # layered waves along the bottom
    x = np.linspace(0, W, 600)
    for base, amp, freq, phase, alpha in [(1.15, 0.18, 1.1, 0.0, 0.18),
                                          (0.85, 0.22, 0.8, 1.3, 0.22),
                                          (0.55, 0.16, 1.4, 2.1, 0.30)]:
        y = base + amp * np.sin(freq * x + phase)
        ax.fill_between(x, 0, y, color="white", alpha=alpha, linewidth=0, zorder=1)

    # droplets on the right
    for cx, cy, s, a in [(13.6, 2.55, 0.62, 0.30), (14.7, 3.05, 0.38, 0.22), (12.7, 3.25, 0.28, 0.18)]:
        ax.add_patch(PathPatch(droplet(cx, cy, s), facecolor="white", edgecolor="none", alpha=a, zorder=2))

    ax.text(0.8, 2.55, "Urban Water Consumption in Saudi Arabia", color="white",
            fontsize=34, fontweight="bold", family="Segoe UI", va="center", zorder=3)
    ax.text(0.8, 1.85, "13 regions  ·  2010–2023  ·  Python data analysis on SAMA data",
            color="#d6eef5", fontsize=17, family="Segoe UI", va="center", zorder=3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=120)
    plt.close(fig)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
