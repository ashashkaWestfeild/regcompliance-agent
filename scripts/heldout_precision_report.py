"""Precision of the high-confidence tier on the held-out banks, from the author's blind labels
and the full-policy text check of every row labelled gap.

    uv run python scripts/heldout_precision_report.py

Inputs (eval/reports/heldout_precision/): <policy>_labelled.csv (the sheet with the author's
labels), <policy>_private.json (which rows were findings), and the CHECK table below (the
outcome of scripts/heldout_full_policy_check.py for each row labelled gap, read by Claude).
Writes eval/reports/heldout_precision/summary.json. Counts only.
"""

import csv
import json
from pathlib import Path

DIR = Path("eval/reports/heldout_precision")
EXTRACTION_COVERAGE = {
    "centralbank": "about 62% of the policy text",
    "dhanlaxmi": "about 8%",
    "southindianbank": "not measured this way (extraction units: 134,634 of 165,629 characters)",
}

# Full-policy check of every row labelled gap: "held" (no other passage covers the obligation)
# or "covered" (covered elsewhere: the label does not count). "relief" marks a held row whose
# RBI text is a permission or relief the policy has not adopted rather than a duty it breaches.
CHECK = {
    "centralbank": {
        "2": (
            "held",
            "relief",
            "65(10)(iv): no text on relying on CKYCR records without "
            "re-verifying; the policy predates the Dec 2025 amendment",
        ),
        "7": (
            "held",
            "relief",
            "42(2): no low-risk relaxation (one year after falling due or 30 Jun 2026)",
        ),
        "9": (
            "covered",
            None,
            "68: a general section flags and monitors accounts as suspected "
            "money mules, not only savings accounts",
        ),
        "12": ("held", None, "42(7): no text on three advance intimations"),
        "13": (
            "held",
            None,
            "18: no text against rejecting an application without application of mind",
        ),
        "14": ("held", None, "42(7): no implementation deadline; the policy predates it"),
        "16": (
            "held",
            None,
            "65(10)(iv): responsibility for the rest of CDD when relying on CKYCR "
            "is not stated (only a general BC responsibility line)",
        ),
        "17": ("held", None, "42(7): no text on advance intimation of customers"),
        "18": (
            "held",
            None,
            "25(8): the declaration covers 'any other Bank', not any other regulated entity",
        ),
        "19": (
            "covered",
            None,
            "44(2): the policy sets a due-diligence process for changing a "
            "registered mobile number (e-KYC authentication, enhanced monitoring)",
        ),
        "20": ("held", None, "42(7): no text on three reminders after the due date"),
    },
    "dhanlaxmi": {
        "1": ("held", None, "24(6): no skew-or-tilt rule for document photographs"),
        "3": (
            "held",
            None,
            "24(11): no completion information or transaction id from the application",
        ),
        "7": (
            "covered",
            None,
            "44(2): alerts and OTPs go only to the Aadhaar-registered number, "
            "so alternate numbers are not used",
        ),
        "10": (
            "held",
            None,
            "24(9): consent to OTP authentication is stated; OTP as the signature on "
            "the CAF is not",
        ),
        "11": ("held", None, "74(3)(i)(c): no review of existing arrangements within three months"),
        "12": (
            "held",
            None,
            "65(10)(iv): no text on which RE verifies identity when relying on CKYCR",
        ),
        "16": ("held", None, "42(7): no text on three advance intimations"),
        "17": (
            "held",
            None,
            "24(4): no live photograph embedded in the CAF (only a self-attested "
            "photograph for small accounts)",
        ),
        "19": (
            "held",
            "relief",
            "24(9): the option to use a family member's mobile number is not "
            "adopted; a permission, not a duty",
        ),
        "20": (
            "held",
            None,
            "74(3)(i)(a): general wire-transfer information rules, nothing on "
            "unregulated entities in the chain",
        ),
    },
    "southindianbank": {
        "1": (
            "held",
            None,
            "65(10)(iv): nothing on the uploading entity verifying identity / address; the policy "
            "follows the Aug 2025 Master Direction, before the Dec 2025 amendment",
        ),
        "2": (
            "held",
            None,
            "45(1)(i): no system to determine whether a customer or beneficial owner is a PEP "
            "(planted gap S01, judged covered by the system)",
        ),
        "5": (
            "covered",
            None,
            "17(2): 'shall consider filing an STR, if necessary, when it is unable to comply with "
            "the relevant CDD measures' is stated in another passage",
        ),
        "10": (
            "held",
            None,
            "41(1): no other passage; 'enhanced due diligence measures are put in place' drops "
            "'establish the need'",
        ),
        "12": (
            "covered",
            None,
            "65(5): that sentence is for REs other than SCBs; the bank's own duty (upload from "
            "1 Jan 2017) is clause (e)",
        ),
        "15": (
            "covered",
            None,
            "6(4)(i): mobile number changes only after identity is verified face to face or by "
            "V-CIP",
        ),
        "16": (
            "covered",
            None,
            "42(7): the requirement is implemented (three advance intimations, 21(e)), so the "
            "deadline is met",
        ),
        "20": (
            "covered",
            None,
            "18: 'Reason(s) of rejection shall be duly recorded by the officer concerned'",
        ),
    },
}


def main() -> None:
    summary = {}
    for bank, checks in CHECK.items():
        private = json.loads((DIR / f"{bank}_private.json").read_text(encoding="utf-8"))["rows"]
        with (DIR / f"{bank}_labelled.csv").open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        col = next(c for c in rows[0] if c.startswith("YOUR_label"))
        out = {"findings": {}, "covered_pairs": {}}
        for r in rows:
            label = r[col].strip().lower()
            after, kind = label, None
            if label == "gap":
                state, kind, _ = checks[r["#"]]
                after = "gap" if state == "held" else "no gap"
            group = "findings" if private[r["#"]]["system_finding"] else "covered_pairs"
            out[group].setdefault("label", {}).setdefault(label or "blank", 0)
            out[group]["label"][label or "blank"] += 1
            out[group].setdefault("after_check", {}).setdefault(after or "blank", 0)
            out[group]["after_check"][after or "blank"] += 1
            if group == "findings" and after == "gap" and kind == "relief":
                out[group]["reliefs_among_real"] = out[group].get("reliefs_among_real", 0) + 1
        f = out["findings"]
        real_before = f["label"].get("gap", 0)
        decided_before = real_before + f["label"].get("no gap", 0)
        real_after = f["after_check"].get("gap", 0)
        decided_after = real_after + f["after_check"].get("no gap", 0)
        reliefs = f.get("reliefs_among_real", 0)
        out["precision_high_tier"] = {
            "labelled_before_check": f"{real_before} of {decided_before}",
            "after_full_policy_check": f"{real_after} of {decided_after}",
            "duties_only": f"{real_after - reliefs} of {decided_after - reliefs} "
            "(leaving out reliefs and permissions the policy has not adopted)",
            "unsure": f["label"].get("unsure", 0),
        }
        c = out["covered_pairs"]
        out["covered_pairs_really_covered"] = (
            f"{c['after_check'].get('no gap', 0)} of {sum(c['after_check'].values())}"
        )
        out["control_extraction_coverage"] = EXTRACTION_COVERAGE[bank]
        out["checks"] = {
            k: {"outcome": v[0], "kind": v[1], "note": v[2]} for k, v in checks.items()
        }
        summary[bank] = out
    (DIR / "summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    for bank, out in summary.items():
        p = out["precision_high_tier"]
        print(f"{bank}: findings labelled gap {p['labelled_before_check']} (decided)")
        print(f"  after the full-policy check {p['after_full_policy_check']}")
        print(f"  duties only {p['duties_only']}; unsure {p['unsure']}")
        print(f"  covered pairs really covered {out['covered_pairs_really_covered']}")


if __name__ == "__main__":
    main()
