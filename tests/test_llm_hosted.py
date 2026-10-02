"""Hosted open-weights path: stage routing by environment, rate-limit waits, no key in errors."""

import io
import json
import urllib.error

import pytest

from regcomp import llm

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


class FakeConn:
    """A cache that never has the answer and accepts every insert."""

    def __init__(self):
        self.inserted = []

    def execute(self, sql, params):
        if sql.startswith("INSERT"):
            self.inserted.append(params)
        return self

    def fetchone(self):
        return None


def _reply(content: str):
    body = {"choices": [{"message": {"content": content}}], "usage": {"completion_tokens": 7}}
    return io.BytesIO(json.dumps(body).encode("utf-8"))


def test_stage_model_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("REGCOMP_MODEL", raising=False)
    monkeypatch.delenv("REGCOMP_MODEL_JUDGE", raising=False)
    assert llm.model_for("judge") == llm.STAGE_MODELS["judge"]
    monkeypatch.setenv("REGCOMP_MODEL", "groq:all-stages")
    assert llm.model_for("judge") == llm.model_for("classify_level") == "groq:all-stages"
    monkeypatch.setenv("REGCOMP_MODEL_JUDGE", "groq:judge-only")
    assert llm.model_for("judge") == "groq:judge-only"


def test_hosted_call_waits_out_a_rate_limit_and_caches_under_the_hosted_model(monkeypatch):
    monkeypatch.setenv("REGCOMP_MODEL_JUDGE", "groq:openai/gpt-oss-120b")
    monkeypatch.setenv("STRONG_MODEL_API_KEY", "test-key-not-real")
    seen, waits = [], []

    def fake_urlopen(req, timeout):
        seen.append(req)
        if len(seen) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down", {"retry-after": "3"}, None)
        return _reply('{"ok": true}')

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm.time, "sleep", waits.append)
    conn = FakeConn()
    assert llm.complete_json("judge", "sys", "user", SCHEMA, conn=conn) == {"ok": True}
    assert waits == [3.0] and len(seen) == 2
    req = seen[-1]
    assert req.full_url == llm.HOSTED["groq"][0]
    assert req.get_header("Authorization") == "Bearer test-key-not-real"
    body = json.loads(req.data)
    assert body["model"] == "openai/gpt-oss-120b" and body["temperature"] == 0
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    (params,) = conn.inserted
    assert params[1:3] == ("judge", "groq:openai/gpt-oss-120b") and params[-1] == 7


def test_missing_key_and_http_errors_are_reported_without_the_key(monkeypatch):
    monkeypatch.setenv("REGCOMP_MODEL_JUDGE", "groq:m")
    monkeypatch.setenv("STRONG_MODEL_API_KEY", "")
    with pytest.raises(llm.LLMError, match="STRONG_MODEL_API_KEY is not set"):
        llm.complete_json("judge", "sys", "user", SCHEMA, conn=FakeConn())
    monkeypatch.setenv("STRONG_MODEL_API_KEY", "secret-value")

    def denied(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"invalid api key"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", denied)
    with pytest.raises(llm.LLMError) as err:
        llm.complete_json("judge", "sys", "user", SCHEMA, conn=FakeConn())
    assert "HTTP 401" in str(err.value) and "secret-value" not in str(err.value)
