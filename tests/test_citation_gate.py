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
