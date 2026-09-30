# Fountain of Youth

A public library of useful websites — curated, searchable, and easy to extend.

**[Open the library →](https://cryptosuess.github.io/FoutainOfYouth/)**

[![Fountain of Youth library UI](docs/library-preview.png)](https://cryptosuess.github.io/FoutainOfYouth/)

Search by name, description, or tag. Filter by category. Hover a card (desktop) to preview the site, then click to open it.

## Run locally

```bash
# any static server from the repo root, e.g.
python3 -m http.server 8080
# then open http://localhost:8080
```

## Site schema

Entries live in [`data/sites.json`](data/sites.json). Each object:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable kebab-case id |
| `name` | string | Display name |
| `url` | string | Full https URL |
| `description` | string | One short sentence |
| `category` | string | One of the existing categories (or a new one) |
| `tags` | string[] | A few lowercase keywords |

Example:

```json
{
  "id": "wikipedia",
  "name": "Wikipedia",
  "url": "https://www.wikipedia.org/",
  "description": "Free encyclopedia anyone can edit.",
  "category": "Reference",
  "tags": ["encyclopedia", "research"]
}
```

## Add a site

1. Open an issue with the **Suggest a site** template, or fork and edit `data/sites.json`.
2. Keep descriptions factual and short; no affiliate links.
3. Open a pull request. Nothing is published until a maintainer merges it.

## Discover sites with the local agent

Fountain of Youth includes a small discovery agent that crawls GitHub for cool candidates, ranks them with the **AI models already on your PC**, and writes them to [`data/suggestions.json`](data/suggestions.json) for your approval.

Works with whatever you already run locally:

- **Ollama** → `http://127.0.0.1:11434`
- **LM Studio** → `http://127.0.0.1:1234/v1`
- Any other **OpenAI-compatible** local server

```bash
# 0) Confirm your PC models are visible
python3 scripts/check_local_ai.py

# Optional: pin a model in data/discover_config.json → local_ai.model
# e.g. "llama3.2", "qwen2.5", "mistral", or whatever check_local_ai lists

# 1) Find + rank candidates (uses `gh` auth + your local model)
python3 scripts/discover_sites.py

# Heuristics only / limit results
python3 scripts/discover_sites.py --no-ai --limit 15

# 2) Review the queue
python3 scripts/review_suggestions.py pending

# 3) Approve / reject
python3 scripts/review_suggestions.py approve some-id another-id
python3 scripts/review_suggestions.py reject noisy-id --reason "too niche"

# 4) Promote approved entries into the live catalog
python3 scripts/promote_suggestions.py
```

Config: [`data/discover_config.json`](data/discover_config.json)

- `github_queries` — what to crawl
- `local_ai.endpoints` — where your models live
- `local_ai.model` — leave blank to auto-pick the first available model

A weekly GitHub Action can refresh suggestions without local AI; on your PC, leave Ollama/LM Studio running and discovery will use it automatically.

## Categories

Reference · Learning · Everyday tools · Developers · Design · Privacy · Maps and weather · News · Science · Crypto
