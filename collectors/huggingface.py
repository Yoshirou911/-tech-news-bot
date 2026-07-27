"""Hugging Faceでトレンド中のAIモデルを取得するモジュール"""
import sys

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://huggingface.co/api/models"


def get_trending_models(limit: int = 10) -> list[dict]:
    res = requests.get(
        API_URL,
        params={"sort": "trendingScore", "direction": -1, "limit": limit},
        timeout=15,
    )
    res.raise_for_status()

    models = []
    for item in res.json():
        model_id = item.get("id") or item.get("modelId")
        if not model_id:
            continue

        models.append({
            "source": "HuggingFace",
            "title": model_id,
            "url": f"https://huggingface.co/{model_id}",
            "score": item.get("likes", 0),
            "discussion_url": f"https://huggingface.co/{model_id}",
        })

    return models


if __name__ == "__main__":
    models = get_trending_models(limit=10)
    for i, m in enumerate(models, 1):
        print(f"{i}. [{m['score']}♥] {m['title']}")
        print(f"   URL: {m['url']}")
        print()
