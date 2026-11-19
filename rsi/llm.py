"""Thin Anthropic client wrapper: streaming, adaptive thinking, effort, refusal fallback,
prompt caching, structured JSON output, and a running USD cost ledger."""
from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import anthropic

FALLBACK_BETA = "server-side-fallback-2026-07-01"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


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


class LLM:
    def __init__(self, pricing: dict, ledger_path: Path | None = None):
        _load_dotenv()
        self.client = anthropic.Anthropic(max_retries=4, timeout=1800)
        self.pricing = pricing
        self.total = Usage()
        self.ledger_path = ledger_path
        self._lock = threading.Lock()

    def _account(self, model: str, role: str, usage) -> Usage:
        p = self.pricing.get(model, {"input": 4, "output": 20, "cache_write": 5, "cache_read": 0.2})
        u = Usage(
            input=usage.input_tokens or 0,
            output=usage.output_tokens or 0,
            cache_write=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cache_read=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )
        u.usd = (u.input * p["input"] + u.output * p["output"] + u.cache_write * p["cache_write"]
                 + u.cache_read * p["cache_read"]) / 1e6
        with self._lock:
            for k in ("input", "output", "cache_write", "cache_read", "usd"):
                setattr(self.total, k, getattr(self.total, k) + getattr(u, k))
            if self.ledger_path:
                with self.ledger_path.open("a") as f:
                    f.write(json.dumps({"role": role, "model": model, **u.__dict__}) + "\n")
        return u

    def call(self, *, role: str, model: str, effort: str, system: list[dict] | str,
             messages: list[dict], json_schema: dict | None = None,
             max_tokens: int = 64000) -> tuple[str, Usage]:
        """Returns (final text, usage). With json_schema, the text is guaranteed-valid JSON."""
        output_config: dict = {"effort": effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        with self.client.beta.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config=output_config,
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
        usage = self._account(model, role, msg.usage)
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"{role}: request refused ({getattr(msg, 'stop_details', None)})")
        if msg.stop_reason == "max_tokens":
            raise RuntimeError(f"{role}: hit max_tokens={max_tokens}; output truncated")
        text = "".join(b.text for b in msg.content if b.type == "text")
        return text, usage


def cached_text(text: str) -> dict:
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}


def image_block(path: Path) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(path.read_bytes()).decode()}}
