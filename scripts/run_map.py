"""Stage 2 of the crude end-to-end run (dev set): load -> embed -> retrieve -> judge -> gaps.

Reads eval/runs/<run>/{obligations,controls}.json from run_extract.py, resets the pipeline
tables in Postgres (never llm_cache), loads documents/clauses/obligations/controls, embeds with
bge-m3 into pgvector, retrieves the top-K controls per obligation, judges per regulation unit,
applies the deterministic gap rules, and writes mappings + gaps. Prints a crude preview against
the frozen dev answer key as counts.

    uv run python scripts/run_map.py --run e2e1
    uv run python scripts/run_map.py --run e2e8 --passages --stop-after-min 25   # resumable

--passages also offers every policy passage that extracted controls do not cover as a candidate
(pipeline/passages.py). --stop-after-min ends the run cleanly once the time is up, before any
result is written; the same command then resumes from the LLM cache.
"""

import argparse
import csv
import hashlib
import json
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from psycopg.types.json import Jsonb

from regcomp.db import connect
from regcomp.ingest.pdf_docling import parse_policy_items
from regcomp.ingest.rbi_html import parse_file
from regcomp.llm import STAGE_MODELS, LLMError, embed
from regcomp.pipeline import rerank as rerank_mod
from regcomp.pipeline.judge import judge_unit, unclear
from regcomp.pipeline.passages import passage_controls
from regcomp.pipeline.rerank import rerank
from regcomp.policies import policy

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"
REG_VERSION = "KYCDIR-2025-upd-20260918"
REG_EFFECTIVE = date(2026, 9, 18)
# Set in main() from --policy (default: the dev bank).
DEV_POLICY = "data/mutated/nainital.items.json"
POLICY_VERSION = "nainital-mutated-350b8e0"
POLICY_ISSUER = "Nainital Bank"
POLICY_EFFECTIVE = date(2026, 9, 27)
DEV_KEY = "eval/answer_key_nainital.jsonl"
TOP_K = 5  # candidates the judge sees
RETRIEVE_K = 20  # bge-m3 candidates before FlashRank reranking
PIPELINE_TABLES = (
    "gap, remediation, mapping, control_test, evidence, review_override, clause_diff, "
    "change_event, embedding, obligation, control, clause, document, bank_profile"
)


# A policy passage offered as a candidate: plain text, no attributes were extracted from it.
PASSAGE_EXTRACTION = {"model": None, "method": "passage", "passes": 0, "pass_agreement": False}


def control_text(c: dict) -> str:
    """What retrieval and reranking see for a candidate."""
    return f"{c['objective']}. {c['quote']}" if c["objective"] else c["quote"]


def deepest(doc, pos: int) -> str | None:
    hits = [c for c in doc.clauses if c.char_start <= pos < c.char_end]
    return max(hits, key=lambda c: c.depth).ref if hits else None


def vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def load(conn, reg, pol, obligations, controls):
    conn.execute(f"TRUNCATE {PIPELINE_TABLES} CASCADE")
    reg_id, pol_id = uuid.uuid4(), uuid.uuid4()
    for doc_id, kind, issuer, title, version, text, synthetic in (
        (
            reg_id,
            "master_direction",
            "RBI",
            "RBI (Commercial Banks - KYC) Directions, 2025",
            REG_VERSION,
            reg.text,
            False,
        ),
        (
            pol_id,
            "policy",
            POLICY_ISSUER,
            "KYC/AML Policy (planted-gap copy)",
            POLICY_VERSION,
            pol.text,
            True,
        ),
    ):
        conn.execute(
            "INSERT INTO document (id, kind, issuer, title, version_label, sha256, text,"
            " is_synthetic) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                doc_id,
                kind,
                issuer,
                title,
                version,
                hashlib.sha256(text.encode()).hexdigest(),
                text,
                synthetic,
            ),
        )
    clause_ids = {}
    rows = []
    for prefix, doc_id, doc, version, eff in (
        ("REG", reg_id, reg, REG_VERSION, REG_EFFECTIVE),
        ("POL", pol_id, pol, POLICY_VERSION, POLICY_EFFECTIVE),
    ):
        for c in doc.clauses:
            cid = uuid.uuid4()
            clause_ids[(prefix, c.ref)] = cid
            rows.append(
                (
                    cid,
                    f"{prefix}:{c.ref}",
                    version,
                    eff,
                    doc_id,
                    c.ref,
                    c.parent_ref,
                    c.section,
                    c.char_start,
                    c.char_end,
                    c.quote,
                )
            )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO clause (id, key, source_version, effective_from, document_id,"
            " clause_ref, parent_ref, heading, char_start, char_end, quote)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )

    extraction = {
        "model": STAGE_MODELS["extract_obligations"],
        "passes": 1,
        "pass_agreement": False,
    }
    ob_rows, per_unit = [], defaultdict(int)
    for o in obligations:
        per_unit[o["unit_ref"]] += 1
        o["id"] = uuid.uuid4()
        o["ref"] = deepest(reg, o["char_start"]) or o["clause_ref"]
        span = {
            "document_id": str(reg_id),
            "char_start": o["char_start"],
            "char_end": o["char_end"],
            "quote": o["quote"],
        }
        ob_rows.append(
            (
                o["id"],
                f"OBL:{o['unit_ref']}#{per_unit[o['unit_ref']]}",
                REG_VERSION,
                REG_EFFECTIVE,
                clause_ids[("REG", o["clause_ref"])],
                o["ref"],
                Jsonb(span),
                o["actor"],
                o["modality"],
                o["action"],
                o["action"],
                Jsonb({"raw": o["threshold"]}) if o.get("threshold") else None,
                Jsonb(
                    {
                        "raw": o.get("applies_to"),
                        "level": o["level"],
                        "level_reason": o.get("level_reason"),
                        "level_rule": o.get("level_rule"),
                    }
                ),
                Jsonb(extraction),
            )
        )
    ct_rows, per_unit = [], defaultdict(int)
    ctl_extraction = dict(extraction, model=STAGE_MODELS["extract_controls"])
    for c in controls:
        per_unit[c["unit_ref"]] += 1
        c["id"] = uuid.uuid4()
        c["ref"] = deepest(pol, c["char_start"]) or c["clause_ref"]
        span = {
            "document_id": str(pol_id),
            "char_start": c["char_start"],
            "char_end": c["char_end"],
            "quote": c["quote"],
        }
        ct_rows.append(
            (
                c["id"],
                f"CTL:{c['unit_ref']}#{per_unit[c['unit_ref']]}",
                POLICY_VERSION,
                POLICY_EFFECTIVE,
                pol_id,
                c["ref"],
                c["objective"],
                c["type"],
                c["nature"],
                c.get("frequency"),
                Jsonb({"raw": c["threshold"]}) if c.get("threshold") else None,
                Jsonb({"raw": c.get("scope")}),
                c.get("owner"),
                c.get("evidence"),
                Jsonb(span),
                Jsonb(PASSAGE_EXTRACTION if c.get("passage") else ctl_extraction),
            )
        )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO obligation (id, key, source_version, effective_from, clause_id,"
            " source_clause_ref, source_span, actor, modality, action, object, threshold,"
            " applicability, extraction) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ob_rows,
        )
        cur.executemany(
            "INSERT INTO control (id, key, source_version, effective_from, document_id,"
            " control_ref, objective, type, nature, frequency, threshold, scope, owner,"
            " expected_evidence, source_span, extraction)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            ct_rows,
        )
    return reg_id, pol_id


def embed_all(conn, obligations, controls):
    ob_text = [f"{o['action']}. {o.get('threshold') or ''} {o['quote']}" for o in obligations]
    ct_text = [control_text(c) for c in controls]
    vectors = embed(ob_text + ct_text)
    rows = [
        ("obligation", o["id"], "bge-m3", vec_literal(v))
        for o, v in zip(obligations, vectors[: len(obligations)], strict=True)
    ]
    rows += [
        ("control", c["id"], "bge-m3", vec_literal(v))
        for c, v in zip(controls, vectors[len(obligations) :], strict=True)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO embedding (owner_kind, owner_id, model, vec) VALUES (%s,%s,%s,%s::vector)",
            rows,
        )
    return dict(zip([o["id"] for o in obligations], vectors[: len(obligations)], strict=True))


def _same_text(a: dict, b: dict) -> bool:
    """Two candidates on (mostly) the same policy text: the judge only sees the quote, so the
    second one would spend a slot on a repeat."""
    inside = min(a["char_end"], b["char_end"]) - max(a["char_start"], b["char_start"])
    return inside >= 0.5 * min(a["char_end"] - a["char_start"], b["char_end"] - b["char_start"])


def retrieve(conn, ob_vectors, obligations, controls, dense_only: bool = False) -> dict:
    """bge-m3 top-RETRIEVE_K from pgvector, then FlashRank rerank to TOP_K.
    Returns {obligation_id: [(control_id, reranker_score), ...]} best first.

    dense_only: keep the embedding order, drop candidates that repeat a higher-ranked one's
    text, and take the top TOP_K (score None). On the dev targets (2 Oct) the reranker pushed the
    right passage out of the top 5 more often than it pulled it in: 14/18 vs 16/18."""
    ob_text = {o["id"]: f"{o['action']}. {o['quote']}" for o in obligations}
    ct_text = {c["id"]: control_text(c) for c in controls}
    by_id = {c["id"]: c for c in controls}
    out = {}
    for oid, v in ob_vectors.items():
        rows = conn.execute(
            "SELECT owner_id FROM embedding WHERE owner_kind = 'control'"
            " ORDER BY vec <=> %s::vector LIMIT %s",
            (vec_literal(v), RETRIEVE_K),
        ).fetchall()
        if dense_only:
            kept: list = []
            for (cid,) in rows:
                if not any(_same_text(by_id[cid], by_id[k]) for k in kept):
                    kept.append(cid)
            out[oid] = [(cid, None) for cid in kept[:TOP_K]]
            continue
        candidates = [(r[0], ct_text[r[0]]) for r in rows]
        out[oid] = rerank(ob_text[oid], candidates, TOP_K)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default="nainital")
    ap.add_argument("--held-out", action="store_true", help="confirm a held-out (test) policy")
    ap.add_argument("--judge-think", action="store_true", help="judge with thinking mode on")
    ap.add_argument("--passages", action="store_true", help="policy passages as candidates too")
    ap.add_argument("--dense-only", action="store_true", help="no reranker; dedupe candidates")
    ap.add_argument("--stop-after-min", type=float, help="stop cleanly after this many minutes")
    args = ap.parse_args()
    global DEV_POLICY, POLICY_VERSION, POLICY_ISSUER, DEV_KEY
    bank = policy(args.policy, args.held_out)
    DEV_POLICY, POLICY_VERSION, DEV_KEY = str(bank.items), bank.version, str(bank.key)
    POLICY_ISSUER = bank.bank
    run = Path("eval/runs") / args.run
    obligations = json.loads((run / "obligations.json").read_text(encoding="utf-8"))["items"]
    controls = json.loads((run / "controls.json").read_text(encoding="utf-8"))["items"]
    apply_levels(run, obligations)
    reg = parse_file(REGULATION)
    pol = parse_policy_items(json.loads(Path(DEV_POLICY).read_text(encoding="utf-8")))
    if args.passages:
        extracted = len(controls)
        controls = controls + passage_controls(pol, controls)
        print(
            f"candidates: {extracted} controls + {len(controls) - extracted} passages", flush=True
        )
    t0 = time.time()

    with connect(autocommit=True) as conn:
        load(conn, reg, pol, obligations, controls)
        print(
            f"loaded {len(obligations)} obligations, {len(controls)} controls "
            f"({time.time() - t0:.0f}s)",
            flush=True,
        )
        ob_vectors = embed_all(conn, obligations, controls)
        print(f"embedded ({time.time() - t0:.0f}s)", flush=True)
        hits = retrieve(conn, ob_vectors, obligations, controls, args.dense_only)
        how = "deduped dense" if args.dense_only else "FlashRank"
        print(
            f"retrieved top-{RETRIEVE_K} -> {how} top-{TOP_K} "
            f"(rerank failures {rerank_mod.failures}) ({time.time() - t0:.0f}s)",
            flush=True,
        )

        by_ctl = {c["id"]: c for c in controls}
        units = defaultdict(list)
        for o in obligations:
            units[o["unit_ref"]].append(o)
        results, failed_units = {}, []
        for i, obs in enumerate(units.values(), 1):
            if args.stop_after_min and time.time() - t0 > args.stop_after_min * 60:
                print(
                    f"[{time.strftime('%H:%M:%S')}] time is up at {i - 1}/{len(units)} units; "
                    "nothing written. Run the same command again to resume from the cache.",
                    flush=True,
                )
                return 3
            cand_ids = list(dict.fromkeys(cid for o in obs for cid, _ in hits[o["id"]]))
            local = {f"C{n}": cid for n, cid in enumerate(cand_ids, 1)}
            candidates = {k: by_ctl[v] for k, v in local.items()}
            reverse = {v: k for k, v in local.items()}
            payload = [
                {
                    "id": f"O{n}",
                    "modality": o["modality"],
                    "quote": o["quote"],
                    "threshold": o.get("threshold"),
                    "applies_to": o.get("applies_to"),
                    "candidates": [reverse[cid] for cid, _ in hits[o["id"]]],
                }
                for n, o in enumerate(obs, 1)
            ]
            try:
                judged = judge_unit(payload, candidates, conn, think=args.judge_think)
            except LLMError as e:
                # One unit's judge call failing (e.g. a runaway generation) must not end a
                # multi-hour run: count it, report it, and send its obligations to review
                # (never silently "no gap", B1 7 Oct).
                failed_units.append(obs[0]["unit_ref"])
                print(
                    f"[{time.strftime('%H:%M:%S')}] judge failed on unit {obs[0]['unit_ref']}: {e}",
                    flush=True,
                )
                judged = [
                    unclear(p["id"], f"the judge call failed: {e}", (p["candidates"] or [None])[0])
                    for p in payload
                ]
            for r in judged:
                o = obs[int(r["obligation"][1:]) - 1]
                r["control_uuid"] = local.get(r["control"]) if r["control"] else None
                results[o["id"]] = r
            if i % 10 == 0 or i == len(units):
                print(f"[{time.strftime('%H:%M:%S')}] judged {i}/{len(units)} units", flush=True)

        if failed_units:
            print(
                f"judge failed on {len(failed_units)} units (skipped): {failed_units}", flush=True
            )
        # Saved before the DB write so a write failure never costs a re-judge.
        (run / "judgments.json").write_text(
            json.dumps({str(k): _plain(v) for k, v in results.items()}, indent=1), encoding="utf-8"
        )
    # Fresh connection for the write: the judge loop can outlive a server-side disconnect.
    with connect(autocommit=True) as conn:
        write_mappings_and_gaps(conn, obligations, results, hits, run)
    preview(obligations, results)
    return 0


def _plain(r: dict) -> dict:
    """Judge result without the resolved control UUID (stored in mapping.control_id)."""
    return {k: v for k, v in r.items() if k != "control_uuid"}


def apply_levels(run: Path, obligations: list[dict]) -> None:
    """Attach the obligation level from levels.json (scripts/run_level.py). Without it every
    obligation counts as policy-level, i.e. the pre-27 Sep behaviour."""
    path = run / "levels.json"
    levels = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for o in obligations:
        v = levels.get(f"{o['char_start']}:{o['char_end']}:{o['action']}", {})
        o["level"] = v.get("level", "policy")
        o["level_reason"] = v.get("reason")
        o["level_rule"] = v.get("rule")
    if levels:
        print(f"levels: {dict(Counter(o['level'] for o in obligations))}", flush=True)


def write_mappings_and_gaps(conn, obligations, results, hits, run: Path):
    risk = {"missing": ("high", 0.8), "partial": ("medium", 0.5), "covered": ("low", 0.2)}
    gap_rows = []
    not_policy = Counter()
    with conn.cursor() as cur:
        for o in obligations:
            r = results.get(o["id"])
            if r is None:
                continue
            mid = uuid.uuid4()
            sim = dict(hits[o["id"]]).get(r["control_uuid"]) if r["control_uuid"] else None
            rank = (
                [cid for cid, _ in hits[o["id"]]].index(r["control_uuid"]) + 1
                if r["control_uuid"] in dict(hits[o["id"]])
                else None
            )
            status = "auto" if r["citation_ok"] and r["confidence"] >= 0.7 else "escalated"
            cur.execute(
                "INSERT INTO mapping (id, key, source_version, effective_from, obligation_id,"
                " control_id, verdict, rationale, obligation_citations, control_citations,"
                " judges, confidence, status, retrieval_rank, reranker_score)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    mid,
                    f"MAP:{o['id']}",
                    REG_VERSION,
                    REG_EFFECTIVE,
                    o["id"],
                    r["control_uuid"],
                    r["verdict"],
                    r["rationale"],
                    Jsonb([{"quote": o["quote"]}]),
                    Jsonb(
                        [{"quote_start": r.get("control_quote_start")}] if r["control_uuid"] else []
                    ),
                    Jsonb([{"judge": "cheap", "model": STAGE_MODELS["judge"], **_plain(r)}]),
                    max(0.0, min(1.0, float(r["confidence"]))),
                    status,
                    rank,
                    sim,
                ),
            )
            if r["gap_type"] and o["level"] != "policy":
                not_policy[o["level"]] += 1  # reported, but not a policy gap (user rule)
            elif r.get("unclear"):
                # an unusable judgment: an unspecified gap in the review queue, for a person
                cur.execute(
                    "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
                    " control_id, mapping_id, inherent_risk, residual_risk, priority_score,"
                    " rationale, tier, evidence) VALUES"
                    " (%s,%s,%s,'unspecified',%s,%s,%s,'medium','medium',0.5,%s,'review',%s)",
                    (
                        f"GAP:{o['id']}",
                        REG_VERSION,
                        REG_EFFECTIVE,
                        o["id"],
                        r["control_uuid"],
                        mid,
                        r["rationale"],
                        Jsonb({"check": "judge_unclear", "detail": r["unclear"]}),
                    ),
                )
            elif r["gap_type"]:
                inherent, score = risk.get(r["verdict"], ("medium", 0.5))
                cur.execute(
                    "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
                    " control_id, mapping_id, inherent_risk, residual_risk, priority_score,"
                    " rationale) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        f"GAP:{o['id']}",
                        REG_VERSION,
                        REG_EFFECTIVE,
                        r["gap_type"],
                        o["id"],
                        r["control_uuid"],
                        mid,
                        inherent,
                        inherent,
                        score,
                        r["rationale"],
                    ),
                )
                gap_rows.append(
                    (
                        o["ref"],
                        o["modality"],
                        r["verdict"],
                        r["issue"],
                        r["gap_type"],
                        r["confidence"],
                        o["quote"][:200],
                        r["rationale"],
                    )
                )
    with (run / "gaps.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "regulation_ref",
                "modality",
                "verdict",
                "issue",
                "gap_type",
                "confidence",
                "obligation_quote",
                "rationale",
            ]
        )
        w.writerows(sorted(gap_rows))
    if not_policy:
        print(f"gaps not raised (obligation not policy-level): {dict(not_policy)}")


def preview(obligations, results):
    verdicts = Counter(r["verdict"] for r in results.values())
    gaps = Counter(r["gap_type"] for r in results.values() if r["gap_type"])
    cites = Counter(r["citation_ok"] for r in results.values())
    print(f"\nmappings: {dict(verdicts)}; judged {len(results)}/{len(obligations)} obligations")
    print(f"gaps by type: {dict(gaps)}")
    print(f"control citations verified: {cites[True]}/{sum(cites.values())}")

    key = [json.loads(line) for line in Path(DEV_KEY).read_text(encoding="utf-8").splitlines()]
    gap_refs = defaultdict(set)
    for o in obligations:
        r = results.get(o["id"])
        if r and r["gap_type"]:
            gap_refs[o["ref"]].add(r["gap_type"])

    def reported(refs):
        return set().union(*(gap_refs.get(ref, set()) for ref in refs)) if refs else set()

    muts = [k for k in key if k["kind"] == "mutation"]
    detected = [k for k in muts if reported(k["target_obligation_refs"])]
    typed = [
        k
        for k in detected
        if reported(k["target_obligation_refs"]) & set(k["acceptable_gap_types"])
    ]
    decoys = [k for k in key if k["kind"] == "decoy"]
    decoy_hits = [k for k in decoys if reported(k["target_obligation_refs"])]
    print("\nCRUDE PREVIEW vs frozen dev key (ref-level match only, not the real harness):")
    print(
        f"  gaps detected {len(detected)}/{len(muts)} (type in accepted set {len(typed)}/"
        f"{len(muts)}), decoys flagged {len(decoy_hits)}/{len(decoys)}"
    )
    for k in muts:
        print(
            f"  {k['mutation_id']:5} {k['target_obligation_refs']} -> "
            f"{sorted(reported(k['target_obligation_refs'])) or 'no gap reported'}"
        )


if __name__ == "__main__":
    sys.exit(main())
