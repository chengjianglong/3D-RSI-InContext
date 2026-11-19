"""Draw the pipeline diagram as a PNG/SVG (renders anywhere, unlike Mermaid).

uv run python scripts/make_diagram.py docs/media
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

C = {"llm": ("#e8f0fb", "#3c6fb4"), "blender": ("#fdf0e2", "#e07a1f"), "data": ("#f2f3f5", "#6b7280"),
     "eval": ("#e7f6ee", "#2e9e5b"), "fixed": ("#fbe9ec", "#d1495b")}

fig, ax = plt.subplots(figsize=(19, 7.4))
ax.set_xlim(-1.3, 21.2)
ax.set_ylim(-1.6, 6.6)
ax.axis("off")
boxes = {}


def box(key, x, y, title, sub="", kind="data", w=2.9, h=1.25, dashed=False):
    fc, ec = C[kind]
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.18",
                                fc=fc, ec=ec, lw=2, ls="--" if dashed else "-", zorder=2))
    ax.text(x, y + (0.18 + 0.1 * sub.count("\n") if sub else 0), title, ha="center", va="center", fontsize=12.5, weight="bold", zorder=3)
    if sub:
        ax.text(x, y - 0.3 - 0.1 * sub.count("\n"), sub, ha="center", va="center", fontsize=9.5, color="#333", zorder=3)
    boxes[key] = (x, y, w, h)


def edge(a, b, side_a, side_b):
    x, y, w, h = boxes[a]
    pa = {"r": (x + w / 2, y), "l": (x - w / 2, y), "t": (x, y + h / 2), "b": (x, y - h / 2)}[side_a]
    x, y, w, h = boxes[b]
    pb = {"r": (x + w / 2, y), "l": (x - w / 2, y), "t": (x, y + h / 2), "b": (x, y - h / 2)}[side_b]
    return pa, pb


def arrow(a, b, sa, sb, label="", rad=0.0, color="#333", ls="-", lx=0, ly=0.18):
    pa, pb = edge(a, b, sa, sb)
    ax.add_patch(FancyArrowPatch(pa, pb, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=18,
                                 lw=1.8, color=color, ls=ls, zorder=1, shrinkA=2, shrinkB=2))
    if label:
        ax.text((pa[0] + pb[0]) / 2 + lx, (pa[1] + pb[1]) / 2 + ly, label, ha="center", va="bottom",
                fontsize=9.5, style="italic", color=color, zorder=4,
                bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.9))


# top row: generation
box("P", 1.9, 5.0, "Prompts  S_t , U_t", "system (expertise) + user (scene spec)", "data", w=4.2)
box("GEN", 7.0, 5.0, "Generator", "Claude · writes bpy script", "llm", w=3.2)
box("B", 12.0, 5.0, "Headless Blender 5.2", "runs build_scene(ctx)", "blender", w=3.4)
box("O", 17.6, 5.0, "scene.blend", "+ 9 fixed-camera renders\n+ inspect.json", "blender", w=4.0)
# evaluation
box("CH", 15.4, 2.3, "Structural checks", "deterministic · rooms,\nlayout, PBR materials", "eval", w=3.4)
box("J", 19.4, 2.3, "Vision judge", "Claude · 1–10 per view\n+ defect list", "llm", w=3.2)
box("G", 19.4, -0.6, "goal_spec.yaml", "IMMUTABLE intent + rubric", "fixed", w=3.2, dashed=True)
box("S", 11.0, 2.3, "Score + defects", "0.35·checks + 0.65·judge\n− 3·repairs", "eval", w=3.4)
# optimization
box("OPT", 6.4, 2.3, "Optimizer", "Claude · rewrites\nboth prompts", "llm", w=3.0)
box("H", 6.4, -0.6, "History", "every edit → Δscore", "data", w=3.0, dashed=True)
# selection diamond
sx, sy = 1.9, 2.3
ax.add_patch(Polygon([(sx, sy + 0.95), (sx + 1.45, sy), (sx, sy - 0.95), (sx - 1.45, sy)], closed=True,
                     fc="#fff8db", ec="#b8920b", lw=2, zorder=2))
ax.text(sx, sy, "better than\nbest so far?", ha="center", va="center", fontsize=11, weight="bold", zorder=3)
boxes["SEL"] = (sx, sy, 2.9, 1.9)

arrow("P", "GEN", "r", "l")
arrow("GEN", "B", "r", "l", "scene_script.py", lx=0)
arrow("B", "GEN", "b", "b", "traceback → repair (≤2)", rad=-0.45, color="#d1495b", ly=-0.75)
arrow("B", "O", "r", "l")
arrow("O", "CH", "b", "t", rad=0.0)
arrow("O", "J", "b", "t", rad=0.0)
arrow("CH", "S", "l", "r")
arrow("J", "S", "b", "b", rad=-0.35)
arrow("G", "CH", "l", "b", "scores against", rad=-0.25, color="#d1495b", ls="--", lx=-0.9, ly=-0.45)
arrow("G", "J", "t", "b", color="#d1495b", ls="--")
arrow("S", "OPT", "l", "r", "+ renders + script")
arrow("H", "OPT", "t", "b")
arrow("OPT", "SEL", "l", "r", "S_t+1 , U_t+1")
arrow("SEL", "P", "t", "b", "yes → new parent", rad=-0.0, color="#2e9e5b", lx=-0.05, ly=0.05)
arrow("SEL", "P", "l", "l", "no → keep best,\nlog the lesson", rad=-0.75, color="#d1495b", lx=-1.35, ly=-0.35)

ax.text(10.0, 6.35, "One self-improvement iteration", ha="center", fontsize=15, weight="bold")
out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/media")
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / "pipeline.png", dpi=110, bbox_inches="tight", facecolor="white")
fig.savefig(out / "pipeline.svg", bbox_inches="tight", facecolor="white")
print(out / "pipeline.png")
