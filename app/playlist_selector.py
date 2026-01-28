# app/playlist_selector.py
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Tuple


def select_playlist_path(playlist_dir: Path, weekday: str) -> Path:
    """
    曜日名から使用する playlist ファイルを決定する。

    Parameters
    ----------
    playlist_dir : Path
        playlists ディレクトリのパス
    weekday : str
        曜日名（"mon", "tue", ...）

    Returns
    -------
    Path
        使用する playlist JSON のパス
    """
    weekday_path = playlist_dir / f"{weekday}.json"
    if weekday_path.exists():
        return weekday_path

    always_path = playlist_dir / "always.json"
    if always_path.exists():
        return always_path

    raise FileNotFoundError("No valid playlist file found.")


def get_now() -> datetime:
    """
    現在時刻を tz-aware datetime として返す。

    優先順位:
    1. hwclock (RTC) が使えればそれを使用
    2. 失敗した場合は system time を使用
    """
    try:
        # hwclock の出力例: 2026-01-27 14:32:10+09:00
        result = subprocess.run(
            ["hwclock", "--show", "--iso-8601=seconds"],
            capture_output=True,
            text=True,
            check=True,
        )
        return datetime.fromisoformat(result.stdout.strip())
    except Exception:
        return datetime.now().astimezone()


_WEEKDAY_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}


def get_weekday(dt: datetime) -> str:
    """
    datetime から曜日名を取得する。
    """
    return _WEEKDAY_MAP[dt.weekday()]


def select_playlist_path_for_now(
    playlist_dir: Path,
) -> Tuple[Path, datetime, str]:
    """
    現在時刻を取得し、曜日に対応する playlist を選ぶ。
    """
    now = get_now()
    weekday = get_weekday(now)
    return select_playlist_path(playlist_dir, weekday), now, weekday
