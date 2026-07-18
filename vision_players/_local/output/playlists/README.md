# Playlist Spec (space-vision-player)

This document defines the playlist JSON format used by vision-player.

## Files and selection
- One file per weekday: `mon.json`, `tue.json`, ... `sun.json`
- If the weekday file does not exist, `always.json` is used

Selection logic lives in `app/playlist_selector.py`.

## Top-level structure
```json
{
  "meta": { ... },
  "active_time": { ... },
  "screen": { ... },
  "auto_policy": { ... },
  "lanes": { ... }
}
```

## meta
Defaults used when lane settings are missing.
```json
{
  "default_volume": 100,
  "default_loop": true,
  "default_start_offset_sec": 0
}
```

## screen
Optional. If omitted, `vision_players/<vision_id>/config/vision_config.json` is used.
```json
{
  "width": 1280,
  "height": 256,
  "cols": 3,
  "rows": 1
}
```

## active_time
Optional. If omitted, playback is always on.

```json
{
  "mon": {"from": "08:00", "until": "22:00"},
  "tue": {"from": "08:00", "until": "22:00"}
}
```

Rules:
- `from` / `until` are **HH:MM** (24h)
- Playback is active when `from <= now < until`
- If the weekday key is missing, playback is always on
- Only `mon` through `sun` are checked. `active_time.always` is ignored.

## lanes
- Lane order follows JSON declaration order.
- Each lane is a logical playback area (1 lane = 1 mpv process).

Example:
```json
{
  "lane0": {
    "volume": 30,
    "start_offset_sec": 0,
    "items": [
      "movie_a.mp4",
      {
        "path": "poster_30sec_.mp4",
        "is_available_from": "2026-01-27T18:00:00+09:00"
      }
    ]
  }
}
```

### items
Two forms are allowed:
1) String path: `"movie_a.mp4"`
2) Object:
```json
{
  "path": "movie_a.mp4",
  "is_available_from": "2026-01-27T18:00:00+09:00",
  "is_available_until": "2026-02-10T23:59:59+09:00"
}
```

Rules:
- `is_available_from` / `is_available_until` must be ISO8601 **with timezone**
- If timezone is missing, it is treated as an error
- availability is re-evaluated during runtime (roughly every 30 seconds)

## auto_policy
Used to auto-generate items from a directory (media outputs).

```json
{
  "directory": "always/lane0",
  "sort": "asc",
  "mode": "replace_if_empty",
  "extensions": [".mp4", ".png", ".jpg"]
}
```

Rules:
- `directory` is resolved relative to `output/media/` (vision root)
  - To target lane0: `"<weekday>/lane0"`
- Do not include the `output/media/` prefix in `directory`
- `auto_policy` can be top-level or lane-level. Lane-level overrides top-level.
- `mode`:
  - `replace_if_empty`: if lane items are empty after availability filtering, use auto items
  - `append_remaining`: append files not already listed in items
  - `disabled`: do not use auto items
  - `append_remaining_always`: append files not already listed, plus `always_directory`
- `mode` default is `replace_if_empty`
- `always_directory` (optional): override always media directory for append_remaining_always
  - To target lane0: `"always/lane0"`

## Path resolution
All relative media paths are resolved against the media base directory.
When using the media-server push layout, the base is `vision_players/<vision_id>/output/media/`.
When using standalone mode, the base is `vision_players/_local/output/media/`.
If a path already starts with the base directory name, it is used as-is.
