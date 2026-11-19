# rsi-in-context

A recursive self-improvement loop over two prompts: a **system prompt** (the generator's reusable Blender expertise) and a **user prompt** (the scene spec). From them, Claude writes a Blender script for a photorealistic house scene and saves it as a `.blend`. The scene has a kitchen, a living room, 3 bedrooms, a road in front and a garden in back.

```
(S_t, U_t) → generator (Claude) → scene_script.py → headless Blender → scene.blend + 9 fixed-camera renders
          → structural checks (inspect.json) + vision judge → score + defects
          → optimizer (Claude) sees prompts, scores, defects, renders, script, history → (S_t+1, U_t+1)
```

Each new iteration starts from the best-scoring prompt pair so far (elitism). A regression is logged, and its lesson is passed to the next proposal.

## Setup

```sh
uv sync
uv run python scripts/fetch_assets.py   # one-time: ~520 MB of CC0 Poly Haven HDRIs/textures/models
export ANTHROPIC_API_KEY=...
```

The Blender path is set in `config.yaml` (default: `/Applications/Blender.app/Contents/MacOS/Blender`).

## Run

```sh
uv run python -m rsi.loop --iterations 2 --samples 1 --render-samples 32   # smoke test (~$3–8)
uv run python -m rsi.loop                                                  # full run (config.yaml)
uv run python -m rsi.loop --resume runs/<run_id> --iterations 15           # continue / extend a run
```

Each run writes `runs/<run_id>/`:
- `report.html`: score curves, the same camera across iterations, and prompt diffs with the optimizer's diagnosis
- `history.jsonl`: one record per iteration, holding prompts, per-sample scores, defects and cost
- `iter_###/system.md`, `iter_###/user.md`: the prompts for that iteration
- `iter_###/optimizer.json`: the optimizer output that produced them
- `iter_###/sample_#/scene_script.py`: the generated script
- `iter_###/sample_#/out/scene.blend`: the scene, with textures packed
- `iter_###/sample_#/out/renders/*.png`, `inspect.json`, `checks.json`, `judge.json`
- `usage.jsonl`: per-call token and USD ledger

## Files

| Path | Role |
|---|---|
| `goal_spec.yaml` | **Immutable** intent, required rooms/furniture/exterior, judge rubric and anchors, score weights. Scoring uses this, never the evolving user prompt. The loop aborts if it changes mid-run. |
| `prompts/seed_*.md` | S₀ / U₀. These are deliberately naive, so the improvement is visible. |
| `config.yaml` | Models (Claude Opus 5.5 for all roles), effort, iterations, samples per iteration, render settings, budget. |
| `rsi/generator.py` | Builds the generator call: the evolving S, then the **fixed output contract** and the asset manifest (which the optimizer cannot edit). Includes the traceback repair loop. |
| `rsi/blender_side/harness.py` | Runs inside Blender: executes `build_scene(ctx)`, inspects the scene, adds fixed cameras, packs and saves the `.blend`, and renders. |
| `rsi/blender_side/cameras.py` | Fixed evaluation cameras derived from collection bounding boxes: front street, backyard, aerial, top-down, and one per room. |
| `rsi/checks.py` | Deterministic 0–100 score covering collections present, layout (road −Y, garden +Y, room areas, overlaps), furniture/elements, and realism proxies (HDRI, textured/bumped materials, glass, bevels, interior lights). |
| `rsi/judge.py` | Claude vision judge. Gives per-view 1–10 scores for photorealism, completeness and plausibility, plus a defect list (structured output). |
| `rsi/optimizer.py` | Rewrites both prompts from the evaluation and history. A keyword guard prevents it from dropping goal requirements. |
| `rsi/loop.py` | Orchestration: samples per iteration, elitism, budget and plateau stopping, resume. |
| `rsi/report.py` | Static HTML report. |

**Score** = `0.35·checks + 0.65·judge − 3·repairs`. A failed sample scores 0. The iteration score is the mean over its samples, which reduces noise.

## Test the harness without the API

```sh
uv run python -c "
import yaml, json; from pathlib import Path
from rsi.blender_runner import run_scene; from rsi import checks
cfg = yaml.safe_load(open('config.yaml')); cfg['render']['samples'] = 16
r = run_scene(Path('tests/stub_scene.py'), Path('runs/_stub/out'), cfg); print(r.ok, r.error)
print(checks.score(json.load(open('runs/_stub/out/inspect.json')), yaml.safe_load(open('goal_spec.yaml'))))"
```
