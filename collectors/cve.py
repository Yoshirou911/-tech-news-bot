"""NVD(National Vulnerability Database)から最近の重大な脆弱性情報を取得するモジュール"""
import sys
from datetime import datetime, timedelta, timezone

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _get_severity(cve: dict) -> tuple[str, float]:
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if metrics.get(key):
            data = metrics[key][0]["cvssData"]
            return data.get("baseSeverity", "UNKNOWN"), data.get("baseScore", 0.0)
    return "UNKNOWN", 0.0


def get_recent_critical_cves(days: int = 3, min_score: float = 7.0, limit: int = 10) -> list[dict]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    res = requests.get(
        API_URL,
        params={
            "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": now.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": 200,
        },
        timeout=20,
    )
    res.raise_for_status()

    articles = []
    for item in res.json().get("vulnerabilities", []):
        cve = item["cve"]
        severity, score = _get_severity(cve)
        if score < min_score:
            continue

        desc = next((d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"), "")
        cve_id = cve["id"]
        detail_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

        articles.append({
            "source": "CVE",
            "title": f"{cve_id} [{severity} {score}] {desc[:150]}",
            "url": detail_url,
            "score": round(score * 10),
            "discussion_url": detail_url,
        })

    articles.sort(key=lambda a: a["score"], reverse=True)
    return articles[:limit]


if __name__ == "__main__":
    articles = get_recent_critical_cves(limit=10)
    for i, a in enumerate(articles, 1):
        print(f"{i}. {a['title']}")
        print(f"   URL: {a['url']}")
        print()
