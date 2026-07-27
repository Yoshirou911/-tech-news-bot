"""Reddit(r/LocalLLaMA, r/MachineLearningなど)のトップ記事を取得するモジュール"""
import sys

import praw

import config

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def get_reddit_client() -> praw.Reddit:
    reddit = praw.Reddit(
        client_id=config.REDDIT_CLIENT_ID,
        client_secret=config.REDDIT_CLIENT_SECRET,
        user_agent=config.REDDIT_USER_AGENT,
    )
    reddit.read_only = True
    return reddit


def get_top_posts(subreddit_name: str, limit: int = 5, time_filter: str = "day") -> list[dict]:
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)

    posts = []
    for post in subreddit.top(time_filter=time_filter, limit=limit):
        if post.stickied:
            continue

        posts.append({
            "source": f"Reddit/r/{subreddit_name}",
            "title": post.title,
            "url": post.url,
            "score": post.score,
            "discussion_url": f"https://reddit.com{post.permalink}",
        })

    return posts


def get_all_subreddit_posts(limit_per_sub: int = 5, time_filter: str = "day") -> list[dict]:
    all_posts = []
    for subreddit_name in config.SUBREDDITS:
        all_posts.extend(get_top_posts(subreddit_name, limit=limit_per_sub, time_filter=time_filter))
    return all_posts


if __name__ == "__main__":
    posts = get_all_subreddit_posts(limit_per_sub=5)
    for i, post in enumerate(posts, 1):
        print(f"{i}. [{post['source']}] [{post['score']}pt] {post['title']}")
        print(f"   URL: {post['url']}")
        print(f"   議論: {post['discussion_url']}")
        print()
