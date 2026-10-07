"""Every fresh reply is checked against the stage's schema (B2, 7 Oct): one repair, then an error.
Only a reply that passes is cached."""

import io
import json

import pytest

from regcomp import llm

SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["covered", "partial", "missing"]}},
    "required": ["verdict"],
}


class FakeConn:
    def __init__(self):
        self.inserted = []

    def execute(self, sql, params):
        if sql.startswith("INSERT"):
            self.inserted.append(params)
        return self

    def fetchone(self):
        return None


def _hosted(monkeypatch, replies: list[str]) -> list:
    monkeypatch.setenv("REGCOMP_MODEL_JUDGE", "groq:test-model")
    monkeypatch.setenv("STRONG_MODEL_API_KEY", "test-key-not-real")
    sent = []

    def fake_urlopen(req, timeout):
        sent.append(json.loads(req.data))
        body = {"choices": [{"message": {"content": replies[len(sent) - 1]}}], "usage": {}}
        return io.BytesIO(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_a_schema_miss_gets_one_repair_and_only_the_valid_reply_is_cached(monkeypatch):
    sent = _hosted(monkeypatch, ['{"verdict": "Covered"}', '{"verdict": "covered"}'])
    conn = FakeConn()
    assert llm.complete_json("judge", "sys", "user", SCHEMA, conn=conn) == {"verdict": "covered"}
    assert len(sent) == 2
    repair = sent[1]["messages"][-1]["content"]
    assert "does not match the schema at verdict" in repair and "corrected JSON" in repair
    (params,) = conn.inserted
    assert params[4].obj == {"verdict": "covered"}  # the repaired reply, never the first


def test_a_reply_still_wrong_after_the_repair_is_an_error_and_is_not_cached(monkeypatch):
    _hosted(monkeypatch, ['{"verdict": "unsure"}', '{"other": 1}'])
    conn = FakeConn()
    with pytest.raises(llm.LLMError, match="judge: still wrong after one repair"):
        llm.complete_json("judge", "sys", "user", SCHEMA, conn=conn)
    assert conn.inserted == []


def test_a_valid_reply_needs_no_repair(monkeypatch):
    sent = _hosted(monkeypatch, ['{"verdict": "missing"}'])
    assert llm.complete_json("judge", "s", "u", SCHEMA, conn=FakeConn()) == {"verdict": "missing"}
    assert len(sent) == 1
