-- Postgres 18 + pgvector. Mirrors src/regcomp/schemas.py.
-- Bitemporal convention on versioned tables:
--   valid time       effective_from / effective_to   (NULL = in force)
--   transaction time recorded_at / superseded_at     (NULL = current belief)
--   key              stable logical id across versions; id = one version row
-- Edges reference version row ids, so a new node version makes old edges stale.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ------------------------------------------------------------ enums
CREATE TYPE doc_kind       AS ENUM ('master_direction','amendment','circular','draft','policy');
CREATE TYPE modality       AS ENUM ('must','must_not','may');  -- may = permissive, advisory only
CREATE TYPE control_type   AS ENUM ('preventive','detective','corrective');
CREATE TYPE control_nature AS ENUM ('manual','automated','semi_automated');
CREATE TYPE verdict        AS ENUM ('covered','partial','missing');
CREATE TYPE review_status  AS ENUM ('auto','escalated','reviewed');
CREATE TYPE test_kind      AS ENUM ('design','operating');
CREATE TYPE test_result    AS ENUM ('effective','ineffective','cannot_assess');
CREATE TYPE gap_type       AS ENUM ('missing_control','weak_threshold','narrow_scope',
                                    'internal_contradiction','stale_control',
                                    'design_deficiency','operating_failure');
CREATE TYPE risk_level     AS ENUM ('low','medium','high','critical');
CREATE TYPE gap_status     AS ENUM ('open','in_remediation','closed','accepted');
CREATE TYPE defense_line   AS ENUM ('1LoD','2LoD','3LoD');
CREATE TYPE change_class   AS ENUM ('cosmetic','modified','new','repealed');

-- ------------------------------------------------------------ reference
CREATE TABLE bank_profile (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name              text NOT NULL,
    entity_type       text NOT NULL,
    products          text[] NOT NULL DEFAULT '{}',
    customer_segments text[] NOT NULL DEFAULT '{}',
    geographies       text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE document (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind           doc_kind NOT NULL,
    issuer         text NOT NULL,
    title          text NOT NULL,
    reference_no   text,
    version_label  text NOT NULL,
    issued_on      date,
    effective_from date,
    url            text,
    sha256         char(64) NOT NULL UNIQUE,
    text           text NOT NULL,          -- normalized full text; spans index into this
    supersedes     uuid REFERENCES document(id),
    is_synthetic   boolean NOT NULL DEFAULT false
);

-- ------------------------------------------------------------ versioned nodes
-- Shared columns are repeated per table (no inheritance: keeps FKs and indexes simple).

CREATE TABLE clause (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key            text NOT NULL,
    source_version text NOT NULL,
    effective_from date NOT NULL,
    effective_to   date,
    recorded_at    timestamptz NOT NULL DEFAULT now(),
    superseded_at  timestamptz,
    document_id    uuid NOT NULL REFERENCES document(id),
    clause_ref     text NOT NULL,
    parent_ref     text,
    heading        text,
    char_start     int NOT NULL,
    char_end       int NOT NULL,
    quote          text NOT NULL,
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (char_end - char_start = length(quote))
);

CREATE TABLE obligation (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key               text NOT NULL,
    source_version    text NOT NULL,
    effective_from    date NOT NULL,
    effective_to      date,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    superseded_at     timestamptz,
    clause_id         uuid NOT NULL REFERENCES clause(id),
    source_clause_ref text NOT NULL,
    source_span       jsonb NOT NULL,     -- Span
    actor             text NOT NULL,
    modality          modality NOT NULL,
    action            text NOT NULL,
    object            text NOT NULL,
    condition         text,
    threshold         jsonb,              -- Threshold
    applicability     jsonb NOT NULL,     -- Applicability
    theme             text,
    extraction        jsonb NOT NULL,     -- ExtractionMeta
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE control (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key               text NOT NULL,
    source_version    text NOT NULL,
    effective_from    date NOT NULL,
    effective_to      date,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    superseded_at     timestamptz,
    document_id       uuid NOT NULL REFERENCES document(id),
    control_ref       text NOT NULL,
    objective         text NOT NULL,
    type              control_type NOT NULL,
    nature            control_nature NOT NULL,
    frequency         text,
    threshold         jsonb,
    scope             jsonb NOT NULL,
    owner             text,
    expected_evidence text,
    source_span       jsonb NOT NULL,
    extraction        jsonb NOT NULL,
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE evidence (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    control_id   uuid NOT NULL REFERENCES control(id),
    source_path  text NOT NULL,
    period_start date NOT NULL,
    period_end   date NOT NULL,
    population   int NOT NULL CHECK (population >= 0),
    sample_size  int NOT NULL CHECK (sample_size >= 0),
    exceptions   int NOT NULL CHECK (exceptions >= 0),
    sha256       char(64) NOT NULL
);

-- ------------------------------------------------------------ edges / judgments
CREATE TABLE mapping (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key                  text NOT NULL,
    source_version       text NOT NULL,
    effective_from       date NOT NULL,
    effective_to         date,
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    superseded_at        timestamptz,
    obligation_id        uuid NOT NULL REFERENCES obligation(id),
    control_id           uuid REFERENCES control(id),
    verdict              verdict NOT NULL,
    rationale            text NOT NULL,
    obligation_citations jsonb NOT NULL,   -- Span[]
    control_citations    jsonb NOT NULL DEFAULT '[]',
    judges               jsonb NOT NULL,   -- JudgeOutput[]
    confidence           real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status               review_status NOT NULL,
    retrieval_rank       int,
    reranker_score       real,
    CHECK ((verdict = 'missing') = (control_id IS NULL))
);

CREATE TABLE control_test (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    control_id     uuid NOT NULL REFERENCES control(id),
    mapping_id     uuid REFERENCES mapping(id),
    kind           test_kind NOT NULL,
    result         test_result NOT NULL,
    evidence_ids   uuid[] NOT NULL DEFAULT '{}',
    exception_rate real,
    tolerance      real,
    rationale      text NOT NULL,
    tested_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (kind = 'design' OR result = 'cannot_assess' OR cardinality(evidence_ids) > 0)
);

CREATE TABLE change_event (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    old_document_id        uuid REFERENCES document(id),
    new_document_id        uuid NOT NULL REFERENCES document(id),
    dry_run                boolean NOT NULL DEFAULT false,
    affected_obligation_ids uuid[] NOT NULL DEFAULT '{}',
    affected_mapping_ids   uuid[] NOT NULL DEFAULT '{}',
    projected_gap_delta    int,
    received_at            timestamptz NOT NULL DEFAULT now(),
    trace_id               text
);

CREATE TABLE clause_diff (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_event_id uuid NOT NULL REFERENCES change_event(id),
    old_clause_id   uuid REFERENCES clause(id),
    new_clause_id   uuid REFERENCES clause(id),
    change_class    change_class NOT NULL,
    summary         text NOT NULL,
    CHECK (old_clause_id IS NOT NULL OR new_clause_id IS NOT NULL)
);

CREATE TABLE gap (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key                       text NOT NULL,
    source_version            text NOT NULL,
    effective_from            date NOT NULL,
    effective_to              date,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    superseded_at             timestamptz,
    type                      gap_type NOT NULL,
    obligation_id             uuid NOT NULL REFERENCES obligation(id),
    control_id                uuid REFERENCES control(id),
    mapping_id                uuid REFERENCES mapping(id),
    control_test_id           uuid REFERENCES control_test(id),
    inherent_risk             risk_level NOT NULL,
    residual_risk             risk_level NOT NULL,
    priority_score            real NOT NULL,
    status                    gap_status NOT NULL DEFAULT 'open',
    rationale                 text NOT NULL,
    detected_by_change_event  uuid REFERENCES change_event(id)
);

CREATE TABLE remediation (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gap_id            uuid NOT NULL REFERENCES gap(id),
    action            text NOT NULL,
    owner_line        defense_line NOT NULL,
    owner_role        text NOT NULL,
    due_date          date NOT NULL,
    success_criterion text NOT NULL,
    status            gap_status NOT NULL DEFAULT 'open',
    drafted_by_model  text NOT NULL
);

-- Reviewer overrides: the trainability loop reads these as few-shot corrections.
CREATE TABLE review_override (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_id  uuid NOT NULL REFERENCES mapping(id),
    old_verdict verdict NOT NULL,
    new_verdict verdict NOT NULL,
    reason      text NOT NULL,
    reviewer    text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------ embeddings
-- Dimension 1024 assumes bge-m3; change before first load if the embedder differs.
CREATE TABLE embedding (
    owner_kind text NOT NULL CHECK (owner_kind IN ('clause','obligation','control')),
    owner_id   uuid NOT NULL,
    model      text NOT NULL,
    vec        vector(1024) NOT NULL,
    PRIMARY KEY (owner_kind, owner_id, model)
);
CREATE INDEX embedding_hnsw ON embedding USING hnsw (vec vector_cosine_ops);

-- ------------------------------------------------------------ indexes
-- At most one current-belief row per key (transaction-time uniqueness).
CREATE UNIQUE INDEX clause_current     ON clause(key)     WHERE superseded_at IS NULL;
CREATE UNIQUE INDEX obligation_current ON obligation(key) WHERE superseded_at IS NULL;
CREATE UNIQUE INDEX control_current    ON control(key)    WHERE superseded_at IS NULL;
CREATE UNIQUE INDEX mapping_current    ON mapping(key)    WHERE superseded_at IS NULL;
CREATE UNIQUE INDEX gap_current        ON gap(key)        WHERE superseded_at IS NULL;

CREATE INDEX mapping_obligation ON mapping(obligation_id);
CREATE INDEX mapping_control    ON mapping(control_id);
CREATE INDEX gap_obligation     ON gap(obligation_id);
CREATE INDEX clause_document    ON clause(document_id, clause_ref);

-- As-of view: what the system believed was in force on a given date, as of now.
-- Usage: SELECT * FROM obligation_as_of('2024-01-01');
CREATE FUNCTION obligation_as_of(d date) RETURNS SETOF obligation
LANGUAGE sql STABLE AS $$
    SELECT * FROM obligation
    WHERE superseded_at IS NULL
      AND effective_from <= d
      AND (effective_to IS NULL OR effective_to > d)
$$;
