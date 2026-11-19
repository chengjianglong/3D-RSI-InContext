"""Static HTML report: score curves, same-view render grid across iterations, prompt diffs."""
from __future__ import annotations

import difflib
import html
import json
import os
from pathlib import Path

from .judge import EXPECTED_VIEWS

CSS = """
:root{--bg:#fbfaf8;--fg:#1d1d1b;--muted:#6b6862;--card:#fff;--line:#e4e1db;--add:#e3f4e6;--del:#fbe4e1;
--s1:#2f6fdf;--s2:#d9822b;--s3:#3a9b5c;--s4:#a24fc2}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe8;--muted:#a19e97;--card:#1f1f1d;--line:#34332f;
--add:#1d3524;--del:#3d201d;--s1:#6b9cf0;--s2:#eba35c;--s3:#62c486;--s4:#c787e0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}
.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.grid figure{margin:0}.grid img{width:100%;border-radius:6px;display:block;border:1px solid var(--line)}
figcaption{font-size:12px;color:var(--muted);margin-top:4px}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;margin:0}
.add{background:var(--add)}.del{background:var(--del)}
details{margin:8px 0}summary{cursor:pointer;font-weight:600}
select{font:inherit;padding:4px 8px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px}
.legend span{display:inline-block;margin-right:14px;font-size:13px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
"""


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _series(history):
    out = {"combined": [], "checks": [], "judge": [], "photorealism x10": []}
    for h in history:
        ok = [s for s in h["samples"] if s.get("ok")]
        out["combined"].append(h["score"])
        out["checks"].append(_mean([s.get("checks_score") for s in ok]))
        out["judge"].append(_mean([s.get("judge_score") for s in ok]))
        pr = _mean([s.get("judge_criteria", {}).get("photorealism") for s in ok])
        out["photorealism x10"].append(pr * 10 if pr is not None else None)
    return out


def _chart(history) -> str:
    series = _series(history)
    W, H, P = 900, 280, 36
    n = max(1, len(history) - 1)
    colors = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]
    x = lambda i: P + (W - 2 * P) * i / n  # noqa: E731
    y = lambda v: H - P - (H - 2 * P) * v / 100  # noqa: E731
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Scores per iteration">']
    for v in (0, 25, 50, 75, 100):
        parts.append(f'<line x1="{P}" x2="{W-P}" y1="{y(v)}" y2="{y(v)}" stroke="var(--line)"/>'
                     f'<text x="4" y="{y(v)+4}" font-size="11" fill="var(--muted)">{v}</text>')
    for i in range(len(history)):
        parts.append(f'<text x="{x(i)-4}" y="{H-10}" font-size="11" fill="var(--muted)">{i}</text>')
    for (name, vals), c in zip(series.items(), colors):
        pts = [(x(i), y(v)) for i, v in enumerate(vals) if v is not None]
        if len(pts) > 1:
            parts.append(f'<polyline fill="none" stroke="{c}" stroke-width="2.5" points="'
                         + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
        for a, b in pts:
            parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.5" fill="{c}"><title>{name}: {(H-P-b)/(H-2*P)*100:.1f}</title></circle>')
    parts.append("</svg>")
    legend = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in zip(series, colors))
    return f'<div class="card">{"".join(parts)}<div class="legend">{legend}</div></div>'


def _diff(a: str, b: str) -> str:
    rows = []
    for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=1):
        if line.startswith(("+++", "---")):
            continue
        cls = "add" if line.startswith("+") else "del" if line.startswith("-") else ""
        rows.append(f'<div class="{cls}">{html.escape(line) or "&nbsp;"}</div>')
    return "<pre>" + "".join(rows) + "</pre>" if rows else '<p class="muted">unchanged</p>'


def write(run_dir: Path, history: list[dict]) -> Path:
    run_dir = Path(run_dir)
    rel = lambda p: os.path.relpath(p, run_dir)  # noqa: E731
    best = max(history, key=lambda h: h["score"])
    body = [f"<h1>Prompt self-improvement run</h1><p class='muted'>{run_dir.name} · {len(history)} iterations · "
            f"best: iteration {best['iter']} ({best['score']:.1f}) · total cost "
            f"${sum(h['cost_usd'] for h in history):.2f}</p>",
            "<h2>Scores per iteration (0–100)</h2>", _chart(history)]

    body.append("<h2>Iterations</h2><div class='card'><table><tr><th>#</th><th>parent</th><th>score</th><th>Δ</th>"
                "<th>new best</th><th>samples</th><th>S / U chars</th><th>cost</th><th>change summary</th></tr>")
    for h in history:
        body.append(f"<tr><td>{h['iter']}</td><td>{h['parent'] if h['parent'] is not None else '–'}</td>"
                    f"<td><b>{h['score']:.1f}</b></td><td>{h['delta']:+.1f}</td><td>{'✓' if h['is_best_at_time'] else ''}</td>"
                    f"<td>{', '.join(f'{s['score']:.0f}' + ('' if s['ok'] else '✗') for s in h['samples'])}</td>"
                    f"<td>{h['system_chars']} / {h['user_chars']}</td><td>${h['cost_usd']:.2f}</td>"
                    f"<td>{html.escape(h.get('change_summary') or '')}</td></tr>")
    body.append("</table></div>")

    # Same view across iterations (best sample per iteration).
    opts = "".join(f'<option value="{v}">{v}</option>' for v in EXPECTED_VIEWS)
    body.append(f"<h2>Same camera across iterations</h2><p><select id='view'>{opts}</select></p><div class='grid' id='views'>")
    for h in history:
        s = max(h["samples"], key=lambda s: s["score"])
        rdir = Path(s["dir"]) / "out" / "renders"
        for v in EXPECTED_VIEWS:
            p = rdir / f"{v}.png"
            img = f'<img loading="lazy" src="{rel(p)}" alt="{v} iteration {h["iter"]}">' if p.exists() else "<p class='muted'>not rendered</p>"
            body.append(f'<figure data-view="{v}">{img}<figcaption>iter {h["iter"]} · sample {s["idx"]} · '
                        f'{s["score"]:.1f}</figcaption></figure>')
    body.append("</div>")

    body.append("<h2>Prompt evolution</h2>")
    by_iter = {h["iter"]: h for h in history}
    for h in history[1:]:
        p = by_iter.get(h["parent"])
        if p is None:
            continue
        edits = "".join(f"<li><b>{html.escape(e['target'])}</b>: {html.escape(e['change'])} "
                        f"<span class='muted'>(for: {html.escape(e['addresses'])})</span></li>" for e in h.get("edits", []))
        body.append(f"<details><summary>iter {h['iter']} vs parent {p['iter']} — {h['score']:.1f} ({h['delta']:+.1f})</summary>"
                    f"<p><b>Diagnosis.</b> {html.escape(h.get('diagnosis') or '')}</p><ul>{edits}</ul>"
                    f"<h3>System prompt diff</h3><div class='card'>{_diff(p['system'], h['system'])}</div>"
                    f"<h3>User prompt diff</h3><div class='card'>{_diff(p['user'], h['user'])}</div></details>")
    body.append(f"<details><summary>Best prompts (iteration {best['iter']})</summary><h3>System</h3><div class='card'>"
                f"<pre>{html.escape(best['system'])}</pre></div><h3>User</h3><div class='card'><pre>{html.escape(best['user'])}</pre></div></details>")
    best_s = max(best["samples"], key=lambda s: s["score"])
    body.append(f"<p class='muted'>Best .blend: {html.escape(str(Path(best_s['dir']) / 'out' / 'scene.blend'))}</p>")

    js = """<script>const sel=document.getElementById('view');function f(){document.querySelectorAll('#views figure')
.forEach(e=>e.style.display=e.dataset.view===sel.value?'':'none')}sel.onchange=f;f();</script>"""
    page = (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>RSI Scene Report</title><style>{CSS}</style></head><body><main>{''.join(body)}</main>{js}</body></html>")
    out = run_dir / "report.html"
    out.write_text(page)
    (run_dir / "summary.json").write_text(json.dumps(
        [{k: h[k] for k in ("iter", "parent", "score", "delta", "cost_usd", "change_summary")} for h in history], indent=2))
    return out
