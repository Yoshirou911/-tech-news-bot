"""ユーザーの自然文の質問からAIがキーワードを抽出し、複数ソースを横断検索する機能"""
import sys

from collectors import arxiv, github_trending, hackernews, qiita
from processors import summarizer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def search_by_question(query: str, limit_per_source: int = 4) -> tuple[str, list[dict]]:
    """質問文からキーワードを抽出し、複数ソースを横断検索して要約付きの記事一覧を返す"""
    keyword = summarizer.extract_search_keyword(query)

    raw_articles = []
    for fetch in (
        lambda: hackernews.search_stories(keyword, limit=limit_per_source),
        lambda: arxiv.search_papers(keyword, limit=limit_per_source),
        lambda: qiita.search_articles(keyword, limit=limit_per_source),
        lambda: github_trending.search_repos(keyword, limit=limit_per_source),
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

    return keyword, results


if __name__ == "__main__":
    keyword, results = search_by_question("ゲームのチートについて知りたい")
    print(f"抽出されたキーワード: {keyword}")
    print(f"{len(results)}件見つかりました\n")
    for r in results:
        print(f"[{r['source']}] {r['title']}")
        print(f"  {r['summary_ja']}")
        print()
