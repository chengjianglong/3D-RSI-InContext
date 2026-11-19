"""Run a generated scene script inside headless Blender via the harness."""
from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "rsi" / "blender_side" / "harness.py"
_GPU_LOCK = threading.Lock()  # one Blender at a time; LLM calls still run in parallel


@dataclass
class BlenderResult:
    ok: bool
    out_dir: Path
    error: str | None = None          # traceback or failure description (for the repair loop)
    result: dict = field(default_factory=dict)
    log_tail: str = ""

    @property
    def renders(self) -> list[Path]:
        return sorted((self.out_dir / "renders").glob("*.png"))


def run_scene(script: Path, out_dir: Path, cfg: dict, skip_render: bool = False) -> BlenderResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    rcfg = cfg["render"]
    job = {
        "script": str(script.resolve()),
        "out_dir": str(out_dir.resolve()),
        "assets_root": str((ROOT / "assets").resolve()),
        "manifest": str((ROOT / "assets" / "manifest.json").resolve()),
        "render": {"samples": rcfg["samples"], "resolution": rcfg["resolution"],
                   "time_limit_s": rcfg.get("view_time_limit_s", 90)},
        "skip_render": skip_render,
    }
    job_path = out_dir / "job.json"
    job_path.write_text(json.dumps(job, indent=2))
    cmd = [cfg["blender"], "-b", "--factory-startup", "--python-exit-code", "2",
           "--python", str(HARNESS), "--", str(job_path)]
    log_path = out_dir / "blender.log"
    try:
        with _GPU_LOCK, log_path.open("w") as log:
            proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=rcfg["timeout_s"], cwd=ROOT)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        return BlenderResult(False, out_dir, f"Blender timed out after {rcfg['timeout_s']} s "
                             "(scene too heavy to build or render?)", log_tail=_tail(log_path))
    tail = _tail(log_path)
    res_file = out_dir / "result.json"
    result = json.loads(res_file.read_text()) if res_file.exists() else {}
    if code == 0 and result.get("status") == "ok":
        return BlenderResult(True, out_dir, result=result, log_tail=tail)
    err = result.get("traceback") or f"Blender exited with code {code}.\n{tail}"
    return BlenderResult(False, out_dir, err, result=result, log_tail=tail)


def _tail(p: Path, n: int = 4000) -> str:
    try:
        return p.read_text(errors="replace")[-n:]
    except FileNotFoundError:
        return ""
