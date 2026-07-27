"""GitHub Trendingのリポジトリを取得するモジュール(公式APIが無いためスクレイピング)"""
import re
import sys

import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TRENDING_URL = "https://github.com/trending"
HEADERS = {"User-Agent": "Mozilla/5.0 tech-news-bot/1.0"}


def _extract_number(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def get_trending_repos(language: str = "", since: str = "daily", limit: int = 10) -> list[dict]:
    url = TRENDING_URL if not language else f"{TRENDING_URL}/{language}"

    res = requests.get(url, params={"since": since}, headers=HEADERS, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    repos = []

    for article in soup.select("article.Box-row")[:limit]:
        title_tag = article.select_one("h2.h3.lh-condensed a")
        if not title_tag or not title_tag.get("href"):
            continue

        repo_path = title_tag["href"].strip("/")
        repo_url = f"https://github.com/{repo_path}"

        desc_tag = article.select_one("p.col-9")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        star_tag = article.select_one(f'a[href="/{repo_path}/stargazers"]')
        total_stars = _extract_number(star_tag.get_text()) if star_tag else 0

        stats_text = article.get_text(" ", strip=True)
        today_match = re.search(r"([\d,]+)\s+stars?\s+today", stats_text)
        stars_today = int(today_match.group(1).replace(",", "")) if today_match else 0

        title = f"{repo_path} - {description}" if description else repo_path

        repos.append({
            "source": "GitHubTrending",
            "title": title,
            "url": repo_url,
            "score": total_stars,
            "discussion_url": repo_url,
            "stars_today": stars_today,
        })

    return repos


def get_owner_locations(repos: list[dict]) -> list[dict]:
    """トレンドリポジトリの作成者の所在地情報を取得する
    (GitHubの公開プロフィールAPIより。所在地は任意入力のため未設定のことも多い)"""
    results = []

    for repo in repos:
        owner = repo["url"].split("github.com/")[-1].split("/")[0]

        try:
            res = requests.get(
                f"https://api.github.com/users/{owner}",
                headers=HEADERS,
                timeout=10,
            )
        except requests.RequestException:
            continue

        if res.status_code != 200:
            continue

        location = (res.json().get("location") or "").strip()
        if location:
            results.append({
                "repo": repo["title"],
                "owner": owner,
                "location": location,
            })

    return results


if __name__ == "__main__":
    repos = get_trending_repos(limit=10)
    for i, repo in enumerate(repos, 1):
        print(f"{i}. [{repo['score']}★ / 本日+{repo['stars_today']}] {repo['title']}")
        print(f"   URL: {repo['url']}")
        print()
