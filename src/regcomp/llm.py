"""LLM access for every pipeline stage: strict-JSON calls to open-weights models, local (Ollama)
or hosted (an OpenAI-compatible endpoint, for the deployed app and for judge comparisons).

- Stage -> model routing lives in STAGE_MODELS (config, not code paths), so a stage can be moved
  to another open-weights model without touching callers.
- Exact-match cache in Postgres (`llm_cache`), keyed on stage, model, messages, schema and
  options. Never a semantic cache: clauses that differ only in "10 days" vs "30 days" must not
  share an answer.
- Invalid JSON or a schema miss gets one repair retry that tells the model what was wrong;
  after that the error is raised for the caller to escalate.
"""

import contextlib
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from regcomp.db import connect

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
STAGE_MODELS = {
    "extract_obligations": "qwen3:8b",
    "extract_definitions": "qwen3:8b",
    "classify_level": "qwen3:8b",
    "extract_controls": "qwen3:8b",
    "judge": "qwen3:8b",
    "draft_remediation": "qwen3:8b",
    "compare_numbers": "qwen3:8b",
}
OPTIONS = {"temperature": 0, "num_ctx": 8192}
EMBED_MODEL = "bge-m3"
# Hosted open-weights providers with an OpenAI-compatible API: prefix -> (chat URL, key variable).
# Used for the deployed app (no GPU there) and for judge comparisons; only public or synthetic
# text is ever sent. Select with REGCOMP_MODEL / REGCOMP_MODEL_<STAGE>, e.g.
# REGCOMP_MODEL_JUDGE=groq:openai/gpt-oss-120b.
HOSTED = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "STRONG_MODEL_API_KEY"),
}
MAX_RATE_WAITS = 8


class LLMError(RuntimeError):
    pass


def _cache_key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _post(path: str, body: dict, timeout: int = 600, retry: bool = True) -> dict:
    """POST to Ollama. A hung model runner (seen 27 Sep: HTTP 400 "dial tcp ... /tokenize") is
    unloaded once and the call retried; Ollama then starts a fresh runner."""
    req = urllib.request.Request(
        OLLAMA_URL + path, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"}
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.URLError as e:
        detail = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else ""
        if retry and body.get("model"):
            with contextlib.suppress(LLMError):
                _post("/api/generate", {"model": body["model"], "keep_alive": 0}, 60, False)
            return _post(path, body, timeout, retry=False)
        raise LLMError(f"Ollama unreachable at {OLLAMA_URL}: {e} {detail}".strip()) from None
    except TimeoutError:
        # A generation that runs past the timeout (seen 28 Sep: thinking mode looping for 10+
        # min). At temperature 0 a retry would loop the same way, so the caller decides.
        raise LLMError(f"{path}: no answer within {timeout}s") from None


def model_for(stage: str) -> str:
    """The model a stage uses: REGCOMP_MODEL_<STAGE>, else REGCOMP_MODEL (all stages), else
    STAGE_MODELS. A name like "groq:openai/gpt-oss-120b" is a hosted open-weights model."""
    load_dotenv()
    return (
        os.environ.get(f"REGCOMP_MODEL_{stage.upper()}")
        or os.environ.get("REGCOMP_MODEL")
        or STAGE_MODELS[stage]
    )


def _hosted_chat(model: str, messages: list[dict], schema: dict, timeout: int = 120) -> dict:
    """One chat call to an OpenAI-compatible hosted endpoint. A rate-limit answer (HTTP 429) is
    waited out, because free tiers cap tokens per minute; the key is never logged."""
    provider, name = model.split(":", 1)
    url, key_var = HOSTED[provider]
    key = os.environ.get(key_var, "").strip()
    if not key:
        raise LLMError(f"{key_var} is not set (needed for the hosted model {provider})")
    body = {
        "model": name,
        "messages": messages,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": schema},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "regcompliance-agent",
    }
    for _ in range(MAX_RATE_WAITS):
        req = urllib.request.Request(url, json.dumps(body).encode("utf-8"), headers)
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = float(e.headers.get("retry-after") or 10)
                time.sleep(min(max(wait, 1.0), 65.0))
                continue
            detail = e.read().decode("utf-8", "replace")[:200]
            raise LLMError(f"{provider} returned HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise LLMError(f"{provider} unreachable: {e}") from None
    raise LLMError(f"{provider}: still rate-limited after {MAX_RATE_WAITS} waits")


def _chat(model: str, messages: list[dict], schema: dict, think: bool) -> tuple[str, int | None]:
    """(reply text, output tokens) from the local or the hosted model."""
    if model.split(":", 1)[0] in HOSTED:
        result = _hosted_chat(model, messages, schema)
        choices = result.get("choices") or [{}]
        content = (choices[0].get("message") or {}).get("content") or ""
        return content, (result.get("usage") or {}).get("completion_tokens")
    body = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "think": think,
        "options": OPTIONS,
        "keep_alive": "30m",
    }
    result = _post("/api/chat", body)
    return (result.get("message") or {}).get("content") or "", result.get("eval_count")


_spare = None  # private cache connection used after the caller's connection drops


def _cache(sql: str, params: tuple, conn):
    """Run one cache statement; if the connection was dropped (seen 27 Sep: Neon AdminShutdown
    mid-run), retry once on a fresh private connection. Returns the cursor."""
    global _spare
    try:
        return (_spare or conn).execute(sql, params)
    except psycopg.OperationalError:
        _spare = connect(autocommit=True)
        return _spare.execute(sql, params)


def complete_json(
    stage: str, system: str, user: str, schema: dict, *, think: bool = False, conn=None
) -> dict:
    """One structured call. Returns the parsed JSON object (cached when seen before)."""
    model = model_for(stage)
    hosted = model.split(":", 1)[0] in HOSTED
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    payload = {
        "stage": stage,
        "model": model,
        "messages": messages,
        "schema": schema,
        "think": think,
        "options": {"temperature": 0} if hosted else OPTIONS,
    }
    key = _cache_key(payload)
    own = conn is None
    conn = conn or connect(autocommit=True)
    try:
        row = _cache("SELECT response FROM llm_cache WHERE key = %s", (key,), conn).fetchone()
        if row:
            return row[0]
        started = time.time()
        content, tokens = _chat(model, messages, schema, think)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as first_error:
            repair = messages + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": f"That was not valid JSON for the schema "
                    f"({first_error}). Return only the corrected JSON.",
                },
            ]
            content, tokens = _chat(model, repair, schema, think)
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                raise LLMError(f"{stage}: invalid JSON after one repair: {e}") from None
        _cache(
            "INSERT INTO llm_cache (key, stage, model, request, response, latency_ms, eval_tokens)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
            (
                key,
                stage,
                model,
                Jsonb(payload),
                Jsonb(parsed),
                int((time.time() - started) * 1000),
                tokens,
            ),
            conn,
        )
        return parsed
    finally:
        if own:
            conn.close()


def embed(texts: list[str], batch: int = 32) -> list[list[float]]:
    """bge-m3 embeddings (1024-dim) via Ollama."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        result = _post("/api/embed", {"model": EMBED_MODEL, "input": texts[i : i + batch]})
        out.extend(result["embeddings"])
    return out
