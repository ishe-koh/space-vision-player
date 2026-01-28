# space-vision-player

Raspberry Pi 向けの LED ビジョン再生プレイヤー。
media-server（別リポジトリ）が出力した
`vision_players/<vision_id>/output/media/` と `output/playlists/` を再生する。

## What this does
- 曜日別のプレイリストを選択して再生
- lane（領域）ごとに mpv を起動して同時再生
- 同期中は updating 動画へ自動切替

## Requirements
- OS: Raspberry Pi OS (Lite 64-bit 推奨) または Desktop
- Python 3
- mpv
- Xorg（mpv の描画に必要）
- rsync（media-server からの push）

## Directory layout
```
space-vision-player/
├─ app/                    # 再生ロジック
├─ vision_players/
│  └─ <vision_id or _local>/
│     ├─ config/           # vision_config.json
│     └─ output/
│        ├─ media/         # runtime
│        └─ playlists/     # runtime + docs
├─ system_media/           # updating 用動画など
└─ systemd/                # systemd service
```

`vision_players/` は実行時に同期されるため git 管理外。

## Raspberry Pi 4 setup (recommended)
1) OS 書き込み + 初期設定
- Raspberry Pi OS Lite 64-bit 推奨（Desktop でも可）
- Lite の場合は後述の X 環境を入れる
- Raspberry Pi Imager で Wi‑Fi / SSH / hostname を事前設定すると楽

2) パッケージ導入
```
sudo apt-get update
sudo apt-get install -y \
  git \
  python3 \
  mpv \
  rsync \
  xserver-xorg \
  xinit \
  openbox \
  lightdm \
  unclutter
```

3) RTC モジュール設定（例: DS3231）
- 5V / GND を GPIO に接続
- I2C 有効化:
```
sudo raspi-config
```
Interfacing Options → I2C → Enable
- `/boot/config.txt` に overlay を追加:
```
dtoverlay=i2c-rtc,ds3231
```
- fake-hwclock を無効化:
```
sudo apt-get remove -y fake-hwclock
sudo systemctl disable fake-hwclock
```
- タイムゾーン設定 + RTC へ書き込み:
```
sudo timedatectl set-timezone Asia/Tokyo
sudo hwclock -w
```
※ RTC が別型番の場合は overlay 名を変更する。

4) 自動ログイン + X 起動
- `sudo raspi-config` → System Options → Boot / Auto Login → Desktop Autologin
- もしくは `/etc/lightdm/lightdm.conf`
```
[Seat:*]
autologin-user=pi
autologin-session=openbox
```

5) 画面スリープ無効化
```
cat <<'EOS' > /home/pi/.xsessionrc
xset s off
xset -dpms
xset s noblank
unclutter -idle 0.5 -root &
EOS
```

6) Wi‑Fi / SSH
- media-server の SSID に接続
- media-server / 操作用 PC の SSH key を登録

7) 機器名（hostname）を決める
- 例: `akiba_01`
- Raspberry Pi Imager か `raspi-config` で設定
- media-server 側に `media/<hostname>/source/` を作成

### Optional: handy commands on the device
```
# update packages
sudo apt-get update && sudo apt-get upgrade -y

# set hostname (if not set by Imager)
sudo hostnamectl set-hostname akiba_01

# enable ssh (if needed)
sudo systemctl enable --now ssh

# set timezone
sudo timedatectl set-timezone Asia/Tokyo
```

## Configuration
### `vision_players/<vision_id>/config/vision_config.json`
キャビネットのサイズと lane 分割を定義。
playlist に `screen` が無い場合に使用される。

### Playlists
- 曜日ファイルが無い場合は `always.json` を使用
- 仕様: `vision_players/_local/output/playlists/README.md`
- サンプル: `vision_players/_local/output/playlists/sample.jsonc`
- 曜日別に分けたい場合は `always.json` を複製
```
cp vision_players/_local/output/playlists/always.json \
  vision_players/_local/output/playlists/mon.json
```
 - `active_time` を指定すると曜日ごとの稼働時間を設定できる

## Usage
### Manual run
```
python3 -m app.main
```

### Sync from media-server (server-side push)
media-server の `bin/push_media.sh` で rsync を実行し、`vision_players/<vision_id>/output/` を更新する。
同期中は `state/media_updating.flag` を作成し、完了後に削除する。
media-server 側の `output/media/` が player 側の `vision_players/<vision_id>/output/media/` に同期される想定。
media-server 側の `output/playlists/` が player 側の `vision_players/<vision_id>/output/playlists/` に同期される想定。

player 側は以下の順で `vision_id` を解決する:
1) `VISION_ID` 環境変数
2) `vision_players/` 直下に `_local` 以外のディレクトリが 1 つだけある場合はそれを使用
3) `vision_players/_local/` があればそれを使用
4) それ以外は `vision_players/_local/` を使う（自動作成）

期待される `push_media.sh` の挙動:
- rsync 前に `state/` を作って `media_updating.flag` を touch
- `output/media/` → `output/playlists/` の順に push
- 成功時にフラグ削除（失敗時は残す）

server 側の環境変数:
- `VISION_ID` (必須): 例 `akiba_01`
- `PLAYER_HOSTNAME` (任意): 既定は `VISION_ID`
- `PLAYER_IP` (任意): hostname 不在時のフォールバック
- `PLAYER_USER` (任意): 既定は `pi`
- `REMOTE_BASE` (任意): 既定は `/home/${PLAYER_USER}/space-vision-player`
- `MEDIA_ROOT` (任意): 既定は media-server のリポジトリルート
- `LEASES_FILE` (任意): 既定は `/var/lib/misc/dnsmasq.leases`
- `RSYNC_OPTS` (任意): 既定は `-az --size-only`
- `RSYNC_DELETE=1` で削除も反映

※ `output/playlists/` は同期で上書きされるため、編集は media-server 側で行う。

### Standalone usage (no media-server)
- `vision_players/_local/output/media/` に動画を配置
- `vision_players/_local/output/playlists/` を編集
- `python3 -m app.main` で起動

### Local encode (simple)
`vision_players/_local/source/media/<weekday>/` から
`vision_players/_local/output/media/<weekday>/` へ簡易エンコード。
```
./bin/encode_local.sh
```

### Generate playlist (simple)
`_local` 用のプレイリストを対話形式で作成する。
```
./bin/gen_playlist.py
```

強制的に updating 表示へ切り替える場合:
```
mkdir -p state
touch state/media_updating.flag   # updating 表示
rm -f state/media_updating.flag   # 通常再生へ戻す
```

## Deploy (systemd)
1) リポジトリ配置
```
sudo mkdir -p /home/pi/space-vision-player
sudo chown -R pi:pi /home/pi/space-vision-player
```

2) service 配置
```
sudo cp systemd/space-vision-player.service /etc/systemd/system/
```

3) `systemd/space-vision-player.service` を編集
- `User`, `Group`, `WorkingDirectory`, `XAUTHORITY` を環境に合わせる
- `DISPLAY=:0` を正しいセッションに合わせる
- `VISION_ID` で再生するディレクトリを指定（例: `akiba_01`）
  - 未指定の場合は `vision_players/_local/` が優先される
  - 複数の `vision_players/` がある場合は必ず指定する

4) 有効化
```
sudo systemctl daemon-reload
sudo systemctl enable --now space-vision-player
```

5) ログ確認
```
journalctl -u space-vision-player -f
```

## Updating behavior
`state/media_updating.flag` が存在する間、
全 lane で `system_media/updating.mp4` をループ再生する。

## Notes
- lane = 1 mpv プロセス
- 1 item = 1 mpv 起動（ただし item が 1 つで loop の場合は mpv 自体を loop 起動）
- mpv のウィンドウ位置・サイズは起動時のみ指定

## References
- playlist spec: `vision_players/_local/output/playlists/README.md`
