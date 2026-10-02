"""Which bank policy a pipeline run works on, and the guard around the held-out banks.

A policy is known by its id in data/sources.yaml. Its planted-gap copy and answer key live at
fixed paths. A policy whose split is a test split is refused unless the caller says the run is
the held-out run (--held-out): nothing may read those policies before the freeze.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

SOURCES = Path("data/sources.yaml")
# Version label written to the database. The first dev load keeps its original label.
LABELS = {"nainital": "nainital-mutated-350b8e0"}


@dataclass
class Policy:
    id: str
    bank: str
    split: str
    items: Path  # planted-gap copy of the policy (Docling items)
    key: Path  # answer key
    version: str
    profile: str  # bank profile id (data/profiles/<profile>.yaml)


def policy(policy_id: str, held_out: bool = False) -> Policy:
    sources = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["policies"]
    src = next((p for p in sources if p["id"] == policy_id), None)
    if src is None:
        raise SystemExit(f"unknown policy {policy_id!r}; see {SOURCES}")
    if str(src["split"]).startswith("test") and not held_out:
        raise SystemExit(
            f"{policy_id} is a held-out test set (split {src['split']}). It is run once, at the "
            "freeze: pass --held-out to confirm."
        )
    return Policy(
        id=policy_id,
        bank=src["bank"],
        split=str(src["split"]),
        items=Path(f"data/mutated/{policy_id}.items.json"),
        key=Path(f"eval/answer_key_{policy_id}.jsonl"),
        version=LABELS.get(policy_id, f"{policy_id}-mutated"),
        profile=src.get("profile", policy_id),
    )
