"""Hacker Newsのトップ記事を取得するモジュール"""
import sys
import time

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ALGOLIA_SEARCH_BY_DATE_URL = "https://hn.algolia.com/api/v1/search_by_date"


def get_top_story_ids(limit: int = 30) -> list[int]:
    res = requests.get(f"{BASE_URL}/topstories.json", timeout=10)
    res.raise_for_status()
    return res.json()[:limit]


def get_item(item_id: int) -> dict:
    res = requests.get(f"{BASE_URL}/item/{item_id}.json", timeout=10)
    res.raise_for_status()
    return res.json()


def get_top_stories(limit: int = 10, min_score: int = 50) -> list[dict]:
    story_ids = get_top_story_ids(limit=limit * 3)
    stories = []

    for story_id in story_ids:
        item = get_item(story_id)

        if not item or "url" not in item:
            continue
        if item.get("score", 0) < min_score:
            continue

        stories.append({
            "source": "HackerNews",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "score": item.get("score", 0),
            "discussion_url": f"https://news.ycombinator.com/item?id={story_id}",
        })

        if len(stories) >= limit:
            break

    return stories


def search_stories(query: str, limit: int = 10) -> list[dict]:
    res = requests.get(
        ALGOLIA_SEARCH_URL,
        params={"query": query, "tags": "story", "hitsPerPage": limit},
        timeout=10,
    )
    res.raise_for_status()

    stories = []
    for hit in res.json().get("hits", []):
        if not hit.get("url"):
            continue

        stories.append({
            "source": "HackerNews",
            "title": hit["title"],
            "url": hit["url"],
            "score": hit.get("points", 0),
            "discussion_url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
        })

    return stories


def search_recent(query: str, limit: int = 10, days: int = 3) -> list[dict]:
    """直近N日以内に投稿されたHN記事をキーワード検索する(セキュリティ/リバースエンジニアリング等の専用収集に使用)"""
    since = int(time.time()) - days * 86400

    res = requests.get(
        ALGOLIA_SEARCH_BY_DATE_URL,
        params={
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{since}",
            "hitsPerPage": limit,
        },
        timeout=10,
    )
    res.raise_for_status()

    stories = []
    for hit in res.json().get("hits", []):
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
        stories.append({
            "source": "HackerNews",
            "title": hit.get("title") or hit.get("story_title") or "",
            "url": url,
            "score": hit.get("points", 0),
            "discussion_url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
        })

    return [s for s in stories if s["title"]]


if __name__ == "__main__":
    stories = get_top_stories(limit=10, min_score=50)
    for i, story in enumerate(stories, 1):
        print(f"{i}. [{story['score']}pt] {story['title']}")
        print(f"   URL: {story['url']}")
        print(f"   議論: {story['discussion_url']}")
        print()
