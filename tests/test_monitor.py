"""Evidence monitoring: what a new operating result means, given the previous one."""

from regcomp.monitor import transition


def test_transitions_between_operating_results():
    assert transition(None, "ineffective") == "newly_failing"
    assert transition("effective", "ineffective") == "newly_failing"
    assert transition("ineffective", "ineffective") == "still_failing"
    # a recovery is reported, never auto-closed
    assert transition("ineffective", "effective") == "recovered"
    assert transition("effective", "effective") == transition(None, "effective") == "healthy"
    assert transition("ineffective", "cannot_assess") == "cannot_assess"
