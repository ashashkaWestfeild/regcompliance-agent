-- 2026-10-02: source metadata for full citations (scripts/load_metadata.py). Every value comes
-- from data/sources.yaml or from the parser; none from a model.
ALTER TABLE document ADD COLUMN IF NOT EXISTS source_title     text;  -- title as published
ALTER TABLE document ADD COLUMN IF NOT EXISTS amended_by       text;  -- amending notification of this version
ALTER TABLE document ADD COLUMN IF NOT EXISTS stated_date      date;  -- a policy's own stated date
ALTER TABLE document ADD COLUMN IF NOT EXISTS stated_date_kind text;  -- what that date is, in the policy's words
-- RBI's clause-level amendment markers ("Inserted with effect from ... vide ..."), as parsed.
ALTER TABLE clause ADD COLUMN IF NOT EXISTS amended_by jsonb NOT NULL DEFAULT '[]';
