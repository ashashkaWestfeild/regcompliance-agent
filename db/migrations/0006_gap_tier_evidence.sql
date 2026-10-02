-- 2026-10-02: triage output (user rule): every gap is either in the high-confidence tier or in
-- the review queue, and carries the evidence that put it there (scripts/run_verify.py).
ALTER TABLE gap ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'high'
    CHECK (tier IN ('high', 'review'));
ALTER TABLE gap ADD COLUMN IF NOT EXISTS evidence jsonb;
