"""Core domain schemas.

Traceability chain:
Regulation -> Clause -> Obligation -> (Applicability vs BankProfile) -> Mapping -> Control
-> Evidence -> ControlTest -> Gap -> Remediation, with ChangeEvent driving re-analysis.

Versioning (bitemporal):
- valid time: effective_from / effective_to -- when the rule/control is in force in the world.
- transaction time: recorded_at / superseded_at -- when this system believed it.
- `key` is the stable logical identity across versions; `id` identifies one version row.
Edges (Mapping, Gap links) reference version row ids, not keys. A new obligation version
therefore makes every mapping to the old version stale by construction, which is what
lets the change agent re-map only affected edges.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _now() -> datetime:
    return datetime.now(UTC)


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


# ---------------------------------------------------------------- enums


class DocKind(StrEnum):
    MASTER_DIRECTION = "master_direction"
    AMENDMENT = "amendment"
    CIRCULAR = "circular"
    DRAFT = "draft"  # what-if input; never committed to the live graph
    POLICY = "policy"  # bank-side document


class Modality(StrEnum):
    MUST = "must"
    MUST_NOT = "must_not"


class ThresholdKind(StrEnum):
    MONETARY = "monetary"  # e.g. cash transactions above INR 10 lakh
    DEADLINE = "deadline"  # e.g. within 7 working days
    FREQUENCY = "frequency"  # e.g. at least once every 2 years
    PERCENTAGE = "percentage"  # e.g. beneficial ownership above 10%
    COUNT = "count"


class ControlType(StrEnum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"


class ControlNature(StrEnum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    SEMI_AUTOMATED = "semi_automated"


class Verdict(StrEnum):
    COVERED = "covered"
    PARTIAL = "partial"
    MISSING = "missing"


class ReviewStatus(StrEnum):
    AUTO = "auto"  # judges agreed with high confidence
    ESCALATED = "escalated"  # sent to strong model / human queue
    REVIEWED = "reviewed"  # human decided; overrides feed back as few-shots


class ControlTestKind(StrEnum):
    DESIGN = "design"  # does the control, as written, address the obligation?
    OPERATING = "operating"  # did it actually run, per evidence?


class ControlTestResult(StrEnum):
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    CANNOT_ASSESS = "cannot_assess"  # evidence missing; never guessed


class GapType(StrEnum):
    # One-to-one with mutation operators (see docs/mutation_taxonomy.md) so the
    # answer key scores directly. OPERATING_FAILURE comes from evidence, not text.
    MISSING_CONTROL = "missing_control"
    WEAK_THRESHOLD = "weak_threshold"
    NARROW_SCOPE = "narrow_scope"
    INTERNAL_CONTRADICTION = "internal_contradiction"
    STALE_CONTROL = "stale_control"
    DESIGN_DEFICIENCY = "design_deficiency"
    OPERATING_FAILURE = "operating_failure"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GapStatus(StrEnum):
    OPEN = "open"
    IN_REMEDIATION = "in_remediation"
    CLOSED = "closed"
    ACCEPTED = "accepted"  # risk accepted by a human, with rationale


class DefenseLine(StrEnum):
    FIRST = "1LoD"  # business / operations
    SECOND = "2LoD"  # compliance / risk
    THIRD = "3LoD"  # internal audit


class ChangeClass(StrEnum):
    COSMETIC = "cosmetic"
    MODIFIED = "modified"
    NEW = "new"
    REPEALED = "repealed"


# ---------------------------------------------------------------- building blocks


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, use_enum_values=False)


class Versioned(Base):
    id: UUID = Field(default_factory=uuid4)
    key: str  # stable logical id, e.g. "RBI-KYC-MD:38(a)#1"
    source_version: str  # document version label this row was derived from
    effective_from: date
    effective_to: date | None = None  # None = still in force
    recorded_at: datetime = Field(default_factory=_now)
    superseded_at: datetime | None = None  # None = current belief

    @model_validator(mode="after")
    def _valid_interval(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to precedes effective_from")
        return self


class Span(Base):
    """Verbatim pointer into a source document. The citation gate checks that
    doc.text[char_start:char_end] == quote exactly; otherwise the output is rejected."""

    document_id: UUID
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def _length_matches(self):
        if self.char_end - self.char_start != len(self.quote):
            raise ValueError("span length does not match quote length")
        return self


class Threshold(Base):
    kind: ThresholdKind
    value: float
    unit: str  # "INR", "days", "working_days", "years", "months", "percent"
    comparator: str = Field(pattern=r"^(<|<=|>|>=|==|within|at_least_every)$")
    raw: str  # original phrase, kept for audit


class Applicability(Base):
    """Empty list means 'all'. Filtered against BankProfile deterministically."""

    entity_types: list[str] = []  # "scheduled_commercial_bank", "rrb", "ucb", "nbfc", ...
    products: list[str] = []
    customer_segments: list[str] = []  # "individual", "company", "trust", "partnership", ...
    geographies: list[str] = []
    raw: str | None = None


class ExtractionMeta(Base):
    model: str
    prompt_hash: str
    pass_agreement: bool  # two-pass extraction agreed field-by-field
    disagreement_fields: list[str] = []
    flags: list[str] = []  # e.g. "instruction_like_content"


# ---------------------------------------------------------------- nodes


class BankProfile(Base):
    id: UUID = Field(default_factory=uuid4)
    name: str  # synthetic name only
    entity_type: str
    products: list[str]
    customer_segments: list[str]
    geographies: list[str]


class Document(Base):
    id: UUID = Field(default_factory=uuid4)
    kind: DocKind
    issuer: str  # "RBI" or the public bank whose policy this is
    title: str
    reference_no: str | None = None
    version_label: str  # e.g. "MD-2016-upd-2023-05-04"
    issued_on: date | None = None
    effective_from: date | None = None
    url: str | None = None
    sha256: str
    supersedes: UUID | None = None  # previous version of the same document
    is_synthetic: bool = False  # True for mutated policies


class Clause(Versioned):
    """Structural unit from the deterministic parser (RBI paragraph numbering)."""

    document_id: UUID
    clause_ref: str  # "38(a)(ii)"
    parent_ref: str | None = None
    heading: str | None = None
    span: Span


class Obligation(Versioned):
    clause_id: UUID
    source_clause_ref: str
    source_span: Span
    actor: str  # "regulated entity", "principal officer", ...
    modality: Modality
    action: str
    object: str
    condition: str | None = None
    threshold_or_deadline: Threshold | None = None
    applicability: Applicability
    theme: str | None = None  # "periodic_rekyc", "ckycr_upload", ...
    extraction: ExtractionMeta


class Control(Versioned):
    document_id: UUID
    control_ref: str  # section number in the policy
    objective: str
    type: ControlType
    nature: ControlNature
    frequency: str | None = None
    threshold: Threshold | None = None
    scope: Applicability
    owner: str | None = None  # None is itself a design-deficiency signal
    expected_evidence: str | None = None  # likewise
    source_span: Span
    extraction: ExtractionMeta


class Evidence(Base):
    id: UUID = Field(default_factory=uuid4)
    control_id: UUID
    source_path: str  # synthetic CSV
    period_start: date
    period_end: date
    population: int = Field(ge=0)
    sample_size: int = Field(ge=0)
    exceptions: int = Field(ge=0)
    sha256: str


# ---------------------------------------------------------------- edges / judgments


class JudgeOutput(Base):
    judge: str  # "cheap", "strong", "jev", "human"
    model: str | None = None
    verdict: Verdict
    confidence: Confidence
    rationale: str
    citations: list[Span] = []
    latency_ms: int | None = None
    cost_usd: float | None = None


class Mapping(Versioned):
    """Obligation -> Control edge. control_id is None when verdict is MISSING
    (no candidate control addresses the obligation)."""

    obligation_id: UUID
    control_id: UUID | None
    verdict: Verdict
    rationale: str
    obligation_citations: list[Span] = Field(min_length=1)
    control_citations: list[Span] = []
    judges: list[JudgeOutput] = Field(min_length=1)
    confidence: Confidence
    status: ReviewStatus
    retrieval_rank: int | None = None
    reranker_score: float | None = None

    @model_validator(mode="after")
    def _control_consistency(self):
        if self.verdict is Verdict.MISSING and self.control_id is not None:
            raise ValueError("MISSING verdict must not name a control")
        if self.verdict is not Verdict.MISSING and (
            self.control_id is None or not self.control_citations
        ):
            raise ValueError("COVERED/PARTIAL requires a control and its citations")
        return self


class ControlTest(Base):
    id: UUID = Field(default_factory=uuid4)
    control_id: UUID
    mapping_id: UUID | None = None
    kind: ControlTestKind
    result: ControlTestResult
    evidence_ids: list[UUID] = []
    exception_rate: float | None = None
    tolerance: float | None = None  # rule used, e.g. 0.05
    rationale: str
    tested_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _operating_needs_evidence(self):
        if (
            self.kind is ControlTestKind.OPERATING
            and self.result is not ControlTestResult.CANNOT_ASSESS
            and not self.evidence_ids
        ):
            raise ValueError("operating test verdict without evidence; use CANNOT_ASSESS")
        return self


class Gap(Versioned):
    type: GapType
    obligation_id: UUID
    control_id: UUID | None = None
    mapping_id: UUID | None = None
    control_test_id: UUID | None = None
    inherent_risk: RiskLevel  # deterministic rubric over obligation theme/penalty history
    residual_risk: RiskLevel  # after crediting partial controls
    priority_score: float  # deterministic; used for ranking
    status: GapStatus = GapStatus.OPEN
    rationale: str  # LLM-written explanation; does not affect the score
    detected_by_change_event: UUID | None = None


class Remediation(Base):
    id: UUID = Field(default_factory=uuid4)
    gap_id: UUID
    action: str
    owner_line: DefenseLine
    owner_role: str
    due_date: date
    success_criterion: str  # what evidence would close the gap
    status: GapStatus = GapStatus.OPEN
    drafted_by_model: str


class ClauseDiff(Base):
    old_clause_id: UUID | None  # None for NEW
    new_clause_id: UUID | None  # None for REPEALED
    change_class: ChangeClass
    summary: str


class ChangeEvent(Base):
    id: UUID = Field(default_factory=uuid4)
    old_document_id: UUID | None
    new_document_id: UUID
    dry_run: bool = False  # True for what-if; nothing committed
    diffs: list[ClauseDiff] = []
    affected_obligation_ids: list[UUID] = []
    affected_mapping_ids: list[UUID] = []
    projected_gap_delta: int | None = None
    received_at: datetime = Field(default_factory=_now)
    trace_id: str | None = None
