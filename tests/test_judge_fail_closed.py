"""The judge fails closed (B1, 7 Oct): an unusable or missing answer goes to review as an
unspecified gap, never silently "no gap". Valid answers are handled exactly as before."""

from regcomp.pipeline import judge

OBS = [
    {"id": "O1", "modality": "must", "quote": "The bank shall do A.", "candidates": ["C1"]},
    {"id": "O2", "modality": "must", "quote": "The bank shall do B.", "candidates": ["C1"]},
]
CANDS = {"C1": {"quote": "The bank does A and B."}}


def _answer(obligation, verdict="covered", issue="none"):
    return {
        "obligation": obligation,
        "verdict": verdict,
        "control": "C1",
        "issue": issue,
        "rationale": "r",
        "control_quote_start": "The bank does",
        "confidence": 0.9,
    }


def _calls(monkeypatch, replies):
    seen = []

    def fake(stage, system, user, schema, think=False, conn=None):
        seen.append(user)
        return {"results": replies[len(seen) - 1]}

    monkeypatch.setattr(judge, "complete_json", fake)
    return seen


def test_valid_answers_are_unchanged(monkeypatch):
    _calls(monkeypatch, [[_answer("O1"), _answer("O2", "partial", "weaker_threshold")]])
    out = {r["obligation"]: r for r in judge.judge_unit(OBS, CANDS, None)}
    assert out["O1"]["gap_type"] is None and out["O1"]["citation_ok"]
    assert out["O2"]["gap_type"] == "weak_threshold"
    assert not any("unclear" in r for r in out.values())


def test_an_unknown_verdict_is_unclear_not_covered(monkeypatch):
    _calls(monkeypatch, [[_answer("O1", "Covered"), _answer("O2", "covered", None)]])
    out = {r["obligation"]: r for r in judge.judge_unit(OBS, CANDS, None)}
    for r in out.values():
        assert r["gap_type"] == "unspecified" and r["issue"] == "unclear"
        assert r["citation_ok"] is False and r["confidence"] == 0.0 and r["unclear"]


def test_a_left_out_obligation_is_asked_once_more(monkeypatch, capsys):
    seen = _calls(monkeypatch, [[_answer("O1")], [_answer("O2", "missing", "not_addressed")]])
    out = {r["obligation"]: r for r in judge.judge_unit(OBS, CANDS, None)}
    assert len(seen) == 2 and "[O2]" in seen[1] and "[O1]" not in seen[1]
    assert out["O2"]["gap_type"] == "missing_control"
    assert "no answer for 1 of 2 obligations (O2); asking once more" in capsys.readouterr().err


def test_left_out_twice_goes_to_review(monkeypatch, capsys):
    seen = _calls(monkeypatch, [[_answer("O1")], []])
    out = {r["obligation"]: r for r in judge.judge_unit(OBS, CANDS, None)}
    assert len(seen) == 2
    assert out["O2"]["gap_type"] == "unspecified" and "left it out, twice" in out["O2"]["unclear"]
    assert "sent to review" in capsys.readouterr().err
