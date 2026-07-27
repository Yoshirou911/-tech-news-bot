"""過去に送信した記事の一覧・検索、トピック検索、トレンド可視化を提供するローカルWebダッシュボード"""
import html as html_lib
from collections import Counter

from flask import Flask, jsonify, render_template_string, request

import analytics
import history
from collectors import arxiv, github_trending, hackernews, websearch
from processors import summarizer

app = Flask(__name__)

NAV = (
    '<nav>'
    '<a href="/terminal">ターミナル</a> | '
    '<a href="/">過去の記事一覧</a> | '
    '<a href="/topic">気になる分野を調べる</a> | '
    '<a href="/trends">トレンドキーワード</a> | '
    '<a href="/hotspots">開発者の所在地</a> | '
    '<a href="/ask">まとめて質問する</a>'
    '</nav>'
)

BASE_STYLE = """
  @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
  * { box-sizing: border-box; }
  body {
    font-family: 'Consolas', 'Courier New', monospace;
    max-width: 900px; margin: 2rem auto; padding: 0 1rem 4rem;
    background: #0a0f0a; color: #33ff66;
    text-shadow: 0 0 4px rgba(51,255,102,0.35);
  }
  h1 { font-size: 1.4rem; letter-spacing: 2px; text-transform: uppercase; border-bottom: 1px solid #33ff66; padding-bottom: 0.6rem; }
  h1::before { content: "root@technews:~$ "; color: #1c8f3a; }
  h1::after { content: "_"; animation: blink 1s step-start infinite; }
  nav { margin-bottom: 1.5rem; padding: 0.6rem 1rem; border: 1px solid #1c8f3a; background: rgba(51,255,102,0.05); }
  nav a { margin-right: 1rem; color: #33ff66; text-decoration: none; }
  nav a:hover { background: #33ff66; color: #0a0f0a; text-shadow: none; padding: 0 2px; }
  form { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  input[type=text] {
    flex: 1; padding: 0.6rem; font-size: 1rem; font-family: inherit;
    background: #000; color: #33ff66; border: 1px solid #1c8f3a;
  }
  input[type=text]::placeholder { color: #1c8f3a; }
  input[type=text]:focus { outline: none; border-color: #33ff66; box-shadow: 0 0 6px rgba(51,255,102,0.6); }
  button {
    padding: 0.6rem 1.2rem; font-size: 1rem; font-family: inherit; font-weight: bold; cursor: pointer;
    background: #33ff66; color: #0a0f0a; border: none;
  }
  button:hover { background: #6fffa0; }
  .count { color: #1c8f3a; margin-bottom: 1rem; }
  .note { color: #1c8f3a; font-size: 0.85rem; }
  .article { border-bottom: 1px dashed #1c8f3a; padding: 1rem 0; }
  .article::before { content: "> "; color: #1c8f3a; }
  .meta { color: #1c8f3a; font-size: 0.8rem; }
  .summary { white-space: pre-line; margin: 0.4rem 0; color: #a8ffc0; }
  a { color: #33ff66; }
  a:hover { text-shadow: 0 0 8px #33ff66; }
  .bar-row { display: flex; align-items: center; margin: 0.4rem 0; gap: 0.6rem; }
  .bar-label { width: 140px; flex-shrink: 0; text-align: right; font-size: 0.9rem; }
  .bar-track { flex: 1; background: #000; border: 1px solid #1c8f3a; }
  .bar-fill { background: #33ff66; color: #0a0f0a; font-weight: bold; font-size: 0.8rem; padding: 2px 6px; white-space: nowrap; }
  ::selection { background: #33ff66; color: #0a0f0a; }
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
    <p class="count">「{{ topic }}」でHackerNews / arXivをリアルタイム検索し、AIが日本語要約しました({{ articles|length }}件)</p>
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
      <div class="cmd-desc">HackerNews / arXivをリアルタイム検索</div>
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
    "&nbsp;&nbsp;search &lt;キーワード&gt; - HackerNews / arXivをリアルタイム検索 (例: search 量子コンピュータ)<br>"
    "&nbsp;&nbsp;ask &lt;質問&gt; - 収集済み記事とWeb検索結果を根拠にAIへ質問 (例: ask 最近のLLM動向は?)<br>"
    "&nbsp;&nbsp;trends - 頻出キーワードランキングを表示<br>"
    "&nbsp;&nbsp;hotspots - GitHub Trending開発者の所在地ランキングを表示<br>"
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


if __name__ == "__main__":
    app.run(port=5000)
