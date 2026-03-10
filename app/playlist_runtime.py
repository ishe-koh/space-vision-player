import threading
import time as time_module
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models import LaneItem
from app.playlist_loader import load_playlist
from app.playlist_selector import select_playlist_path_for_now


class PlaylistRuntime:
    def __init__(
        self,
        playlist_dir: Path,
        media_dir: Path,
        refresh_interval_sec: int = 30,
    ):
        self._playlist_dir = playlist_dir
        self._media_dir = media_dir
        self._refresh_interval_sec = refresh_interval_sec
        self._lock = threading.Lock()
        self._last_loaded_at = 0.0
        self._cache: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        playlist_path, now, weekday = select_playlist_path_for_now(self._playlist_dir)
        playlist = load_playlist(
            playlist_path=playlist_path,
            media_base_dir=self._media_dir,
            now=now,
        )
        return {
            "playlist_path": playlist_path,
            "now": now,
            "weekday": weekday,
            "playlist": playlist,
        }

    def get_snapshot(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            current = time_module.monotonic()
            if (
                force
                or self._cache is None
                or current - self._last_loaded_at >= self._refresh_interval_sec
            ):
                self._cache = self._load()
                self._last_loaded_at = current
            return self._cache

    def get_lane_items(self, lane_id: str, force: bool = False) -> List[LaneItem]:
        snapshot = self.get_snapshot(force=force)
        lane_conf = snapshot["playlist"].get("lanes", {}).get(lane_id, {})
        return list(lane_conf.get("items", []))

    def get_active_time(self, force: bool = False) -> Dict[str, Any]:
        snapshot = self.get_snapshot(force=force)
        return dict(snapshot["playlist"].get("active_time", {}))

    def get_playlist_path(self, force: bool = False) -> Path:
        snapshot = self.get_snapshot(force=force)
        return snapshot["playlist_path"]

    def get_now(self, force: bool = False) -> datetime:
        snapshot = self.get_snapshot(force=force)
        return snapshot["now"]

    def get_weekday(self, force: bool = False) -> str:
        snapshot = self.get_snapshot(force=force)
        return snapshot["weekday"]
