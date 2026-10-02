-- 2026-10-02: applicability by bank profile (scripts/run_applicability.py). One current decision
-- per obligation and profile; a changed decision closes the old row and adds a new one.
CREATE TABLE IF NOT EXISTS applicability_decision (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    obligation_id  uuid NOT NULL REFERENCES obligation(id),
    profile        text NOT NULL,            -- data/profiles/<profile>.yaml
    profile_sha256 char(64) NOT NULL,        -- the profile file the decision was made against
    answer         text NOT NULL CHECK (answer IN ('yes', 'no', 'conditional')),
    reason         text NOT NULL,
    decided_by     text NOT NULL CHECK (decided_by IN ('rule', 'model')),
    attribute      text,                     -- profile attribute relied on, e.g. channels
    value          text,                     -- its value, e.g. the channel's name
    basis          text,                     -- where the profile got it from
    matched_in     text CHECK (matched_in IN ('condition', 'sentence')),
    recorded_at    timestamptz NOT NULL DEFAULT now(),
    superseded_at  timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS applicability_current
    ON applicability_decision (obligation_id, profile) WHERE superseded_at IS NULL;

-- An obligation that does not apply to the bank keeps its gap row, out of both tiers.
ALTER TABLE gap DROP CONSTRAINT IF EXISTS gap_tier_check;
ALTER TABLE gap ADD CONSTRAINT gap_tier_check
    CHECK (tier IN ('high', 'review', 'not_applicable'));
