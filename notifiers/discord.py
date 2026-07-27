"""DiscordのWebhookへメッセージを送信するモジュール"""
import sys

import requests

import config

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SOURCE_COLORS = {
    "HackerNews": 0xFF6600,
    "Reddit": 0xFF4500,
    "GitHubTrending": 0x6E5494,
    "arXiv": 0xB31B1B,
    "Lobsters": 0xA43225,
    "HuggingFace": 0xFFD21E,
}
DEFAULT_COLOR = 0x5865F2


def send_message(content: str) -> None:
    response = requests.post(
        config.DISCORD_WEBHOOK_URL,
        json={"content": content},
        timeout=10,
    )
    response.raise_for_status()


def _build_embed(source: str, articles: list[dict]) -> dict:
    articles = sorted(articles, key=lambda a: a.get("score", 0), reverse=True)

    fields = []
    for article in articles[:25]:
        value = article.get("summary_ja") or "(要約なし)"
        value += f"\n[記事を見る]({article['url']})"
        fields.append({
            "name": article["title"][:256],
            "value": value[:1024],
            "inline": False,
        })

    return {
        "title": f"{source}（{len(articles)}件）",
        "color": SOURCE_COLORS.get(source, DEFAULT_COLOR),
        "fields": fields,
    }


def send_digest(articles: list[dict]) -> None:
    if not articles:
        return

    grouped: dict[str, list[dict]] = {}
    for article in articles:
        grouped.setdefault(article["source"], []).append(article)

    embeds = [_build_embed(source, items) for source, items in grouped.items()]

    # Discordは1メッセージにつき埋め込み最大10件までなので分割して送信する
    for i in range(0, len(embeds), 10):
        chunk = embeds[i:i + 10]
        payload = {"embeds": chunk}
        if i == 0:
            payload["content"] = f"📰 新着 {len(articles)}件のAI/技術ニュース"

        response = requests.post(
            config.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()


if __name__ == "__main__":
    send_message("テスト送信です。Botの接続が確認できました。")
    print("送信しました。Discordチャンネルを確認してください。")
