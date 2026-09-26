from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from regcomp.schemas import (
    ControlTest, ControlTestKind, ControlTestResult, JudgeOutput, Mapping,
    ReviewStatus, Span, Verdict,
)

DOC = uuid4()


def span(q="shall verify"):
    return Span(document_id=DOC, char_start=10, char_end=10 + len(q), quote=q)


def judge(v=Verdict.MISSING):
    return JudgeOutput(judge="cheap", verdict=v, confidence=0.9, rationale="r")


def mapping(**kw):
    base = dict(key="m1", source_version="v1", effective_from=date(2024, 1, 1),
                obligation_id=uuid4(), control_id=None, verdict=Verdict.MISSING,
                rationale="r", obligation_citations=[span()], judges=[judge()],
                confidence=0.9, status=ReviewStatus.AUTO)
    return Mapping(**(base | kw))


def test_span_length_must_match_quote():
    with pytest.raises(ValidationError):
        Span(document_id=DOC, char_start=0, char_end=5, quote="abc")


def test_missing_mapping_has_no_control():
    assert mapping().control_id is None
    with pytest.raises(ValidationError):
        mapping(control_id=uuid4())


def test_covered_mapping_needs_control_citations():
    with pytest.raises(ValidationError):
        mapping(verdict=Verdict.COVERED, control_id=uuid4())
    m = mapping(verdict=Verdict.COVERED, control_id=uuid4(), control_citations=[span()])
    assert m.verdict is Verdict.COVERED


def test_effective_interval_order():
    with pytest.raises(ValidationError):
        mapping(effective_to=date(2023, 1, 1))


def test_operating_test_without_evidence_must_be_cannot_assess():
    with pytest.raises(ValidationError):
        ControlTest(control_id=uuid4(), kind=ControlTestKind.OPERATING,
                    result=ControlTestResult.EFFECTIVE, rationale="r")
    ok = ControlTest(control_id=uuid4(), kind=ControlTestKind.OPERATING,
                     result=ControlTestResult.CANNOT_ASSESS, rationale="no evidence")
    assert ok.result is ControlTestResult.CANNOT_ASSESS
