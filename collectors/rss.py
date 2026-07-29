"""RSSフィードから最新記事を取得する汎用モジュール(Zenn, TechCrunchなどに使用)"""
import sys

import feedparser

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def get_latest_from_feed(feed_url: str, source_name: str, limit: int = 10) -> list[dict]:
    feed = feedparser.parse(feed_url)

    articles = []
    for entry in feed.entries[:limit]:
        url = entry.get("link", "")
        articles.append({
            "source": source_name,
            "title": entry.get("title", ""),
            "url": url,
            "score": 0,
            "discussion_url": url,
        })

    return articles


if __name__ == "__main__":
    articles = get_latest_from_feed("https://zenn.dev/feed", "Zenn", limit=10)
    for i, a in enumerate(articles, 1):
        print(f"{i}. {a['title']}")
        print(f"   URL: {a['url']}")
        print()
