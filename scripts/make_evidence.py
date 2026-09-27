"""Generate the synthetic evidence files (seeded, identifier-only) and print their tests.

Dev bank (Nainital) evidence: re-KYC log passes (2% overdue), CKYCR upload log deliberately
fails (12% late against the 10-day deadline, tolerance 5%).

    uv run python scripts/make_evidence.py
"""

from datetime import date
from pathlib import Path

from regcomp.evidence import (
    ckycr_late,
    generate_ckycr,
    generate_rekyc,
    operating_test,
    read_csv,
    rekyc_overdue,
    write_csv,
)

AS_OF = date(2026, 9, 30)
OUT = Path("data/evidence/nainital")


def main() -> None:
    write_csv(
        generate_rekyc(1200, overdue_rate=0.02, seed=101, as_of=AS_OF),
        OUT / "rekyc_updation_log.csv",
    )
    write_csv(
        generate_ckycr(800, late_rate=0.12, seed=202, start=date(2026, 3, 1)),
        OUT / "ckycr_upload_log.csv",
    )
    rekyc = operating_test(
        read_csv(OUT / "rekyc_updation_log.csv"),
        rekyc_overdue(AS_OF),
        rule="KYC updation overdue for the risk category",
    )
    ckycr = operating_test(
        read_csv(OUT / "ckycr_upload_log.csv"),
        ckycr_late(10),
        rule="uploaded more than 10 days after opening",
    )
    for name, t in (("re-KYC updation", rekyc), ("CKYCR upload", ckycr)):
        print(f"{name}: {t.result} - {t.rationale}")


if __name__ == "__main__":
    main()
