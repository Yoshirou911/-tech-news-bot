"""Brave Search APIでWeb全体を検索するモジュール"""
import sys

import requests

import config

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://api.search.brave.com/res/v1/web/search"


def search_web(query: str, limit: int = 5) -> list[dict]:
    if not config.BRAVE_API_KEY:
        return []

    res = requests.get(
        API_URL,
        params={"q": query, "count": limit},
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": config.BRAVE_API_KEY,
        },
        timeout=15,
    )
    res.raise_for_status()

    results = []
    for item in res.json().get("web", {}).get("results", [])[:limit]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", ""),
        })

    return results


if __name__ == "__main__":
    results = search_web("latest LLM news 2026", limit=5)
    if not results:
        print("結果が0件、またはBRAVE_API_KEYが未設定です。")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   {r['url']}")
        print(f"   {r['snippet']}")
        print()
