import subprocess
import time
from pathlib import Path
from typing import List

from app.models import LaneConfig
from app.rect import Rect


class LanePlayer:
    def __init__(
        self,
        lane_config: LaneConfig,
        active_checker=None,
        inactive_sleep_sec: int = 30,
    ):
        self.cfg = lane_config
        self._updating_flag = Path("./state/media_updating.flag")
        self._updating_media = Path("./system_media/updating.mp4")
        self._active_checker = active_checker
        self._inactive_sleep_sec = inactive_sleep_sec

    def run(self):
        print(f"[Lane {self.cfg.lane_id}] start")

        # 再生開始オフセット
        if self.cfg.start_offset_sec > 0:
            print(
                f"[Lane {self.cfg.lane_id}] "
                f"start offset {self.cfg.start_offset_sec}s"
            )
            time.sleep(self.cfg.start_offset_sec)

        while True:
            if self._is_updating():
                self._play_updating()
                continue
            if self._active_checker and not self._active_checker():
                time.sleep(self._inactive_sleep_sec)
                continue

            if not self.cfg.items:
                time.sleep(1)
                continue

            if self.cfg.loop and len(self.cfg.items) == 1:
                if self._is_updating():
                    continue
                self.play_item(
                    self.cfg.items[0],
                    loop=True,
                    active_checker=self._active_checker,
                )
            else:
                for item in self.cfg.items:
                    if self._is_updating():
                        break
                    self.play_item(
                        item,
                        loop=False,
                        active_checker=self._active_checker,
                    )
                    if self._is_updating():
                        break

            if not self.cfg.loop:
                print(f"[Lane {self.cfg.lane_id}] loop disabled, exit")
                break

    def play_item(self, item, loop: bool = False, active_checker=None):
        cmd = build_mpv_command(
            media_path=item.path,
            rect=self.cfg.rect,
            volume=self.cfg.volume,
            loop=loop,
        )

        print(f"[Lane {self.cfg.lane_id}] play {item.path.name}")

        try:
            proc = subprocess.Popen(cmd)
            while True:
                if proc.poll() is not None:
                    break
                if active_checker and not active_checker():
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break
                if self._is_updating():
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break
                time.sleep(0.5)
        except Exception as e:
            print(
                f"[Lane {self.cfg.lane_id}] "
                f"ERROR: {e}"
            )
            time.sleep(1)

    def _is_updating(self) -> bool:
        return self._updating_flag.exists()

    def _play_updating(self):
        if not self._updating_media.exists():
            print(f"[Lane {self.cfg.lane_id}] updating media missing")
            time.sleep(1)
            return

        print(f"[Lane {self.cfg.lane_id}] updating mode")
        cmd = build_mpv_command(
            media_path=self._updating_media,
            rect=self.cfg.rect,
            volume=self.cfg.volume,
            loop=True,
        )

        proc = None
        try:
            proc = subprocess.Popen(cmd)
            while self._is_updating():
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
        except Exception as e:
            print(
                f"[Lane {self.cfg.lane_id}] "
                f"ERROR: {e}"
            )
        finally:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()


def build_mpv_command(
    media_path: Path,
    rect: Rect,
    volume: int,
    loop: bool,
) -> List[str]:
    """
    mpv 起動コマンドを構築する

    Args:
        media_path: 再生する動画ファイル
        rect: Rect(x, y, width, height)
        volume: 音量 (0-100)
        loop: 無限ループするか

    Returns:
        mpv 起動用のコマンド配列
    """
    cmd = [
        "mpv",
        str(media_path),
        "--no-border",
        "--ontop",
        "--fullscreen=no",
        "--force-window=yes",
        "--idle=no",
        "--keep-open=no",
        f"--geometry={rect.width}x{rect.height}+{rect.x}+{rect.y}",
        f"--volume={volume}",
        "--mute=no",
        "--audio-device=auto",
        "--osd-level=0",
        "--cursor-autohide=always",
        "--input-default-bindings=no",
        "--input-vo-keyboard=no",
        "--no-terminal",
        "--msg-level=all=no",
    ]

    if loop:
        cmd.append("--loop-file=inf")

    return cmd
