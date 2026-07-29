"""ダッシュボードのターミナル機能をDiscordのスラッシュコマンドとして使えるようにするBot"""
import sys
from collections import Counter

import discord
from discord import app_commands
from discord.ext import commands

import analytics
import config
import history
import status as status_module
from collectors import arxiv, github_trending, hackernews, qiita, websearch
from processors import summarizer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

MESSAGE_LIMIT = 1900  # Discordの1メッセージ最大2000文字に余裕を持たせる


def _format_articles(articles: list[dict]) -> str:
    if not articles:
        return "該当する記事はありませんでした。"

    lines = [
        f"**[{a.get('source', '')}]** [{a.get('title', '')}]({a.get('url', '')})\n{a.get('summary_ja', '')}"
        for a in articles
    ]
    return "\n\n".join(lines)[:MESSAGE_LIMIT]


def _format_bars(items: list[tuple[str, int]], label_width: int = 18) -> str:
    if not items:
        return "まだ十分なデータがありません。"

    max_count = items[0][1]
    lines = []
    for name, count in items:
        filled = round(count / max_count * 20) if max_count else 0
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"`{name[:label_width]:<{label_width}}` {bar} {count}")

    return "\n".join(lines)[:MESSAGE_LIMIT]


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"ログイン完了: {bot.user}")


@bot.tree.command(name="list", description="収集済み記事の一覧を表示")
@app_commands.describe(count="表示件数(デフォルト10)")
async def list_command(interaction: discord.Interaction, count: int = 10):
    await interaction.response.defer()

    records = history.load_history()
    records.sort(key=lambda a: a.get("sent_at", ""), reverse=True)

    await interaction.followup.send(_format_articles(records[:count]))


@bot.tree.command(name="search", description="HackerNews / arXiv / Qiitaをリアルタイム検索")
@app_commands.describe(keyword="検索キーワード")
async def search_command(interaction: discord.Interaction, keyword: str):
    await interaction.response.defer()

    raw_articles = []
    for fetch in (
        lambda: hackernews.search_stories(keyword, limit=3),
        lambda: arxiv.search_papers(keyword, limit=3),
        lambda: qiita.search_articles(keyword, limit=3),
    ):
        try:
            raw_articles += fetch()
        except Exception:
            pass

    results = []
    for article in raw_articles:
        result = summarizer.summarize_topic(article)
        if result:
            results.append(result)

    if results:
        records = history.load_history()
        history.append_and_save(records, results)

    await interaction.followup.send(_format_articles(results))


@bot.tree.command(name="ask", description="収集済み記事とWeb検索を根拠にAIへ質問")
@app_commands.describe(question="質問内容")
async def ask_command(interaction: discord.Interaction, question: str):
    await interaction.response.defer()

    records = history.load_history()
    records.sort(key=lambda a: a.get("sent_at", ""), reverse=True)

    try:
        web_results = websearch.search_web(question, limit=5)
    except Exception:
        web_results = []

    answer = summarizer.answer_question(question, records[:100], web_results)
    await interaction.followup.send((answer or "回答を取得できませんでした。")[:MESSAGE_LIMIT])


@bot.tree.command(name="trends", description="頻出キーワードランキングを表示")
async def trends_command(interaction: discord.Interaction):
    await interaction.response.defer()

    records = history.load_history()
    titles = [r["title"] for r in records if r.get("title")]
    keywords = analytics.extract_keywords(titles, top_n=15)

    await interaction.followup.send(_format_bars(keywords))


@bot.tree.command(name="hotspots", description="GitHub Trending開発者の所在地ランキングを表示")
async def hotspots_command(interaction: discord.Interaction):
    await interaction.response.defer()

    repos = github_trending.get_trending_repos(limit=15)
    locations = github_trending.get_owner_locations(repos)
    places = Counter(loc["location"] for loc in locations).most_common(15)

    await interaction.followup.send(_format_bars(places, label_width=22))


@bot.tree.command(name="status", description="Botの実行状況を表示")
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer()

    run = status_module.load_status()
    if not run:
        await interaction.followup.send("まだ実行記録がありません。")
        return

    overall_ok = run["discord_ok"] and all(v.startswith("ok") for v in run["source_results"].values())
    lines = [
        f"最終実行: {run['last_run_at']}",
        f"状態: {'✓ 正常' if overall_ok else '⚠ 異常あり'}",
        f"収集 {run['collected_count']}件 / 送信 {run['sent_count']}件",
        "",
        "**情報源:**",
    ]
    for name, result in run["source_results"].items():
        icon = "✓" if result.startswith("ok") else "✗"
        lines.append(f"{icon} {name}: {result}")

    await interaction.followup.send("\n".join(lines)[:MESSAGE_LIMIT])


if __name__ == "__main__":
    if not config.DISCORD_BOT_TOKEN:
        print("[エラー] DISCORD_BOT_TOKEN が .env に設定されていません")
    else:
        bot.run(config.DISCORD_BOT_TOKEN)
