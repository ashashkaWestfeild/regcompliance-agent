from regcomp.pipeline.extract import locate, sentence_from

TEXT = "Intro. The bank shall apply a Risk Based Approach (RBA) for mitigation of risks. Next one."


def test_exact_prefix_is_preferred():
    assert locate(TEXT, "The bank shall apply a Risk Based")[2] == "exact"


def test_model_typo_is_located_but_quote_stays_verbatim():
    found = locate(TEXT, "The bank shall apply a Risk Based Approach (RBA}")
    assert found is not None and found[2] == "normalised"
    s, e = sentence_from(TEXT, "The bank shall apply a Risk Based Approach (RBA}")
    assert TEXT[s:e] == "The bank shall apply a Risk Based Approach (RBA) for mitigation of risks."


def test_whitespace_and_case_differences():
    s, e = sentence_from(TEXT, "the bank  shall apply a risk based")
    assert TEXT[s:e].startswith("The bank shall apply")


def test_unrelated_prefix_is_still_rejected():
    assert locate(TEXT, "The bank shall never apply anything") is None
    assert locate(TEXT, "too short") is None


def test_repeated_items_from_a_looping_model_are_collapsed():
    from regcomp.pipeline.extract import Extracted, _gate
    from regcomp.pipeline.units import Unit

    unit = Unit("6", "6", TEXT, 1000, "")
    item = {"action": "Apply a Risk-Based Approach", "quote_start": "The bank shall apply a Risk"}
    raw = {
        "obligations": [dict(item) for _ in range(69)]
        + [{"action": "mitigate risks", "quote_start": "The bank shall apply a Risk"}]
    }
    out = Extracted()
    _gate(unit, raw, "obligations", out)
    assert [i["action"] for i in out.items] == ["Apply a Risk-Based Approach", "mitigate risks"]
    assert out.duplicates == 68
    assert out.items[0]["char_start"] == 1000 + TEXT.index("The bank")
