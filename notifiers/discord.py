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
    "Qiita": 0x55C500,
    "Zenn": 0x3EA8FF,
    "TechCrunch": 0x0ABF53,
}
DEFAULT_COLOR = 0x5865F2


def send_message(content: str) -> None:
    response = requests.post(
        config.DISCORD_WEBHOOK_URL,
        json={"content": content},
        timeout=10,
    )
    response.raise_for_status()


# Discordの制限: 1メッセージ内の埋め込み合計文字数は6000まで、埋め込みは最大10個まで。
# 安全マージンを取って、埋め込み1個あたり2500文字、メッセージ合計5500文字を上限にする。
EMBED_CHAR_BUDGET = 2500
MAX_FIELDS_PER_EMBED = 20
MESSAGE_CHAR_BUDGET = 5500
MAX_EMBEDS_PER_MESSAGE = 10


def _build_embeds_for_source(source: str, articles: list[dict]) -> list[dict]:
    articles = sorted(articles, key=lambda a: a.get("score", 0), reverse=True)

    field_groups: list[list[dict]] = [[]]
    char_count = 0

    for article in articles:
        value = article.get("summary_ja") or "(要約なし)"
        value += f"\n[記事を見る]({article['url']})"
        field = {
            "name": article["title"][:256],
            "value": value[:1024],
            "inline": False,
        }
        field_len = len(field["name"]) + len(field["value"])

        current_group = field_groups[-1]
        if current_group and (
            char_count + field_len > EMBED_CHAR_BUDGET or len(current_group) >= MAX_FIELDS_PER_EMBED
        ):
            field_groups.append([])
            char_count = 0

        field_groups[-1].append(field)
        char_count += field_len

    total_parts = len(field_groups)
    embeds = []
    for i, fields in enumerate(field_groups, 1):
        title = f"{source}（{len(articles)}件）"
        if total_parts > 1:
            title += f" [{i}/{total_parts}]"
        embeds.append({
            "title": title,
            "color": SOURCE_COLORS.get(source, DEFAULT_COLOR),
            "fields": fields,
        })

    return embeds


def _embed_char_count(embed: dict) -> int:
    total = len(embed.get("title", "")) + len(embed.get("description", ""))
    for field in embed.get("fields", []):
        total += len(field.get("name", "")) + len(field.get("value", ""))
    return total


def _chunk_embeds_into_messages(embeds: list[dict]) -> list[list[dict]]:
    """メッセージあたりの埋め込み数(最大10)・合計文字数(最大6000、余裕を持って5500)を守って分割する"""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0

    for embed in embeds:
        embed_chars = _embed_char_count(embed)
        if current and (
            len(current) >= MAX_EMBEDS_PER_MESSAGE or current_chars + embed_chars > MESSAGE_CHAR_BUDGET
        ):
            chunks.append(current)
            current = []
            current_chars = 0

        current.append(embed)
        current_chars += embed_chars

    if current:
        chunks.append(current)

    return chunks


def send_digest(articles: list[dict]) -> None:
    if not articles:
        return

    grouped: dict[str, list[dict]] = {}
    for article in articles:
        grouped.setdefault(article["source"], []).append(article)

    embeds = []
    for source, items in grouped.items():
        embeds += _build_embeds_for_source(source, items)

    for i, chunk in enumerate(_chunk_embeds_into_messages(embeds)):
        payload = {"embeds": chunk}
        if i == 0:
            payload["content"] = f"📰 新着 {len(articles)}件のAI/技術ニュース"

        response = requests.post(
            config.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=15,
        )
        if not response.ok:
            print(f"[Discord APIエラー詳細] status={response.status_code} body={response.text[:500]}")
        response.raise_for_status()


if __name__ == "__main__":
    send_message("テスト送信です。Botの接続が確認できました。")
    print("送信しました。Discordチャンネルを確認してください。")
