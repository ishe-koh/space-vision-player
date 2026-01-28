#!/usr/bin/env bash
set -euo pipefail

# Simple local encoder for vision_players/_local
# Usage:
#   ./bin/encode_local.sh
# Optional env:
#   VISION_ID=_local
#   SOURCE_ROOT=vision_players/_local/source/media
#   OUTPUT_ROOT=vision_players/_local/output/media
#   FPS=30
#   IMAGE_DURATION=10
#   CRF=23
#   PRESET=veryfast

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VISION_ID="${VISION_ID:-_local}"
SOURCE_ROOT="${SOURCE_ROOT:-${REPO_ROOT}/vision_players/${VISION_ID}/source/media}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/vision_players/${VISION_ID}/output/media}"
CONFIG_PATH="${REPO_ROOT}/vision_players/${VISION_ID}/config/vision_config.json"

FPS="${FPS:-30}"
IMAGE_DURATION="${IMAGE_DURATION:-10}"
CRF="${CRF:-23}"
PRESET="${PRESET:-veryfast}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "vision_config.json not found: ${CONFIG_PATH}" >&2
  exit 1
fi

if [[ ! -d "${SOURCE_ROOT}" ]]; then
  echo "source dir not found: ${SOURCE_ROOT}" >&2
  exit 1
fi

read -r LANE_W LANE_H <<EOF_DIM
$(python3 - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path("${CONFIG_PATH}").read_text(encoding="utf-8"))
cap = cfg["cabinet"]
layout = cfg.get("lane_layout", {})
screen_w = cap["width"] * cap["cols"]
screen_h = cap["height"] * cap["rows"]
cols = layout.get("cols", 1)
rows = layout.get("rows", 1)
print(screen_w // cols, screen_h // rows)
PY
)
EOF_DIM

if [[ -z "${LANE_W}" || -z "${LANE_H}" ]]; then
  echo "failed to resolve lane size" >&2
  exit 1
fi

encode_video() {
  local in_path="$1"
  local out_path="$2"
  ffmpeg -y -i "${in_path}" \
    -vf "scale=${LANE_W}:${LANE_H}:force_original_aspect_ratio=decrease,pad=${LANE_W}:${LANE_H}:(ow-iw)/2:(oh-ih)/2" \
    -r "${FPS}" -c:v libx264 -preset "${PRESET}" -crf "${CRF}" -pix_fmt yuv420p \
    -movflags +faststart "${out_path}"
}

encode_image() {
  local in_path="$1"
  local out_path="$2"
  ffmpeg -y -loop 1 -t "${IMAGE_DURATION}" -i "${in_path}" \
    -vf "scale=${LANE_W}:${LANE_H}:force_original_aspect_ratio=decrease,pad=${LANE_W}:${LANE_H}:(ow-iw)/2:(oh-ih)/2" \
    -r "${FPS}" -c:v libx264 -preset "${PRESET}" -crf "${CRF}" -pix_fmt yuv420p \
    -movflags +faststart "${out_path}"
}

shopt -s nullglob

for src_dir in "${SOURCE_ROOT}"/*; do
  if [[ ! -d "${src_dir}" ]]; then
    continue
  fi
  weekday="$(basename "${src_dir}")"
  out_dir="${OUTPUT_ROOT}/${weekday}"
  mkdir -p "${out_dir}"

  for f in "${src_dir}"/*; do
    if [[ ! -f "${f}" ]]; then
      continue
    fi
    ext="${f##*.}"
    base="$(basename "${f%.*}")"
    out_path="${out_dir}/${base}.mp4"
    case "${ext,,}" in
      mp4|mov|m4v|mkv|avi|webm)
        echo "[encode] video ${f} -> ${out_path}"
        encode_video "${f}" "${out_path}"
        ;;
      png|jpg|jpeg)
        echo "[encode] image ${f} -> ${out_path}"
        encode_image "${f}" "${out_path}"
        ;;
      *)
        echo "[skip] ${f} (unsupported)" >&2
        ;;
    esac
  done
done

echo "[done] output: ${OUTPUT_ROOT}"
