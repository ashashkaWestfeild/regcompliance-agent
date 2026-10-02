-- 2026-10-02: a mandatory duty that the policy states as optional ("may"); planted by the
-- weaken_modality operator (user decision on the test2 key).
ALTER TYPE gap_type ADD VALUE IF NOT EXISTS 'weak_modality';
