"""Fetch published output before playback; retry until a complete snapshot is received."""
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


def sync_once(root, host, user, remote_root, vision):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", vision):
        raise ValueError("invalid VISION_ID")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", user) or not re.fullmatch(r"[A-Za-z0-9_.:-]+", host):
        raise ValueError("invalid MediaServer connection")
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", remote_root) or ".." in remote_root.split("/"):
        raise ValueError("invalid MediaServer root")
    remote = f"{user}@{host}"
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2"]
    base = root / "vision_players" / vision
    base.mkdir(parents=True, exist_ok=True)
    stage = base / ".boot-output"
    stage.mkdir(exist_ok=True)
    subprocess.run(["rsync", "-azc", "--delete", "--timeout=60", "-e", " ".join(ssh),
                    f"{remote}:{remote_root}/vision_players/{vision}/output/", str(stage) + "/"], check=True)
    if not (stage / "media").is_dir() or not (stage / "playlists/always.json").is_file() or not (stage / "media_availability.json").is_file():
        raise ValueError("Published output incomplete; run full publish on MediaServer first")
    output, previous = base / "output", base / ".pre-boot-output"
    if previous.exists():
        shutil.rmtree(previous)
    if output.exists():
        output.rename(previous)
    try:
        stage.rename(output)
    except Exception:
        if previous.exists():
            previous.rename(output)
        raise
    if previous.exists():
        shutil.rmtree(previous)
    (root / "state/media_updating.flag").unlink(missing_ok=True)


def main():
    root = Path.cwd()
    host = os.environ["MEDIA_SERVER_HOST"]
    user = os.environ["MEDIA_SERVER_USER"]
    remote_root = os.environ.get("MEDIA_SERVER_ROOT", "/srv/space-media-server")
    vision = os.environ["VISION_ID"]
    while True:
        try:
            print(f"[boot-sync] fetching {vision} from {host}", flush=True)
            sync_once(root, host, user, remote_root, vision)
            print("[boot-sync] complete; playback may start", flush=True)
            return
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(f"[boot-sync] waiting: {error}; retry in 15s", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()
