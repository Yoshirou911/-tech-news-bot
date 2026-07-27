"""Lobsters(lobste.rs)のホット記事を取得するモジュール"""
import sys

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://lobste.rs/hottest.json"


def get_hot_stories(limit: int = 10) -> list[dict]:
    res = requests.get(API_URL, timeout=10)
    res.raise_for_status()

    stories = []
    for item in res.json()[:limit]:
        stories.append({
            "source": "Lobsters",
            "title": item["title"],
            "url": item.get("url") or item["comments_url"],
            "score": item.get("score", 0),
            "discussion_url": item["comments_url"],
        })

    return stories


if __name__ == "__main__":
    stories = get_hot_stories(limit=10)
    for i, story in enumerate(stories, 1):
        print(f"{i}. [{story['score']}pt] {story['title']}")
        print(f"   URL: {story['url']}")
        print()
