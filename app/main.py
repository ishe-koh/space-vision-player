import json
import os
import threading
import time as time_module
from datetime import time
from pathlib import Path
from typing import Optional

from app.lane_player import LanePlayer
from app.models import LaneConfig
from app.playlist_runtime import PlaylistRuntime
from app.playlist_selector import get_now, get_weekday
from app.rect import calc_lane_rects


PLAYLIST_DIR = Path("./playlists")
MEDIA_DIR = Path("./media")
VISION_PLAYERS_DIR = Path("./vision_players")


def _load_screen_from_vision_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"vision_config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    cabinet = config["cabinet"]
    lane_layout = config.get("lane_layout", {})

    screen_width = cabinet["width"] * cabinet["cols"]
    screen_height = cabinet["height"] * cabinet["rows"]

    return {
        "width": screen_width,
        "height": screen_height,
        "cols": lane_layout.get("cols", 1),
        "rows": lane_layout.get("rows", 1),
    }


def _resolve_vision_root() -> Path:
    vision_id = os.getenv("VISION_ID", "").strip()
    if vision_id:
        candidate = VISION_PLAYERS_DIR / vision_id
        if not candidate.exists():
            raise FileNotFoundError(f"vision_players/{vision_id} not found")
        return candidate

    local_root = VISION_PLAYERS_DIR / "_local"

    if VISION_PLAYERS_DIR.exists():
        dirs = [
            p for p in VISION_PLAYERS_DIR.iterdir()
            if p.is_dir() and p.name != "_local"
        ]
        if len(dirs) > 1:
            raise ValueError(
                "Multiple vision_players found; set VISION_ID to select one."
            )
        if len(dirs) == 1:
            return dirs[0]

    if local_root.exists():
        return local_root

    return local_root


class ActiveTimeGate:
    def __init__(self, runtime: PlaylistRuntime, check_interval_sec: int = 30):
        self._runtime = runtime
        self._last_state: Optional[bool] = None
        self._last_log_at = 0.0
        self._check_interval_sec = check_interval_sec

    def _parse_hhmm(self, value: str) -> Optional[time]:
        try:
            hh, mm = value.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return None

    def is_active(self) -> bool:
        now = get_now()
        weekday = get_weekday(now)
        active_time = self._runtime.get_active_time()
        rule = active_time.get(weekday)
        if not rule:
            self._log_state(True, weekday, now, "no rule")
            return True

        start = self._parse_hhmm(rule.get("from", ""))
        end = self._parse_hhmm(rule.get("until", ""))
        if not start or not end:
            self._log_state(True, weekday, now, "invalid rule")
            return True

        now_t = now.timetz().replace(tzinfo=None)
        is_on = start <= now_t < end
        self._log_state(
            is_on,
            weekday,
            now,
            f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}",
        )
        return is_on

    def _log_state(self, is_on: bool, weekday, now, reason: str) -> None:
        if self._last_state is None or self._last_state != is_on:
            state = "on" if is_on else "off"
            print(
                f"[main] active_time: {state} "
                f"(weekday={weekday} now={now.isoformat()} rule={reason})"
            )
            self._last_state = is_on
            self._last_log_at = time_module.time()


def main():
    Path("./state").mkdir(parents=True, exist_ok=True)

    vision_root = _resolve_vision_root()
    playlist_dir = vision_root / "output" / "playlists"
    media_dir = vision_root / "output" / "media"
    vision_config_path = vision_root / "config" / "vision_config.json"

    playlist_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    runtime = PlaylistRuntime(playlist_dir=playlist_dir, media_dir=media_dir)
    snapshot = runtime.get_snapshot(force=True)
    playlist_path = snapshot["playlist_path"]
    now = snapshot["now"]
    weekday = snapshot["weekday"]
    print(f"[main] now = {now}")
    print(f"[main] weekday = {weekday}")

    print(f"[main] playlist_path = {playlist_path.resolve()}")

    playlist = snapshot["playlist"]

    active_gate = ActiveTimeGate(runtime)

    lanes = playlist["lanes"]
    auto_policy = playlist.get("auto_policy", {})
    meta = playlist.get("meta", {})

    # rect 計算
    screen = playlist.get("screen") or _load_screen_from_vision_config(
        vision_config_path
    )
    rects = calc_lane_rects(
        screen_width=screen["width"],
        screen_height=screen["height"],
        cols=screen["cols"],
        rows=screen["rows"],
    )
    if len(rects) < len(lanes):
        raise ValueError(
            f"lane count exceeds rects: lanes={len(lanes)} rects={len(rects)}"
        )

    threads = []

    for lane_index, (lane_id, lane_conf) in enumerate(lanes.items()):
        lane_rect = rects[lane_index]

        lane_player = LanePlayer(
            lane_config=LaneConfig(
                lane_id=lane_id,
                rect=lane_rect,
                volume=lane_conf.get(
                    "volume",
                    meta.get("default_volume", 100),
                ),
                items=lane_conf["items"],
                loop=lane_conf.get(
                    "loop",
                    meta.get(
                        "default_loop",
                        auto_policy.get("loop", True),
                    ),
                ),
                start_offset_sec=lane_conf.get(
                    "start_offset_sec",
                    meta.get("default_start_offset_sec", 0),
                ),
            ),
            items_provider=lambda lane_id=lane_id: runtime.get_lane_items(lane_id),
            active_checker=active_gate.is_active,
            items_refresh_interval_sec=30,
            inactive_sleep_sec=30,
        )

        t = threading.Thread(
            target=lane_player.run,
            name=f"LaneThread-{lane_id}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    # 全 lane が生きている限り main は待機
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
