#!/usr/bin/env python3
"""Probe local AI servers already running on this machine.

Checks Ollama and OpenAI-compatible endpoints (LM Studio, llama.cpp,
LocalAI, etc.) and prints which models are available for discovery.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "discover_config.json"


def get_json(url: str, timeout: float = 2.0, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe_ollama(base_url: str) -> list[str]:
    data = get_json(base_url.rstrip("/") + "/api/tags")
    return [m.get("name") for m in data.get("models", []) if m.get("name")]


def probe_openai(base_url: str, api_key: str = "") -> list[str]:
    headers = {"Authorization": f"Bearer {api_key or 'local'}"}
    data = get_json(base_url.rstrip("/") + "/models", headers=headers)
    models = data.get("data") or data.get("models") or []
    names = []
    for item in models:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("id"):
            names.append(item["id"])
    return names


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    local_ai = config.get("local_ai") or config.get("ollama") or {}
    endpoints = local_ai.get("endpoints")
    if not endpoints and local_ai.get("base_url"):
        # Backward-compatible single Ollama block
        endpoints = [
            {
                "name": "ollama",
                "provider": "ollama",
                "base_url": local_ai.get("base_url", "http://127.0.0.1:11434"),
            }
        ]

    found_any = False
    preferred_model = (local_ai.get("model") or "").strip()

    print("Probing local AI endpoints…\n")
    for endpoint in endpoints or []:
        name = endpoint.get("name") or endpoint.get("base_url")
        provider = (endpoint.get("provider") or "auto").lower()
        base_url = endpoint.get("base_url")
        if not base_url:
            continue
        try:
            if provider == "ollama" or (provider == "auto" and base_url.rstrip("/").endswith("11434")):
                models = probe_ollama(base_url)
                provider_label = "ollama"
            else:
                models = probe_openai(base_url, local_ai.get("api_key", ""))
                provider_label = "openai-compatible"
        except Exception as exc:
            print(f"✗ {name}")
            print(f"    {base_url}")
            print(f"    offline ({exc.__class__.__name__})")
            print()
            continue

        found_any = True
        print(f"✓ {name} [{provider_label}]")
        print(f"    {base_url}")
        if models:
            for model in models:
                mark = " (configured)" if preferred_model and model == preferred_model else ""
                print(f"    - {model}{mark}")
        else:
            print("    (no models listed)")
        print()

    if not found_any:
        print("No local AI servers responded.")
        print("Start Ollama, LM Studio, or another OpenAI-compatible local server, then retry.")
        print("Config: data/discover_config.json → local_ai")
        sys.exit(1)

    if preferred_model:
        print(f"Configured model: {preferred_model}")
    else:
        print("No model pinned in config — discovery will use the first model each server lists.")
    print("\nRun discovery with local AI:")
    print("  python3 scripts/discover_sites.py")


if __name__ == "__main__":
    main()
