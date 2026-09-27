-- 2026-09-27: a partial mapping whose judge gave no specific reason is recorded as
-- 'unspecified' instead of being forced into a named type (counts as a classification miss).
ALTER TYPE gap_type ADD VALUE IF NOT EXISTS 'unspecified';
