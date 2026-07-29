"""過去に送信した記事の一覧・検索、トピック検索、トレンド可視化を提供するローカルWebダッシュボード"""
import html as html_lib
from collections import Counter
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

import analytics
import history
import mute
import status as status_module
from collectors import arxiv, github_trending, hackernews, qiita, websearch
from processors import summarizer

app = Flask(__name__)

NAV = (
    '<nav>'
    '<a href="/terminal">ターミナル</a> | '
    '<a href="/">過去の記事一覧</a> | '
    '<a href="/topic">気になる分野を調べる</a> | '
    '<a href="/trends">トレンドキーワード</a> | '
    '<a href="/hotspots">開発者の所在地</a> | '
    '<a href="/ask">まとめて質問する</a> | '
    '<a href="/status">ステータス</a>'
    '</nav>'
)

BASE_STYLE = """
  @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
  * { box-sizing: border-box; }
  body {
    font-family: 'Consolas', 'Courier New', monospace;
    max-width: 760px; margin: 2rem auto; padding: 0 1.2rem 4rem;
    background: #0a0f0a; color: #cdeeda;
    line-height: 1.7; font-size: 16px;
  }
  h1 {
    font-size: 1.3rem; letter-spacing: 1px; text-transform: uppercase; color: #33ff66;
    text-shadow: 0 0 6px rgba(51,255,102,0.5);
    border-bottom: 1px solid #1c8f3a; padding-bottom: 0.6rem; margin-bottom: 1.2rem;
  }
  h1::before { content: "root@technews:~$ "; color: #1c8f3a; }
  h1::after { content: "_"; animation: blink 1s step-start infinite; }
  nav { margin-bottom: 1.5rem; padding: 0.7rem 1rem; border: 1px solid #1c8f3a; background: rgba(51,255,102,0.05); line-height: 2; }
  nav a { margin-right: 1rem; color: #33ff66; text-decoration: none; font-weight: bold; }
  nav a:hover { background: #33ff66; color: #0a0f0a; padding: 2px 4px; border-radius: 3px; }
  form { display: flex; gap: 0.5rem; margin-bottom: 1.2rem; }
  input[type=text] {
    flex: 1; padding: 0.7rem; font-size: 1rem; font-family: inherit;
    background: #000; color: #33ff66; border: 1px solid #1c8f3a; border-radius: 3px;
  }
  input[type=text]::placeholder { color: #4a7a58; }
  input[type=text]:focus { outline: none; border-color: #33ff66; box-shadow: 0 0 6px rgba(51,255,102,0.5); }
  button {
    padding: 0.7rem 1.3rem; font-size: 1rem; font-family: inherit; font-weight: bold; cursor: pointer;
    background: #33ff66; color: #0a0f0a; border: none; border-radius: 3px;
  }
  button:hover { background: #6fffa0; }
  .count { color: #8fcaa0; margin-bottom: 1.2rem; font-size: 0.9rem; }
  .note { color: #8fcaa0; font-size: 0.85rem; line-height: 1.6; margin-bottom: 1rem; }
  .article { border-bottom: 1px solid #17301f; padding: 1.1rem 0; }
  .article::before { content: "> "; color: #1c8f3a; }
  .meta { color: #6fae7f; font-size: 0.78rem; margin-bottom: 0.3rem; letter-spacing: 0.3px; }
  .article strong a { color: #5fffa0; font-size: 1.02rem; text-decoration: none; }
  .article strong a:hover { text-decoration: underline; }
  .summary { white-space: pre-line; margin-top: 0.5rem; color: #d4ffe0; font-size: 0.94rem; }
  a { color: #33ff66; }
  a:hover { color: #6fffa0; }
  .bar-row { display: flex; align-items: center; margin: 0.5rem 0; gap: 0.7rem; }
  .bar-label { width: 150px; flex-shrink: 0; text-align: right; font-size: 0.88rem; color: #a8e0ba; }
  .bar-track { flex: 1; background: #000; border: 1px solid #1c8f3a; border-radius: 2px; }
  .bar-fill { background: #33ff66; color: #0a0f0a; font-weight: bold; font-size: 0.8rem; padding: 3px 6px; white-space: nowrap; }
  ::selection { background: #33ff66; color: #0a0f0a; }
  .status-ok { color: #33ff66; }
  .status-error { color: #ff6b6b; }
  .status-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
  .status-table th, .status-table td { text-align: left; padding: 0.5rem 0.7rem; border-bottom: 1px solid #17301f; }
  .status-badge { display: inline-block; padding: 0.25rem 0.8rem; border-radius: 4px; font-weight: bold; font-size: 0.85rem; }
  .status-badge.ok { background: #143d1e; color: #33ff66; border: 1px solid #33ff66; }
  .status-badge.error { background: #3d1414; color: #ff6b6b; border: 1px solid #ff6b6b; }
"""

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>技術ニュースBot ダッシュボード</title><style>{{ style }}</style></head>
<body>
  <h1>技術ニュースBot ダッシュボード</h1>
  {{ nav | safe }}
  <form method="get">
    <input type="text" name="q" placeholder="キーワードで検索(タイトル・要約)" value="{{ query }}">
    <button type="submit">検索</button>
  </form>
  <p class="count">{{ articles|length }}件表示中</p>
  {% for a in articles %}
  <div class="article">
    <div class="meta">{{ a.source }} ・ {{ a.sent_at[:16] }}</div>
    <strong><a href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a></strong>
    <div class="summary">{{ a.summary_ja }}</div>
  </div>
  {% else %}
  <p>該当する記事がありません。</p>
  {% endfor %}
</body>
</html>
"""

TOPIC_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>気になる分野を調べる - 技術ニュースBot</title><style>{{ style }}</style></head>
<body>
  <h1>気になる分野を調べる</h1>
  {{ nav | safe }}
  <form method="get" action="/topic">
    <input type="text" name="topic" placeholder="例: 量子コンピュータ、ロボット掃除機" value="{{ topic }}">
    <button type="submit">調べる</button>
  </form>
  {% if topic %}
    <p class="count">「{{ topic }}」でHackerNews / arXiv / Qiitaをリアルタイム検索し、AIが日本語要約しました({{ articles|length }}件)</p>
  {% endif %}
  {% for a in articles %}
  <div class="article">
    <div class="meta">{{ a.source }} ・ {{ a.score }}pt</div>
    <strong><a href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a></strong>
    <div class="summary">{{ a.summary_ja }}</div>
  </div>
  {% else %}
    {% if topic %}<p>該当する記事が見つかりませんでした。</p>{% endif %}
  {% endfor %}
</body>
</html>
"""

TRENDS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>トレンドキーワード - 技術ニュースBot</title><style>{{ style }}</style></head>
<body>
  <h1>トレンドキーワード</h1>
  {{ nav | safe }}
  <p class="note">これまで収集した記事タイトル{{ total }}件から、頻出する単語を集計しています(英語タイトルが対象)。</p>
  {% for word, count in keywords %}
  <div class="bar-row">
    <div class="bar-label">{{ word }}</div>
    <div class="bar-track">
      <div class="bar-fill" style="width: {{ (count / max_count * 100) | round(1) }}%">{{ count }}</div>
    </div>
  </div>
  {% else %}
  <p>まだ十分なデータがありません。main.pyを実行して記事を集めてください。</p>
  {% endfor %}
</body>
</html>
"""

HOTSPOTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>開発者の所在地 - 技術ニュースBot</title><style>{{ style }}</style></head>
<body>
  <h1>開発者の所在地</h1>
  {{ nav | safe }}
  <p class="note">GitHub Trendingの上位リポジトリ作成者の、公開プロフィールに設定された所在地を集計した参考値です
  (任意入力のため未設定の場合や、地名の表記ゆれはそのまま集計しています)。</p>
  {% for place, count in places %}
  <div class="bar-row">
    <div class="bar-label">{{ place }}</div>
    <div class="bar-track">
      <div class="bar-fill" style="width: {{ (count / max_count * 100) | round(1) }}%">{{ count }}</div>
    </div>
  </div>
  {% else %}
  <p>所在地情報を取得できませんでした(GitHubのAPI制限の可能性があります。時間を置いて再度お試しください)。</p>
  {% endfor %}
</body>
</html>
"""

ASK_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>まとめて質問する - 技術ニュースBot</title><style>{{ style }}</style></head>
<body>
  <h1>まとめて質問する</h1>
  {{ nav | safe }}
  <p class="note">これまで収集した記事{{ total }}件と、Web検索結果を根拠に、AIが日本語で答えます。</p>
  <form method="post" action="/ask">
    <input type="text" name="question" placeholder="例: 最近話題のLLMは何がある？" value="{{ question }}">
    <button type="submit">質問する</button>
  </form>
  {% if question and answer %}
  <div class="article">
    <div class="meta">Q. {{ question }}</div>
    <div class="summary">{{ answer }}</div>
  </div>
  {% elif question %}
  <p>回答を取得できませんでした(AI APIキーが未設定か、エラーが発生した可能性があります)。</p>
  {% endif %}
</body>
</html>
"""

STATUS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>ステータス - 技術ニュースBot</title><style>{{ style }}</style></head>
<body>
  <h1>実行ステータス</h1>
  {{ nav | safe }}
  {% if not run %}
  <p>まだ実行記録がありません。main.pyを一度実行してください。</p>
  {% else %}
  <p class="count">
    最終実行: {{ run.last_run_at_local }}（{{ run.relative_time }}）
    <span class="status-badge {{ 'ok' if run.overall_ok else 'error' }}">{{ '正常' if run.overall_ok else '異常あり' }}</span>
  </p>
  <p class="note">
    収集 {{ run.collected_count }}件 / 送信済みスキップ {{ run.skipped_count }}件 / Discord通知 {{ run.sent_count }}件
  </p>

  <h2 style="font-size:1rem; border-bottom:1px solid #1c8f3a; padding-bottom:0.4rem;">Discord通知</h2>
  {% if run.discord_ok %}
  <p class="status-ok">✓ 正常に送信されました</p>
  {% else %}
  <p class="status-error">✗ 送信に失敗しました: {{ run.discord_error }}</p>
  {% endif %}

  <h2 style="font-size:1rem; border-bottom:1px solid #1c8f3a; padding-bottom:0.4rem; margin-top:1.5rem;">情報源ごとの収集結果</h2>
  <table class="status-table">
    <tr><th>ソース</th><th>結果</th></tr>
    {% for name, result in run.source_results.items() %}
    <tr>
      <td>{{ name }}</td>
      <td class="{{ 'status-ok' if result.startswith('ok') else 'status-error' }}">{{ result }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
</body>
</html>
"""


TERMINAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>技術ニュースBot ターミナル</title><style>{{ style }}
  #terminal {
    background: #000; border: 1px solid #33ff66; padding: 1rem;
    height: 60vh; overflow-y: auto; line-height: 1.5;
  }
  #terminal .line { margin: 0.25rem 0; word-wrap: break-word; }
  .prompt { color: #1c8f3a; }
  .input-line { display: flex; align-items: center; margin-top: 0.6rem; border: 1px solid #1c8f3a; padding: 0.5rem; }
  .input-line .prompt { margin-right: 0.5rem; white-space: nowrap; }
  #cmd-input {
    flex: 1; background: transparent; border: none; color: #33ff66; font-family: inherit; font-size: 1rem;
    outline: none; text-shadow: 0 0 4px rgba(51,255,102,0.35);
  }

  #cmd-tab {
    position: fixed; top: 6rem; right: 0; z-index: 1001;
    background: #33ff66; color: #0a0f0a; font-weight: bold; font-family: inherit;
    padding: 0.6rem 0.5rem; cursor: pointer; border-radius: 6px 0 0 6px; border: none;
    writing-mode: vertical-rl; text-orientation: upright; letter-spacing: 2px;
  }
  #cmd-tab:hover { background: #6fffa0; }
  #cmd-panel {
    position: fixed; top: 0; right: -320px; width: 300px; height: 100vh;
    background: #000; border-left: 1px solid #33ff66; padding: 1.2rem;
    overflow-y: auto; z-index: 1000; transition: right 0.25s ease;
    box-shadow: -4px 0 12px rgba(0,0,0,0.6);
  }
  #cmd-panel.open { right: 0; }
  #cmd-panel h2 { font-size: 1rem; border-bottom: 1px solid #1c8f3a; padding-bottom: 0.5rem; margin: 0 0 1rem; }
  .cmd-item { margin: 0.9rem 0; cursor: pointer; }
  .cmd-name { color: #33ff66; font-weight: bold; }
  .cmd-name:hover { text-shadow: 0 0 8px #33ff66; }
  .cmd-desc { color: #1c8f3a; font-size: 0.8rem; margin-top: 0.15rem; }
</style></head>
<body>
  <h1>技術ニュースBot ターミナル</h1>
  {{ nav | safe }}
  <div id="terminal">
    <div class="line">Tech News Bot Terminal v1.0</div>
    <div class="line">右端の「コマンド」タブから一覧を開けます。直接入力もできます。</div>
  </div>
  <div class="input-line">
    <span class="prompt">root@technews:~$</span>
    <input type="text" id="cmd-input" autofocus autocomplete="off">
  </div>

  <button id="cmd-tab" onclick="togglePanel()">コマンド</button>
  <div id="cmd-panel">
    <h2>コマンド一覧</h2>
    <div class="cmd-item" onclick="insertCommand('list ')">
      <div class="cmd-name">list [件数]</div>
      <div class="cmd-desc">収集済み記事の一覧を表示</div>
    </div>
    <div class="cmd-item" onclick="insertCommand('search ')">
      <div class="cmd-name">search &lt;キーワード&gt;</div>
      <div class="cmd-desc">HackerNews / arXiv / Qiitaをリアルタイム検索</div>
    </div>
    <div class="cmd-item" onclick="insertCommand('ask ')">
      <div class="cmd-name">ask &lt;質問&gt;</div>
      <div class="cmd-desc">収集済み記事とWeb検索を根拠にAIへ質問</div>
    </div>
    <div class="cmd-item" onclick="runCommand('trends')">
      <div class="cmd-name">trends</div>
      <div class="cmd-desc">頻出キーワードランキングを表示</div>
    </div>
    <div class="cmd-item" onclick="runCommand('hotspots')">
      <div class="cmd-name">hotspots</div>
      <div class="cmd-desc">GitHub Trending開発者の所在地ランキングを表示</div>
    </div>
    <div class="cmd-item" onclick="insertCommand('mute ')">
      <div class="cmd-name">mute &lt;キーワード&gt;</div>
      <div class="cmd-desc">指定キーワードを含む記事を通知から除外</div>
    </div>
    <div class="cmd-item" onclick="insertCommand('unmute ')">
      <div class="cmd-name">unmute &lt;キーワード&gt;</div>
      <div class="cmd-desc">ミュートを解除</div>
    </div>
    <div class="cmd-item" onclick="runCommand('muted')">
      <div class="cmd-name">muted</div>
      <div class="cmd-desc">ミュート中のキーワード一覧を表示</div>
    </div>
    <div class="cmd-item" onclick="runCommand('clear')">
      <div class="cmd-name">clear</div>
      <div class="cmd-desc">画面をクリア</div>
    </div>
    <div class="cmd-item" onclick="runCommand('help')">
      <div class="cmd-name">help</div>
      <div class="cmd-desc">このコマンド一覧をターミナルにも表示</div>
    </div>
  </div>

<script>
const terminal = document.getElementById('terminal');
const input = document.getElementById('cmd-input');
const panel = document.getElementById('cmd-panel');

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function appendLine(innerHtml) {
  const div = document.createElement('div');
  div.className = 'line';
  div.innerHTML = innerHtml;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

function togglePanel() {
  panel.classList.toggle('open');
}

function insertCommand(prefix) {
  input.value = prefix;
  input.focus();
  panel.classList.remove('open');
}

async function runCommand(command) {
  input.value = '';
  panel.classList.remove('open');
  appendLine('<span class="prompt">root@technews:~$</span> ' + escapeHtml(command));

  if (command === 'clear' || command === 'cls') {
    terminal.innerHTML = '';
    return;
  }

  appendLine('<span class="prompt">実行中...</span>');
  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({command}),
    });
    const data = await res.json();
    terminal.lastChild.remove();
    appendLine(data.output || '(出力なし)');
  } catch (err) {
    terminal.lastChild.remove();
    appendLine('通信エラーが発生しました。');
  }
  input.focus();
}

input.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  const command = input.value;
  if (!command.trim()) return;
  runCommand(command);
});

input.focus();
</script>
</body>
</html>
"""

HELP_TEXT = (
    "使えるコマンド一覧:<br>"
    "&nbsp;&nbsp;list [件数] - 収集済み記事の一覧を表示 (例: list 5)<br>"
    "&nbsp;&nbsp;search &lt;キーワード&gt; - HackerNews / arXiv / Qiitaをリアルタイム検索 (例: search 量子コンピュータ)<br>"
    "&nbsp;&nbsp;ask &lt;質問&gt; - 収集済み記事とWeb検索結果を根拠にAIへ質問 (例: ask 最近のLLM動向は?)<br>"
    "&nbsp;&nbsp;trends - 頻出キーワードランキングを表示<br>"
    "&nbsp;&nbsp;hotspots - GitHub Trending開発者の所在地ランキングを表示<br>"
    "&nbsp;&nbsp;mute &lt;キーワード&gt; - 指定キーワードを含む記事を今後の通知から除外<br>"
    "&nbsp;&nbsp;unmute &lt;キーワード&gt; - ミュートを解除<br>"
    "&nbsp;&nbsp;muted - 現在ミュート中のキーワード一覧を表示<br>"
    "&nbsp;&nbsp;clear - 画面をクリア<br>"
    "&nbsp;&nbsp;help - このヘルプを表示"
)


def _ascii_bar(count: int, max_count: int, width: int = 20) -> str:
    filled = round(count / max_count * width) if max_count else 0
    return "█" * filled + "░" * (width - filled)


def _render_article_lines(articles: list[dict]) -> str:
    if not articles:
        return "該当する記事はありませんでした。"

    lines = []
    for a in articles:
        title = html_lib.escape(a.get("title", ""))
        url = html_lib.escape(a.get("url", ""))
        source = html_lib.escape(a.get("source", ""))
        summary = html_lib.escape(a.get("summary_ja", "")).replace("\n", "<br>")
        lines.append(f'[{source}] <a href="{url}" target="_blank" rel="noopener">{title}</a><br>{summary}')

    return "<br><br>".join(lines)


@app.route("/api/command", methods=["POST"])
def api_command():
    data = request.get_json(force=True, silent=True) or {}
    raw = (data.get("command") or "").strip()

    if not raw:
        return jsonify({"output": ""})

    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("help", "?"):
        output = HELP_TEXT

    elif cmd in ("list", "ls", "articles"):
        n = int(arg) if arg.isdigit() else 10
        records = history.load_history()
        records.sort(key=lambda a: a.get("sent_at", ""), reverse=True)
        output = _render_article_lines(records[:n])

    elif cmd in ("search", "find"):
        if not arg:
            output = "使い方: search &lt;キーワード&gt;"
        else:
            raw_articles = []
            try:
                raw_articles += hackernews.search_stories(arg, limit=5)
            except Exception:
                pass
            try:
                raw_articles += arxiv.search_papers(arg, limit=5)
            except Exception:
                pass
            try:
                raw_articles += qiita.search_articles(arg, limit=5)
            except Exception:
                pass

            results = []
            for article in raw_articles:
                r = summarizer.summarize_topic(article)
                if r:
                    results.append(r)

            if results:
                records = history.load_history()
                history.append_and_save(records, results)

            output = _render_article_lines(results)

    elif cmd == "ask":
        if not arg:
            output = "使い方: ask &lt;質問文&gt;"
        else:
            records = history.load_history()
            records.sort(key=lambda a: a.get("sent_at", ""), reverse=True)
            try:
                web_results = websearch.search_web(arg, limit=5)
            except Exception:
                web_results = []
            answer = summarizer.answer_question(arg, records[:100], web_results)
            output = html_lib.escape(answer).replace("\n", "<br>") if answer else "回答を取得できませんでした。"

    elif cmd == "trends":
        records = history.load_history()
        titles = [r["title"] for r in records if r.get("title")]
        keywords = analytics.extract_keywords(titles, top_n=15)
        if keywords:
            max_count = keywords[0][1]
            lines = [
                f"{html_lib.escape(w):<15} {_ascii_bar(c, max_count)} {c}"
                for w, c in keywords
            ]
            output = "<br>".join(lines)
        else:
            output = "まだ十分なデータがありません。"

    elif cmd == "hotspots":
        repos = github_trending.get_trending_repos(limit=15)
        locations = github_trending.get_owner_locations(repos)
        place_counts = Counter(loc["location"] for loc in locations)
        places = place_counts.most_common(15)
        if places:
            max_count = places[0][1]
            lines = [
                f"{html_lib.escape(p):<25} {_ascii_bar(c, max_count)} {c}"
                for p, c in places
            ]
            output = "<br>".join(lines)
        else:
            output = "所在地情報を取得できませんでした。"

    elif cmd == "mute":
        if not arg:
            output = "使い方: mute &lt;キーワード&gt;"
        else:
            keywords = mute.add_muted_keyword(arg)
            output = f"「{html_lib.escape(arg)}」をミュートしました。(現在{len(keywords)}件)"

    elif cmd == "unmute":
        if not arg:
            output = "使い方: unmute &lt;キーワード&gt;"
        else:
            keywords = mute.remove_muted_keyword(arg)
            output = f"「{html_lib.escape(arg)}」のミュートを解除しました。(現在{len(keywords)}件)"

    elif cmd == "muted":
        keywords = mute.load_muted_keywords()
        if keywords:
            output = "<br>".join(html_lib.escape(k) for k in keywords)
        else:
            output = "ミュート中のキーワードはありません。"

    else:
        output = f'command not found: {html_lib.escape(cmd)} ("help"で使い方を確認できます)'

    return jsonify({"output": output})


@app.route("/terminal")
def terminal():
    return render_template_string(TERMINAL_TEMPLATE, style=BASE_STYLE, nav=NAV)


@app.route("/")
def index():
    query = request.args.get("q", "").strip().lower()
    records = history.load_history()
    records.sort(key=lambda a: a.get("sent_at", ""), reverse=True)

    if query:
        records = [
            a for a in records
            if query in a.get("title", "").lower()
            or query in a.get("summary_ja", "").lower()
        ]

    return render_template_string(INDEX_TEMPLATE, articles=records, query=query, style=BASE_STYLE, nav=NAV)


@app.route("/topic")
def topic_search():
    topic = request.args.get("topic", "").strip()
    articles = []

    if topic:
        raw_articles = []
        try:
            raw_articles += hackernews.search_stories(topic, limit=5)
        except Exception:
            pass
        try:
            raw_articles += arxiv.search_papers(topic, limit=5)
        except Exception:
            pass
        try:
            raw_articles += qiita.search_articles(topic, limit=5)
        except Exception:
            pass

        for article in raw_articles:
            result = summarizer.summarize_topic(article)
            if result:
                articles.append(result)

        if articles:
            records = history.load_history()
            history.append_and_save(records, articles)

    return render_template_string(TOPIC_TEMPLATE, topic=topic, articles=articles, style=BASE_STYLE, nav=NAV)


@app.route("/trends")
def trends():
    records = history.load_history()
    titles = [r["title"] for r in records if r.get("title")]
    keywords = analytics.extract_keywords(titles, top_n=25)
    max_count = keywords[0][1] if keywords else 1

    return render_template_string(
        TRENDS_TEMPLATE, keywords=keywords, max_count=max_count, total=len(titles), style=BASE_STYLE, nav=NAV
    )


@app.route("/hotspots")
def hotspots():
    repos = github_trending.get_trending_repos(limit=15)
    locations = github_trending.get_owner_locations(repos)

    place_counts = Counter(loc["location"] for loc in locations)
    places = place_counts.most_common(20)
    max_count = places[0][1] if places else 1

    return render_template_string(
        HOTSPOTS_TEMPLATE, places=places, max_count=max_count, style=BASE_STYLE, nav=NAV
    )


@app.route("/ask", methods=["GET", "POST"])
def ask():
    question = ""
    answer = None
    records = history.load_history()

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            records.sort(key=lambda a: a.get("sent_at", ""), reverse=True)
            try:
                web_results = websearch.search_web(question, limit=5)
            except Exception:
                web_results = []
            answer = summarizer.answer_question(question, records[:100], web_results)

    return render_template_string(
        ASK_TEMPLATE, question=question, answer=answer, total=len(records), style=BASE_STYLE, nav=NAV
    )


def _relative_time_ja(dt: datetime) -> str:
    delta = datetime.now(timezone.utc) - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return "たった今"
    if seconds < 3600:
        return f"{int(seconds // 60)}分前"
    if seconds < 86400:
        return f"{int(seconds // 3600)}時間前"
    return f"{int(seconds // 86400)}日前"


@app.route("/status")
def status_page():
    run = status_module.load_status()

    if run:
        last_run_dt = datetime.fromisoformat(run["last_run_at"])
        run["last_run_at_local"] = last_run_dt.strftime("%Y-%m-%d %H:%M:%S")
        run["relative_time"] = _relative_time_ja(last_run_dt)
        run["overall_ok"] = run["discord_ok"] and all(
            v.startswith("ok") for v in run["source_results"].values()
        )

    return render_template_string(STATUS_TEMPLATE, run=run, style=BASE_STYLE, nav=NAV)


if __name__ == "__main__":
    app.run(port=5000)
