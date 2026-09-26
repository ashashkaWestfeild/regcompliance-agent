# regcompliance-agent

An agentic system that keeps a bank's KYC controls traceable to the regulation they implement,
finds gaps, and re-assesses only what changes when the regulator amends a rule.

Built for the **ET AI Hackathon 2026: Agentic Edition (presented by Accenture), Problem 1:
Banking/financial regulations**.

> Status: work in progress (build sprint 23 Sep – 11 Oct 2026). Sections marked *planned* are
> not built yet.

## The problem

Regulations → obligations → applicability → internal policies/controls → evidence → testing →
gaps → remediation → ongoing monitoring. The chain has to stay traceable while both sides keep
changing.

## What this repository does

| Stage | How | Status |
|---|---|---|
| Regulation ingestion | Deterministic parser splits the RBI Directions into numbered clauses with verbatim character spans (no LLM, no fixed-size chunking) | built |
| Change intelligence | Clause-level diff with deterministic noise filtering; only substantive changes reach the agent | built (diff) |
| Policy ingestion | Docling layout parsing of public bank KYC/AML policies | in progress |
| Obligation / control extraction | Open-weights LLMs, strict JSON, two passes | planned |
| Mapping and gaps | Retrieval (bge-m3 + FlashRank) → LLM judge → citation gate → rule-based gap scoring | planned |
| Change agent | LangGraph: plan → re-map affected edges only → recover → open remediation; dry-run for what-if | planned |

## Data (all public or synthetic)

- **Regulation:** RBI (Commercial Banks – Know Your Customer) Directions, 2025
  (RBI/DOR/2025-26/169). Three real versions: the original (28 Nov 2025) and the versions after
  the 29 Dec 2025 and 18 Sep 2026 amendments.
- **Bank policies:** the public KYC/AML policies of Nainital Bank and Central Bank of India.
- **Evidence:** synthetic CSV logs (planned).
- Provenance, source URLs and sha256 for every file: [`data/sources.yaml`](data/sources.yaml).
  Raw files are stored byte-identical (`.gitattributes`) so citation offsets stay valid.
- No material from any employer is used, in any form.

## Quick start

```bash
uv sync                  # core (HTML parsing, diff, tests)
uv sync --extra pdf      # adds Docling for PDF parsing (large: pulls PyTorch)
uv run pytest
uv run python scripts/parse_corpus.py   # parse all sources into data/parsed/
```

Docling output is cached in `data/parsed/docling_cache/` (keyed by file sha256) and committed,
so the PDF-derived clauses are reproducible without installing Docling.

Optional local database: `docker compose up -d` (or `podman compose up -d`) starts Postgres 16 +
pgvector and applies [`db/schema.sql`](db/schema.sql). CI applies the same schema on every push.

## Project layout

```
src/regcomp/ingest/   deterministic parsing (RBI HTML, Docling PDFs, clause tree, normalization)
src/regcomp/change/   clause-level diff and change classification
src/regcomp/schemas.py  domain models (bitemporal versioning)
db/schema.sql         Postgres + pgvector DDL
docs/                 plan, mutation taxonomy, architecture decision records
data/                 public sources + provenance
```

## Responsible AI

Guardrails sit where a compliance agent can fail: poisoned inputs (prompt-injection scanner,
data-egress allowlist), fabricated outputs (strict schemas, verbatim citation gate, number and
negation checks, human review queue), and unsafe actions (read-only what-if, blast-radius pause,
humans close gaps). Details: [`docs/PLAN.md`](docs/PLAN.md) section 3a.

## AI assistance disclosure

This project was developed with **Claude Code** (Anthropic) as a coding assistant. All design
decisions, data choices and ground-truth labels are the author's. The system itself runs on
open-weights models by default.

## Acknowledgements

Architecture patterns (Docling parsing, FlashRank reranking, retry-with-fallback, LangGraph
Postgres checkpointing) were informed by the public "8-hour marathon" RAG sessions and their
repositories ([d-hackmt/8hr-MARATHON](https://github.com/d-hackmt/8hr-MARATHON),
[sourangshupal/8hr-MARATHON](https://github.com/sourangshupal/8hr-MARATHON)). No code was copied.

## Licence

[Apache-2.0](LICENSE)
