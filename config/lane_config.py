from dataclasses import dataclass
from pathlib import Path
from typing import List

from vision_player.rect import Rect


@dataclass
class LaneItem:
    path: Path


@dataclass
class LaneConfig:
    lane_id: str
    rect: Rect
    volume: int
    items: List[LaneItem]
    loop: bool
    start_offset_sec: int = 0
