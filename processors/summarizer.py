"""記事をAIでフィルタリングし、日本語3行要約を生成するモジュール"""
import json
import sys

import config

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

FILTER_PROMPT = """あなたは技術ニュースの編集者です。渡された記事のタイトルとURLを見て、
AI・LLM・IoT・ハードウェア・セキュリティに関する「実用的で驚きのある(ヤバい)情報」かどうかを判定してください。

判定基準:
- 実用的な技術的進展、驚くべき性能向上、新しいハードウェアなどは該当する
- 重大な脆弱性(CVE)、サイバー攻撃、侵入テスト、CTF、リバースエンジニアリング等のセキュリティ関連情報も該当する
- 単なる意見記事、ゴシップ、無関係な話題(政治・スポーツ等)は該当しない

必ず以下のJSON形式のみで回答してください(説明文やコードブロックは不要):
{"is_relevant": true または false, "summary_ja": "日本語3行要約(該当する場合のみ。改行は\\nで表現)"}
"""

TOPIC_PROMPT = """あなたは技術ニュースの編集者です。渡された記事のタイトルとURLを見て、日本語3行で要約してください。

必ず以下のJSON形式のみで回答してください(説明文やコードブロックは不要):
{"summary_ja": "日本語3行要約(改行は\\nで表現)"}
"""


def _build_user_prompt(article: dict) -> str:
    return f"タイトル: {article['title']}\nURL: {article['url']}\n出典: {article['source']}"


def _parse_response(text: str) -> dict:
    text = text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    return json.loads(text)


def _call_anthropic(article: dict, system_prompt: str) -> dict:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": _build_user_prompt(article)}],
    )
    return _parse_response(response.content[0].text)


def _call_openai(article: dict, system_prompt: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(article)},
        ],
    )
    return _parse_response(response.choices[0].message.content)


def _call_gemini(article: dict, system_prompt: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=_build_user_prompt(article),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
    )
    return _parse_response(response.text)


def _call_groq(article: dict, system_prompt: str) -> dict:
    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(article)},
        ],
    )
    return _parse_response(response.choices[0].message.content)


_PROVIDERS = {
    "groq": (_call_groq, lambda: bool(config.GROQ_API_KEY)),
    "gemini": (_call_gemini, lambda: bool(config.GEMINI_API_KEY)),
    "anthropic": (_call_anthropic, lambda: bool(config.ANTHROPIC_API_KEY)),
    "openai": (_call_openai, lambda: bool(config.OPENAI_API_KEY)),
}


def _call_anthropic_text(system_prompt: str, user_prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_openai_text(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def _call_gemini_text(system_prompt: str, user_prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text


def _call_groq_text(system_prompt: str, user_prompt: str) -> str:
    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


_TEXT_PROVIDERS = {
    "groq": (_call_groq_text, lambda: bool(config.GROQ_API_KEY)),
    "gemini": (_call_gemini_text, lambda: bool(config.GEMINI_API_KEY)),
    "anthropic": (_call_anthropic_text, lambda: bool(config.ANTHROPIC_API_KEY)),
    "openai": (_call_openai_text, lambda: bool(config.OPENAI_API_KEY)),
}


def answer_question(question: str, articles: list[dict], web_results: list[dict] | None = None) -> str | None:
    """収集済み記事とWeb検索結果を根拠として、ユーザーの質問に自由文で回答する"""
    context = "\n".join(
        f"- [{a.get('source', '')}] {a.get('title', '')}: {a.get('summary_ja') or '(要約なし)'}"
        for a in articles
    )

    web_context = ""
    if web_results:
        web_lines = "\n".join(
            f"- {r.get('title', '')} ({r.get('url', '')}): {r.get('snippet', '')}"
            for r in web_results
        )
        web_context = f"\n\nWeb検索結果:\n{web_lines}"

    system_prompt = (
        "あなたは技術ニュースのアシスタントです。以下はBotがこれまで収集した記事の一覧(タイトルと要約)、"
        "および質問に関連する最新のWeb検索結果です。\n"
        "これらの情報を根拠に、ユーザーの質問に日本語でわかりやすく答えてください。\n"
        "根拠にした記事やWebページがあれば具体的に言及してください。情報が見当たらない場合は、正直にその旨を伝えてください。\n\n"
        f"記事一覧:\n{context}"
        f"{web_context}"
    )

    last_error = None
    for name in config.AI_PROVIDER_PRIORITY:
        call_fn, is_configured = _TEXT_PROVIDERS[name]
        if not is_configured():
            continue

        try:
            return call_fn(system_prompt, question)
        except Exception as e:
            last_error = e
            continue

    if last_error:
        print(f"[エラー] すべてのAIプロバイダで失敗しました: {last_error}")
    return None


def summarize_and_filter(article: dict) -> dict | None:
    """AI/ハードウェア関連の「ヤバい情報」かどうか判定し、該当する場合のみ要約を返す"""
    last_error = None

    for name in config.AI_PROVIDER_PRIORITY:
        call_fn, is_configured = _PROVIDERS[name]
        if not is_configured():
            continue

        try:
            result = call_fn(article, FILTER_PROMPT)
        except Exception as e:
            print(f"[警告] {name} での処理に失敗、次のプロバイダを試します: {e}")
            last_error = e
            continue

        if result.get("is_relevant"):
            return {**article, "summary_ja": result["summary_ja"]}
        return None

    if last_error:
        print(f"[エラー] すべてのAIプロバイダで失敗しました: {last_error}")
    else:
        print("[エラー] 利用可能なAI APIキーが .env に設定されていません")
    return None


def summarize_topic(article: dict) -> dict | None:
    """関連性フィルタなしで、常に日本語3行要約を返す(トピック検索用)"""
    last_error = None

    for name in config.AI_PROVIDER_PRIORITY:
        call_fn, is_configured = _PROVIDERS[name]
        if not is_configured():
            continue

        try:
            result = call_fn(article, TOPIC_PROMPT)
        except Exception as e:
            last_error = e
            continue

        return {**article, "summary_ja": result.get("summary_ja", "")}

    if last_error:
        print(f"[エラー] すべてのAIプロバイダで失敗しました: {last_error}")
    return None


if __name__ == "__main__":
    test_article = {
        "source": "HackerNews",
        "title": "New chip design cuts LLM inference cost by 90%",
        "url": "https://example.com/chip-news",
        "score": 500,
        "discussion_url": "https://news.ycombinator.com/item?id=1",
    }

    result = summarize_and_filter(test_article)
    if result:
        print("関連あり、要約:")
        print(result["summary_ja"])
    else:
        print("関連なし、またはエラーで処理されませんでした")
