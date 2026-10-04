"""The reviewer code that turns a simulated decision in the app into a recorded one."""

import hmac


def code_matches(code: str, expected: str) -> bool:
    """Constant-time check of a reviewer code against the configured one. An unset code never
    matches, so without REVIEWER_CODE every decision in the app is a simulation."""
    return bool(expected) and bool(code) and hmac.compare_digest(code.encode(), expected.encode())
