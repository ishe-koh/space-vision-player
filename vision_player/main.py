import json
import threading
from pathlib import Path

from config.lane_config import LaneConfig
from vision_player.lane_player import LanePlayer
from vision_player.playlist_loader import load_playlist
from vision_player.playlist_selector import select_playlist_path_for_now
from vision_player.rect import calc_lane_rects


PLAYLIST_DIR = Path("./playlists")
ENCODED_DIR = Path("./encoded")
VISION_CONFIG_PATH = Path("./config/vision_config.json")


def _load_screen_from_vision_config() -> dict:
    if not VISION_CONFIG_PATH.exists():
        raise FileNotFoundError(f"vision_config not found: {VISION_CONFIG_PATH}")

    with VISION_CONFIG_PATH.open("r", encoding="utf-8") as f:
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


def main():
    playlist_path, now, weekday = select_playlist_path_for_now(PLAYLIST_DIR)
    print(f"[main] now = {now}")
    print(f"[main] weekday = {weekday}")

    print(f"[main] playlist_path = {playlist_path}")

    playlist = load_playlist(
        playlist_path=playlist_path,
        encoded_base_dir=ENCODED_DIR,
        now=now,
    )

    lanes = playlist["lanes"]
    auto_policy = playlist.get("auto_policy", {})
    meta = playlist.get("meta", {})

    # rect 計算
    screen = playlist.get("screen") or _load_screen_from_vision_config()
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
            )
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
