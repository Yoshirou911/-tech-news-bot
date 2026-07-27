"""送信済み記事の履歴(タイトル・要約・送信日時など)を記録するモジュール"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

HISTORY_FILE = Path(__file__).parent / "data" / "sent_history.json"


def _save(records: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data and isinstance(data[0], str):
        # 旧形式(URL文字列のみのリスト)からの移行
        data = [
            {"url": url, "title": "", "source": "", "score": 0, "summary_ja": "", "sent_at": ""}
            for url in data
        ]
        _save(data)

    return data


def get_sent_urls(records: list[dict]) -> set[str]:
    return {r["url"] for r in records}


def append_and_save(records: list[dict], new_articles: list[dict]) -> list[dict]:
    existing_urls = get_sent_urls(records)
    now = datetime.now(timezone.utc).isoformat()

    for article in new_articles:
        if article["url"] in existing_urls:
            continue

        records.append({
            "url": article["url"],
            "title": article["title"],
            "source": article["source"],
            "score": article.get("score", 0),
            "summary_ja": article.get("summary_ja", ""),
            "sent_at": now,
        })
        existing_urls.add(article["url"])

    _save(records)
    return records


if __name__ == "__main__":
    records = load_history()
    print(f"記録済み件数: {len(records)}")

    test_article = {
        "url": "https://example.com/test-article",
        "title": "テスト記事",
        "source": "Test",
        "score": 1,
        "summary_ja": "テスト用の要約です",
    }
    records = append_and_save(records, [test_article])
    print("テスト用記事を1件追加して保存しました")

    reloaded = load_history()
    assert any(r["url"] == test_article["url"] for r in reloaded)
    print(f"再読み込み後の件数: {len(reloaded)}（保存・読み込みが正常に動作しています）")
