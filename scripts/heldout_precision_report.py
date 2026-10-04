"""Precision of the high-confidence tier on the held-out banks, from the author's blind labels
and the full-policy text check of every row labelled gap.

    uv run python scripts/heldout_precision_report.py

Inputs (eval/reports/heldout_precision/): <policy>_labelled.csv (the sheet with the author's
labels), <policy>_private.json (which rows were findings), and the CHECK table below (the
outcome of scripts/heldout_full_policy_check.py for each row labelled gap, read by Claude).
Writes eval/reports/heldout_precision/summary.json and report.md. Counts only.

A "gap" label is set aside only when another passage of the policy carries the whole duty: the
same subject (and the same scope), mandatory wording, and the same requirement or a stricter one
(the three-part test, applied to all three banks on 4 Oct).
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
            "held",
            None,
            "68 (planted gap C05): reversed on 4 Oct under the three-part test. The first pass "
            "relied on 7.5.7.4, which flags only accounts meeting listed criteria (small "
            "accounts under named product codes, dormant individual SB/CD accounts) and states "
            "no action and no STR to FIU-IND; the full duty appears only in the narrowed 7.5.7.1",
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
            "44(2): 3.1.2.10(b) i-iii, same scope as RBI 44 (non-face-to-face accounts other "
            "than Section 17): a change of registered mobile number 'shall be done after' "
            "conversion to face-to-face or V-CIP, UIDAI e-KYC, or Regional Office approval at "
            "Scale IV and above; the policy is Board-approved (2(a)). Passes the three-part test",
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
            "held",
            None,
            "44(2): reversed on 4 Oct under the three-part test. The first pass relied on 'alerts "
            "and OTPs only to the Aadhaar-registered number', which sits in the Aadhaar OTP "
            "e-KYC section, the accounts RBI 44 excludes; nothing covers other non-face-to-face "
            "accounts",
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
            "held",
            None,
            "17(2): first-pass set-aside reversed under the three-part test (author, 4 Oct). "
            "Section 9(b), page 18 adds a precondition: 'Bank if finds any kind of suspicious "
            "activity under such situations shall consider filing an STR'; RBI makes failed CDD "
            "itself the trigger to consider one. Not the same or stricter",
        ),
        "10": (
            "held",
            None,
            "41(1): no other passage; 'enhanced due diligence measures are put in place' drops "
            "'establish the need'",
        ),
        "12": (
            "not_applicable",
            None,
            "65(5): not applicable (author, 4 Oct): the sentence binds REs other than SCBs; the "
            "applicability step did not exclude it. Counted as a false positive. The SCB duty "
            "(upload from 1 Jan 2017) is section 39(e), page 43",
        ),
        "15": (
            "held",
            None,
            "6(4)(i): first-pass set-aside reversed under the three-part test (author, 4 Oct). "
            "Section 22(b), page 35 ('Change of mobile number ... only after the identity of the "
            "customer is verified in face-to-face manner or through V-CIP') excludes Aadhaar OTP "
            "e-KYC accounts (section 13), which RBI 6(4)(i) covers; section 13 has no rule for "
            "change requests. Narrower scope",
        ),
        "16": (
            "covered",
            None,
            "42(7): section 21(e), page 34, states the whole requirement as in force (three "
            "advance intimations, three reminders, audit trail) in a policy approved 21 Mar 2026, "
            "after the 1 Jan 2026 deadline",
        ),
        "20": (
            "covered",
            None,
            "18: section 9.2, page 19: 'Reason(s) of rejection shall be duly recorded by the "
            "officer concerned'",
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
    (DIR / "report.md").write_text(report(summary), encoding="utf-8", newline="\n")
    for bank, out in summary.items():
        p = out["precision_high_tier"]
        print(f"{bank}: findings labelled gap {p['labelled_before_check']} (decided)")
        print(f"  after the full-policy check {p['after_full_policy_check']}")
        print(f"  duties only {p['duties_only']}; unsure {p['unsure']}")
        print(f"  covered pairs really covered {out['covered_pairs_really_covered']}")


NAMES = {
    "centralbank": "Central Bank",
    "dhanlaxmi": "Dhanlaxmi",
    "southindianbank": "South Indian Bank",
}


def report(summary: dict) -> str:
    banks = list(summary)
    p = {b: summary[b]["precision_high_tier"] for b in banks}

    def total(key: str) -> str:
        num = sum(int(p[b][key].split(" of ")[0]) for b in banks)
        den = sum(int(p[b][key].split(" of ")[1].split()[0]) for b in banks)
        return f"{num} of {den}"

    head = "| | " + " | ".join(NAMES[b] for b in banks) + " | Three banks |"
    rows = [
        head,
        "|---" * (len(banks) + 2) + "|",
        "| Findings labelled gap, of those decided | "
        + " | ".join(p[b]["labelled_before_check"] for b in banks)
        + f" | {total('labelled_before_check')} |",
        "| Real gaps after the full-policy check | "
        + " | ".join(p[b]["after_full_policy_check"] for b in banks)
        + f" | {total('after_full_policy_check')} |",
        "| Covered pairs really covered | "
        + " | ".join(summary[b]["covered_pairs_really_covered"] for b in banks)
        + " | |",
    ]
    lines = [
        "# Precision of the high-confidence tier on the unseen banks",
        "",
        "Generated by `scripts/heldout_precision_report.py` from the author's blind labels and the",
        "full-policy check. Counts only.",
        "",
        *rows,
        "",
        '**The three-part test.** A "gap" label is set aside only when another passage of the',
        "policy carries the whole duty: the same subject and scope, mandatory wording, and the",
        "same requirement or a stricter one. On 4 Oct the test was re-applied to every set-aside",
        "on all three banks:",
        "",
        "- South Indian Bank rows 5 and 15: the first-pass set-asides were reversed (row 5: the",
        "  policy adds a precondition before an STR is considered; row 15: the passage excludes",
        "  Aadhaar OTP e-KYC accounts). Both are real gaps.",
        "- South Indian Bank row 12 is recorded as not applicable: RBI 65(5) binds lenders other",
        "  than scheduled commercial banks, and the applicability step did not exclude it. It",
        "  counts as a false positive.",
        "- Central Bank row 9 (planted gap C05) and Dhanlaxmi row 7, both covered pairs: the",
        "  first-pass set-asides were reversed (row 9: the other passage flags only listed account",
        "  types and states no STR; row 7: the passage is in the Aadhaar OTP e-KYC section, which",
        "  RBI 44 excludes). Central Bank row 19 passes the test and stays covered.",
        "- No finding on Central Bank or Dhanlaxmi was set aside, so their precision is unchanged.",
        "",
        "On the third bank most high-confidence findings were duties the policy states in a",
        "different passage from the one the system compared, so its high-confidence tier was weak",
        "there.",
        "",
        "## Every checked row",
        "",
    ]
    for b in banks:
        lines.append(f"**{NAMES[b]}**")
        lines.append("")
        for n, c in summary[b]["checks"].items():
            lines.append(f"- row {n}: {c['outcome']}" + (f" ({c['kind']})" if c["kind"] else "")
                         + f". {c['note']}")  # fmt: skip
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
