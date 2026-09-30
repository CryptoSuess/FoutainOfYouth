#!/usr/bin/env python3
"""Mark suggestion statuses quickly from the CLI.

Examples:
  python3 scripts/review_suggestions.py approve public-apis-public-apis
  python3 scripts/review_suggestions.py reject some-id --reason "too niche"
  python3 scripts/review_suggestions.py list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUGGESTIONS_PATH = ROOT / "data" / "suggestions.json"


def load():
    return json.loads(SUGGESTIONS_PATH.read_text(encoding="utf-8"))


def save(payload):
    SUGGESTIONS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "approve", "reject", "pending"])
    parser.add_argument("ids", nargs="*", help="Suggestion ids")
    parser.add_argument("--reason", default="", help="Optional reject reason")
    args = parser.parse_args()

    payload = load()
    suggestions = payload.get("suggestions") or []

    if args.action == "list":
        for item in suggestions:
            print(f"{item.get('status','?'):9} {item.get('score',0):>6}  {item.get('id')}  {item.get('url')}")
        return

    if args.action == "pending":
        for item in suggestions:
            if item.get("status") == "pending":
                print(f"{item.get('score',0):>6}  {item.get('id')}  {item.get('name')}  {item.get('url')}")
        return

    if not args.ids:
        print("Provide one or more suggestion ids.", file=sys.stderr)
        sys.exit(1)

    wanted = set(args.ids)
    matched = 0
    for item in suggestions:
        if item.get("id") not in wanted:
            continue
        matched += 1
        if args.action == "approve":
            item["status"] = "approved"
            item.pop("reject_reason", None)
        else:
            item["status"] = "rejected"
            if args.reason:
                item["reject_reason"] = args.reason

    if matched != len(wanted):
        missing = wanted - {s.get("id") for s in suggestions}
        print(f"Unknown ids: {', '.join(sorted(missing))}", file=sys.stderr)
        sys.exit(1)

    save(payload)
    print(f"Updated {matched} suggestion(s).")


if __name__ == "__main__":
    main()
