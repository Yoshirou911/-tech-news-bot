# 技術ニュース自動収集AIボット

Hacker News / Reddit / GitHub Trending / arXiv / Lobsters / Hugging Face から技術ニュースを自動収集し、AIで「実用的でヤバい情報」だけをフィルタリング・日本語要約して、Discordに自動通知するボットです。あわせて、収集した記事を閲覧・検索できるローカルWebダッシュボードも搭載しています。

## 主な機能

- **複数ソースからの自動収集**: Hacker News, Reddit (r/LocalLLaMA, r/MachineLearning), GitHub Trending, arXiv, Lobsters, Hugging Face
- **AIによるフィルタリング・要約**: Groq / Gemini / Anthropic / OpenAI に対応、優先順位に従って自動フォールバック
- **Discord通知**: ソースごとに色分けされたダイジェスト形式で通知
- **重複送信防止**: 一度送った記事は二度と送らない
- **定期実行**: Windowsタスクスケジューラで1日3回自動実行
- **Webダッシュボード**:
  - 過去の記事一覧・キーワード検索
  - 気になる分野をリアルタイム検索(HackerNews/arXiv)
  - トレンドキーワード・GitHub開発者所在地の可視化
  - 収集記事+Web検索を根拠にAIへ質問できる機能
  - コマンド入力で操作するターミナル風UI

## セットアップ

### 1. ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. `.env` ファイルの作成

`.env.example` をコピーして `.env` を作成し、必要なキーを設定してください。

```
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=
DISCORD_WEBHOOK_URL=
GROQ_API_KEY=        # 無料。これだけでも動作します
GEMINI_API_KEY=      # 任意
ANTHROPIC_API_KEY=   # 任意
OPENAI_API_KEY=      # 任意
BRAVE_API_KEY=       # 任意。ダッシュボードのWeb検索機能に使用
```

APIキーの取得先:

| キー | 取得先 |
|---|---|
| Reddit | https://www.reddit.com/prefs/apps (種類は「script」を選択) |
| Discord Webhook | 対象チャンネルの設定 → 連携サービス → ウェブフックを作成 |
| Groq (無料) | https://console.groq.com/keys |
| Gemini (無料) | https://aistudio.google.com/apikey |
| Anthropic | https://console.anthropic.com/ |
| OpenAI | https://platform.openai.com/api-keys |
| Brave Search | https://api.search.brave.com/register |

## 使い方

### 収集 → 要約 → Discord通知を実行

```bash
python main.py
```

### Webダッシュボードを起動

```bash
python dashboard.py
```

起動後、ブラウザで `http://127.0.0.1:5000` を開いてください。

### 定期実行(Windows)

`run_bot.bat` をタスクスケジューラに登録すると、指定した時刻に自動実行されます。

## フォルダ構成

```
.
├── main.py                # 収集→要約→Discord通知のエントリーポイント
├── dashboard.py            # Webダッシュボード
├── config.py               # 環境変数の読み込み
├── history.py               # 送信履歴の記録・重複防止
├── analytics.py             # トレンドキーワード抽出
├── collectors/               # 各情報源の収集ロジック
│   ├── hackernews.py
│   ├── reddit.py
│   ├── github_trending.py
│   ├── arxiv.py
│   ├── lobsters.py
│   ├── huggingface.py
│   └── websearch.py
├── processors/
│   └── summarizer.py         # AIによるフィルタリング・要約・質問応答
├── notifiers/
│   └── discord.py            # Discord Webhook通知
├── data/                     # 送信履歴(Git管理外)
└── logs/                     # 実行ログ(Git管理外)
```

## 注意事項

- `.env` は `.gitignore` で除外されているため、APIキーがGitHubに公開されることはありません
- 各AI/検索APIの無料枠には利用制限があります。詳細は各サービスの利用規約をご確認ください
