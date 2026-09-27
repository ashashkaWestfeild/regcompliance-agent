-- 2026-09-27: exact-match LLM response cache (never semantic: near-identical clauses differ in
-- thresholds). Key = sha256 of (stage, model, prompt, schema, options). Safe to re-run.
CREATE TABLE IF NOT EXISTS llm_cache (
    key          char(64) PRIMARY KEY,
    stage        text NOT NULL,
    model        text NOT NULL,
    request      jsonb NOT NULL,
    response     jsonb NOT NULL,
    latency_ms   int,
    eval_tokens  int,
    created_at   timestamptz NOT NULL DEFAULT now()
);
