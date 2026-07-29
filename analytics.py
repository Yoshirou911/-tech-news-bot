"""記事タイトルからトレンドキーワードを抽出したり、似たタイトルの重複を検出するモジュール"""
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "with", "and", "or", "is",
    "are", "this", "that", "from", "by", "at", "as", "it", "be", "new", "how",
    "why", "what", "your", "you", "we", "i", "using", "use", "can", "will",
    "not", "but", "about", "into", "up", "out", "my", "our", "their", "its",
    "was", "were", "has", "have", "had", "do", "does", "did", "if", "than",
    "more", "most", "all", "some", "no", "yes", "get", "one", "now", "just",
}


def extract_keywords(titles: list[str], top_n: int = 25) -> list[tuple[str, int]]:
    counter = Counter()

    for title in titles:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#\-\.]{1,}", title.lower())
        for word in words:
            word = word.strip(".-")
            if len(word) < 3 or word in STOPWORDS:
                continue
            counter[word] += 1

    return counter.most_common(top_n)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def dedupe_similar_titles(articles: list[dict], threshold: float = 0.85) -> list[dict]:
    """タイトルが似ている記事(同じ話題が複数ソースに載っているもの)をまとめ、最初の1件だけ残す"""
    kept: list[dict] = []
    kept_normalized: list[str] = []

    for article in articles:
        normalized = _normalize_title(article.get("title", ""))

        is_duplicate = any(
            SequenceMatcher(None, normalized, existing).ratio() >= threshold
            for existing in kept_normalized
        )
        if is_duplicate:
            continue

        kept.append(article)
        kept_normalized.append(normalized)

    return kept


if __name__ == "__main__":
    sample_titles = [
        "New LLM beats GPT-4 on benchmark",
        "LLM inference speed improved with new chip",
        "Understanding LLM architecture in depth",
    ]
    for word, count in extract_keywords(sample_titles):
        print(f"{word}: {count}")
