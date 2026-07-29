"""通知したくない話題をキーワードでミュート(除外)するモジュール"""
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

MUTE_FILE = Path(__file__).parent / "data" / "muted_keywords.json"


def load_muted_keywords() -> list[str]:
    if not MUTE_FILE.exists():
        return []

    with open(MUTE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_muted_keywords(keywords: list[str]) -> None:
    MUTE_FILE.parent.mkdir(exist_ok=True)
    with open(MUTE_FILE, "w", encoding="utf-8") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)


def add_muted_keyword(keyword: str) -> list[str]:
    keywords = load_muted_keywords()
    keyword = keyword.strip().lower()

    if keyword and keyword not in keywords:
        keywords.append(keyword)
        save_muted_keywords(keywords)

    return keywords


def remove_muted_keyword(keyword: str) -> list[str]:
    keywords = load_muted_keywords()
    keyword = keyword.strip().lower()
    keywords = [k for k in keywords if k != keyword]
    save_muted_keywords(keywords)
    return keywords


def is_muted(title: str, keywords: list[str] | None = None) -> bool:
    keywords = load_muted_keywords() if keywords is None else keywords
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in keywords)


def filter_muted(articles: list[dict]) -> tuple[list[dict], int]:
    """ミュート対象を除いた記事リストと、除外した件数を返す"""
    keywords = load_muted_keywords()
    if not keywords:
        return articles, 0

    kept = [a for a in articles if not is_muted(a.get("title", ""), keywords)]
    return kept, len(articles) - len(kept)


if __name__ == "__main__":
    print("現在のミュートキーワード:", load_muted_keywords())
