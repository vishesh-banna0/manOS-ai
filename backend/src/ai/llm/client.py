"""
File: client.py

Purpose:
Ollama chat/generate client that returns validated JSON.

Why this exists:
Local 7-8B models are unreliable at free-form tool calling but reasonably good
at "fill in this JSON shape" when you constrain the decoder. This client uses
Ollama's `format: json` mode, then validates the parsed payload against a
lightweight schema and retries with the validation error appended to the
prompt. That is what makes the agent state machine dependable enough to build
on - each node gets a typed result or a clean failure, never half-parsed prose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

from ...core.config import settings


class LLMUnavailable(RuntimeError):
    """Ollama could not be reached or the model is missing."""


class LLMInvalidOutput(RuntimeError):
    """The model returned output that never validated against the schema."""


@dataclass
class LLMCall:
    """One request/response pair, retained for agent traces."""

    node: str
    model: str
    ok: bool
    attempts: int
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class LLMTrace:
    """Observability record for an agent run."""

    calls: List[LLMCall] = field(default_factory=list)

    def add(self, call: LLMCall) -> None:
        self.calls.append(call)

    def summary(self) -> dict:
        return {
            "llm_calls": len(self.calls),
            "failed_calls": sum(1 for c in self.calls if not c.ok),
            "total_ms": sum(c.duration_ms for c in self.calls),
            "by_node": {
                node: sum(1 for c in self.calls if c.node == node)
                for node in {c.node for c in self.calls}
            },
        }


def available(model: Optional[str] = None) -> bool:
    """Check that Ollama is up and (optionally) that a model is pulled."""
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            return False
        if model is None:
            return True
        names = {m.get("name", "") for m in response.json().get("models", [])}
        wanted = model.split(":")[0]
        return any(name.split(":")[0] == wanted for name in names)
    except requests.RequestException:
        return False


def list_models() -> List[str]:
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            return []
        return [m.get("name", "") for m in response.json().get("models", [])]
    except requests.RequestException:
        return []


def _extract_json(raw: str) -> Any:
    """
    Parse JSON from a model response.

    `format: json` usually yields clean JSON, but models still occasionally
    wrap it in prose or a code fence, so fall back to bracket slicing.
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty response")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"no JSON object found in response: {raw[:200]}")


def _raw_generate(prompt: str, model: str, temperature: float, json_mode: bool) -> str:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"

    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json=payload,
            timeout=settings.LLM_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise LLMUnavailable(f"Ollama request failed: {exc}") from exc

    if response.status_code == 404:
        raise LLMUnavailable(f"Model '{model}' is not available in Ollama")
    if response.status_code != 200:
        raise LLMUnavailable(f"Ollama HTTP {response.status_code}: {response.text[:200]}")

    return response.json().get("response", "")


def generate_json(
    prompt: str,
    validator: Callable[[Any], Any],
    *,
    node: str = "llm",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    trace: Optional[LLMTrace] = None,
    max_retries: Optional[int] = None,
) -> Any:
    """
    Call the model and return a validated JSON payload.

    Args:
        prompt: the instruction, which must describe the JSON shape
        validator: callable that returns a normalised value or raises ValueError
        node: label for tracing which agent step made the call
        model: override settings.LLM_MODEL
        trace: optional LLMTrace to record attempts on

    Raises:
        LLMUnavailable: Ollama unreachable / model missing
        LLMInvalidOutput: never produced schema-valid JSON within the retries
    """
    import time

    model = model or settings.LLM_MODEL
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    max_retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries

    started = time.time()
    attempt_prompt = prompt
    last_error: Optional[str] = None

    for attempt in range(max_retries + 1):
        try:
            raw = _raw_generate(attempt_prompt, model, temperature, json_mode=True)
            parsed = _extract_json(raw)
            value = validator(parsed)
        except LLMUnavailable:
            if trace:
                trace.add(
                    LLMCall(
                        node=node,
                        model=model,
                        ok=False,
                        attempts=attempt + 1,
                        error="unavailable",
                        duration_ms=int((time.time() - started) * 1000),
                    )
                )
            raise
        except (ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
            # Feed the failure back so the retry can correct itself.
            attempt_prompt = (
                f"{prompt}\n\n"
                f"Your previous response was rejected: {last_error}\n"
                f"Return ONLY valid JSON matching the requested shape."
            )
            continue

        if trace:
            trace.add(
                LLMCall(
                    node=node,
                    model=model,
                    ok=True,
                    attempts=attempt + 1,
                    duration_ms=int((time.time() - started) * 1000),
                )
            )
        return value

    if trace:
        trace.add(
            LLMCall(
                node=node,
                model=model,
                ok=False,
                attempts=max_retries + 1,
                error=last_error,
                duration_ms=int((time.time() - started) * 1000),
            )
        )
    raise LLMInvalidOutput(
        f"{node}: model '{model}' produced no valid JSON after "
        f"{max_retries + 1} attempts. Last error: {last_error}"
    )


def generate_text(
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> str:
    """Plain text completion, used where JSON structure is not needed."""
    return _raw_generate(
        prompt,
        model or settings.LLM_MODEL,
        settings.LLM_TEMPERATURE if temperature is None else temperature,
        json_mode=False,
    )
