# space-vision-player

LED ビジョン向けの常時自動再生プレイヤー。  
Raspberry Pi 上で動作し、media-server がエンコードした動画を曜日別に再生する。

## 役割分担（重要）
- **vision-player**: 再生のみ（mpv 起動・曜日切替・更新中表示）
- **media-server**: エンコードと配信のみ（rect/アスペクト調整は server 側）

## 主要仕様
- **lane = 1 mpv プロセス**
- **1 item = 1 mpv 起動**（再生後はプロセス破棄）
- playlist は **曜日別ファイル**（`mon.json` など）
- mpv のウィンドウ位置・サイズは起動時のみ指定（再生中に変更しない）

## ディレクトリ構成（抜粋）
```
space-vision-player/
├─ vision_player/
├─ playlists/
├─ encoded/
├─ system_media/
└─ state/
```

## playlist の仕様
詳細は `playlists/README.md` を参照。

要点:
- 曜日ファイルが無い場合は `always.json` を使用
- `auto_policy.mode` のデフォルトは `replace_if_empty`
- `is_available_*` は timezone 必須

## config
- `config/vision_config.json`  
  cabinet サイズ/台数と lane 分割を定義。  
  playlist に `screen` が無い場合に使用。

- `config/lane_config.py`  
  実行時のデータクラス定義（`LaneConfig`, `LaneItem`）

## auto_policy の責務
- items の自動生成（ディレクトリスキャンと並び順決定のみ）
- 曜日判定・lane 分岐・再生制御は行わない

## 更新中の挙動
`state/media_updating.flag` が存在する間、  
全 lane で `system_media/updating.mp4` をループ再生する。

## 起動
```
python -m vision_player.main
```
