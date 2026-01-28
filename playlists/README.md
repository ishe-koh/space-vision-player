# Playlist Spec (space-vision-player)

This document defines the playlist JSON format used by vision-player.

## Files and selection
- One file per weekday: `mon.json`, `tue.json`, ... `sun.json`
- If the weekday file does not exist, `always.json` is used

Selection logic lives in `vision_player/playlist_selector.py`.

## Top-level structure
```json
{
  "meta": { ... },
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
Optional. If omitted, `config/vision_config.json` is used.
```json
{
  "width": 1280,
  "height": 256,
  "cols": 3,
  "rows": 1
}
```

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

## auto_policy
Used to auto-generate items from a directory (encoded media).

```json
{
  "directory": "encoded/always",
  "sort": "asc",
  "mode": "replace_if_empty",
  "extensions": [".mp4", ".png", ".jpg"]
}
```

Rules:
- `directory` is fixed to `encoded/<weekday>` style (relative to project root)
- `mode`:
  - `replace_if_empty`: if lane items are empty, use auto items
  - `append_remaining`: append files not already listed in items
  - `disabled`: do not use auto items
- `mode` default is `replace_if_empty`

## Path resolution
All relative media paths are resolved against `encoded/`.
If a path already starts with `encoded/`, it is used as-is.
