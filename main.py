"""収集 → AI要約・フィルタリング → Discord通知 を1本につなげるエントリーポイント"""
import logging
import sys
from pathlib import Path

import history
from collectors import arxiv, github_trending, hackernews, huggingface, lobsters, reddit
from notifiers import discord
from processors import summarizer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)


COLLECTORS = [
    ("HackerNews", lambda: hackernews.get_top_stories(limit=10, min_score=50)),
    ("Reddit", lambda: reddit.get_all_subreddit_posts(limit_per_sub=5)),
    ("GitHubTrending", lambda: github_trending.get_trending_repos(limit=10)),
    ("arXiv", lambda: arxiv.get_latest_papers(limit=10)),
    ("Lobsters", lambda: lobsters.get_hot_stories(limit=10)),
    ("HuggingFace", lambda: huggingface.get_trending_models(limit=10)),
]


def collect_all_articles() -> list[dict]:
    articles = []

    for name, collect_fn in COLLECTORS:
        try:
            articles += collect_fn()
        except Exception:
            logging.exception(f"{name}の収集に失敗しました")
            print(f"[警告] {name}の収集に失敗しました（スキップします）")

    return articles


def main() -> None:
    records = history.load_history()
    sent_urls = history.get_sent_urls(records)

    articles = collect_all_articles()
    print(f"{len(articles)}件の記事を収集しました")
    logging.info(f"{len(articles)}件の記事を収集しました")

    new_articles = [a for a in articles if a["url"] not in sent_urls]
    skipped = len(articles) - len(new_articles)
    if skipped:
        print(f"{skipped}件は送信済みのためスキップします")

    relevant_articles = []
    for article in new_articles:
        try:
            result = summarizer.summarize_and_filter(article)
            if result is None:
                continue
            relevant_articles.append(result)
        except Exception:
            logging.exception(f"記事の処理に失敗しました: {article.get('url')}")
            continue

    discord.send_digest(relevant_articles)
    history.append_and_save(records, relevant_articles)

    print(f"{len(relevant_articles)}件をDiscordに通知しました")
    logging.info(f"{len(relevant_articles)}件をDiscordに通知しました")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Botの実行が異常終了しました")
        raise
