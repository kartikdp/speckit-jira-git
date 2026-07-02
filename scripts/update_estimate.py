"""Set or update the original estimate on a Jira issue.

Accepts compound time strings (`1w 2d 3h 4m`) or decimals (`18.4h`, `3.5h`).
Decimals are converted to whole hours and minutes before being sent.

Usage:
    python update_estimate.py --issue PROJ-100 --estimate "18h 24m"
    python update_estimate.py --issue PROJ-100 --estimate "18.4h"
    python update_estimate.py --issue PROJ-100 --estimate "3.5h"
"""
from __future__ import annotations

import argparse
import re

from jira_client import JiraClient


_DECIMAL_HOUR_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*h\s*$", re.IGNORECASE)


def normalise_estimate(estimate: str) -> str:
    """Convert decimals like 18.4h to '18h 24m'. Pass through compound strings."""
    m = _DECIMAL_HOUR_RE.match(estimate)
    if not m:
        return estimate
    hours_decimal = float(m.group(1))
    h = int(hours_decimal)
    m_int = round((hours_decimal - h) * 60)
    if m_int == 60:
        h += 1
        m_int = 0
    if h and m_int:
        return f"{h}h {m_int}m"
    if h:
        return f"{h}h"
    return f"{m_int}m"


def main() -> None:
    ap = argparse.ArgumentParser(description="Set originalEstimate on a Jira issue")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--estimate", required=True, help='e.g. "18h 24m" or "18.4h"')
    args = ap.parse_args()

    estimate = normalise_estimate(args.estimate)
    client = JiraClient()
    client.put(
        f"/rest/api/3/issue/{args.issue}",
        {"fields": {"timetracking": {"originalEstimate": estimate}}},
    )
    print(f"Set originalEstimate={estimate} on {args.issue}")


if __name__ == "__main__":
    main()
