"""arXiv(cs.AI, cs.LGカテゴリ)の最新論文を取得するモジュール"""
import sys

import feedparser
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "http://export.arxiv.org/api/query"


def get_latest_papers(categories: list[str] | None = None, limit: int = 10) -> list[dict]:
    categories = categories or ["cs.AI", "cs.LG"]
    search_query = " OR ".join(f"cat:{c}" for c in categories)

    res = requests.get(
        API_URL,
        params={
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": limit,
        },
        timeout=15,
    )
    res.raise_for_status()

    feed = feedparser.parse(res.text)

    papers = []
    for entry in feed.entries:
        papers.append({
            "source": "arXiv",
            "title": entry.title.replace("\n", " ").strip(),
            "url": entry.link,
            "score": 0,
            "discussion_url": entry.link,
        })

    return papers


def search_papers(query: str, limit: int = 10) -> list[dict]:
    res = requests.get(
        API_URL,
        params={
            "search_query": f"all:{query}",
            "sortBy": "relevance",
            "sortOrder": "descending",
            "max_results": limit,
        },
        timeout=15,
    )
    res.raise_for_status()

    feed = feedparser.parse(res.text)

    papers = []
    for entry in feed.entries:
        papers.append({
            "source": "arXiv",
            "title": entry.title.replace("\n", " ").strip(),
            "url": entry.link,
            "score": 0,
            "discussion_url": entry.link,
        })

    return papers


if __name__ == "__main__":
    papers = get_latest_papers(limit=10)
    for i, paper in enumerate(papers, 1):
        print(f"{i}. {paper['title']}")
        print(f"   URL: {paper['url']}")
        print()
