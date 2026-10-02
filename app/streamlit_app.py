"""RegCompliance Agent: the hosted demo (Streamlit).

Reads the compliance graph from Postgres and shows it: gaps in two tiers with their evidence,
the review queue, the change agent on real and draft amendments, operating evidence and the
evaluation numbers. Public visitors can look and simulate; writing needs the reviewer code.

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

from regcomp.db import connect  # noqa: E402
from regcomp.llm import model_for  # noqa: E402
from regcomp.review import DECISIONS, decide  # noqa: E402
from regcomp.risk import assess  # noqa: E402

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


@st.cache_data(ttl=120, show_spinner=False)
def query(sql: str, params: tuple = ()) -> list[tuple]:
    with connect(autocommit=True) as conn:
        return conn.execute(sql, params).fetchall()


@st.cache_data(ttl=120, show_spinner=False)
def gaps(tier: str) -> list[dict]:
    rows = query(
        "SELECT g.id::text, o.source_clause_ref, g.type::text, g.residual_risk::text,"
        " g.priority_score, o.action, o.source_span->>'quote', c.source_span->>'quote',"
        " c.control_ref, g.rationale, g.evidence, o.applicability->>'level', c.id::text,"
        " g.status::text, r.action, r.owner_line::text, r.owner_role, r.due_date::text,"
        " r.success_criterion, r.drafted_by_model"
        " FROM gap g JOIN obligation o ON o.id = g.obligation_id"
        " LEFT JOIN control c ON c.id = g.control_id"
        " LEFT JOIN remediation r ON r.gap_id = g.id"
        " WHERE g.tier = %s AND g.superseded_at IS NULL AND g.status = 'open'"
        " ORDER BY g.priority_score DESC, o.source_clause_ref",
        (tier,),
    )
    keys = (
        "id", "ref", "type", "risk", "priority", "action", "rbi_text", "policy_text",
        "policy_ref", "why", "evidence", "level", "control_id", "status", "fix", "owner_line",
        "owner_role", "due", "closes_when", "drafted_by",
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
    docs = query("SELECT kind::text, title, version_label FROM document ORDER BY kind")
    st.subheader("What is loaded")
    for kind, title, version in docs:
        st.write(f"**{kind.replace('_', ' ')}**: {title} (`{version}`)")
    a, b, c, d, e = st.columns(5)
    a.metric("Obligations", counts.get("obligations", 0))
    b.metric("Policy passages", counts.get("candidates", 0))
    c.metric("Covered", counts.get("covered", 0))
    d.metric("Gaps, high confidence", counts.get("high", 0))
    e.metric("Review queue", counts.get("review", 0))
    st.caption(
        "Chain: regulation → obligations → applicability → policy passages → evidence → tests → "
        "gaps → remediation → monitoring. A model extracts and judges; code checks every "
        "citation, compares the wording, decides the gap type, ranks the risk and sets the tier."
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
    st.markdown(f"**Why it was raised:** {g['why']}")
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
    reason = assess(f"{g['action']}. {g['rbi_text']}", "", g["type"]).reasons[1]
    st.markdown(f"**Risk:** residual {g['risk']} (priority {g['priority']:.2f}); {reason}")
    if g["fix"]:
        st.markdown("**Remediation draft**")
        st.success(g["fix"])
        st.caption(
            f"Owner: {g['owner_line']} {g['owner_role']} · due {g['due']} · closes when: "
            f"{g['closes_when']} · drafted by {g['drafted_by']}"
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


def review_form(g: dict) -> None:
    st.markdown("**Reviewer decision**")
    with st.form(f"review-{g['id']}"):
        decision = st.radio("Decision", list(DECISIONS), horizontal=True)
        reviewer = st.text_input("Reviewer name")
        reason = st.text_input("Reason")
        code = st.text_input("Reviewer code (leave empty to simulate)", type="password")
        sent = st.form_submit_button("Record decision")
    if not sent:
        return
    real = bool(os.environ.get("REVIEWER_CODE")) and code == os.environ["REVIEWER_CODE"]
    conn = connect()
    try:
        out = decide(conn, g["id"], decision, reviewer, reason)
        if real:
            conn.commit()
            st.cache_data.clear()
            st.success("Recorded: " + ", ".join(f"{k} {v}" for k, v in out.items() if v))
        else:
            conn.rollback()
            st.info(
                "Simulation only, nothing was saved. It would record: "
                + ", ".join(f"{k} {v}" for k, v in out.items() if v)
            )
    except ValueError as e:
        conn.rollback()
        st.error(str(e))
    finally:
        conn.close()


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
    fail = st.checkbox("Inject one failure in the re-mapping step (to show recovery)")
    if not st.button("Run the agent"):
        return
    from langgraph.checkpoint.memory import InMemorySaver
    from run_change import DbTools

    from regcomp.change.agent import build, graph_from_db

    old, new = SCENARIOS[name]

    def load_graph() -> dict:
        with connect(autocommit=True) as conn:
            return graph_from_db(conn)

    start = {"old_path": old, "new_path": new, "dry_run": True}
    if fail:
        start["inject_failure"] = "re_map"
    with st.spinner("Running: diff, classify, scope, plan, re-extract, re-map, compare"):
        try:
            agent = build(load_graph, InMemorySaver(), DbTools("demo"))
            out = agent.invoke(start, {"configurable": {"thread_id": f"demo-{name}-{fail}"}})
        except Exception as e:  # shown to the visitor instead of a stack trace
            st.error(f"The run stopped: {e}")
            return
    st.markdown("**What the agent did**")
    for line in out.get("log", []):
        st.write("•", line)
    st.markdown(f"**Outcome:** {out.get('status', '?').replace('_', ' ')}")
    for step in out.get("plan", []):
        if step["action"] == "advise":
            st.info(f"Advisory for clause {step['ref']}: {step['note']} {step['summary']}")
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


def evidence_page() -> None:
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
        "this bank's misses. Two banks the system has never seen are scored once, at the freeze."
    )


st.title("RegCompliance Agent")
st.caption("RBI KYC Directions against a bank's published KYC policy · ET × Accenture AI Hackathon")
try:
    tabs = st.tabs(["Overview", "Gaps", "Review queue", "Change agent", "Evidence", "Evaluation"])
    with tabs[0]:
        overview()
    with tabs[1]:
        gaps_page("high")
    with tabs[2]:
        gaps_page("review")
    with tabs[3]:
        change_page()
    with tabs[4]:
        evidence_page()
    with tabs[5]:
        evaluation_page()
except RuntimeError as e:  # database not configured or unreachable: say so, without details
    st.error(f"Cannot reach the database: {e}")
