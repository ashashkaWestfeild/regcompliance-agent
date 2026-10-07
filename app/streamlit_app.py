"""RegCompliance Agent: the hosted demo (Streamlit).

Reads the compliance graph from Postgres and shows it: gaps in two tiers with their evidence,
source citation, applicability and confidence note; the review queue; the change agent on real
and draft amendments; a what-if on the bank profile; operating evidence and the evaluation
numbers. Public visitors can look and simulate; writing needs the reviewer code.

    uv run streamlit run app/streamlit_app.py
"""

import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
for sub in ("src", "scripts"):
    sys.path.insert(0, str(ROOT / sub))
os.chdir(ROOT)  # data paths in the code are relative to the repository root
try:  # on Streamlit Cloud the settings come from the app's secrets; locally from .env
    for name in ("DATABASE_URL", "STRONG_MODEL_API_KEY", "REGCOMP_MODEL", "REVIEWER_CODE"):
        if name in st.secrets:
            os.environ[name] = str(st.secrets[name])
except Exception:  # no secrets file on a local run
    pass
# The database guard keeps unlabelled hosts read-only; the hosted app's host has no label and the
# app writes its model-call cache, so it opts in. Labelled live stays read-only on local runs.
os.environ.setdefault("REGCOMP_ALLOW_UNLABELLED", "1")

from regcomp import applicability as appl  # noqa: E402
from regcomp.citation import (  # noqa: E402
    DOC_FIELDS,
    day,
    policy_citation,
    policy_lines,
    predates,
    regulation_citation,
    regulation_lines,
)
from regcomp.confidence import note as confidence_note  # noqa: E402
from regcomp.db import connect  # noqa: E402
from regcomp.llm import model_for  # noqa: E402
from regcomp.monitor import preview_batch  # noqa: E402
from regcomp.record_decision import record  # noqa: E402
from regcomp.remediation import readable  # noqa: E402
from regcomp.review import DECISIONS  # noqa: E402
from regcomp.reviewer_code import code_matches  # noqa: E402
from regcomp.risk import assess  # noqa: E402
from regcomp.sources import document_fields, regulation_meta_for_file  # noqa: E402

st.set_page_config(page_title="RegCompliance Agent", page_icon="📋", layout="wide")

SCENARIOS = {
    "Real amendment, 18 Sep 2026 (FPIs added to a permitted option)": (
        "data/raw/rbi/kycdir_v2_20251229.html",
        "data/raw/rbi/kycdir_v3_20260918.html",
    ),
    "What-if: synthetic draft circular (one invented duty in paragraph 18)": (
        "data/raw/rbi/kycdir_v3_20260918.html",
        "data/synthetic/kycdir_draft_whatif.html",
    ),
    "Real amendment, 29 Dec 2025 (CKYCR reliance explanation)": (
        "data/raw/rbi/kycdir_v1_20251128.pdf",
        "data/raw/rbi/kycdir_v2_20251229.pdf",
    ),
}
APPLIES = {"yes": "applies", "no": "does not apply", "conditional": "to confirm"}
LIMIT_WORDS = ("rate-limited", "HTTP 429", "allowance")


@st.cache_data(ttl=120, show_spinner=False)
def query(sql: str, params: tuple = ()) -> list[tuple]:
    with connect(autocommit=True) as conn:
        return conn.execute(sql, params).fetchall()


@st.cache_data(ttl=600, show_spinner=False)
def documents() -> dict[str, dict]:
    """{kind: the stored source fields of that document}. Loaded from data/sources.yaml by
    scripts/load_metadata.py; nothing here comes from a model."""
    rows = query("SELECT kind::text, title, " + ", ".join(DOC_FIELDS) + " FROM document")
    out = {}
    for kind, title, *fields in rows:
        doc = dict(zip(DOC_FIELDS, fields, strict=True))
        doc["source_title"] = doc["source_title"] or title
        out["policy" if kind == "policy" else "regulation"] = doc
    return out


@st.cache_data(ttl=600, show_spinner=False)
def amendment_markers() -> list[tuple[str, list[str]]]:
    return query(
        "SELECT c.clause_ref, c.amended_by FROM clause c JOIN document d ON d.id = c.document_id"
        " WHERE d.kind <> 'policy' AND c.superseded_at IS NULL"
        " AND jsonb_array_length(c.amended_by) > 0"
    )


def markers_for(ref: str) -> list[str]:
    """RBI's markers on the paragraph or on a paragraph that contains it."""
    return [
        m
        for clause, found in amendment_markers()
        if ref == clause or ref.startswith(clause + "(")
        for m in found
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def confidence_table() -> dict:
    path = ROOT / "eval" / "reports" / "confidence_table.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@st.cache_data(ttl=120, show_spinner=False)
def gaps(tier: str) -> list[dict]:
    rows = query(
        "SELECT g.id::text, o.source_clause_ref, g.type::text, g.residual_risk::text,"
        " g.priority_score, o.action, o.source_span->>'quote', c.source_span->>'quote',"
        " c.control_ref, g.rationale, g.evidence, o.applicability->>'level', c.id::text,"
        " g.status::text, r.action, r.owner_line::text, r.owner_role, r.due_date::text,"
        " r.success_criterion, r.drafted_by_model, m.verdict::text,"
        " m.judges->0->>'citation_ok', g.control_test_id IS NOT NULL, a.answer, a.reason,"
        " a.decided_by, a.attribute, a.value, a.basis"
        " FROM gap g JOIN obligation o ON o.id = g.obligation_id"
        " LEFT JOIN control c ON c.id = g.control_id"
        " LEFT JOIN mapping m ON m.id = g.mapping_id"
        " LEFT JOIN applicability_decision a ON a.obligation_id = o.id"
        " AND a.superseded_at IS NULL"
        # one remedy per regulation paragraph, shown on every high-confidence gap of it
        " LEFT JOIN LATERAL (SELECT r.* FROM remediation r JOIN gap g2 ON g2.id = r.gap_id"
        " JOIN obligation o2 ON o2.id = g2.obligation_id"
        " WHERE o2.source_clause_ref = o.source_clause_ref AND g.tier = 'high'"
        " ORDER BY (r.gap_id = g.id) DESC LIMIT 1) r ON true"
        " WHERE g.tier = %s AND g.superseded_at IS NULL AND g.status = 'open'"
        " ORDER BY g.priority_score DESC, o.source_clause_ref",
        (tier,),
    )
    keys = (
        "id", "ref", "type", "risk", "priority", "action", "rbi_text", "policy_text",
        "policy_ref", "why", "evidence", "level", "control_id", "status", "fix", "owner_line",
        "owner_role", "due", "closes_when", "drafted_by", "verdict", "citation_ok", "has_test",
        "applies", "applies_reason", "applies_by", "applies_attribute", "applies_value",
        "applies_basis",
    )  # fmt: skip
    return [dict(zip(keys, r, strict=True)) for r in rows]


def overview() -> None:
    counts = dict(
        query(
            "SELECT 'obligations', count(*) FROM obligation WHERE superseded_at IS NULL"
            " UNION ALL SELECT 'candidates', count(*) FROM control"
            " UNION ALL SELECT 'covered', count(*) FROM mapping WHERE verdict = 'covered'"
            " AND superseded_at IS NULL"
            " UNION ALL SELECT 'high', count(*) FROM gap WHERE tier = 'high' AND status = 'open'"
            " AND superseded_at IS NULL"
            " UNION ALL SELECT 'review', count(*) FROM gap WHERE tier = 'review'"
            " AND status = 'open' AND superseded_at IS NULL"
        )
    )
    docs = documents()
    st.info(
        "**Start here: three clicks, about two minutes**\n\n"
        "1. **Change agent** tab: choose *Real amendment, 29 Dec 2025* and press *Run the agent*. "
        "In about 15 seconds from the cache (under half a minute on a first run) it re-checks "
        "only the amended paragraph and reports the gaps that would open and close (5 to 10 "
        "analyst hours by our own estimate). Adding `?scenario=3` "
        "to the address preselects it.\n"
        "2. **Gaps** tab: select the row **65(10)(iv)**, then *Source citation*: the RBI sentence "
        "beside the policy sentence, three labelled dates, and a warning that the policy "
        "predates the amendment.\n"
        "3. **Evaluation** tab: *Banks the system had never seen*. Answer keys were frozen in "
        "git before the first run; the code was run once from a tagged commit."
    )
    st.subheader("What is loaded")
    if "regulation" in docs:
        st.markdown(f"**Regulation:** {docs['regulation']['source_title']}")
        for line in regulation_lines(regulation_citation(docs["regulation"], "all"))[1:]:
            st.write("•", line)
    if "policy" in docs:
        st.markdown("**Bank policy** (a copy with known gaps planted for testing)")
        for line in policy_lines(policy_citation(docs["policy"], None)):
            st.write("•", line)
    a, b, c, d, e = st.columns(5)
    a.metric("Obligations", counts.get("obligations", 0))
    b.metric("Policy passages", counts.get("candidates", 0))
    c.metric("Covered", counts.get("covered", 0))
    d.metric("Gaps, high confidence", counts.get("high", 0))
    e.metric("Review queue", counts.get("review", 0))
    st.caption(
        "Chain: regulation → obligations → applicability → policy passages → evidence → tests → "
        "gaps → remediation → monitoring. A model extracts and judges; code checks every "
        "citation, decides applicability, compares the wording, decides the gap type, ranks the "
        "risk and sets the tier. A person chooses which policy is checked against which "
        "Direction."
    )
    risk = query(
        "SELECT residual_risk::text, tier, count(*) FROM gap WHERE status = 'open'"
        " AND superseded_at IS NULL GROUP BY 1, 2"
    )
    if risk:
        st.subheader("Open gaps by residual risk")
        levels = ["critical", "high", "medium", "low"]
        table = {
            tier: [sum(n for lv, t, n in risk if lv == level and t == tier) for level in levels]
            for tier in ("high", "review")
        }
        st.bar_chart(
            {"risk": levels, "high confidence": table["high"], "review queue": table["review"]},
            x="risk",
        )


COMPARISON = {
    "same": "the policy states this near verbatim, same numbers and same force",
    "number_differs": "a number differs",
    "optional": "the policy sentence says 'may' where the obligation is mandatory",
    "adds_words": "the policy sentence adds a limiting phrase",
    "loose": "only loosely similar policy text exists",
    "no_similar_text": "no policy text resembles the obligation's wording",
}


@st.cache_data(ttl=600, show_spinner=False)
def policy_text() -> str:
    return query("SELECT text FROM document WHERE kind = 'policy'")[0][0]


def source_block(ref: str, policy_ref: str | None) -> None:
    """The full citation of a finding: both documents, with the three dates kept apart."""
    docs = documents()
    if "regulation" not in docs:
        return
    reg = regulation_citation(docs["regulation"], ref, markers_for(ref))
    with st.expander(f"Source citation: {reg['document']}, paragraph {ref}", expanded=False):
        left, right = st.columns(2)
        left.markdown("**Regulation**")
        for line in regulation_lines(reg):
            left.write("• " + line)
        if "policy" in docs:
            pol = policy_citation(docs["policy"], policy_ref)
            right.markdown("**Bank policy**")
            for line in policy_lines(pol):
                right.write("• " + line)
            for flag in predates(pol, reg):
                st.warning(flag)
        st.caption("Every date and reference is read from the stored source record, not a model.")


def gap_detail(g: dict) -> None:
    left, right = st.columns(2)
    left.markdown(f"**RBI {g['ref']}**")
    left.info(g["rbi_text"] or "-")
    ev = g["evidence"] or {}
    compared = ""
    if ev.get("kind") in COMPARISON and ev.get("char_start", -1) >= 0:
        compared = policy_text()[ev["char_start"] : ev["char_end"]].strip()
    right.markdown(f"**Policy passage** {g['policy_ref'] or ''}")
    if g["policy_text"]:
        right.warning(g["policy_text"])
    elif compared:
        right.warning(compared)
        right.caption("The judge cited no passage; this is the closest policy text by wording.")
    else:
        right.error("No passage in the policy addresses this.")
    source_block(g["ref"], g["policy_ref"])
    st.markdown(f"**Why it was raised:** {readable(g['why'])}")
    if ev.get("kind") in COMPARISON:
        note = COMPARISON[ev["kind"]] + (f": {ev['detail']}" if ev.get("detail") else "")
        st.markdown(
            f"**Text comparison:** {note}" + (f" ({ev['reason']})" if ev.get("reason") else "")
        )
        if compared and g["policy_text"] and compared[:60] not in g["policy_text"]:
            st.caption(f"Compared with: {compared[:400]}")
    if ev.get("check") == "level":
        level = ev.get("level", "").replace("_", " ")
        st.markdown(f"**Obligation level:** {level} (shown for review, not scored as a policy gap)")
    if g["applies"]:
        basis = (
            f" Profile attribute: {g['applies_attribute']} ({g['applies_value']}); basis: "
            f"{g['applies_basis'] or 'not stated'}."
            if g["applies_value"]
            else ""
        )
        st.markdown(
            f"**Applies to this bank:** {APPLIES[g['applies']]}: {g['applies_reason']}.{basis} "
            f"Decided by {g['applies_by']}."
        )
    cn = confidence_note(
        g["verdict"] or "partial", g["type"], ev, g["has_test"], g["citation_ok"] == "true",
        confidence_table(),
    )  # fmt: skip
    st.markdown(f"**Confidence note:** {'. '.join(cn['signals'])}. {cn['record']}")
    reason = assess(f"{g['action']}. {g['rbi_text']}", "", g["type"]).reasons[1]
    st.markdown(f"**Risk:** residual {g['risk']} (priority {g['priority']:.2f}); {reason}")
    if g["fix"]:
        st.markdown(f"**Remediation draft for RBI paragraph {g['ref']}** (one per paragraph)")
        st.success(g["fix"])
        doc = documents().get("regulation", {})
        version = day(doc.get("effective_from"))
        st.caption(
            f"Owner: {g['owner_line']} {g['owner_role']} · due {g['due']} · closes when: "
            f"{g['closes_when']} · drafted by {g['drafted_by']} · a proposal for a reviewer. "
            f"Basis: {doc.get('source_title', 'the regulation')}, paragraph {g['ref']} "
            f"({doc.get('reference_no', '')}; version updated as on {version})."
        )


def gaps_page(tier: str) -> None:
    rows = gaps(tier)
    label = "high-confidence tier" if tier == "high" else "review queue"
    st.subheader(f"{len(rows)} open gaps in the {label}")
    if tier == "review":
        st.caption(
            "Items a person should look at: the policy states the text nearly verbatim, the "
            "policy adds a limiting phrase, the obligation is procedure-level, or evidence has "
            "recovered. The system never closes a gap itself."
        )
    if not rows:
        return
    table = [
        {"RBI ref": g["ref"], "Gap type": g["type"].replace("_", " "), "Residual risk": g["risk"],
         "Priority": round(g["priority"], 2), "Obligation": g["action"][:110]}
        for g in rows
    ]  # fmt: skip
    picked = st.dataframe(
        table, use_container_width=True, hide_index=True, on_select="rerun",
        selection_mode="single-row", key=f"table-{tier}",
    )  # fmt: skip
    chosen = picked.selection.rows[0] if picked.selection.rows else 0
    g = rows[chosen]
    st.divider()
    gap_detail(g)
    if tier == "review":
        review_form(g)


MAX_CODE_ATTEMPTS = 5  # wrong reviewer codes per session; after that, simulation only


def review_form(g: dict) -> None:
    st.markdown("**Reviewer decision**")
    with st.form(f"review-{g['id']}"):
        decision = st.radio("Decision", list(DECISIONS), horizontal=True)
        reviewer = st.text_input("Reviewer name", max_chars=80)
        reason = st.text_input("Reason", max_chars=500)
        code = st.text_input("Reviewer code (leave empty to simulate)", type="password",
                             max_chars=64)  # fmt: skip
        sent = st.form_submit_button("Record decision")
    if not sent:
        return
    failed = st.session_state.get("code_failures", 0)
    if code and failed >= MAX_CODE_ATTEMPTS:
        st.warning("Too many wrong reviewer codes in this session; decisions are simulated only.")
        code = ""
    real = code_matches(code, os.environ.get("REVIEWER_CODE", ""))
    if code and not real:
        st.session_state["code_failures"] = failed + 1
    conn = connect()
    try:  # record() keeps the decision only when real; a simulation is rolled back as a whole
        out = record(conn, g["id"], decision, reviewer, reason, save=real)
        if real:
            st.cache_data.clear()
            st.success("Recorded: " + ", ".join(f"{k} {v}" for k, v in out.items() if v))
        else:
            st.info(
                "Simulation only, nothing was saved. It would record: "
                + ", ".join(f"{k} {v}" for k, v in out.items() if v)
            )
    except ValueError as e:
        st.error(str(e))
    finally:
        conn.close()


def version_citation(path: str) -> None:
    """Which document the agent is reading as the new version."""
    meta = regulation_meta_for_file(path)
    if meta is None:
        st.caption(
            f"New version: `{path}`, a synthetic draft written for this demo. It is not an RBI "
            "document and carries no RBI reference."
        )
        return
    lines = regulation_lines(regulation_citation(document_fields(meta), "all"))
    st.caption("New version: " + " · ".join(lines[1:]))


def change_page() -> None:
    st.subheader("Change agent")
    st.caption(
        "A new version of the regulation arrives. The agent compares the versions clause by "
        "clause, decides what each change means, finds the obligations and mappings it touches, "
        "re-extracts and re-judges only those, and reports which gaps would open or close. "
        "Here it always runs as a dry run: nothing is written."
    )
    # ?scenario=2 in the address opens the page on that scenario (links for the demo and checks)
    asked = st.query_params.get("scenario", "1")
    first = int(asked) - 1 if asked.isdigit() and 1 <= int(asked) <= len(SCENARIOS) else 0
    name = st.selectbox("Scenario", list(SCENARIOS), index=first)
    old, new = SCENARIOS[name]
    version_citation(new)
    fail = st.checkbox("Inject one failure in the re-mapping step (to show recovery)")
    if not st.button("Run the agent"):
        return
    from langgraph.checkpoint.memory import InMemorySaver
    from run_change import DbTools

    from regcomp.change.agent import build, graph_from_db

    def load_graph() -> dict:
        with connect(autocommit=True) as conn:
            return graph_from_db(conn)

    start = {"old_path": old, "new_path": new, "dry_run": True}
    if fail:
        start["inject_failure"] = "re_map"
    config = {"configurable": {"thread_id": f"demo-{name}-{fail}"}}
    # each step is shown as it finishes (the agent's own log lines), then the summary below
    with st.status("Running the agent", expanded=True) as status:
        try:
            agent = build(load_graph, InMemorySaver(), DbTools("demo"))
            for update in agent.stream(start, config, stream_mode="updates"):
                for step, change in update.items():
                    if step.startswith("__"):
                        continue
                    lines = change.get("log", []) if isinstance(change, dict) else []
                    for line in lines or [step.replace("_", " ")]:
                        status.write(f"• {line}")
            out = agent.get_state(config).values
            status.update(label="Finished", state="complete", expanded=False)
        except Exception as e:  # shown to the visitor instead of a stack trace
            status.update(label="Stopped", state="error")
            if any(word in str(e) for word in LIMIT_WORDS):
                st.warning(
                    "The hosted model's free allowance is used up for now, so the steps that "
                    "need a model (re-extract and re-judge) could not run. Nothing is wrong with "
                    "the data. Please try again later; the first scenario needs no model call."
                )
            else:
                st.error(
                    "The run stopped before it finished, most often because the hosted model "
                    "could not be reached just now. Nothing was written. The first scenario "
                    "needs no model and still runs; the other tabs need no model at all."
                )
                print(f"change agent stopped: {type(e).__name__}: {e}", file=sys.stderr)
            return
    st.markdown("**What the agent did**")
    for line in out.get("log", []):
        st.write("•", line)
    st.markdown(f"**Outcome:** {out.get('status', '?').replace('_', ' ')}")
    for step in out.get("plan", []):
        if step["action"] == "advise":
            st.info(
                f"Advisory for paragraph {step['ref']} (not a gap): {step['note']} "
                f"{step['summary']}"
            )
    delta = out.get("delta")
    if delta:
        a, b, c = st.columns(3)
        a.metric("Gaps that would open", len(delta["opened"]))
        b.metric("Gaps that would close", len(delta["closed"]))
        c.metric("Need review", len(delta["needs_review"]))
        for title, key in (
            ("Would open", "opened"),
            ("Would close", "closed"),
            ("Need review", "needs_review"),
        ):
            if delta[key]:
                st.markdown(f"**{title}**")
                st.dataframe(delta[key], use_container_width=True, hide_index=True)
    st.caption(f"Model used for the re-analysis steps: {model_for('judge')}")


@st.cache_data(ttl=300, show_spinner=False)
def applicability_inputs() -> tuple[str | None, list[tuple], list[tuple]]:
    profile = query(
        "SELECT profile FROM applicability_decision WHERE superseded_at IS NULL"
        " GROUP BY 1 ORDER BY max(recorded_at) DESC LIMIT 1"
    )
    obligations = query(
        "SELECT id::text, source_clause_ref, applicability->>'raw', source_span->>'quote'"
        " FROM obligation WHERE superseded_at IS NULL ORDER BY source_clause_ref"
    )
    open_gaps = query(
        "SELECT obligation_id::text, tier FROM gap WHERE status = 'open'"
        " AND superseded_at IS NULL AND tier IN ('high', 'review')"
    )
    return (profile[0][0] if profile else None), obligations, open_gaps


def applicability_page() -> None:
    st.subheader("Does each obligation apply to this bank?")
    profile_id, obligations, open_gaps = applicability_inputs()
    if not profile_id:
        st.write("The applicability stage has not been run for this bank.")
        return
    profile, vocab = appl.load_profile(profile_id), appl.load_vocab()
    st.caption(
        f"Bank profile: {profile['bank']} ({profile['entity_type']['value']}). The profile is "
        "built by code from the bank's own published policy: a product, channel, customer "
        "segment or geography is listed because the policy deals with it. Each obligation's "
        "limiting condition is matched against it by fixed rules. An obligation is excluded only "
        "when the profile states that the bank does not offer what the condition names."
    )
    listed = [
        {"Attribute": attribute.replace("_", " "), "The policy deals with": e["value"],
         "Where": e.get("where", ""), "Evidence (first mention)": e.get("evidence", "")}
        for attribute, entries in profile.get("has", {}).items()
        for e in entries
    ]  # fmt: skip
    with st.expander(f"Profile: {len(listed)} attributes found in the policy"):
        st.dataframe(listed, use_container_width=True, hide_index=True)

    def decide_all(p: dict) -> dict[str, dict]:
        return {
            oid: appl.decide({"applies_to": raw, "quote": quote}, p, vocab)
            for oid, _, raw, quote in obligations
        }

    now = decide_all(profile)
    counts = {a: sum(d["answer"] == a for d in now.values()) for a in APPLIES}
    a, b, c = st.columns(3)
    a.metric("Apply", counts["yes"])
    b.metric("Do not apply", counts["no"])
    c.metric("To confirm", counts["conditional"])

    st.caption(
        "On the banks tested this stage excluded nothing: a policy that restates the "
        "regulation mentions almost every product and channel. No precision gain is claimed."
    )
    st.markdown(
        "**Hypothetical: what if the bank did not offer something?** (dry run, nothing is written)"
    )
    options = [f"{x['Attribute']}: {x['The policy deals with']}" for x in listed]
    choice = st.selectbox("Suppose the bank did not offer", ["(nothing)", *options])
    if choice == "(nothing)":
        return
    picked = listed[options.index(choice)]
    changed = decide_all(
        appl.without(
            profile,
            picked["Attribute"].replace(" ", "_"),
            picked["The policy deals with"],
            basis="what-if statement",
        )
    )
    gaps_on = {}
    for oid, tier in open_gaps:
        gaps_on.setdefault(oid, []).append(tier)
    moved = [
        {"RBI ref": ref, "Now": APPLIES[changed[oid]["answer"]], "Reason": changed[oid]["reason"],
         "Open gaps on it": ", ".join(sorted(gaps_on.get(oid, []))) or "-",
         "Obligation": (quote or "")[:140]}
        for oid, ref, _, quote in obligations
        if changed[oid]["answer"] != now[oid]["answer"]
    ]  # fmt: skip
    out_ids = {oid for oid in changed if changed[oid]["answer"] == "no"}
    leaving = [t for oid in out_ids for t in gaps_on.get(oid, [])]
    a, b, c = st.columns(3)
    a.metric("Obligations that no longer apply", len(out_ids))
    b.metric("Obligations to confirm", sum(r["Now"] == "to confirm" for r in moved))
    c.metric(
        "Open gaps that would leave the tiers",
        len(leaving),
        help=f"high confidence {leaving.count('high')}, review queue {leaving.count('review')}",
    )
    st.caption(
        "Only an obligation whose own limiting condition names the attribute is excluded. One "
        "that merely mentions it in its sentence is marked 'to confirm' and keeps its gap."
    )
    if moved:
        st.dataframe(moved, use_container_width=True, hide_index=True)


def design_effectiveness() -> None:
    """Feature 6, design side: the stored design test of every control a mapping cites."""
    st.subheader("Design effectiveness")
    st.caption(
        "Every policy control that a mapping cites, tested by a fixed rule: does the passage name "
        "an owner, a frequency (or trigger or threshold) and the evidence the control produces? "
        "The model extracted these attributes offline; code decides. The rule checks that each "
        "attribute is stated, not that it is adequate ('as needed' counts as a frequency)."
    )
    rows = query(
        "SELECT k.control_ref, k.objective, k.owner, k.frequency, k.expected_evidence,"
        " t.result::text, t.rationale FROM control_test t JOIN control k ON k.id = t.control_id"
        " WHERE t.kind = 'design' ORDER BY t.result, k.control_ref"
    )
    a, b, c = st.columns(3)
    a.metric("Controls tested", len(rows))
    b.metric("Design-effective", sum(r[5] == "effective" for r in rows))
    c.metric("Missing an attribute", sum(r[5] != "effective" for r in rows))
    with st.expander("All design tests", expanded=False):
        st.dataframe(
            [
                {"Policy passage": ref, "Control": obj, "Owner": own or "",
                 "Frequency": freq or "", "Evidence": ev or "", "Result": res,
                 "Why": why}
                for ref, obj, own, freq, ev, res, why in rows
            ],
            use_container_width=True, hide_index=True,
        )  # fmt: skip


def evidence_page() -> None:
    design_effectiveness()
    st.subheader("Operating evidence")
    st.caption(
        "Synthetic logs (identifiers only) are tested by fixed rules; the model never sees a row. "
        "A failing control opens a gap; a recovered one waits for a reviewer."
    )
    rows = query(
        "SELECT e.source_path, e.period_start::text, e.period_end::text, e.population,"
        " e.exceptions, t.result::text, t.tolerance, t.tested_at::text FROM control_test t"
        " JOIN evidence e ON e.id = ANY(t.evidence_ids) WHERE t.kind = 'operating'"
        " ORDER BY t.tested_at"
    )
    st.dataframe(
        [
            {"Evidence file": Path(p).name, "Period": f"{a} to {b}", "Records": n,
             "Exceptions": x, "Tolerance": f"{tol:.0%}", "Result": res, "Tested": when[:16]}
            for p, a, b, n, x, res, tol, when in rows
        ],
        use_container_width=True, hide_index=True,
    )  # fmt: skip
    batch_simulation()


BATCH = ROOT / "data" / "evidence" / "nainital" / "batches"


def batch_simulation() -> None:
    """Features 6 and 7, ongoing monitoring: test the next evidence batch in memory."""
    import yaml

    st.markdown("**Test a new evidence batch (simulation)**")
    st.caption(
        "The October batch (synthetic, identifiers only) is tested by the same code-only rules as "
        "the offline monitor (`scripts/run_evidence.py`) and compared with each control's last "
        "result. Runs in memory: no model, nothing is written."
    )
    if not st.button("Test a new evidence batch (simulation)"):
        return
    entries = yaml.safe_load((BATCH / "manifest_2026-10.yaml").read_text(encoding="utf-8"))
    conn = connect()
    try:
        out = [preview_batch(conn, e, BATCH / e["file"]) for e in entries]
    finally:
        conn.rollback()
        conn.close()
    st.dataframe(
        [
            {"Evidence file": r["file"], "RBI ref": r["obligation_ref"],
             "Last result": r["previous"] or "none", "This batch": r["result"],
             "Figures": r["figures"], "Change": r["change"].replace("_", " "),
             "What would happen": r["would"]}
            for r in out
        ],
        use_container_width=True, hide_index=True,
    )  # fmt: skip
    st.info(
        "Simulation only: nothing was saved. A recovered control is never closed by the "
        "system; a reviewer closes it."
    )


def version_history() -> None:
    """'Evolves over time': a recorded commit of the change agent, made on the d2 copy."""
    path = ROOT / "eval" / "reports" / "version_history_d2.json"
    if not path.exists():
        return
    h = json.loads(path.read_text(encoding="utf-8"))
    st.divider()
    st.markdown("**Version history (recorded run on a copy of the database)**")
    st.caption(
        "The demo above never writes. To show the commit step, the agent was run once without "
        "the dry run on a copy of the database (d2), with the synthetic draft circular; this is "
        f"what it recorded. Code commit `{h['code_commit'][:7]}`. Development data."
    )
    e = h["event"]
    st.write(
        f"Change event `{e['id'][:8]}`: version `{e['old_version']}` → `{e['new_version']}`, "
        f"received {e['received_at'][:16]} UTC, gap delta {e['projected_gap_delta']:+d}."
    )
    for d in h["clause_diff"]:
        with st.expander(f"Clause {d['clause_ref']}: {d['change_class']}", expanded=False):
            st.caption(d["summary"])
            a, b = st.columns(2)
            a.markdown("**Before**")
            a.write(d["before"] or "(none)")
            b.markdown("**After**")
            b.write(d["after"] or "(none)")
    for kind, closed_key, new_key, cols in (
        ("Obligations", "closed", "added", ("ref", "action", "source_version")),
        ("Mappings", "closed", "added", ("ref", "verdict", "source_version")),
        ("Gaps", "closed", "opened", ("ref", "type", "tier")),
    ):
        part = h[kind.lower()]
        st.markdown(f"*{kind}*: {len(part[closed_key])} closed in time, "
                    f"{len(part[new_key])} added beside them (nothing deleted)")  # fmt: skip
        rows = [{"": "closed", **{c: r.get(c) for c in cols}} for r in part[closed_key]]
        rows += [{"": "new", **{c: r.get(c) for c in cols}} for r in part[new_key]]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def review_trail() -> None:
    """Reviewer decisions, as recorded on the d2 copy (the hosted demo never saves one)."""
    path = ROOT / "eval" / "reports" / "review_trail_d2.json"
    if not path.exists():
        return
    t = json.loads(path.read_text(encoding="utf-8"))
    st.divider()
    st.markdown("**Reviewer decision trail (recorded on a copy of the database)**")
    st.caption(
        "Decisions in this demo are simulations unless the reviewer code is given. These two "
        "were recorded on a copy of the database (d2) with the same decision code, as a "
        f"demonstration made on the author's instruction. Code commit `{t['code_commit'][:7]}`. "
        "Development data."
    )
    st.dataframe(
        [
            {"RBI ref": d["before"]["ref"], "Decision": d["decision"],
             "Status": d["result"]["status"], "Tier": d["result"]["tier"],
             "Mapping verdict": d["result"]["mapping_verdict"] or "unchanged",
             "Reason": d["reason"]}
            for d in t["decisions"]
        ],
        use_container_width=True, hide_index=True,
    )  # fmt: skip
    if t["review_override"]:
        st.caption(
            "A dismissal also writes a correction record (review_override), later used to check "
            "the judge against human decisions: "
            + "; ".join(
                f"RBI {o['ref']}: {o['old_verdict']} → {o['new_verdict']}"
                for o in t["review_override"]
            )  # fmt: skip
        )


SOURCE = {
    "offline": "results computed offline (local qwen3:8b, one laptop GPU), read from the database",
    "live": "live: runs now, with the hosted model (gpt-oss-120b) for re-extraction and judging",
    "code": "live: computed now by code from stored results (no model)",
}


def source_label(kind: str, also: str = "") -> None:
    """Say where a tab's content comes from: computed offline, or live in this app."""
    st.caption(f"Source: {SOURCE[kind]}" + (f"; {also}" if also else "") + ".")


def evaluation_page() -> None:
    st.subheader("How well does it work?")
    path = ROOT / "eval" / "reports" / "scorecard_nainital.json"
    if not path.exists():
        st.write("No scorecard has been published yet.")
        return
    card = json.loads(path.read_text(encoding="utf-8"))
    st.caption(
        f"Development bank, run `{card['run']}`, answer key `{card['key_commit']}`, scored "
        f"{card['scored_at']}. Known gaps were planted in a public bank policy before any run, "
        "with decoys that must not be flagged. Counts, never percentages: the sets are small."
    )
    for line in card["summary"]:
        st.write("•", line)
    st.dataframe(card["planted"], use_container_width=True, hide_index=True)
    st.warning(
        "These are development-set numbers; the comparison rules were written after studying "
        "this bank's misses. The three banks below were never seen while building the system."
    )
    held = {
        name: json.loads(f.read_text(encoding="utf-8"))
        for name, f in (
            ("Central Bank of India", ROOT / "eval" / "reports" / "scorecard_centralbank.json"),
            ("Dhanlaxmi Bank", ROOT / "eval" / "reports" / "scorecard_dhanlaxmi.json"),
            ("South Indian Bank", ROOT / "eval" / "reports" / "scorecard_southindianbank.json"),
        )
        if f.exists()
    }
    if held:
        tag = next(iter(held.values())).get("evaluated_code", {})
        st.markdown("**Banks the system had never seen** (run once, nothing tuned afterwards)")
        st.caption(
            f"Code: tag `{tag.get('tag', '?')}`, commit `{str(tag.get('commit', '?'))[:7]}`, run "
            "from a clean checkout. Answer keys were committed before any model read these "
            "policies. Claim: F3 / D1."
        )
        cols = st.columns(len(held))
        for col, (name, hc) in zip(cols, held.items(), strict=True):
            col.markdown(f"*{name}* (key `{hc['key_commit'].split()[0]}`)")
            for line in hc["summary"][:5]:
                col.write("• " + line)
            if hc.get("procedure_note"):
                col.caption("Note: " + hc["procedure_note"])
    if card.get("applicability"):
        st.markdown("**Applicability (bank profile)**")
        for line in card["applicability"]:
            st.write("•", line.lstrip("- "))
    if card.get("judge_confidence_reliability"):
        st.markdown("**Is the judge's own confidence number worth showing?**")
        st.dataframe(
            card["judge_confidence_reliability"], use_container_width=True, hide_index=True
        )
        st.caption(
            "Verdicts with a known answer come from the answer key and 50 adjudicated pairs. The "
            "number mostly restates the verdict (every checked verdict at 1.00 was 'covered'), so "
            "it is not shown on findings. Each finding carries a note built from checks that "
            "code can verify, with the record of that kind of finding on the development bank:"
        )
        st.dataframe(card["signal_records"], use_container_width=True, hide_index=True)
        st.caption(
            "Most findings of each kind are not adjudicated, and most adjudicated ones are gaps "
            "we planted, so these records are counts, not hit rates."
        )


st.title("RegCompliance Agent")
st.caption("RBI KYC Directions against a bank's published KYC policy · ET × Accenture AI Hackathon")
try:
    tabs = st.tabs(
        ["Overview", "Gaps", "Review queue", "Applicability", "Change agent", "Evidence",
         "Evaluation"]
    )  # fmt: skip
    with tabs[0]:
        source_label("offline")
        overview()
    with tabs[1]:
        source_label("offline")
        gaps_page("high")
    with tabs[2]:
        source_label("offline")
        gaps_page("review")
        review_trail()
    with tabs[3]:
        source_label("code")
        applicability_page()
    with tabs[4]:
        source_label("live")
        change_page()
        version_history()
    with tabs[5]:
        source_label("offline", also="the batch simulation runs live, in code")
        evidence_page()
    with tabs[6]:
        source_label("offline")
        evaluation_page()
except RuntimeError as e:  # database not configured or unreachable: say so, without details
    print(f"database error: {e}", file=sys.stderr)  # host only (regcomp.db), never credentials
    st.error("The database cannot be reached right now. Please try again in a minute.")
