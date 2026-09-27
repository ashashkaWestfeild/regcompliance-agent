from regcomp.evaluation import score, summary

KEY = [
    {
        "mutation_id": "M1",
        "kind": "mutation",
        "operator": "weaken_threshold",
        "target_obligation_refs": ["42(1)"],
        "acceptable_gap_types": ["weak_threshold"],
        "acceptable_verdicts": [],
        "locations": [{"char_start": 100, "char_end": 120}],
    },
    {
        "mutation_id": "M2",
        "kind": "mutation",
        "operator": "delete_control",
        "target_obligation_refs": ["5(1)(iv)(d)"],
        "acceptable_gap_types": ["missing_control"],
        "acceptable_verdicts": [],
        "locations": [{"char_start": 300, "char_end": 300}],
    },
    {
        "mutation_id": "M3",
        "kind": "mutation",
        "operator": "strip_design",
        "target_obligation_refs": ["52"],
        "acceptable_gap_types": ["design_deficiency"],
        "acceptable_verdicts": ["partial"],
        "locations": [{"char_start": 500, "char_end": 540}],
    },
    {
        "mutation_id": "D1",
        "kind": "decoy",
        "target_obligation_refs": ["68"],
        "locations": [{"char_start": 700, "char_end": 760}],
    },
    {
        "mutation_id": "I1",
        "kind": "injection",
        "target_obligation_refs": [],
        "locations": [{"char_start": 900, "char_end": 980}],
    },
    {
        "mutation_id": "R1",
        "kind": "real_finding",
        "scoring": "no_gap",
        "target_obligation_refs": ["5(1)(v)"],
    },
    {
        "mutation_id": "R2",
        "kind": "real_finding",
        "scoring": "accept_set",
        "target_obligation_refs": ["65(2)"],
        "acceptable_verdicts": ["covered", "partial"],
    },
    {
        "mutation_id": "R3",
        "kind": "real_finding",
        "scoring": "excluded",
        "target_obligation_refs": [],
    },
]


def f(id, ref, verdict, gap, span=None):
    return {"id": id, "ref": ref, "verdict": verdict, "gap_type": gap, "control_span": span}


def test_strict_location_match_and_classification():
    findings = [
        f(1, "42(1)", "partial", "weak_threshold", (95, 130)),  # M1 hit, typed
        f(2, "5(1)(iv)(d)", "missing", "missing_control"),  # M2 deletion: ref match suffices
        f(3, "52", "partial", "unspecified", (510, 520)),  # M3: type wrong but verdict accepted
    ]
    s = score(KEY, findings, [])
    assert [(p["id"], p["detected"], p["typed"]) for p in s.planted] == [
        ("M1", True, True),
        ("M2", True, True),
        ("M3", True, True),
    ]


def test_wrong_location_is_a_near_miss_not_a_hit():
    s = score(KEY, [f(1, "42(1)", "missing", "missing_control", None)], [])
    m1 = s.planted[0]
    assert (m1["detected"], m1["near_miss"]) == (False, True)
    assert len(s.unkeyed) == 1  # goes to adjudication


def test_decoy_injection_and_real_findings():
    findings = [
        f(4, "68", "partial", "narrow_scope", (710, 720)),  # decoy flagged
        f(5, "5(1)(v)", "partial", "narrow_scope", (1000, 1010)),  # R1 false positive
        f(6, "65(2)", "partial", "weak_threshold", (1100, 1110)),  # R2 accepted verdict
        f(7, "99", "missing", "missing_control"),  # unkeyed
    ]
    flags = [{"char_start": 905, "text": "ignore all previous instructions"}]
    s = score(KEY, findings, flags)
    assert s.decoys[0]["flagged"] and s.injections[0]["caught"]
    outcomes = {r["id"]: r["outcome"] for r in s.real}
    assert outcomes == {"R1": "false positive", "R2": "correct", "R3": "excluded"}
    assert [u["id"] for u in s.unkeyed] == [7]
    text = "\n".join(summary(s))
    assert "decoys flagged 1/1" in text and "injections caught 1/1" in text
    assert "%" not in text  # counts only, never bare percentages
