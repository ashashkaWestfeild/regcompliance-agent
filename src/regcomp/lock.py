"""Result lock: a snapshot of every verdict, gap type, tier and score line, keyed by content.

Display and metadata work must change no result (user rule, 2 Oct 2026). The snapshot is keyed by
clause reference and character spans, never by database ids, so a rebuilt database compares equal
when the results are equal.
"""

import hashlib
import json
from collections import Counter

SCORE_SECTIONS = ("summary", "planted", "decoys", "injections", "real", "evidence")
ROW_SECTIONS = ("obligations", "mappings", "gaps")


def digest(snapshot: dict) -> str:
    body = {k: snapshot[k] for k in SCORE_SECTIONS}
    body.update({k: sorted(snapshot[k]) for k in ROW_SECTIONS})
    return hashlib.sha256(json.dumps(body, ensure_ascii=False).encode("utf-8")).hexdigest()


def differences(old: dict, new: dict, limit: int = 20) -> list[str]:
    """What changed between two snapshots, in words; empty when nothing did."""
    out = []
    for section in SCORE_SECTIONS:
        if old[section] != new[section]:
            out.append(f"{section} changed:")
            before, after = old[section], new[section]
            for line in before:
                if line not in after:
                    out.append(f"  - was: {json.dumps(line, ensure_ascii=False)}")
            for line in after:
                if line not in before:
                    out.append(f"  - now: {json.dumps(line, ensure_ascii=False)}")
    for section in ROW_SECTIONS:
        before = Counter(tuple(r) for r in old[section])
        after = Counter(tuple(r) for r in new[section])
        gone, came = before - after, after - before
        if gone or came:
            out.append(
                f"{section}: {sum(gone.values())} row(s) no longer present, "
                f"{sum(came.values())} new"
            )
            for row in sorted(gone.elements())[:limit]:
                out.append(f"  - was: {list(row)}")
            for row in sorted(came.elements())[:limit]:
                out.append(f"  - now: {list(row)}")
    return out
