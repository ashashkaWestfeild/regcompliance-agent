from regcomp.confidence import band, basis, combination, note, record


def test_basis_comes_from_stored_checks():
    assert basis("partial", "operating_failure", None, True) == "evidence_test"
    assert (
        basis(
            "partial",
            "weak_threshold",
            {"kind": "number_differs", "check": "number", "direction": "weaker"},
        )
        == "judge_and_text"
    )
    assert (
        basis(
            "covered",
            "weak_threshold",
            {"kind": "number_differs", "check": "number", "direction": "weaker"},
        )
        == "text_only"
    )
    assert (
        basis(
            "partial",
            "weak_threshold",
            {"kind": "number_differs", "check": "number", "direction": "stricter"},
        )
        == "number_not_weaker"
    )
    assert (
        basis("covered", "narrow_scope", {"kind": "adds_words", "check": "sentence"}) == "text_only"
    )
    assert (
        basis("partial", "narrow_scope", {"kind": "same", "check": "sentence"})
        == "judge_contradicted"
    )
    assert (
        basis("partial", "narrow_scope", {"kind": "loose", "check": "level"}) == "procedure_level"
    )
    assert (
        basis("partial", "narrow_scope", {"kind": "same", "check": "technical"})
        == "technical_requirement"
    )
    assert (
        basis("missing", "missing_control", {"kind": "no_similar_text", "check": "sentence"})
        == "judge_only"
    )
    assert basis("partial", "narrow_scope", None) == "judge_only"


def test_bands_cover_the_whole_range():
    assert [band(x) for x in (1.0, 0.99, 0.95, 0.94, 0.8, 0.79, 0.0)] == [
        "1.00",
        "0.95 to 0.99",
        "0.95 to 0.99",
        "0.80 to 0.94",
        "0.80 to 0.94",
        "below 0.80",
        "below 0.80",
    ]


def test_record_gives_counts_and_no_percentage_on_small_samples():
    text = record({"findings": 5, "real": 2, "real_planted": 1, "false_alarm": 1})
    assert text == (
        "Development bank: 2 of 3 adjudicated finding(s) of this kind were real gaps (1 of them "
        "gaps we planted); 2 more not adjudicated. Too few cases for a percentage."
    )
    assert "%" not in text
    assert record({"findings": 4, "real": 0, "false_alarm": 0}).endswith("none adjudicated.")
    assert record(None) == "No finding of this kind on the development bank."
    assert record({"findings": 40, "real": 30, "false_alarm": 10}).endswith("(75%).")


def test_note_never_shows_the_raw_model_confidence():
    table = {
        "combinations": {
            combination("judge_and_text", True): {"findings": 1, "real": 1, "false_alarm": 0}
        }
    }
    n = note(
        "partial", "weak_threshold", {"kind": "optional", "check": "sentence"}, False, True, table
    )
    assert n["basis"] == "judge_and_text"
    assert n["signals"][1] == "Policy citation verified against the source"
    assert n["record"].startswith("Development bank: 1 of 1 adjudicated")
    assert set(n) == {"basis", "signals", "record"}
