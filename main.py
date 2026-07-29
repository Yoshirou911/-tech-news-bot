"""収集 → AI要約・フィルタリング → Discord通知 を1本につなげるエントリーポイント"""
import logging
import sys
from pathlib import Path

import history
import status
from collectors import arxiv, cve, github_trending, hackernews, huggingface, lobsters, qiita, reddit, rss
from notifiers import discord
from processors import summarizer

SECURITY_GITHUB_TOPICS = ["reverse-engineering", "game-hacking", "ctf"]


def _collect_security_repos(limit_per_topic: int = 4) -> list[dict]:
    repos = []
    for topic in SECURITY_GITHUB_TOPICS:
        repos += github_trending.search_by_topic(topic, limit=limit_per_topic)
    return repos

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
    ("Qiita", lambda: qiita.get_popular_articles(limit=10)),
    ("Zenn", lambda: rss.get_latest_from_feed("https://zenn.dev/feed", "Zenn", limit=10)),
    ("TechCrunch", lambda: rss.get_latest_from_feed("https://techcrunch.com/feed/", "TechCrunch", limit=10)),
    ("CVE", lambda: cve.get_recent_critical_cves(limit=10)),
    ("TheHackerNews", lambda: rss.get_latest_from_feed("https://feeds.feedburner.com/TheHackersNews", "TheHackerNews", limit=10)),
    ("SecurityRepos", lambda: _collect_security_repos(limit_per_topic=4)),
]


def collect_all_articles() -> tuple[list[dict], dict[str, str]]:
    articles = []
    source_results = {}

    for name, collect_fn in COLLECTORS:
        try:
            result = collect_fn()
            articles += result
            source_results[name] = f"ok ({len(result)}件)"
        except Exception as e:
            logging.exception(f"{name}の収集に失敗しました")
            print(f"[警告] {name}の収集に失敗しました（スキップします）")
            source_results[name] = f"error: {e}"

    return articles, source_results


def main() -> None:
    records = history.load_history()
    sent_urls = history.get_sent_urls(records)

    articles, source_results = collect_all_articles()
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

    discord_ok = True
    discord_error = None
    try:
        discord.send_digest(relevant_articles)
        print(f"{len(relevant_articles)}件をDiscordに通知しました")
        logging.info(f"{len(relevant_articles)}件をDiscordに通知しました")
    except Exception as e:
        logging.exception("Discordへの通知に失敗しました")
        print("[エラー] Discordへの通知に失敗しました（詳細はlogs/bot.logを確認してください）")
        discord_ok = False
        discord_error = str(e)

    # Discordへの通知が失敗しても、要約済みの記事は送信済みとして記録する。
    # (記録しないと、次回実行時に同じ記事を再処理し続けてしまうため)
    history.append_and_save(records, relevant_articles)

    status.save_run_status(
        collected_count=len(articles),
        skipped_count=skipped,
        sent_count=len(relevant_articles),
        source_results=source_results,
        discord_ok=discord_ok,
        discord_error=discord_error,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Botの実行が異常終了しました")
        raise
