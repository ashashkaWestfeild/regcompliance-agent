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


class _ReadOnlyConn:
    """Answers the two reads of preview_batch; any write would fail the test."""

    def __init__(self, previous):
        self.previous = previous

    def execute(self, sql, params=()):
        assert sql.lstrip().upper().startswith("SELECT"), f"preview must not write: {sql}"
        rows = [("control-1",)] if "FROM mapping" in sql else [(self.previous,)]
        return type("R", (), {"fetchone": lambda _self: rows[0] if rows[0][0] else None})()


def test_preview_batch_reads_only_and_reports_the_change():
    from pathlib import Path

    import yaml

    from regcomp.monitor import preview_batch

    folder = Path("data/evidence/nainital/batches")
    entries = {e["file"]: e for e in yaml.safe_load((folder / "manifest_2026-10.yaml").read_text())}
    rekyc = entries["rekyc_updation_log_2026-10.csv"]
    out = preview_batch(_ReadOnlyConn("effective"), rekyc, folder / rekyc["file"])
    assert (out["result"], out["change"]) == ("ineffective", "newly_failing")
    assert "121/1200" in out["figures"]
    ckycr = entries["ckycr_upload_log_2026-10.csv"]
    out = preview_batch(_ReadOnlyConn("ineffective"), ckycr, folder / ckycr["file"])
    assert (out["result"], out["change"]) == ("effective", "recovered")
    assert "review queue" in out["would"]
