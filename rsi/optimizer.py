"""Meta-optimizer: rewrites (system prompt, user prompt) from evaluation feedback + history."""
from __future__ import annotations

import json
from pathlib import Path

from .generator import CONTRACT
from .llm import LLM, cached_text, image_block

SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "edits": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": ["system", "user"]},
                "addresses": {"type": "string"},
                "change": {"type": "string"},
            },
            "required": ["target", "addresses", "change"],
            "additionalProperties": False,
        }},
        "system_prompt": {"type": "string"},
        "user_prompt": {"type": "string"},
        "change_summary": {"type": "string"},
    },
    "required": ["diagnosis", "edits", "system_prompt", "user_prompt", "change_summary"],
    "additionalProperties": False,
}

OPTIMIZER_SYSTEM = f"""You are a prompt engineer running a recursive self-improvement loop. A generator model
receives a SYSTEM PROMPT and a USER PROMPT and writes a Blender Python script that builds a 3D scene.
The script runs headless, fixed cameras render it, and a scorer evaluates the result. Your job: rewrite
both prompts so that the NEXT generation scores higher. You see the current best prompts, how they scored
and why, the renders, the generated script, and a history of past edits with the score change each caused.

Roles of the two prompts (keep them separated):
- SYSTEM PROMPT = the generator's reusable expertise: how to write robust bpy for Blender 5.2, modeling
  techniques (walls with real door/window openings, roofs, bevels, UVs and texture scale), PBR material
  recipes using the asset manifest, lighting and exposure (HDRI + sun, interior area lights, AgX/Filmic),
  realism tricks (imperfections, variation, scale cues), code structure, and pitfalls that caused errors.
- USER PROMPT = the scene specification: concrete layout and dimensions, room adjacency, which furniture
  and assets go in each room and where, the exterior (facade, roof, driveway, road with lanes/markings/
  curbs/sidewalk/street lamps, backyard lawn/fence/trees/beds/patio), and the intended photographic look.

Rules:
1. Every edit must target an observed defect, a check failure, an error, or a pattern from the history.
   Prefer concrete, checkable instructions (numbers, API names, asset ids) over adjectives.
2. Never weaken or remove the goal: kitchen, living room, three bedrooms, road in front, garden in back,
   photorealism. You cannot change how scoring works; only the prompts.
3. Learn from history: keep what raised scores, revert or rework what lowered them. If the last attempt
   regressed, explain why and do not repeat it.
4. Blender errors and repairs are expensive: if the scripts crashed, add precise API guidance (Blender 5.2
   names, e.g. Principled BSDF inputs 'Transmission Weight', 'Specular IOR Level', 'Emission Color').
5. Keep prompts dense and non-redundant. If combined length exceeds about {{cap}} tokens, consolidate.
6. Return the COMPLETE new prompts (not diffs). Do not include the fixed contract or the asset manifest;
   they are appended automatically and cannot be changed:

{CONTRACT}"""


def _sample_digest(s: dict) -> str:
    lines = [f"- sample {s['idx']}: score {s['score']:.1f} (checks {s.get('checks_score', 0):.1f}, "
             f"judge {s.get('judge_score', 0):.1f}, repairs {s['repairs']}, ok={s['ok']})"]
    for e in s.get("errors", [])[-2:]:
        lines.append("  blender error: " + e[-1500:].replace("\n", "\n    "))
    if s.get("check_failures"):
        lines.append("  check failures: " + "; ".join(s["check_failures"]))
    if s.get("judge_criteria"):
        lines.append(f"  judge means (1-10): {s['judge_criteria']}")
    for d in s.get("defects", []):
        lines.append(f"  defect[{d['severity']}] {d['view']}: {d['description']} (cause: {d['likely_cause']})")
    if s.get("judge_summary"):
        lines.append("  judge summary: " + s["judge_summary"])
    return "\n".join(lines)


def history_table(history: list[dict]) -> str:
    rows = ["iter | parent | score | Δ vs parent | accepted | change summary"]
    for h in history:
        rows.append(f"{h['iter']} | {h.get('parent', '-')} | {h['score']:.1f} | "
                    f"{h.get('delta', 0):+.1f} | {'yes' if h.get('is_best_at_time') else 'no'} | "
                    f"{h.get('change_summary', 'seed')}")
    return "\n".join(rows)


def propose(llm: LLM, cfg: dict, parent: dict, last: dict | None, history: list[dict],
            iter_dir: Path, guard_keywords: list[str]) -> dict:
    """parent/last: iteration records incl. 'system', 'user', 'samples', 'iter_dir'."""
    content: list[dict] = [{"type": "text", "text": (
        f"HISTORY (all iterations so far):\n{history_table(history)}\n\n"
        f"CURRENT BEST = iteration {parent['iter']} (score {parent['score']:.1f}).\n\n"
        f"=== CURRENT SYSTEM PROMPT ===\n{parent['system']}\n\n"
        f"=== CURRENT USER PROMPT ===\n{parent['user']}\n\n"
        f"=== EVALUATION OF CURRENT BEST ===\n"
        + "\n".join(_sample_digest(s) for s in parent["samples"]))}]
    if last is not None and last["iter"] != parent["iter"]:
        content.append({"type": "text", "text": (
            f"\n=== LAST ATTEMPT (iteration {last['iter']}) REGRESSED to {last['score']:.1f} and was "
            f"rejected. Its change summary: {last.get('change_summary')}\nIts evaluation:\n"
            + "\n".join(_sample_digest(s) for s in last["samples"]))})

    best = max(parent["samples"], key=lambda s: s["score"])
    renders = sorted((Path(best["dir"]) / "out" / "renders").glob("*.png"))
    if renders:
        content.append({"type": "text", "text": f"\nRenders of the best sample ({best['idx']}) of the current best:"})
        for p in renders:
            content += [{"type": "text", "text": f"View: {p.stem}"}, image_block(p)]
    script = Path(best["dir"]) / "scene_script.py"
    if script.exists():
        content.append({"type": "text", "text": "\nThe script that produced it:\n```python\n"
                        + script.read_text()[:60000] + "\n```"})
    content.append({"type": "text", "text": "\nDiagnose, then return improved complete prompts."})

    cap = cfg["loop"]["prompt_token_cap"]
    system = [cached_text(OPTIMIZER_SYSTEM.replace("{cap}", str(cap)))]
    messages = [{"role": "user", "content": content}]
    for attempt in range(2):
        text, usage = llm.call(role="optimizer", model=cfg["models"]["optimizer"],
                               effort=cfg["effort"]["optimizer"], system=system,
                               messages=messages, json_schema=SCHEMA, max_tokens=64000)
        out = json.loads(text)
        missing = [k for k in guard_keywords if k.lower() not in out["user_prompt"].lower()]
        if not missing:
            break
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Rejected: the user prompt no longer mentions {missing}. "
                      "The goal may not be weakened. Return the full JSON again with those requirements kept."}]
    else:
        out["user_prompt"] = parent["user"]
        out["change_summary"] += " [guard: user prompt reverted, dropped required elements]"
    out["cost_usd"] = usage.usd
    (iter_dir / "optimizer.json").write_text(json.dumps(out, indent=2))
    return out
