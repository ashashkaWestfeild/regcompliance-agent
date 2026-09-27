"""Evidence and control testing (chain links: evidence -> testing).

Evidence is synthetic, seeded and identifier-only (no personal data). Tests are deterministic:
- design test: does the control, as written, name an owner, a frequency or trigger, and the
  evidence it leaves? (attributes come from control extraction)
- operating test: exception rate in the evidence against a tolerance.
The LLM never sees evidence rows; at most it sees the aggregate test result (data guardrail).
"""

import csv
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

DEFAULT_TOLERANCE = 0.05  # exception rate above which a control is operating-ineffective


@dataclass
class TestOutcome:
    kind: str  # design | operating
    result: str  # effective | ineffective | cannot_assess
    population: int = 0
    exceptions: int = 0
    exception_rate: float | None = None
    tolerance: float | None = None
    rationale: str = ""


def design_test(control: dict) -> TestOutcome:
    """A control is design-effective if it names an owner, a frequency (or trigger/threshold)
    and the evidence it produces. Missing attributes are listed in the rationale."""
    missing = [
        name
        for name, value in (
            ("owner", control.get("owner")),
            ("frequency or threshold", control.get("frequency") or control.get("threshold")),
            ("evidence", control.get("evidence") or control.get("expected_evidence")),
        )
        if not value
    ]
    if not missing:
        return TestOutcome("design", "effective", rationale="owner, frequency and evidence named")
    return TestOutcome("design", "ineffective", rationale="not stated: " + ", ".join(missing))


def operating_test(
    rows: list[dict], is_exception, tolerance: float = DEFAULT_TOLERANCE, rule: str = ""
) -> TestOutcome:
    if not rows:
        return TestOutcome("operating", "cannot_assess", rationale="no evidence supplied")
    exceptions = sum(1 for r in rows if is_exception(r))
    rate = exceptions / len(rows)
    result = "effective" if rate <= tolerance else "ineffective"
    return TestOutcome(
        "operating",
        result,
        len(rows),
        exceptions,
        round(rate, 4),
        tolerance,
        f"{exceptions}/{len(rows)} exceptions ({rule}); tolerance {tolerance:.0%}",
    )


# ---------------------------------------------------------------- synthetic evidence

PERIOD_YEARS = {"high": 2, "medium": 8, "low": 10}  # periodicities stated in the Directions


def generate_rekyc(n: int, overdue_rate: float, seed: int, as_of: date) -> list[dict]:
    """Periodic KYC updation log: one row per account with its last and next KYC dates."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        risk = rng.choices(["high", "medium", "low"], weights=[15, 35, 50])[0]
        last = as_of - timedelta(days=rng.randint(30, PERIOD_YEARS[risk] * 365 - 30))
        if rng.random() < overdue_rate:  # overdue: last updation older than the period
            last = as_of - timedelta(days=PERIOD_YEARS[risk] * 365 + rng.randint(15, 400))
        rows.append(
            {
                "account_id": f"A{seed % 1000:03d}{i:05d}",
                "risk_category": risk,
                "last_kyc_update": last.isoformat(),
            }
        )
    return rows


def rekyc_overdue(as_of: date):
    def check(row: dict) -> bool:
        years = PERIOD_YEARS[row["risk_category"]]
        return date.fromisoformat(row["last_kyc_update"]) < as_of - timedelta(days=years * 365)

    return check


def generate_ckycr(
    n: int, late_rate: float, seed: int, start: date, deadline_days: int = 10
) -> list[dict]:
    """CKYCR upload log: account opening date and the date its KYC record was uploaded."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        opened = start + timedelta(days=rng.randint(0, 180))
        lag = rng.randint(1, deadline_days)
        if rng.random() < late_rate:
            lag = rng.randint(deadline_days + 1, deadline_days + 45)
        rows.append(
            {
                "account_id": f"C{seed % 1000:03d}{i:05d}",
                "opened_on": opened.isoformat(),
                "ckycr_uploaded_on": (opened + timedelta(days=lag)).isoformat(),
            }
        )
    return rows


def ckycr_late(deadline_days: int = 10):
    def check(row: dict) -> bool:
        lag = date.fromisoformat(row["ckycr_uploaded_on"]) - date.fromisoformat(row["opened_on"])
        return lag.days > deadline_days

    return check


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_dict(outcome: TestOutcome) -> dict:
    return asdict(outcome)
