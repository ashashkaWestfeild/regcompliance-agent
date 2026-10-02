"""Change agent part 1 on the real Sep 2026 amendment: classify, scope, approval gate, resume."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from regcomp.change.agent import build
from regcomp.change.classify import classify
from regcomp.change.diff import ClauseChange
from regcomp.change.scope import scope

V2 = "data/raw/rbi/kycdir_v2_20251229.html"
V3 = "data/raw/rbi/kycdir_v3_20260918.html"


def _change(old, new, cls="modified"):
    return classify(ClauseChange(cls, "9", "9", old, new, 0.9))


def test_effects_follow_the_changed_words():
    duty = "The bank shall verify the PAN."
    assert _change(duty, duty + " The bank may use digital storage.").effect == "advisory"
    assert _change(duty, duty + " The bank shall also obtain Form 60.").effect == "new_duty"
    assert _change("Upload within ten days.", "Upload within seven days.").effect == "threshold"
    assert _change(duty[:-1] + " and shall obtain a photograph.", duty).effect == "relaxed"
    assert _change(duty, None, "repealed").effect == "repealed"
    # A widened scope inside a duty sentence is a duty change even without its own "shall".
    wider = _change(
        "The bank shall identify individuals.", "The bank shall identify individuals and firms."
    )
    assert wider.effect == "new_duty" and wider.reanalyse


GRAPH = {
    "obligations": [
        {"id": "o1", "ref": "5(1)(v)", "action": "compare the copy", "quote": "…"},
        {"id": "o2", "ref": "16(2)", "action": "obtain a Certified Copy of the OVD", "quote": "…"},
        {"id": "o3", "ref": "65(2)", "action": "upload KYC records", "quote": "…"},
    ],
    "mappings": [
        {"id": f"m{n}", "obligation_id": o, "control_id": f"c{n}"}
        for n, o in enumerate(["o1", "o2", "o3"] + ["o3"] * 17)
    ],
    "gaps": [{"id": "g1", "obligation_id": "o2"}, {"id": "g2", "obligation_id": "o3"}],
}


def test_scope_follows_the_clause_and_the_defined_term():
    found = scope([{"ref": "5(1)(v)", "defined_term": "Certified Copy"}], GRAPH)
    assert found.direct == ["o1"] and found.by_definition == ["o2"]
    assert found.mappings == ["m0", "m1"] and found.open_gaps == ["g1"]
    assert found.blast_radius == 2 / 20 and not found.needs_approval
    assert not scope([{"ref": "5(1)", "defined_term": None}], GRAPH).by_definition


def test_sep_2026_amendment_is_an_advisory_not_a_gap():
    agent = build(lambda: GRAPH, InMemorySaver())
    out = agent.invoke(
        {"old_path": V2, "new_path": V3, "dry_run": False},
        {"configurable": {"thread_id": "fpi"}},
    )
    assert out["status"] == "planned" and out["counts"]["modified"] == 1
    (change,) = out["changes"]
    assert change["ref"] == "5(1)(v)" and change["effect"] == "advisory"
    assert change["defined_term"] == "Certified Copy" and "FPIs" in change["added"]
    assert [s["action"] for s in out["plan"]] == ["advise"]  # nothing is re-mapped


def test_identical_versions_end_without_a_plan():
    out = build(lambda: GRAPH).invoke({"old_path": V3, "new_path": V3})
    assert out["status"] == "no_change" and out["plan"] == []


def test_large_blast_radius_waits_for_a_reviewer_and_resumes(monkeypatch):
    wide = {**GRAPH, "mappings": GRAPH["mappings"][:3]}  # 1 of 3 mappings in scope: above 20%
    monkeypatch.setattr(
        "regcomp.change.agent.classify",
        lambda c, d: classify(
            ClauseChange(
                "modified", c.old_ref, c.new_ref, "x shall y.", "x shall y. z shall w.", 0.9
            ),
            d,
        ),
    )
    for answer, status in ((True, "planned"), (False, "rejected")):
        agent = build(lambda g=wide: g, InMemorySaver())
        cfg = {"configurable": {"thread_id": f"gate-{answer}"}}
        paused = agent.invoke({"old_path": V2, "new_path": V3, "dry_run": False}, cfg)
        assert paused["__interrupt__"][0].value["mappings"] == 1 and "plan" not in paused
        done = agent.invoke(Command(resume=answer), cfg)  # resumes from the checkpoint
        assert done["status"] == status
    # dry run (what-if) never pauses: it writes nothing
    dry = build(lambda: wide).invoke({"old_path": V2, "new_path": V3, "dry_run": True})
    assert dry["status"] == "planned" and "re_map" in [s["action"] for s in dry["plan"]]


class FakeTools:
    """Part 2 tools without a database or a model."""

    def __init__(self):
        self.calls = []

    def re_extract(self, new_path, refs):
        self.calls.append(("re_extract", refs))
        return [
            {"id": "new-1", "ref": "5(1)(v)", "action": "compare the copy", "level": "policy"},
            {"id": "new-2", "ref": "5(1)(v)", "action": "tell the applicant", "level": "policy"},
        ]

    def re_map(self, obligations):
        self.calls.append(("re_map", len(obligations)))
        return [
            dict(obligations[0], verdict="covered", gap_type=None, rationale="same text"),
            dict(
                obligations[1], verdict="missing", gap_type="missing_control", rationale="no text"
            ),
        ]

    def current(self, ids):
        return [
            {"id": "o1", "ref": "5(1)(v)", "action": "Compare the copy", "verdict": "partial",
             "gap_type": "narrow_scope"},
            {"id": "o9", "ref": "5(1)(v)", "action": "keep a register", "verdict": "missing",
             "gap_type": "missing_control"},
        ]  # fmt: skip


def test_part_two_projects_the_gap_delta_and_recovers_from_a_failed_step(monkeypatch):
    duty = ClauseChange(
        "modified", "5(1)(v)", "5(1)(v)", "x shall y.", "x shall y. z shall w.", 0.9
    )
    monkeypatch.setattr("regcomp.change.agent.classify", lambda c, d: classify(duty, d))
    tools = FakeTools()
    agent = build(lambda: GRAPH, InMemorySaver(), tools)
    out = agent.invoke(
        {"old_path": V2, "new_path": V3, "dry_run": True, "inject_failure": "re_map"},
        {"configurable": {"thread_id": "whatif"}},
    )
    assert out["status"] == "projected"
    assert [c[0] for c in tools.calls] == ["re_extract", "re_map"]  # the failed attempt never ran
    assert any("re_map: recovered after a failed attempt" in line for line in out["log"])
    delta = out["delta"]
    assert [g["action"] for g in delta["opened"]] == ["tell the applicant"]
    # the old narrow-scope gap closes (now covered); the retired obligation's gap closes too
    assert {g["action"] for g in delta["closed"]} == {"compare the copy", "keep a register"}
    assert (delta["gap_delta"], delta["new_obligations"], delta["retired_obligations"]) == (
        -1,
        1,
        1,
    )


def test_an_advisory_never_reaches_part_two():
    tools = FakeTools()
    out = build(lambda: GRAPH, None, tools).invoke({"old_path": V2, "new_path": V3})
    assert out["status"] == "planned" and tools.calls == [] and "delta" not in out


def test_changed_units_are_the_units_holding_the_changed_clause():
    from regcomp.change.agent import parse
    from regcomp.change.execute import changed_units

    us = changed_units(parse(V3), ["5(1)(v)"])
    assert us and all(u.ref.startswith("5(1)(v)") for u in us) and us[0].kind == "definition"
