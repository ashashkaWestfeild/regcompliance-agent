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


LIST = (
    "17. Without prejudice to the above, the bank shall:\n"
    "(a) not open an account in an anonymous name;\n"
    "(b) follow the CDD Procedure for all the joint account holders, while opening a joint "
    "account;\n"
    "(c) verify the digital signature on the equivalent e-document."
)


def test_lead_in_anchor_moves_to_the_list_item_that_states_the_duty():
    from regcomp.pipeline.extract import Extracted, _gate, list_item_for
    from regcomp.pipeline.units import Unit

    raw = {
        "obligations": [
            {"action": "follow the CDD Procedure for joint account holders", "quote_start": q}
            for q in ("17. Without prejudice to the above", "(c) verify the digital signature")
        ]
        + [{"action": "maintain a register of visitors", "quote_start": "17. Without prejudice to"}]
    }
    out = Extracted()
    _gate(Unit("17", "17", LIST, 500, ""), raw, "obligations", out)
    moved, direct, unmatched = out.items
    assert moved["quote"].startswith("(b) follow the CDD Procedure") and moved["quote"][-1] == ";"
    assert moved["lead_in"].endswith("the bank shall:")
    assert LIST[moved["char_start"] - 500 : moved["char_end"] - 500] == moved["quote"]  # verbatim
    assert direct["quote"].startswith("(c) verify") and "lead_in" not in direct
    # no list item states this action: the lead-in stays the citation
    assert unmatched["quote"].endswith("the bank shall:") and "lead_in" not in unmatched
    assert list_item_for(TEXT, (7, 80), "apply a Risk Based Approach") is None  # not a lead-in
