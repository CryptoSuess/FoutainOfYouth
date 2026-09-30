#!/usr/bin/env python3
"""Promote approved suggestions into data/sites.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES_PATH = ROOT / "data" / "sites.json"
SUGGESTIONS_PATH = ROOT / "data" / "suggestions.json"

LIBRARY_FIELDS = ("id", "name", "url", "description", "category", "tags")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def to_library_entry(item: dict) -> dict:
    entry = {key: item[key] for key in LIBRARY_FIELDS if key in item}
    if not isinstance(entry.get("tags"), list):
        entry["tags"] = []
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-approved",
        action="store_true",
        help="Keep approved items in suggestions.json after promoting (default: mark promoted)",
    )
    args = parser.parse_args()

    sites = load_json(SITES_PATH)
    suggestions_payload = load_json(SUGGESTIONS_PATH)
    suggestions = suggestions_payload.get("suggestions") or []

    existing_urls = {s.get("url", "").rstrip("/").lower() for s in sites}
    existing_ids = {s.get("id") for s in sites}

    promoted = []
    for item in suggestions:
        if item.get("status") != "approved":
            continue
        entry = to_library_entry(item)
        missing = [k for k in LIBRARY_FIELDS if k not in entry]
        if missing:
            print(f"Skipping {item.get('id')}: missing {missing}", file=sys.stderr)
            continue
        url_key = entry["url"].rstrip("/").lower()
        if url_key in existing_urls or entry["id"] in existing_ids:
            item["status"] = "promoted"
            continue
        sites.append(entry)
        existing_urls.add(url_key)
        existing_ids.add(entry["id"])
        item["status"] = "promoted"
        promoted.append(entry["id"])

    # Keep compact tag formatting like the rest of the catalog when possible
    save_json(SITES_PATH, sites)

    if not args.keep_approved:
        suggestions_payload["suggestions"] = suggestions
        save_json(SUGGESTIONS_PATH, suggestions_payload)

    print(f"Promoted {len(promoted)} site(s): {', '.join(promoted) or '(none)'}")


if __name__ == "__main__":
    main()
