# 0001. Parse regulations by their own numbering, no fixed-size chunks

- Status: accepted (2026-09-26)

## Context
RBI Directions are organised as numbered paragraphs (`38.`) with nested sub-clauses (`(2)`,
`(iv)`, `(a)`). Obligations, amendments and citations all refer to these numbers. Fixed-size
chunking splits obligations mid-sentence and loses the reference a compliance officer needs.

## Decision
A deterministic parser (`src/regcomp/ingest/structure.py`) builds a clause tree from the
document's own markers, using a stack of marker types that handles any nesting order and
resolves `(i)` letter-vs-roman ambiguity. Every clause stores a character span into canonical
text, so `text[start:end] == quote` holds by construction. No LLM is involved.

## Consequences
- Citations are machine-checkable (see 0004).
- RBI's own amendment markers attach to the exact clause, giving free ground truth.
- New document families need a small block reader (HTML, Docling PDF); the tree builder is shared.
