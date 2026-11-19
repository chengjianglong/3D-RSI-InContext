"""Prompts -> Blender script -> headless run, with a traceback repair loop."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .blender_runner import BlenderResult, run_scene
from .llm import LLM, cached_text

ROOT = Path(__file__).resolve().parent.parent

# Fixed interface contract. It is appended to every evolving system prompt and is NOT
# subject to optimization, so the optimizer can never break the harness interface.
CONTRACT = """\
=== FIXED OUTPUT CONTRACT (enforced by the harness; do not deviate) ===
Return exactly ONE fenced ```python code block containing the complete script, and nothing else is required.
The script runs inside Blender 5.2 (headless, factory settings, empty scene) and must define:

    def build_scene(ctx): ...

The harness calls build_scene(ctx). `ctx` provides only plumbing:
  ctx.collection(name) -> bpy.types.Collection   # get-or-create; room/shell collections auto-nest under "House"
  ctx.import_model(model_id, collection) -> list[Object]  # glTF from the asset manifest; returns root objects
  ctx.asset(rel_path) -> absolute path str        # for any manifest path (textures, HDRIs)
  ctx.manifest -> dict                            # the asset manifest below

Every object you create must be linked into exactly one of these collections:
  House_Shell (exterior walls, interior walls, roof, windows, doors, floors/ceilings not owned by a room),
  Kitchen, LivingRoom, Bedroom_1, Bedroom_2, Bedroom_3 (each room's floor, ceiling and contents),
  Road (street, sidewalk, curbs, markings, street furniture), Garden (backyard lawn, plants, trees, fence, paths),
  Lighting (lights; world/HDRI setup has no object).
Conventions: meters, +Z up, ground at z=0. The house front faces -Y: the road runs along the X axis at
negative Y in front of the house; the backyard garden is at positive Y behind it.
Do not create cameras or set the render engine, samples, or resolution: the harness adds fixed evaluation
cameras (front street, backyard, aerial, top-down, one corner camera inside each room) and renders with
Cycles. You may set world, lights, color management (view transform, look, exposure).
No network access; only files from the manifest exist. Keep the build under ~5 minutes of CPU.
"""


def manifest_text() -> str:
    m = json.loads((ROOT / "assets" / "manifest.json").read_text())
    lines = ["=== ASSET MANIFEST (CC0, local) ===", "HDRIs (equirectangular .hdr):"]
    lines += [f"  {h['id']}: {h['desc']} -> {h['path']}" for h in m["hdris"]]
    lines.append("PBR texture sets (2k jpg; maps: diff, nor_gl (OpenGL normal), rough, ao, disp):")
    for t in m["textures"]:
        lines.append(f"  {t['id']}: {t['desc']} -> " + json.dumps(t["maps"]))
    lines.append("Models (glTF, real-world scale, use ctx.import_model(id, collection)):")
    lines += [f"  {x['id']}: {x['desc']}" for x in m["models"]]
    return "\n".join(lines)


def build_system(system_prompt: str) -> list[dict]:
    return [cached_text(f"{system_prompt.strip()}\n\n{CONTRACT}\n{manifest_text()}")]


def extract_code(text: str) -> str | None:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    if not blocks:
        return None
    return max(blocks, key=len)


@dataclass
class SampleResult:
    sample_dir: Path
    ok: bool
    repairs: int
    errors: list[str] = field(default_factory=list)
    blender: BlenderResult | None = None
    script_path: Path | None = None
    cost_usd: float = 0.0


def generate_sample(llm: LLM, cfg: dict, system_prompt: str, user_prompt: str,
                    sample_dir: Path) -> SampleResult:
    sample_dir.mkdir(parents=True, exist_ok=True)
    (sample_dir / "system.md").write_text(system_prompt)
    (sample_dir / "user.md").write_text(user_prompt)
    system = build_system(system_prompt)
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    res = SampleResult(sample_dir, ok=False, repairs=0)
    max_repairs = cfg["loop"]["max_repairs"]

    for attempt in range(max_repairs + 1):
        text, usage = llm.call(role="generator", model=cfg["models"]["generator"],
                               effort=cfg["effort"]["generator"], system=system, messages=messages)
        res.cost_usd += usage.usd
        (sample_dir / f"generator_response_{attempt}.md").write_text(text)
        code = extract_code(text)
        if code is None:
            err = "Response contained no ```python code block."
        else:
            script = sample_dir / "scene_script.py"
            script.write_text(code)
            res.script_path = script
            br = run_scene(script, sample_dir / "out", cfg)
            res.blender = br
            if br.ok:
                res.ok = True
                return res
            err = br.error or "unknown Blender failure"
        res.errors.append(err)
        if attempt == max_repairs:
            break
        res.repairs += 1
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "The script failed when run in Blender:\n\n```\n"
             f"{err[-5000:]}\n```\nFix the cause and return the COMPLETE corrected script "
             "in one ```python block."},
        ]
    return res
