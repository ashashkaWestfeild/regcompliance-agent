from regcomp.lock import differences, digest


def _snap(**over):
    base = {
        "summary": ["planted gaps detected 5/7"],
        "planted": [["N01", "yes", "high", True, ["missing_control"]]],
        "decoys": [["N-D01", False, "-"]],
        "injections": [["N-I01", True]],
        "real": [["R01", "no_gap", "correct"]],
        "evidence": ["- evidence rows correct 2/2"],
        "obligations": [["42(1)", 10, 90, "policy"]],
        "mappings": [["42(1)", 10, 90, "partial", 5, 50, "auto"]],
        "gaps": [["42(1)", 10, 90, "weak_threshold", "high", "open", 5, 50]],
    }
    base.update(over)
    return base


def test_same_results_compare_equal_whatever_the_row_order():
    a = _snap(
        gaps=[
            ["1", 0, 5, "narrow_scope", "high", "open", 1, 2],
            ["2", 6, 9, "x", "review", "open", 3, 4],
        ]
    )
    b = _snap(gaps=list(reversed(a["gaps"])))
    assert differences(a, b) == []
    assert digest(a) == digest(b)


def test_a_tier_change_is_reported():
    a = _snap()
    b = _snap(gaps=[["42(1)", 10, 90, "weak_threshold", "review", "open", 5, 50]])
    out = differences(a, b)
    assert out[0] == "gaps: 1 row(s) no longer present, 1 new"
    assert digest(a) != digest(b)


def test_a_score_line_change_is_reported():
    out = differences(_snap(), _snap(summary=["planted gaps detected 4/7"]))
    assert out[0] == "summary changed:"
    assert any("5/7" in line for line in out) and any("4/7" in line for line in out)


def test_duplicate_rows_are_counted_not_collapsed():
    row = ["42(1)", 10, 90, "partial", 5, 50, "auto"]
    out = differences(_snap(mappings=[row, row]), _snap(mappings=[row]))
    assert out[0] == "mappings: 1 row(s) no longer present, 0 new"
