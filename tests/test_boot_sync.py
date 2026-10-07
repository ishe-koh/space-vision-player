import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.boot_sync import sync_once

class BootSyncTest(unittest.TestCase):
    def test_failed_transfer_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "vision_players/akiba_01/output"
            old.mkdir(parents=True)
            (old / "old").write_text("keep")
            with patch("app.boot_sync.subprocess.run", side_effect=subprocess.CalledProcessError(1, "rsync")):
                with self.assertRaises(subprocess.CalledProcessError):
                    sync_once(root, "192.168.10.2", "ishii", "/srv/space-media-server", "akiba_01")
            self.assertEqual((old / "old").read_text(), "keep")

    def test_complete_transfer_replaces_output_and_clears_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state").mkdir()
            flag = root / "state/media_updating.flag"
            flag.touch()
            def transfer(command, **kwargs):
                stage = Path(command[-1])
                (stage / "media").mkdir()
                (stage / "playlists").mkdir()
                (stage / "playlists/always.json").write_text("{}")
                (stage / "media_availability.json").write_text("{}")
            with patch("app.boot_sync.subprocess.run", side_effect=transfer):
                sync_once(root, "192.168.10.2", "ishii", "/srv/space-media-server", "akiba_01")
            self.assertTrue((root / "vision_players/akiba_01/output/playlists/always.json").exists())
            self.assertFalse(flag.exists())

    def test_incomplete_transfer_does_not_allow_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.boot_sync.subprocess.run"):
                with self.assertRaises(ValueError):
                    sync_once(Path(directory), "192.168.10.2", "ishii", "/srv/space-media-server", "akiba_01")
