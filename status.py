"""Botの実行状況(最終実行日時・成功/失敗・各ソースの結果)を記録・取得するモジュール"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

STATUS_FILE = Path(__file__).parent / "data" / "status.json"


def save_run_status(
    *,
    collected_count: int,
    skipped_count: int,
    sent_count: int,
    source_results: dict[str, str],
    discord_ok: bool,
    discord_error: str | None = None,
) -> None:
    status = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "collected_count": collected_count,
        "skipped_count": skipped_count,
        "sent_count": sent_count,
        "source_results": source_results,
        "discord_ok": discord_ok,
        "discord_error": discord_error,
    }

    STATUS_FILE.parent.mkdir(exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def load_status() -> dict | None:
    if not STATUS_FILE.exists():
        return None

    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    save_run_status(
        collected_count=10,
        skipped_count=2,
        sent_count=8,
        source_results={"HackerNews": "ok", "Reddit": "error: connection failed"},
        discord_ok=True,
    )
    print("テスト用のステータスを保存しました")
    print(load_status())
