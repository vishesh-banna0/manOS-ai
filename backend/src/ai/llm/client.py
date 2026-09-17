"""
File: client.py

Purpose:
Provider-agnostic LLM client that returns validated JSON.

Why this exists:
Models are unreliable at free-form tool calling but reasonably good at "fill in
this JSON shape" when you constrain the decoder. This client asks the provider
for JSON, validates the parsed payload against a lightweight schema, and
retries with the validation error appended to the prompt. That is what makes
the agent state machine dependable enough to build on - each node gets a typed
result or a clean failure, never half-parsed prose.

Providers:
    settings.LLM_PROVIDER = "openrouter"  -> hosted, chat completions API
    settings.LLM_PROVIDER = "ollama"      -> local /api/generate

Only _raw_generate() knows which one is active. Everything above it - retries,
JSON extraction, validation, tracing - is shared, so the agents never branch on
provider. settings.LLM_FALLBACK_PROVIDER (default off) retries a transient
failure on the other provider.

Note: embeddings are not routed here. OpenRouter has no embeddings endpoint, so
ai/embeddings/embedding_generator.py always talks to Ollama.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

from ...core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER = "openrouter"
OLLAMA = "ollama"


class LLMUnavailable(RuntimeError):
    """The provider could not be reached, or refused the request outright."""


class LLMTransient(LLMUnavailable):
    """
    A failure worth retrying: timeout, rate limit, 5xx, connection reset.

    Subclasses LLMUnavailable so the existing `except LLMUnavailable` handlers
    in the agents and API routes keep working unchanged.
    """


class LLMInvalidOutput(RuntimeError):
    """The model returned output that never validated against the schema."""


class LLMMalformedJSON(ValueError):
    """
    Model output was not parseable JSON.

    str() carries a snippet of the response, because that gets fed back to the
    model on retry. `safe_message` is the redacted form used for logging - the
    raw snippet can contain document text.
    """

    def __init__(self, message: str, safe_message: str):
        super().__init__(message)
        self.safe_message = safe_message


# ------------------------------------------------------------------ redaction


def _scrub(text: str) -> str:
    """Strip the API key out of anything that might be logged or returned."""
    key = settings.OPENROUTER_API_KEY
    if key and key in text:
        text = text.replace(key, "***")
    # Belt and braces: anything shaped like an OpenRouter key.
    return re.sub(r"sk-or-[A-Za-z0-9\-_]+", "***", text)


def _safe_error(exc: BaseException) -> str:
    """A log-safe one-line description of a failure."""
    message = getattr(exc, "safe_message", None) or str(exc)
    return _scrub(message)[:200]


# ------------------------------------------------------------ system prompts

# Each agent has a clearly separated responsibility. The node label that every
# call site already passes selects the system prompt, so no call site changed.
_SYSTEM_PROMPTS: Dict[str, str] = {
    "planner": (
        "You are the PLANNER in a flashcard authoring pipeline. You decide "
        "which concepts in the supplied corpus deserve flashcards and how many "
        "each warrants. You do not write flashcards yourself. Plan only over "
        "concepts that appear in the supplied context; never invent topics. "
        "Return only the requested JSON."
    ),
    "author": (
        "You are the AUTHOR in a flashcard authoring pipeline. You write "
        "flashcards using ONLY the retrieved context supplied in the prompt. "
        "You never add outside knowledge, never infer beyond what the context "
        "states, and write fewer cards rather than inventing facts. Every "
        "answer must be traceable to a quoted sentence in the context. "
        "Return only the requested JSON."
    ),
    "critic": (
        "You are the CRITIC in a flashcard authoring pipeline. You check each "
        "flashcard against the retrieved context and identify unsupported "
        "claims. A statement that is true in general but absent from the "
        "context is unsupported and must not be accepted. You also check "
        "answer correctness, clarity, self-containment and duplication. You "
        "are strict: plausibility is not grounding. Return only the requested "
        "JSON."
    ),
    "repair": (
        "You are the REPAIR agent in a flashcard authoring pipeline. You fix "
        "the specific defect the critic named, using ONLY the retrieved "
        "context. Where a claim was unsupported, correct it to what the "
        "context actually says or drop it - do not paraphrase the same "
        "unsupported claim in new words. Preserve whatever was already "
        "correct. Return only the requested JSON."
    ),
    "revision_planner": (
        "You are the REVISION PLANNER. Given a learner's review history you "
        "decide per topic whether to reteach, drill, reschedule or promote, "
        "based only on the supplied statistics. Return only the requested JSON."
    ),
    "recommender": (
        "You are the RECOMMENDER. You give study advice anchored to the "
        "supplied performance evidence, never generic advice. Return only the "
        "requested JSON."
    ),
}

_DEFAULT_SYSTEM = (
    "You answer strictly in the JSON shape requested. No prose, no markdown."
)


def system_prompt_for(node: str) -> str:
    return _SYSTEM_PROMPTS.get(node, _DEFAULT_SYSTEM)


# ------------------------------------------------------------- health checks


def available(model: Optional[str] = None) -> bool:
    """Check that the active provider is reachable and the model is usable."""
    if settings.LLM_PROVIDER == OPENROUTER:
        if not settings.OPENROUTER_API_KEY:
            return False
        try:
            response = requests.get(
                f"{settings.OPENROUTER_URL}/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                timeout=5,
            )
            if response.status_code != 200:
                return False
            if model is None:
                return True
            ids = {m.get("id", "") for m in response.json().get("data", [])}
            return model in ids
        except (requests.RequestException, ValueError):
            return False

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
    """Models this deployment uses - not the provider's whole catalogue."""
    if settings.LLM_PROVIDER == OPENROUTER:
        return sorted({settings.LLM_MODEL, settings.CRITIC_MODEL})
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            return []
        return [m.get("name", "") for m in response.json().get("models", [])]
    except requests.RequestException:
        return []


# ------------------------------------------------------------- JSON handling


def _extract_json(raw: str) -> Any:
    """
    Parse JSON from a model response.

    JSON mode usually yields clean JSON, but models still occasionally wrap it
    in prose or a code fence, so fall back to bracket slicing.
    """
    raw = (raw or "").strip()
    if not raw:
        raise LLMMalformedJSON("empty response", "empty response")

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

    raise LLMMalformedJSON(
        f"no JSON object found in response: {raw[:200]}",
        f"no JSON object found in response ({len(raw)} chars)",
    )


# ----------------------------------------------------------------- providers

# Models that reject `response_format`. Populated at runtime the first time a
# model 400s on it, so later calls skip it instead of failing again. Every
# prompt already says "return only JSON" and _extract_json copes with prose, so
# dropping JSON mode degrades output slightly rather than breaking the run.
_no_json_mode: set = set()


def _openrouter_generate(
    prompt: str, model: str, temperature: float, json_mode: bool, system: Optional[str]
) -> str:
    if not settings.OPENROUTER_API_KEY:
        raise LLMUnavailable(
            "OPENROUTER_API_KEY is not set. Add it to .env, or set "
            "LLM_PROVIDER=ollama to use local models."
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode and model not in _no_json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(
            f"{settings.OPENROUTER_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "X-Title": "Manos AI",
            },
            timeout=settings.LLM_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise LLMTransient(
            f"OpenRouter timed out after {settings.LLM_TIMEOUT}s"
        ) from exc
    except requests.RequestException as exc:
        raise LLMTransient(f"OpenRouter request failed: {_scrub(str(exc))}") from exc

    status = response.status_code
    body = _scrub(response.text[:300])

    if status in (401, 403):
        # Not retryable - a bad key will still be bad in two seconds.
        raise LLMUnavailable(
            f"OpenRouter rejected the credentials (HTTP {status}). "
            "Check OPENROUTER_API_KEY."
        )
    if status == 404:
        raise LLMUnavailable(f"Model '{model}' is not available on OpenRouter")
    if status == 429:
        retry_after = response.headers.get("Retry-After")
        raise LLMTransient(
            f"OpenRouter rate limited (retry-after={retry_after or 'n/a'})"
        )
    if status == 400 and "response_format" in body and model not in _no_json_mode:
        # This model does not support JSON mode. Remember it, retry without.
        _no_json_mode.add(model)
        logger.warning(
            "model %s rejected response_format; falling back to prompt-only JSON",
            model,
        )
        return _openrouter_generate(prompt, model, temperature, json_mode, system)
    if status >= 500:
        raise LLMTransient(f"OpenRouter HTTP {status}: {body}")
    if status != 200:
        raise LLMUnavailable(f"OpenRouter HTTP {status}: {body}")

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMTransient("OpenRouter returned a non-JSON body") from exc

    # Upstream provider errors can arrive inside a 200 envelope.
    error = data.get("error")
    if isinstance(error, dict):
        raise LLMTransient(
            f"OpenRouter upstream error: {_scrub(str(error.get('message')))[:200]}"
        )

    choices = data.get("choices")
    if not choices:
        raise LLMTransient("OpenRouter returned no choices")

    return (choices[0].get("message") or {}).get("content") or ""


def _ollama_generate(
    prompt: str, model: str, temperature: float, json_mode: bool, system: Optional[str]
) -> str:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"

    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json=payload,
            timeout=settings.LLM_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise LLMTransient(f"Ollama timed out after {settings.LLM_TIMEOUT}s") from exc
    except requests.RequestException as exc:
        raise LLMTransient(f"Ollama request failed: {exc}") from exc

    if response.status_code == 404:
        raise LLMUnavailable(f"Model '{model}' is not available in Ollama")
    if response.status_code >= 500:
        raise LLMTransient(
            f"Ollama HTTP {response.status_code}: {response.text[:200]}"
        )
    if response.status_code != 200:
        raise LLMUnavailable(
            f"Ollama HTTP {response.status_code}: {response.text[:200]}"
        )

    return response.json().get("response", "")


_PROVIDERS: Dict[str, Callable[..., str]] = {
    OPENROUTER: _openrouter_generate,
    OLLAMA: _ollama_generate,
}


def _model_for(provider: str, node: str) -> str:
    """The model to use on a given provider - needed when falling back."""
    if provider == settings.LLM_PROVIDER:
        return settings.CRITIC_MODEL if node == "critic" else settings.LLM_MODEL
    if provider == OLLAMA:
        return settings.OLLAMA_CRITIC_MODEL if node == "critic" else settings.OLLAMA_MODEL
    return settings.OPENROUTER_MODEL


def _raw_generate(
    prompt: str,
    model: str,
    temperature: float,
    json_mode: bool,
    system: Optional[str] = None,
    node: str = "llm",
) -> str:
    """Dispatch to the active provider, with an optional fallback provider."""
    provider = settings.LLM_PROVIDER
    generate = _PROVIDERS.get(provider)
    if generate is None:
        raise LLMUnavailable(
            f"Unknown LLM_PROVIDER {provider!r}. Use 'openrouter' or 'ollama'."
        )

    try:
        return generate(prompt, model, temperature, json_mode, system)
    except LLMTransient as exc:
        fallback = settings.LLM_FALLBACK_PROVIDER
        if not fallback or fallback == provider or fallback not in _PROVIDERS:
            raise
        logger.warning(
            "node=%s provider=%s failed (%s); trying fallback provider=%s",
            node,
            provider,
            _safe_error(exc),
            fallback,
        )
        return _PROVIDERS[fallback](
            prompt, _model_for(fallback, node), temperature, json_mode, system
        )


# ------------------------------------------------------------------- tracing


@dataclass
class LLMCall:
    """One request/response pair, retained for agent traces."""

    node: str
    model: str
    ok: bool
    attempts: int
    error: Optional[str] = None
    duration_ms: int = 0
    provider: str = ""


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
            "retries": sum(max(0, c.attempts - 1) for c in self.calls),
            "by_node": {
                node: sum(1 for c in self.calls if c.node == node)
                for node in {c.node for c in self.calls}
            },
        }


# ------------------------------------------------------------ public helpers


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter, capped. Bounded by the retry budget."""
    delay = min(settings.LLM_BACKOFF_BASE * (2**attempt), settings.LLM_BACKOFF_MAX)
    return delay * (0.5 + random.random() / 2)


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

    Two failure modes share one bounded retry budget:
      - schema/parse failures retry immediately, with the error fed back
      - transient provider failures (429 / 5xx / timeout) retry after a backoff

    Args:
        prompt: the instruction, which must describe the JSON shape
        validator: callable that returns a normalised value or raises ValueError
        node: label for tracing which agent step made the call; also selects
              the system prompt
        model: override the provider's configured model
        trace: optional LLMTrace to record attempts on

    Raises:
        LLMUnavailable: provider unreachable, credentials rejected, or the
            transient retry budget was exhausted
        LLMInvalidOutput: never produced schema-valid JSON within the retries
    """
    model = model or settings.LLM_MODEL
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    max_retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries
    system = system_prompt_for(node)

    started = time.time()
    attempt_prompt = prompt
    last_error: Optional[str] = None

    def _record(ok: bool, attempts: int, error: Optional[str] = None) -> None:
        duration = int((time.time() - started) * 1000)
        if trace:
            trace.add(
                LLMCall(
                    node=node,
                    model=model,
                    ok=ok,
                    attempts=attempts,
                    error=error,
                    duration_ms=duration,
                    provider=settings.LLM_PROVIDER,
                )
            )
        if ok:
            logger.info(
                "node=%s provider=%s model=%s ok attempts=%d latency_ms=%d",
                node,
                settings.LLM_PROVIDER,
                model,
                attempts,
                duration,
            )
        else:
            logger.error(
                "node=%s provider=%s model=%s FAILED attempts=%d latency_ms=%d reason=%s",
                node,
                settings.LLM_PROVIDER,
                model,
                attempts,
                duration,
                error,
            )

    for attempt in range(max_retries + 1):
        try:
            raw = _raw_generate(attempt_prompt, model, temperature, True, system, node)
            parsed = _extract_json(raw)
            value = validator(parsed)
        except LLMTransient as exc:
            last_error = _safe_error(exc)
            if attempt >= max_retries:
                _record(False, attempt + 1, last_error)
                raise LLMUnavailable(
                    f"{node}: provider failed after {attempt + 1} attempts: {last_error}"
                ) from exc
            delay = _backoff_seconds(attempt)
            logger.warning(
                "node=%s transient failure (%s); retry %d/%d in %.1fs",
                node,
                last_error,
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)
            continue
        except LLMUnavailable as exc:
            # Not retryable: bad credentials, missing model, bad provider name.
            _record(False, attempt + 1, _safe_error(exc))
            raise
        except (ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
            logger.warning(
                "node=%s validation failure on attempt %d/%d: %s",
                node,
                attempt + 1,
                max_retries + 1,
                _safe_error(exc),
            )
            # Feed the failure back so the retry can correct itself.
            attempt_prompt = (
                f"{prompt}\n\n"
                f"Your previous response was rejected: {last_error}\n"
                f"Return ONLY valid JSON matching the requested shape."
            )
            continue

        _record(True, attempt + 1)
        return value

    _record(False, max_retries + 1, _scrub(last_error or "unknown")[:200])
    raise LLMInvalidOutput(
        f"{node}: model '{model}' produced no valid JSON after "
        f"{max_retries + 1} attempts. Last error: {_scrub(last_error or 'unknown')}"
    )


def generate_text(
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    node: str = "llm",
) -> str:
    """Plain text completion, used where JSON structure is not needed."""
    return _raw_generate(
        prompt,
        model or settings.LLM_MODEL,
        settings.LLM_TEMPERATURE if temperature is None else temperature,
        False,
        system_prompt_for(node),
        node,
    )
