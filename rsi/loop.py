"""Recursive self-improvement loop over (system prompt, user prompt).

uv run python -m rsi.loop                       # new run with config.yaml defaults
uv run python -m rsi.loop --iterations 2 --samples 1 --render-samples 32   # smoke test
uv run python -m rsi.loop --resume runs/<run_id>                           # continue a run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import checks, judge, optimizer, report
from .generator import generate_sample
from .llm import LLM, LLMFatalError

ROOT = Path(__file__).resolve().parent.parent


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def log(msg: str) -> None:
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def evaluate_sample(llm: LLM, cfg: dict, goal: dict, S: str, U: str, sdir: Path, idx: int) -> dict:
    w = goal["score_weights"]
    rec: dict = {"idx": idx, "dir": str(sdir), "ok": False, "repairs": 0, "errors": [],
                 "score": float(w["failure_score"]), "cost_usd": 0.0}
    try:
        gen = generate_sample(llm, cfg, S, U, sdir)
        rec.update(ok=gen.ok, repairs=gen.repairs, errors=gen.errors, cost_usd=gen.cost_usd)
        if not gen.ok:
            return rec
        out = sdir / "out"
        c = checks.score(json.loads((out / "inspect.json").read_text()), goal)
        (out / "checks.json").write_text(json.dumps(c, indent=2))
        j = judge.judge_sample(llm, cfg, goal, out)
        rec.update(
            checks_score=c["score"], check_failures=c["failures"], checks_parts=c["parts"],
            judge_score=j["score"], judge_criteria=judge.criterion_means(j),
            defects=j["defects"][:8], judge_summary=j["summary"],
            cost_usd=rec["cost_usd"] + j["cost_usd"],
        )
        rec["score"] = round(max(0.0, w["checks"] * c["score"] + w["judge"] * j["score"]
                                 - w["repair_penalty"] * gen.repairs), 2)
    except LLMFatalError:
        raise  # configuration problems: abort the run (resumable) instead of scoring 0
    except Exception:  # noqa: BLE001 - one bad sample must not kill the run
        rec["errors"].append("pipeline error: " + traceback.format_exc()[-3000:])
    finally:
        (sdir / "sample.json").write_text(json.dumps(rec, indent=2))
    return rec


def evaluate(llm, cfg, goal, S, U, iter_dir: Path, k: int) -> list[dict]:
    with ThreadPoolExecutor(k) as ex:
        futs = [ex.submit(evaluate_sample, llm, cfg, goal, S, U, iter_dir / f"sample_{i}", i)
                for i in range(k)]
        return [f.result() for f in futs]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--run-id")
    ap.add_argument("--resume", help="path to an existing run dir")
    ap.add_argument("--iterations", type=int)
    ap.add_argument("--samples", type=int)
    ap.add_argument("--render-samples", type=int)
    ap.add_argument("--budget", type=float)
    a = ap.parse_args(argv)

    cfg = yaml.safe_load((ROOT / a.config).read_text())
    if a.iterations:
        cfg["loop"]["iterations"] = a.iterations
    if a.samples:
        cfg["loop"]["samples_per_iter"] = a.samples
    if a.render_samples:
        cfg["render"]["samples"] = a.render_samples
    if a.budget:
        cfg["loop"]["budget_usd"] = a.budget

    goal_path = ROOT / "goal_spec.yaml"
    goal_hash = hashlib.sha256(goal_path.read_bytes()).hexdigest()
    goal = judge.load_goal(goal_path)

    run_dir = Path(a.resume) if a.resume else ROOT / "runs" / (a.run_id or time.strftime("%Y%m%d-%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.used.yaml").write_text(yaml.safe_dump(cfg))
    hist_path = run_dir / "history.jsonl"
    history: list[dict] = [json.loads(l) for l in hist_path.read_text().splitlines()] if hist_path.exists() else []

    llm = LLM(cfg["pricing_per_mtok"], ledger_path=run_dir / "usage.jsonl",
              backend=cfg.get("backend", "claude_cli"))
    spent_before = sum(h["cost_usd"] for h in history)
    K, N = cfg["loop"]["samples_per_iter"], cfg["loop"]["iterations"]
    keywords = goal["keywords_user_prompt_must_keep"]

    def spent() -> float:
        return spent_before + llm.total.usd

    def best_of(hs):
        return max(hs, key=lambda h: h["score"]) if hs else None

    while len(history) < N:
        t = len(history)
        iter_dir = run_dir / f"iter_{t:03d}"
        iter_dir.mkdir(exist_ok=True)
        cost0 = llm.total.usd
        if t == 0:
            S = (ROOT / "prompts" / "seed_system.md").read_text()
            U = (ROOT / "prompts" / "seed_user.md").read_text()
            parent_iter, opt = None, {"change_summary": "seed prompts", "edits": [], "diagnosis": ""}
        else:
            parent = best_of(history)
            log(f"iter {t}: optimizing prompts from best iter {parent['iter']} ({parent['score']:.1f})")
            opt = optimizer.propose(llm, cfg, parent, history[-1], history, iter_dir, keywords)
            S, U, parent_iter = opt["system_prompt"], opt["user_prompt"], parent["iter"]
        (iter_dir / "system.md").write_text(S)
        (iter_dir / "user.md").write_text(U)

        log(f"iter {t}: generating + rendering {K} samples")
        samples = evaluate(llm, cfg, goal, S, U, iter_dir, K)
        score = round(sum(s["score"] for s in samples) / len(samples), 2)
        prev_best = best_of(history)
        rec = {
            "iter": t, "parent": parent_iter, "score": score,
            "delta": round(score - prev_best["score"], 2) if prev_best else 0.0,
            "is_best_at_time": prev_best is None or score > prev_best["score"],
            "samples": samples, "system": S, "user": U,
            "system_sha": sha(S), "user_sha": sha(U),
            "system_chars": len(S), "user_chars": len(U),
            "change_summary": opt.get("change_summary"), "diagnosis": opt.get("diagnosis"),
            "edits": opt.get("edits", []),
            "cost_usd": round(llm.total.usd - cost0, 4), "iter_dir": str(iter_dir),
            "goal_sha": goal_hash[:12],
        }
        history.append(rec)
        with hist_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        report.write(run_dir, history)
        log(f"iter {t}: score {score:.1f} (Δ {rec['delta']:+.1f}) "
            f"samples={[s['score'] for s in samples]} cost ${rec['cost_usd']:.2f} total ${spent():.2f}")

        if hashlib.sha256(goal_path.read_bytes()).hexdigest() != goal_hash:
            log("goal_spec.yaml changed during the run; aborting (it must stay immutable)")
            return 3
        if spent() >= cfg["loop"]["budget_usd"]:
            log(f"budget ${cfg['loop']['budget_usd']} reached; stopping")
            break
        patience = cfg["loop"]["plateau_patience"]
        best = best_of(history)
        if len(history) - 1 - best["iter"] >= patience:
            log(f"no improvement for {patience} iterations; stopping")
            break

    best = best_of(history)
    log(f"done. best iter {best['iter']} score {best['score']:.1f}; report: {run_dir / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
