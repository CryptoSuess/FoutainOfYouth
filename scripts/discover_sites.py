#!/usr/bin/env python3
"""Discover cool GitHub/web sites for Fountain of Youth.

Sources:
  - GitHub Search API via `gh`
  - Optional homepage URLs from matching repos
  - Optional local Ollama model for ranking + short descriptions

Nothing is published automatically. Candidates land in data/suggestions.json
with status=pending for human approval.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "discover_config.json"
SITES_PATH = ROOT / "data" / "sites.json"
SUGGESTIONS_PATH = ROOT / "data" / "suggestions.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:64] or "site"


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc:
        return None
    # Drop common tracking params
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    clean_query = [
        (k, v)
        for k, v in query
        if not k.lower().startswith("utm_") and k.lower() not in {"ref", "fbclid", "gclid"}
    ]
    cleaned = parsed._replace(query=urllib.parse.urlencode(clean_query), fragment="")
    return urllib.parse.urlunparse(cleaned)


def existing_urls_and_ids():
    sites = load_json(SITES_PATH, [])
    suggestions = load_json(SUGGESTIONS_PATH, {"suggestions": []}).get("suggestions", [])
    urls = set()
    ids = set()
    for item in list(sites) + list(suggestions):
        if item.get("url"):
            urls.add(item["url"].rstrip("/").lower())
        if item.get("id"):
            ids.add(item["id"])
        # Also treat github html_url variants
        if item.get("source_repo"):
            urls.add(item["source_repo"].rstrip("/").lower())
    return urls, ids


def gh_api(path: str):
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh api failed for {path}")
    return json.loads(result.stdout)


def search_github(query: str, per_page: int):
    q = urllib.parse.quote(query)
    path = f"search/repositories?q={q}&sort=stars&order=desc&per_page={per_page}"
    data = gh_api(path)
    return data.get("items", [])


def heuristic_score(repo: dict, min_stars: int) -> float:
    stars = float(repo.get("stargazers_count") or 0)
    forks = float(repo.get("forks_count") or 0)
    has_home = 1.0 if repo.get("homepage") else 0.0
    has_desc = 1.0 if (repo.get("description") or "").strip() else 0.0
    topics = repo.get("topics") or []
    topic_bonus = min(len(topics), 5) * 0.2
    # Log-ish star score so mega-repos don't dominate forever
    star_score = min(10.0, (stars / max(min_stars, 1)) ** 0.35 * 4.0)
    return round(star_score + has_home + has_desc + topic_bonus + min(forks, 5000) / 5000.0, 3)


def guess_category(text: str, categories: list[str]) -> str:
    t = text.lower()
    rules = [
        ("Crypto", ["crypto", "bitcoin", "ethereum", "defi", "web3", "blockchain", "nft"]),
        ("Privacy", ["privacy", "password", "encryption", "vpn", "osint", "security-audit"]),
        ("Developers", [
            "developer", "api", "cli", "agent", "agents", "llm", "mcp", "sdk",
            "framework", "github", "copilot", "autogpt", "puppeteer", "scraping",
            "devops", "compiler", "runtime",
        ]),
        ("Learning", ["learn", "course", "tutorial", "education", "book", "awesome-list", "curriculum", "from-scratch"]),
        ("Science", ["science", "physics", "biology", "arxiv", "research", "nasa"]),
        ("Maps and weather", ["map", "geo", "weather", "gis", "openstreetmap"]),
        ("News", ["news", "journalism", "media"]),
        ("Design", ["design", "figma", "ui", "ux", "font", "color", "css", "icon"]),
        ("Everyday tools", ["tool", "utility", "converter", "editor", "productivity"]),
        ("Reference", ["reference", "docs", "documentation", "encyclopedia", "wiki"]),
    ]
    for category, keywords in rules:
        if category in categories and any(k in t for k in keywords):
            return category
    return "Developers" if "Developers" in categories else categories[0]


def ollama_available(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def ollama_enrich(candidate: dict, categories: list[str], base_url: str, model: str) -> dict:
    prompt = f"""You help curate a public library of useful websites.
Return ONLY compact JSON with keys: keep (boolean), category (one of {categories}), description (one short factual sentence <= 140 chars), tags (array of 3-5 lowercase keywords), reason (short why keep/reject).

Candidate:
name: {candidate['name']}
url: {candidate['url']}
source: {candidate.get('source_repo')}
stars: {candidate.get('stars')}
raw_description: {candidate.get('raw_description')}
"""
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        raw = payload.get("response", "{}")
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        candidate["ai"] = {"error": str(exc)}
        return candidate

    if data.get("keep") is False:
        candidate["status"] = "rejected"
        candidate["reject_reason"] = data.get("reason") or "Rejected by local AI"
    if data.get("category") in categories:
        candidate["category"] = data["category"]
    if isinstance(data.get("description"), str) and data["description"].strip():
        candidate["description"] = data["description"].strip()[:180]
    if isinstance(data.get("tags"), list):
        tags = []
        for tag in data["tags"][:5]:
            cleaned = slugify(str(tag))
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
        if tags:
            candidate["tags"] = tags
    candidate["ai"] = {"model": model, "reason": data.get("reason")}
    return candidate


SKIP_HOMEPAGE_HOSTS = {
    "amzn.to",
    "amazon.com",
    "www.amazon.com",
    "partnerlinks.io",
    "n8n.partnerlinks.io",
    "bit.ly",
    "t.co",
    "tinyurl.com",
}


def usable_homepage(url: str | None) -> str | None:
    if not url:
        return None
    host = urllib.parse.urlparse(url).netloc.lower()
    if host in SKIP_HOMEPAGE_HOSTS or host.endswith(".partnerlinks.io"):
        return None
    return url


def repo_to_candidate(repo: dict, categories: list[str], min_stars: int, used_ids: set[str]):
    html_url = normalize_url(repo.get("html_url"))
    homepage = usable_homepage(normalize_url(repo.get("homepage")))
    # Prefer homepage when it looks like a real product site; otherwise the repo.
    url = homepage or html_url
    if not url:
        return None

    raw_name = repo.get("name") or repo.get("full_name") or "Untitled"
    if "-" in raw_name or "_" in raw_name:
        name = raw_name.replace("_", " ").replace("-", " ").strip()
        name = " ".join(part.capitalize() if part.islower() else part for part in name.split())
    else:
        name = raw_name

    base_id = slugify(repo.get("full_name") or raw_name)
    site_id = base_id
    n = 2
    while site_id in used_ids:
        site_id = f"{base_id}-{n}"
        n += 1
    used_ids.add(site_id)

    description = (repo.get("description") or "").strip() or f"GitHub project {repo.get('full_name')}"
    description = re.sub(r"\s+", " ", description)[:180]
    blob = " ".join(
        [
            name,
            description,
            " ".join(repo.get("topics") or []),
            repo.get("full_name") or "",
        ]
    )
    return {
        "id": site_id,
        "name": name,
        "url": url,
        "description": description,
        "category": guess_category(blob, categories),
        "tags": [slugify(t) for t in (repo.get("topics") or [])[:4] if t],
        "status": "pending",
        "score": heuristic_score(repo, min_stars),
        "stars": repo.get("stargazers_count"),
        "source_repo": html_url,
        "raw_description": repo.get("description"),
        "discovered_from": "github_search",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }


def discover(config: dict, use_ollama: bool, limit: int | None):
    urls, ids = existing_urls_and_ids()
    min_stars = int(config.get("min_stars", 1500))
    max_per_query = int(config.get("max_per_query", 8))
    max_suggestions = int(limit or config.get("max_suggestions", 25))
    categories = config.get("categories") or ["Developers"]
    queries = config.get("github_queries") or []

    found = []
    seen = set(urls)

    print(f"Running {len(queries)} GitHub queries…", file=sys.stderr)
    for query in queries:
        try:
            repos = search_github(query, max_per_query)
        except Exception as exc:
            print(f"  ! query failed ({query}): {exc}", file=sys.stderr)
            continue
        print(f"  • {query}: {len(repos)} repos", file=sys.stderr)
        for repo in repos:
            stars = repo.get("stargazers_count") or 0
            if stars < min_stars:
                continue
            candidate = repo_to_candidate(repo, categories, min_stars, ids)
            if not candidate:
                continue
            key = candidate["url"].rstrip("/").lower()
            repo_key = (candidate.get("source_repo") or "").rstrip("/").lower()
            if key in seen or (repo_key and repo_key in seen):
                continue
            seen.add(key)
            if repo_key:
                seen.add(repo_key)
            candidate["query"] = query
            found.append(candidate)

    found.sort(key=lambda c: c.get("score", 0), reverse=True)
    found = found[:max_suggestions]

    ollama_cfg = config.get("ollama") or {}
    if use_ollama and ollama_cfg.get("enabled", True):
        base_url = ollama_cfg.get("base_url", "http://127.0.0.1:11434")
        model = ollama_cfg.get("model", "llama3.2")
        if ollama_available(base_url):
            print(f"Enriching with local Ollama model `{model}`…", file=sys.stderr)
            enriched = []
            for candidate in found:
                enriched.append(ollama_enrich(candidate, categories, base_url, model))
            found = [c for c in enriched if c.get("status") != "rejected"]
        else:
            print("Ollama not reachable; using heuristic ranking only.", file=sys.stderr)

    # Ensure tags exist
    for candidate in found:
        if not candidate.get("tags"):
            candidate["tags"] = ["github", "open-source"]

    return found


def suggestion_keys(item: dict) -> set[str]:
    keys = set()
    if item.get("url"):
        keys.add("url:" + item["url"].rstrip("/").lower())
    if item.get("source_repo"):
        keys.add("repo:" + item["source_repo"].rstrip("/").lower())
    if item.get("id"):
        keys.add("id:" + item["id"])
    return keys


def merge_suggestions(new_items: list[dict]) -> dict:
    payload = load_json(
        SUGGESTIONS_PATH,
        {
            "generated_at": None,
            "notes": "Set status to approved or rejected. Run scripts/promote_suggestions.py to merge approved entries into sites.json.",
            "suggestions": [],
        },
    )
    existing = payload.get("suggestions") or []

    locked = []
    replaceable = []
    for item in existing:
        if item.get("status") in {"approved", "rejected", "promoted"}:
            locked.append(item)
        else:
            replaceable.append(item)

    # Drop replaceable items that match an incoming candidate by url/repo/id
    incoming_keys = set()
    for item in new_items:
        incoming_keys |= suggestion_keys(item)

    kept = []
    for item in replaceable:
        if suggestion_keys(item) & incoming_keys:
            continue
        kept.append(item)

    # Also avoid colliding with locked human decisions
    locked_keys = set()
    for item in locked:
        locked_keys |= suggestion_keys(item)

    merged_new = []
    for item in new_items:
        if suggestion_keys(item) & locked_keys:
            continue
        merged_new.append(item)

    merged = locked + kept + merged_new
    # Dedupe by url preferentially
    deduped = []
    seen = set()
    for item in merged:
        key = (item.get("url") or "").rstrip("/").lower() or item.get("id")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda s: (-float(s.get("score") or 0), s.get("name") or ""))
    payload["suggestions"] = deduped
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Max new suggestions to keep")
    parser.add_argument("--no-ollama", action="store_true", help="Skip local AI enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates without writing")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    found = discover(config, use_ollama=not args.no_ollama, limit=args.limit)
    print(f"Discovered {len(found)} candidate(s).", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(found, indent=2, ensure_ascii=False))
        return

    payload = merge_suggestions(found)
    save_json(SUGGESTIONS_PATH, payload)
    pending = sum(1 for s in payload["suggestions"] if s.get("status") == "pending")
    print(f"Wrote {SUGGESTIONS_PATH} ({pending} pending).", file=sys.stderr)


if __name__ == "__main__":
    main()
