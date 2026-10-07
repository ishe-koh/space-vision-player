import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.playlist_loader import load_playlist


class AvailabilityTest(unittest.TestCase):
    def test_final_filter_applies_to_explicit_and_automatic_items(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / "media"
            media.mkdir()
            for name in ("active.mp4", "expired.mp4", "unknown.mp4"):
                (media / name).touch()
            playlist = root / "playlist.json"
            playlist.write_text(json.dumps({"media_availability": "availability.json", "lanes": {
                "lane0": {"items": ["expired.mp4"], "auto_policy": {
                    "directory": ".", "mode": "append_remaining"}}}}))
            manifest = root / "availability.json"
            manifest.write_text(json.dumps({"version": 1, "items": {
                "active.mp4": {}, "expired.mp4": {"is_available_until": "2026-10-06T23:59:59+09:00"}}}))
            now = datetime.fromisoformat("2026-10-07T12:00:00+09:00")
            result = load_playlist(playlist, media, now)
            self.assertEqual([item.path.name for item in result["lanes"]["lane0"]["items"]], ["active.mp4"])
            # Changing only the manifest affects the next runtime refresh.
            manifest.write_text(json.dumps({"version": 1, "items": {"active.mp4": {"enabled": False}}}))
            self.assertEqual(load_playlist(playlist, media, now)["lanes"]["lane0"]["items"], [])

    def test_legacy_playlist_without_manifest_remains_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            playlist = root / "playlist.json"
            playlist.write_text(json.dumps({"lanes": {"lane0": {"items": ["normal.mp4"]}}}))
            result = load_playlist(playlist, root, datetime.now().astimezone())
            self.assertEqual(len(result["lanes"]["lane0"]["items"]), 1)
