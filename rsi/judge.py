"""Vision-model judge: scores the fixed evaluation renders against the immutable goal_spec."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from .llm import LLM, cached_text, image_block

EXPECTED_VIEWS = ["front_street", "backyard", "aerial", "top_down", "room_Kitchen",
                  "room_LivingRoom", "room_Bedroom_1", "room_Bedroom_2", "room_Bedroom_3"]
VIEW_WEIGHTS = {"photorealism": 0.5, "completeness": 0.3, "plausibility": 0.2}

SCHEMA = {
    "type": "object",
    "properties": {
        "views": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "view": {"type": "string"},
                "photorealism": {"type": "integer"},
                "completeness": {"type": "integer"},
                "plausibility": {"type": "integer"},
                "notes": {"type": "string"},
            },
            "required": ["view", "photorealism", "completeness", "plausibility", "notes"],
            "additionalProperties": False,
        }},
        "defects": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "view": {"type": "string"},
                "severity": {"type": "integer"},
                "description": {"type": "string"},
                "likely_cause": {"type": "string"},
            },
            "required": ["view", "severity", "description", "likely_cause"],
            "additionalProperties": False,
        }},
        "summary": {"type": "string"},
    },
    "required": ["views", "defects", "summary"],
    "additionalProperties": False,
}


def _system(goal: dict) -> list[dict]:
    anchors = "\n".join(f"  {k}/10: {v}" for k, v in goal["judge_anchors"].items())
    crit = "\n".join(f"  {k}: {v}" for k, v in goal["judge_criteria"].items())
    return [cached_text(f"""You are a strict, consistent judge of 3D architectural renders. You compare renders
of a generated Blender scene against a fixed goal and score them. You are calibrated: the same image
must always get the same score, and you never grade on effort or improvement, only on what is visible.

GOAL (fixed):
{goal['intent']}
Required: kitchen, living room, three bedrooms (each with appropriate furniture), house exterior
(walls, roof, windows, door), a traffic road with sidewalk in FRONT of the house, a backyard garden
(lawn, plants, trees, fence) BEHIND the house.

Score every view 1-10 on each criterion:
{crit}

Anchors (apply to every criterion):
{anchors}

The views come from fixed harness cameras: front_street (eye level across the road),
backyard (eye level from the back of the garden), aerial (3/4 overview), top_down (orthographic
plan; judge layout: road on one side, garden on the other), and room_<Name> (a corner camera
inside each room). A missing or black/empty view scores 1 on every criterion.

Then list the most important concrete defects (at most 8, most severe first; severity 3=critical,
2=major, 1=minor). Each defect names the view, describes exactly what is wrong as seen in the image,
and gives the likely technical cause in Blender terms (e.g. "no interior lights, exposure too low",
"texture stretched: missing UV unwrap/scale", "objects floating above floor", "flat untextured
material"). Be specific and visual; these defects drive the next improvement."""
    )]


def judge_sample(llm: LLM, cfg: dict, goal: dict, out_dir: Path) -> dict:
    renders = {p.stem: p for p in (out_dir / "renders").glob("*.png")}
    content: list[dict] = []
    for v in EXPECTED_VIEWS:
        if v in renders:
            content += [{"type": "text", "text": f"View: {v}"}, image_block(renders[v])]
        else:
            content.append({"type": "text", "text": f"View: {v} -- MISSING (not rendered)"})
    content.append({"type": "text", "text": "Score every view listed above and list defects."})
    text, usage = llm.call(role="judge", model=cfg["models"]["judge"], effort=cfg["effort"]["judge"],
                           system=_system(goal), messages=[{"role": "user", "content": content}],
                           json_schema=SCHEMA, max_tokens=32000)
    data = json.loads(text)
    data["cost_usd"] = usage.usd
    data["score"] = normalized(data)
    (out_dir / "judge.json").write_text(json.dumps(data, indent=2))
    return data


def _clamp(x) -> int:
    return max(1, min(10, int(x)))


def normalized(data: dict) -> float:
    """0-100. Every expected view counts; a view the judge omitted scores 1s."""
    by_view = {v["view"]: v for v in data["views"]}
    total = 0.0
    for v in EXPECTED_VIEWS:
        s = by_view.get(v)
        if s is None:
            total += 1.0
            continue
        total += sum(w * _clamp(s[k]) for k, w in VIEW_WEIGHTS.items())
    mean = total / len(EXPECTED_VIEWS)       # 1..10
    return round((mean - 1) / 9 * 100, 2)


def criterion_means(data: dict) -> dict:
    by_view = {v["view"]: v for v in data["views"]}
    return {k: round(sum(_clamp(by_view[v][k]) if v in by_view else 1 for v in EXPECTED_VIEWS)
                     / len(EXPECTED_VIEWS), 2) for k in VIEW_WEIGHTS}


def load_goal(path: Path) -> dict:
    return yaml.safe_load(path.read_text())
