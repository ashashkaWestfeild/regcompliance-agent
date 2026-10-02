"""Run the change agent on two versions of a regulation: diff -> classify -> scope -> plan ->
re-extract -> re-map -> compare.

    uv run python scripts/run_change.py --old data/raw/rbi/kycdir_v2_20251229.html \\
        --new data/raw/rbi/kycdir_v3_20260918.html
    uv run python scripts/run_change.py --old ... --new ... --dry-run     # what-if: writes nothing
    uv run python scripts/run_change.py --old ... --new ... --approve     # answer a paused run
    uv run python scripts/run_change.py --old data/raw/rbi/kycdir_v3_20260918.html \
        --new data/synthetic/kycdir_draft_whatif.html --dry-run --inject-failure re_map

The compliance graph is read from Postgres (the last run_map.py load). Agent state is
checkpointed in Postgres under the thread id, so a paused or crashed run continues from its last
completed step when the same command is given again.
"""

import argparse
import json
import sys
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from regcomp.change import execute
from regcomp.change.agent import build, graph_from_db, parse
from regcomp.db import connect, database_url


class DbTools:
    """Part 2 tools on the live graph. Each call opens its own connection: a model call can
    outlive an idle connection (Neon closes them)."""

    def re_extract(self, new_path: str, refs: list[str]) -> list[dict]:
        with connect(autocommit=True) as conn:
            return execute.re_extract(parse(new_path), refs, conn)

    def re_map(self, obligations: list[dict]) -> list[dict]:
        with connect(autocommit=True) as conn:
            return execute.re_map(obligations, conn)

    def current(self, obligation_ids: list[str]) -> list[dict]:
        with connect(autocommit=True) as conn:
            return execute.current(conn, obligation_ids)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--dry-run", action="store_true", help="what-if: plan only, never writes")
    ap.add_argument("--thread", help="checkpoint thread id (default: from the file names)")
    ap.add_argument(
        "--inject-failure",
        choices=["re_extract", "re_map"],
        help="recovery demo: this step fails once and the agent retries it",
    )
    answer = ap.add_mutually_exclusive_group()
    answer.add_argument("--approve", action="store_true", help="resume a paused run: continue")
    answer.add_argument("--reject", action="store_true", help="resume a paused run: stop")
    args = ap.parse_args()
    thread = args.thread or (
        f"{Path(args.old).stem}->{Path(args.new).stem}" + ("-dry" if args.dry_run else "")
    )
    config = {"configurable": {"thread_id": thread}}

    def load_graph() -> dict:
        with connect(autocommit=True) as conn:  # fresh connection: Neon drops idle ones
            return graph_from_db(conn)

    with PostgresSaver.from_conn_string(database_url()) as saver:
        saver.setup()
        agent = build(load_graph, saver, DbTools())
        if args.approve or args.reject:
            out = agent.invoke(Command(resume=args.approve), config)
        else:
            if agent.get_state(config).next:
                print(f"thread {thread!r} is paused; answer it with --approve or --reject")
                return 2
            start = {"old_path": args.old, "new_path": args.new, "dry_run": args.dry_run}
            if args.inject_failure:
                start["inject_failure"] = args.inject_failure
            out = agent.invoke(start, config)

    print(f"thread: {thread}")
    for line in out.get("log", []):
        print(" ", line)
    if "__interrupt__" in out:
        ask = out["__interrupt__"][0].value
        print(
            f"PAUSED: {ask['question']} {ask['mappings']} mappings, "
            f"{ask['blast_radius']:.1%} of the graph (limit {ask['limit']:.0%}). "
            "Re-run with --approve or --reject."
        )
        return 2
    print(f"status: {out['status']}")
    show = out["delta"] if "delta" in out else out["plan"]
    print(json.dumps(show, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
