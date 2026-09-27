-- 2026-09-27: permissive provisions ("may") become a third obligation modality.
-- Needed for databases created before schema.sql gained 'may'. Safe to re-run.
ALTER TYPE modality ADD VALUE IF NOT EXISTS 'may';
