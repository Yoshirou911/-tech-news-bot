"""Qiitaの人気記事を取得・検索するモジュール"""
import sys

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://qiita.com/api/v2/items"


def _to_articles(items: list[dict]) -> list[dict]:
    articles = []
    for item in items:
        articles.append({
            "source": "Qiita",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "score": item.get("likes_count", 0),
            "discussion_url": item.get("url", ""),
        })
    return articles


def get_popular_articles(limit: int = 10, min_likes: int = 30) -> list[dict]:
    res = requests.get(
        API_URL,
        params={"page": 1, "per_page": limit, "query": f"stocks:>{min_likes}"},
        timeout=15,
    )
    res.raise_for_status()
    return _to_articles(res.json())


def search_articles(query: str, limit: int = 10) -> list[dict]:
    res = requests.get(
        API_URL,
        params={"page": 1, "per_page": limit, "query": query},
        timeout=15,
    )
    res.raise_for_status()
    return _to_articles(res.json())


if __name__ == "__main__":
    articles = get_popular_articles(limit=10)
    for i, a in enumerate(articles, 1):
        print(f"{i}. [{a['score']}♥] {a['title']}")
        print(f"   URL: {a['url']}")
        print()
