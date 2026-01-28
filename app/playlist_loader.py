# app/playlist_loader.py
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models import LaneItem


def _is_item_available(item: Dict[str, Any], now: datetime) -> bool:
    """
    単一 item が現在時刻で再生可能かを判定する。

    Parameters
    ----------
    item : dict
        playlist の item 定義
    now : datetime
        現在時刻（tz-aware）

    Returns
    -------
    bool
        再生可能なら True
    """
    if "is_available_from" in item:
        from_time = datetime.fromisoformat(item["is_available_from"])
        if from_time.tzinfo is None:
            raise ValueError("is_available_from must include timezone")
        if now < from_time:
            return False

    if "is_available_until" in item:
        until_time = datetime.fromisoformat(item["is_available_until"])
        if until_time.tzinfo is None:
            raise ValueError("is_available_until must include timezone")
        if now > until_time:
            return False

    return True


def _filter_items(items: List[Dict[str, Any]], now: datetime) -> List[Dict[str, Any]]:
    """
    items リストから、再生可能なものだけを抽出する。
    """
    return [item for item in items if _is_item_available(item, now)]


def _resolve_media_path(path: str, media_base_dir: Path) -> Path:
    media_path = Path(path)
    if not media_path.is_absolute():
        if media_path.parts and media_path.parts[0] == media_base_dir.name:
            media_path = media_base_dir.parent / media_path
        else:
            media_path = media_base_dir / media_path
    return media_path


def _build_auto_items(
    auto_policy: Dict[str, Any],
    media_base_dir: Path,
) -> List[LaneItem]:
    directory = auto_policy.get("directory")
    if not directory:
        return []

    base_dir = Path(directory)
    if not base_dir.is_absolute():
        if base_dir.parts and base_dir.parts[0] == media_base_dir.name:
            base_dir = media_base_dir.parent / base_dir
        else:
            base_dir = media_base_dir / base_dir

    if not base_dir.exists():
        print(f"[playlist_loader] auto_policy directory not found: {base_dir}")
        return []

    extensions = auto_policy.get("extensions", [".mp4"])
    allowed_ext = {ext.lower() for ext in extensions}

    files = [
        p for p in base_dir.iterdir()
        if p.is_file() and p.suffix.lower() in allowed_ext
    ]

    sort_order = auto_policy.get("sort", "asc")
    files.sort(reverse=(sort_order == "desc"))

    return [LaneItem(path=p) for p in files]


def _merge_items(
    lane_items: List[LaneItem],
    auto_items: List[LaneItem],
    mode: str,
) -> List[LaneItem]:
    if mode == "disabled":
        return lane_items
    if mode == "replace_if_empty":
        return auto_items if not lane_items else lane_items
    if mode == "append_remaining":
        lane_paths = {item.path for item in lane_items}
        remaining = [item for item in auto_items if item.path not in lane_paths]
        return lane_items + remaining
    raise ValueError(f"Unknown auto_policy.mode: {mode}")


def _normalize_items(
    items: List[Dict[str, Any]],
    media_base_dir: Path,
) -> List[LaneItem]:
    normalized: List[LaneItem] = []
    for item in items:
        if isinstance(item, LaneItem):
            normalized.append(item)
            continue

        if isinstance(item, dict):
            path = item.get("path")
            if not path:
                continue
            normalized.append(LaneItem(path=_resolve_media_path(path, media_base_dir)))
        elif isinstance(item, str):
            normalized.append(LaneItem(path=_resolve_media_path(item, media_base_dir)))
    return normalized


def load_playlist(
    playlist_path: Path,
    media_base_dir: Path,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    playlist.json を読み込み、現在時刻に基づいて
    再生可能な items のみを含む構造を返す。

    Parameters
    ----------
    playlist_path : Path
        使用する playlist JSON のパス
    media_base_dir : Path
        メディアファイルの基準ディレクトリ
    now : datetime, optional
        現在時刻（tz-aware）。None の場合はフィルタしない。

    Returns
    -------
    dict
        フィルタ後の playlist データ
    """
    with playlist_path.open("r", encoding="utf-8") as f:
        playlist = json.load(f)

    lanes = playlist.get("lanes", {})
    auto_policy = playlist.get("auto_policy", {})
    auto_items = _build_auto_items(auto_policy, media_base_dir)
    auto_mode = auto_policy.get("mode", "replace_if_empty")
    filtered_lanes: Dict[str, Any] = {}

    for lane_id, lane_conf in lanes.items():
        items = lane_conf.get("items")
        if items is None:
            items = []
        else:
            if now is not None and items and isinstance(items[0], dict):
                items = _filter_items(items, now)

        # lane 設定は保ったまま、items だけ差し替える
        filtered_lane_conf = dict(lane_conf)
        lane_items = _normalize_items(items, media_base_dir)
        filtered_lane_conf["items"] = _merge_items(
            lane_items,
            auto_items,
            auto_mode,
        )

        filtered_lanes[lane_id] = filtered_lane_conf

    playlist["lanes"] = filtered_lanes
    return playlist
