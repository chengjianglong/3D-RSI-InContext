"""LLM backends behind one call() interface.

backend "claude_cli" (default): runs `claude -p` headless, using your Claude subscription
  login (no API key; ANTHROPIC_API_KEY is removed from the subprocess env so it can't override
  the login). Images and structured output go through stream-json / --json-schema.
backend "api": Anthropic SDK with an API key (streaming, adaptive thinking, refusal fallback).

Both return (text, Usage). Usage.usd is the API-list-price equivalent; on a subscription it is
not billed, but it is still a useful size measure and drives the optional budget cap.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

FALLBACK_BETA = "server-side-fallback-2026-07-01"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class LLMFatalError(RuntimeError):
    """Not worth retrying or scoring as a bad sample (auth, usage limit, bad request): abort the run."""


class OutputTooLongError(RuntimeError):
    """The response exceeded the output-token cap; retrying the same request won't help."""


def _load_dotenv() -> None:
    """Project .env (KEY=VALUE lines) overrides the shell environment, e.g. ANTHROPIC_API_KEY."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0
    usd: float = 0.0


def _system_text(system: list[dict] | str) -> str:
    return system if isinstance(system, str) else "\n\n".join(b["text"] for b in system)


class LLM:
    def __init__(self, pricing: dict, ledger_path: Path | None = None, backend: str = "claude_cli",
                 cli_timeout_s: int = 3600):
        self.backend = backend
        self.pricing = pricing
        self.total = Usage()
        self.ledger_path = ledger_path
        self.cli_timeout_s = cli_timeout_s
        self._lock = threading.Lock()
        if backend == "api":
            import anthropic
            _load_dotenv()
            self.client = anthropic.Anthropic(max_retries=4, timeout=1800)
        elif backend != "claude_cli":
            raise ValueError(f"unknown backend {backend!r}")

    # ------------------------------------------------------------------ accounting
    def _record(self, role: str, model: str, u: Usage) -> Usage:
        with self._lock:
            for k in ("input", "output", "cache_write", "cache_read", "usd"):
                setattr(self.total, k, getattr(self.total, k) + getattr(u, k))
            if self.ledger_path:
                with self.ledger_path.open("a") as f:
                    f.write(json.dumps({"role": role, "model": model, "backend": self.backend,
                                        **u.__dict__}) + "\n")
        return u

    # ------------------------------------------------------------------ public
    def call(self, *, role: str, model: str, effort: str, system: list[dict] | str,
             messages: list[dict], json_schema: dict | None = None,
             max_tokens: int = 64000) -> tuple[str, Usage]:
        """Returns (final text, usage). With json_schema, the text is valid JSON for the schema.
        `messages` must be a single user message (content: str or list of text/image blocks)."""
        if len(messages) != 1 or messages[0]["role"] != "user":
            raise ValueError("call() takes exactly one user message")
        if self.backend == "api":
            return self._call_api(role, model, effort, system, messages, json_schema, max_tokens)
        return self._call_cli(role, model, effort, system, messages[0], json_schema, max_tokens)

    # ------------------------------------------------------------------ claude CLI
    def _call_cli(self, role, model, effort, system, message, json_schema, max_tokens):
        env = {k: v for k, v in os.environ.items()
               if k not in {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE"}}
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_tokens)
        content = message["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        content = [{k: v for k, v in b.items() if k != "cache_control"} for b in content]
        stdin = json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"
        with tempfile.TemporaryDirectory(prefix="rsi-cli-") as tmp:
            sys_file = Path(tmp) / "system.md"
            sys_file.write_text(_system_text(system))
            cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                   "--verbose", "--model", model, "--effort", effort, "--tools", "",
                   "--system-prompt-file", str(sys_file), "--no-session-persistence",
                   "--strict-mcp-config", "--disable-slash-commands", "--setting-sources", ""]
            if json_schema is not None:
                cmd += ["--json-schema", json.dumps(json_schema)]
            last_err = ""
            for attempt in range(4):
                try:
                    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=env,
                                       cwd=tmp, timeout=self.cli_timeout_s)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"{role}: claude CLI timed out after {self.cli_timeout_s}s")
                result = None
                texts: list[str] = []  # `result` holds only the LAST text block; collect them all
                for line in p.stdout.splitlines():
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("type") == "assistant":
                        texts += [b.get("text", "") for b in ev.get("message", {}).get("content", [])
                                  if b.get("type") == "text"]
                    elif ev.get("type") == "result":
                        result = ev
                if result is None:
                    last_err = f"claude CLI exit {p.returncode}: {p.stderr[-1500:] or p.stdout[-1500:]}"
                elif result.get("is_error") or result.get("subtype") != "success":
                    last_err = f"claude CLI error: {result.get('result') or result.get('subtype')} " \
                               f"(api status {result.get('api_error_status')})"
                    status = result.get("api_error_status")
                    msg = str(result.get("result", "")).lower()
                    if "output token maximum" in msg:
                        raise OutputTooLongError(f"{role}: {last_err}")  # same request would fail again
                    if status in (400, 401, 403, 404) or "limit" in msg or "login" in msg:
                        raise LLMFatalError(f"{role}: {last_err}")
                else:
                    u = result.get("usage") or {}
                    usage = self._record(role, model, Usage(
                        input=u.get("input_tokens", 0), output=u.get("output_tokens", 0),
                        cache_write=u.get("cache_creation_input_tokens", 0),
                        cache_read=u.get("cache_read_input_tokens", 0),
                        usd=float(result.get("total_cost_usd") or 0.0)))
                    if json_schema is not None:
                        so = result.get("structured_output")
                        text = json.dumps(so) if so is not None else result.get("result", "")
                    else:
                        text = "\n".join(texts) if texts else result.get("result", "")
                    if result.get("stop_reason") == "max_tokens":
                        raise OutputTooLongError(f"{role}: output truncated at max_tokens={max_tokens}")
                    return text, usage
                time.sleep(15 * (attempt + 1))
            raise RuntimeError(f"{role}: {last_err}")

    # ------------------------------------------------------------------ Anthropic API
    def _call_api(self, role, model, effort, system, messages, json_schema, max_tokens):
        import anthropic
        output_config: dict = {"effort": effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        try:
            with self.client.beta.messages.stream(
                model=model, max_tokens=max_tokens, system=system, messages=messages,
                thinking={"type": "adaptive"}, output_config=output_config,
                betas=[FALLBACK_BETA], fallbacks="default",
            ) as stream:
                msg = stream.get_final_message()
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                anthropic.BadRequestError, anthropic.NotFoundError) as e:
            raise LLMFatalError(f"{role}: {e}") from e
        p = self.pricing.get(model, {"input": 4, "output": 20, "cache_write": 5, "cache_read": 0.2})
        u = msg.usage
        usage = Usage(input=u.input_tokens or 0, output=u.output_tokens or 0,
                      cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
                      cache_read=getattr(u, "cache_read_input_tokens", 0) or 0)
        usage.usd = (usage.input * p["input"] + usage.output * p["output"]
                     + usage.cache_write * p["cache_write"] + usage.cache_read * p["cache_read"]) / 1e6
        self._record(role, model, usage)
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"{role}: request refused ({getattr(msg, 'stop_details', None)})")
        if msg.stop_reason == "max_tokens":
            raise OutputTooLongError(f"{role}: hit max_tokens={max_tokens}; output truncated")
        return "".join(b.text for b in msg.content if b.type == "text"), usage


def cached_text(text: str) -> dict:
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}


def image_block(path: Path) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(path.read_bytes()).decode()}}
