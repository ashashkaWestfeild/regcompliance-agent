"""Measure the change agent's wall time per circular (dry run: nothing is written).

    uv run python scripts/time_change_agent.py                    # local model (Ollama, GPU)
    REGCOMP_MODEL=groq:openai/gpt-oss-120b uv run python scripts/time_change_agent.py   # hosted

For each scenario it reports the measured wall time of this run and every model call it made.
Calls found in the exact-match cache cost almost nothing now, so the run also reports what those
calls took when they were first made (llm_cache.latency_ms): measured wall time plus that is the
time a first, uncached run of the same circular takes. Writes eval/reports/change_agent_timing.json
(one entry per model path).
"""

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from run_change import DbTools

from regcomp import llm
from regcomp.change.agent import build, graph_from_db
from regcomp.db import connect

SCENARIOS = {
    "Real amendment, 29 Dec 2025 (CKYCR reliance)": (
        "data/raw/rbi/kycdir_v1_20251128.pdf",
        "data/raw/rbi/kycdir_v2_20251229.pdf",
    ),
    "Real amendment, 18 Sep 2026 (FPIs, certified copy)": (
        "data/raw/rbi/kycdir_v2_20251229.html",
        "data/raw/rbi/kycdir_v3_20260918.html",
    ),
    "Synthetic draft circular (one new duty)": (
        "data/raw/rbi/kycdir_v3_20260918.html",
        "data/synthetic/kycdir_draft_whatif.html",
    ),
}
OUT = Path("eval/reports/change_agent_timing.json")
calls: list[dict] = []
_original = llm._cache


def _spy(sql: str, params: tuple, conn):
    """Record each model-call lookup: was it cached, and what did it cost when first made."""
    if sql.startswith("SELECT response FROM llm_cache"):
        row = _original(
            "SELECT latency_ms, stage FROM llm_cache WHERE key = %s", params, conn
        ).fetchone()
        calls.append(
            {
                "cached": bool(row),
                "first_ms": row[0] if row else None,
                "stage": row[1] if row else None,
            }
        )
    elif sql.startswith("INSERT INTO llm_cache") and calls:
        calls[-1].update(stage=params[1], new_ms=params[5])
    return _original(sql, params, conn)


def machine() -> str:
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return f"one laptop, {platform.machine()} CPU, GPU {gpu or 'none'} (8 GB)"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    llm._cache = _spy
    model = llm.model_for("judge")
    path = "hosted" if model.split(":", 1)[0] in llm.HOSTED else "local"

    def load_graph() -> dict:
        with connect(autocommit=True) as conn:
            return graph_from_db(conn)

    results = []
    for name, (old, new) in SCENARIOS.items():
        calls.clear()
        agent = build(load_graph, InMemorySaver(), DbTools(f"timing-{path}"))
        start = time.perf_counter()
        out = agent.invoke(
            {"old_path": old, "new_path": new, "dry_run": True},
            {"configurable": {"thread_id": f"timing-{path}-{name}"}},
        )
        wall = time.perf_counter() - start
        cached = [c for c in calls if c["cached"]]
        fresh = [c for c in calls if not c["cached"]]
        first = sum(c["first_ms"] or 0 for c in cached) / 1000
        results.append(
            {
                "scenario": name,
                "status": out.get("status"),
                "model_calls": len(calls),
                "calls_from_cache": len(cached),
                "calls_made_now": len(fresh),
                "measured_wall_s": round(wall, 1),
                "cached_calls_first_run_s": round(first, 1),
                "first_run_estimate_s": round(wall + first, 1),
            }
        )
        r = results[-1]
        print(
            f"{name}: {r['status']}; {r['model_calls']} model calls ({r['calls_from_cache']} "
            f"cached); wall {r['measured_wall_s']} s; first-run estimate "
            f"{r['first_run_estimate_s']} s"
        )

    report = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    report[path] = {
        "model": model,
        "machine": machine()
        if path == "local"
        else f"hosted endpoint ({model}); run from {machine()}",
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "dry_run": True,
        "scenarios": results,
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"written: {OUT} ({path})")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
