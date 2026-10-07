"""設定値。環境変数は呼び出し時に読むので、テストで差し替えやすい。"""

import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tokyo")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
THUMB_SIZE = 400


def data_dir() -> Path:
    return Path(os.environ.get("TODO_HABIT_DATA_DIR", "data")).resolve()


def uploads_dir() -> Path:
    return data_dir() / "uploads"


def now_jst() -> datetime:
    """日本時間の現在時刻（tzなし）。DBにはこの形式で保存する。"""
    return datetime.now(TZ).replace(tzinfo=None)


def today_jst() -> date:
    return now_jst().date()
