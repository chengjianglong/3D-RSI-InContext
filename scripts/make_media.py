"""Build README media from a finished run: score charts, per-view evolution GIFs, a comparison grid,
and (if fly-through frames exist) an MP4 + GIF of the best scene.

uv run python scripts/make_media.py runs/exp1 docs/media [--fly runs/_fly]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
VIEWS = {"front_street": "Front street", "backyard": "Backyard", "aerial": "Aerial",
         "room_LivingRoom": "Living room", "room_Kitchen": "Kitchen", "room_Bedroom_1": "Bedroom 1"}
GREEN, RED, BLUE, GREY = "#2e9e5b", "#d1495b", "#3c6fb4", "#8a8f98"


def font(size, bold=True):
    try:
        return ImageFont.truetype(FONT if bold else FONT_REG, size)
    except OSError:
        return ImageFont.load_default()


def best_sample(h):
    ok = [s for s in h["samples"] if s["ok"]]
    return max(ok, key=lambda s: s["score"]) if ok else None


def render_path(h, view):
    s = best_sample(h)
    if not s:
        return None
    p = Path(s["dir"]) / "out" / "renders" / f"{view}.png"
    return p if p.exists() else None


def placeholder(size, text):
    im = Image.new("RGB", size, (40, 42, 48))
    d = ImageDraw.Draw(im)
    f = font(size[1] // 12)
    w = d.textlength(text, font=f)
    d.text(((size[0] - w) / 2, size[1] / 2 - size[1] // 24), text, fill=(200, 200, 205), font=f)
    return im


def labeled(h, view, size, best_iter):
    p = render_path(h, view)
    im = Image.open(p).convert("RGB").resize(size, Image.LANCZOS) if p else placeholder(size, "build failed / view missing")
    d = ImageDraw.Draw(im, "RGBA")
    bar = size[1] // 9
    d.rectangle([0, 0, size[0], bar], fill=(0, 0, 0, 150))
    tag = "BEST" if h["iter"] == best_iter else ("accepted" if h["is_best_at_time"] else "rejected")
    col = (80, 220, 130) if tag != "rejected" else (255, 120, 120)
    f = font(int(bar * 0.55))
    txt = f"iter {h['iter']}   score {h['score']:.1f}"
    d.text((bar * 0.35, bar * 0.2), txt, fill="white", font=f)
    tw = d.textlength(tag, font=f)
    d.text((size[0] - tw - bar * 0.35, bar * 0.2), tag, fill=col, font=f)
    return im


# --------------------------------------------------------------------------- charts
def charts(history, out: Path):
    it = [h["iter"] for h in history]
    score = [h["score"] for h in history]
    best, b = [], -1
    for s in score:
        b = max(b, s)
        best.append(b)

    def mean(h, key):
        v = [s.get(key) for s in h["samples"] if s.get(key) is not None]
        return sum(v) / len(v) if v else None

    def crit(h, c):
        v = [s["judge_criteria"][c] for s in h["samples"] if s.get("judge_criteria")]
        return sum(v) / len(v) if v else None

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1.25, 1]})
    cols = [GREEN if h["is_best_at_time"] else RED for h in history]
    a1.bar(it, score, color=cols, alpha=0.85, width=0.65, zorder=2)
    a1.step(it, best, where="mid", color="black", lw=2, label="best so far (parent)", zorder=3)
    a1.plot(it, [mean(h, "checks_score") for h in history], "o--", color=GREY, label="structural checks", zorder=3)
    a1.plot(it, [mean(h, "judge_score") for h in history], "s--", color=BLUE, label="vision judge", zorder=3)
    for x, y in zip(it, score):
        a1.text(x, y + 1.5, f"{y:.1f}", ha="center", fontsize=9)
    a1.set_ylim(0, 105)
    a1.set_xticks(it)
    a1.set_xlabel("iteration")
    a1.set_ylabel("score (0–100)")
    a1.set_title("Combined score per iteration (green = accepted, red = rejected)")
    a1.grid(axis="y", alpha=0.3, zorder=0)
    a1.legend(loc="lower right", fontsize=9)

    for c, colr in (("photorealism", "#e07a1f"), ("completeness", BLUE), ("plausibility", GREEN)):
        a2.plot(it, [crit(h, c) for h in history], "o-", color=colr, label=c, lw=2)
    a2.set_ylim(0, 10)
    a2.set_xticks(it)
    a2.set_xlabel("iteration")
    a2.set_ylabel("judge mean (1–10)")
    a2.set_title("Vision-judge criteria")
    a2.grid(alpha=0.3)
    a2.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "score_progress.png", dpi=110)
    plt.close(fig)

    fig, a = plt.subplots(figsize=(13, 3.6))
    w = 0.38
    a.bar([x - w / 2 for x in it], [h["system_chars"] for h in history], w, color=BLUE, label="system prompt")
    a.bar([x + w / 2 for x in it], [h["user_chars"] for h in history], w, color="#e07a1f", label="user prompt")
    a.set_yscale("log")
    a.set_xticks(it)
    a.set_xlabel("iteration")
    a.set_ylabel("characters (log)")
    a.set_title("Prompt length: from one-line seeds to dense, defect-driven specs")
    ax2 = a.twinx()
    ax2.plot(it, [sum(s["repairs"] for s in h["samples"]) for h in history], "kD-", label="repairs (both samples)")
    ax2.set_ylabel("repairs")
    ax2.set_ylim(0, 4)
    ax2.spines["top"].set_visible(False)
    h1, l1 = a.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    a.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "prompt_growth.png", dpi=110)
    plt.close(fig)


# --------------------------------------------------------------------------- image evolution
def evolution(history, out: Path, best_iter):
    size = (640, 360)
    for view, name in VIEWS.items():
        frames = [labeled(h, view, size, best_iter) for h in history]
        frames[0].save(out / f"evolution_{view}.gif", save_all=True, append_images=frames[1:],
                       duration=[1400] * (len(frames) - 1) + [3000], loop=0, optimize=True)


def grid(history, out: Path, iters, best_iter):
    cw, ch = 480, 270
    pad, head, side = 6, 40, 130
    hs = [h for h in history if h["iter"] in iters]
    W = side + len(hs) * (cw + pad)
    H = head + len(VIEWS) * (ch + pad)
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    for j, h in enumerate(hs):
        tag = " (best)" if h["iter"] == best_iter else (" (seed)" if h["iter"] == 0 else "")
        d.text((side + j * (cw + pad) + 8, 10), f"iteration {h['iter']}{tag} — score {h['score']:.1f}",
               fill="black", font=font(20))
    for i, (view, name) in enumerate(VIEWS.items()):
        y = head + i * (ch + pad)
        d.text((10, y + ch // 2 - 12), name, fill="black", font=font(20))
        for j, h in enumerate(hs):
            p = render_path(h, view)
            tile = Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS) if p else placeholder((cw, ch), "not built (sample failed)")
            im.paste(tile, (side + j * (cw + pad), y))
    im.save(out / "evolution_grid.jpg", quality=82)


# --------------------------------------------------------------------------- fly-through video
def flythrough(fly: Path, out: Path):
    shots = [s for s in ("orbit", "living") if (fly / s).is_dir() and any((fly / s).glob("*.png"))]
    if not shots:
        return
    lst = out / "_concat.txt"
    parts = []
    for s in shots:
        mp4 = out / f"_{s}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "25", "-i", str(fly / s / "%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", str(mp4)], check=True)
        parts.append(mp4)
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out / "flythrough.mp4")], check=True)
    for s, p in zip(shots, parts):  # README-friendly GIFs (GitHub plays GIFs inline)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-vf",
                        "fps=12,scale=560:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];"
                        "[b][p]paletteuse=dither=bayer:bayer_scale=4",
                        str(out / f"flythrough_{s}.gif")], check=True)
        p.unlink()
    lst.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("out")
    ap.add_argument("--fly")
    ap.add_argument("--grid-iters", default="0,1,3,5")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    history = [json.loads(l) for l in (Path(a.run) / "history.jsonl").read_text().splitlines()]
    best_iter = max(history, key=lambda h: h["score"])["iter"]
    charts(history, out)
    evolution(history, out, best_iter)
    grid(history, out, [int(x) for x in a.grid_iters.split(",")], best_iter)
    if a.fly:
        flythrough(Path(a.fly), out)
    for p in sorted(out.iterdir()):
        print(f"{p.stat().st_size / 1e6:6.2f} MB  {p}")


if __name__ == "__main__":
    main()
