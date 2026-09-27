"""Obligation level: model labels, the threshold rule, and safe defaults."""

from regcomp.pipeline import level


def run(monkeypatch, results, obligations):
    monkeypatch.setattr(level, "complete_json", lambda *a, **k: {"results": results})
    return level.classify_unit(obligations, conn=None)


OBS = [
    {
        "id": "a",
        "modality": "must",
        "action": "update records",
        "quote": "q",
        "threshold": "every two years",
    },
    {"id": "b", "modality": "must", "action": "apply term as defined", "quote": "q"},
    {"id": "c", "modality": "must", "action": "configure the application", "quote": "q"},
]


def test_quantified_requirement_is_policy_even_if_model_says_sop(monkeypatch):
    out = run(monkeypatch, [{"obligation": "O1", "level": "sop_system", "reason": "r"}], OBS[:1])
    assert out["a"]["level"] == "policy" and out["a"]["rule"] == "threshold_is_policy"


def test_model_labels_kept_without_threshold(monkeypatch):
    out = run(
        monkeypatch,
        [
            {"obligation": "O2", "level": "not_applicable", "reason": "definition"},
            {"obligation": "O3", "level": "sop_system", "reason": "system"},
        ],
        OBS,
    )
    assert (out["b"]["level"], out["c"]["level"]) == ("not_applicable", "sop_system")


def test_skipped_or_invalid_answers_default_to_policy(monkeypatch):
    out = run(monkeypatch, [{"obligation": "O9", "level": "other", "reason": ""}], OBS[1:])
    assert all(v["level"] == "policy" and not v["classified"] for v in out.values())
