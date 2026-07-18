# space-vision-player

Raspberry Pi 向けの LED ビジョン再生プレイヤー。
media-server（別リポジトリ）が出力した
`vision_players/<vision_id>/output/media/` と `output/playlists/` を再生する。

## What this does
- 曜日別のプレイリストを選択して再生
- lane（領域）ごとに mpv を起動して同時再生
- 同期中は updating 動画へ自動切替
- `is_available_*` は実行中も定期再評価される

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

## Raspberry Pi 4 setup (recommended: systemd kiosk)

本番運用では LightDM やデスクトップの自動ログインを使わない。
`xorg-kiosk` が専用 Xorg を起動し、`space-vision-player` がその上で mpv を起動する。
以下は OS ユーザー名を `pi`、配置先を
`/home/pi/space-vision-player` とした手順。異なるユーザー名を使う場合は、
ユーザー名とホームディレクトリを読み替える。

### 1. OS 書き込みと初期設定

- Raspberry Pi OS Lite 64-bit 推奨
- Raspberry Pi Imager でユーザー `pi`、Wi-Fi、SSH、hostname を設定
- media-server と同じネットワークへ接続

### 2. 必要パッケージの導入

```sh
sudo apt-get update
sudo apt-get install -y git python3 mpv rsync xserver-xorg
```

### 3. リポジトリ配置

```sh
cd /home/pi
git clone <REPOSITORY_URL> space-vision-player
cd /home/pi/space-vision-player
```

すでに clone 済みの場合は、次で配置と所有者を確認する。

```sh
pwd
test "$(pwd)" = /home/pi/space-vision-player
test "$(stat -c %U .)" = pi
```

### 4. systemd service の配置

```sh
sudo cp systemd/xorg-kiosk.service /etc/systemd/system/
sudo cp systemd/space-vision-player.service /etc/systemd/system/
sudo systemctl daemon-reload
```

`space-vision-player.service` は `pi` と
`/home/pi/space-vision-player` を初期値にしている。
通常は `VISION_ID` だけを override する。

```sh
sudo systemctl edit space-vision-player
```

開いたエディターに次を入力する。
`VISION_ID` は実機の hostname/media-server 側の vision ID に合わせる。

```ini
[Service]
Environment=VISION_ID=akiba_01
```

保存後、override が反映されたことを確認する。

```sh
sudo systemctl daemon-reload
systemctl cat space-vision-player
```

`VISION_ID` を指定せず `_local` で確認する場合は、override の作成自体を省略できる。
`pi` 以外の OS ユーザーや配置先を使う場合だけ、`User` / `Group` /
`WorkingDirectory` / `XAUTHORITY` を合わせて override する。

### 5. kiosk 自動起動の有効化

LightDM と tty1 の login console は専用 Xorg と競合するため無効化する。
この手順では、作業中のコンソールを切り替えないよう `--now` を付けず、
再起動後に service を開始する。
`xorg-kiosk.service` は `-s 0 -dpms` で Xorg のスクリーンセーバーと
DPMS を無効化するため、`.xsessionrc` の作成は不要。

```sh
sudo systemctl disable --now lightdm 2>/dev/null || true
sudo systemctl disable getty@tty1
sudo systemctl enable xorg-kiosk space-vision-player
sudo reboot
```

### 6. 再起動後の確認

SSH で接続し、2つの service が `active` であることを確認する。

```sh
systemctl is-active xorg-kiosk space-vision-player
```

起動できない場合は次のログを確認する。

```sh
systemctl status xorg-kiosk space-vision-player --no-pager -l
journalctl -u xorg-kiosk -u space-vision-player -b --no-pager -n 100
```

### 7. Wi-Fi / SSH / hostname / sudo

- media-server と同じネットワークへ接続
- media-server 側の実行ユーザーの SSH 公開鍵を `pi` の `authorized_keys` に登録
- hostname と `VISION_ID` を media-server 側の設定に合わせる
- media-server の push は `sudo -n systemctl restart space-vision-player` を実行するため、`pi` で passwordless sudo が必要

必要なら player 側で restart だけを許可する sudoers を追加する。

```sh
echo 'pi ALL=(root) NOPASSWD: /usr/bin/systemctl restart space-vision-player, /bin/systemctl restart space-vision-player' | sudo tee /etc/sudoers.d/space-vision-player-restart
sudo chmod 440 /etc/sudoers.d/space-vision-player-restart
sudo visudo -cf /etc/sudoers.d/space-vision-player-restart
sudo -n systemctl restart space-vision-player
```

### 8. RTC モジュール設定（必要な場合のみ、例: DS3231）

- 5V / GND を GPIO に接続
- I2C 有効化:
```sh
sudo raspi-config
```
Interfacing Options → I2C → Enable
- `/boot/config.txt` に overlay を追加:
```ini
dtoverlay=i2c-rtc,ds3231
```
- fake-hwclock を無効化:
```sh
sudo apt-get remove -y fake-hwclock
sudo systemctl disable fake-hwclock
```
- タイムゾーン設定 + RTC へ書き込み:
```sh
sudo timedatectl set-timezone Asia/Tokyo
sudo hwclock -w
```
※ RTC が別型番の場合は overlay 名を変更する。

### Manual run (service 化前の短時間テスト用)

GUI/Xorg が起動済みの環境でのみ実行できる。本番運用では
systemd kiosk を使う。

```sh
cd /home/pi/space-vision-player
python3 -m app.main
```

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
- `active_time` は `mon`〜`sun` の曜日キーだけを見る。`always` キーは使わない
- `auto_policy.directory` と item path は `output/media/` 基準の相対パス

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
- `PLAYER_HOSTNAME` (任意): `push_media.sh` の既定は `vision-player-${VISION_ID}`、`encode_and_push.sh` の既定は `${VISION_ID}`
- `PLAYER_IP` (任意): hostname / DHCP lease 不在時の固定IP指定
- `PLAYER_USER` (任意): 既定は `pi`
- `REMOTE_PLAYER_ROOT` (任意): 既定は `/home/${PLAYER_USER}/space-vision-player`
- `REMOTE_OUTPUT_DIR` (任意): 既定は `${REMOTE_PLAYER_ROOT}/vision_players/${VISION_ID}/output`
- `REPO_ROOT` (任意): 既定は media-server のリポジトリルート
- `LEASES_FILE` (任意): 既定は `/var/lib/misc/dnsmasq.leases`
- `RSYNC_OPTS` (任意): 既定は `-az --size-only`
- `RSYNC_DELETE=1` で削除も反映（既定で有効）

`pi` 構成なら通常は `PLAYER_USER` / `REMOTE_PLAYER_ROOT` の指定は不要。
固定IPで push する例:

```sh
VISION_ID=akiba_01 PLAYER_IP=192.168.x.x PLAYER_USER=pi ./bin/encode_and_push.sh
```

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

## Service management

```sh
# 状態確認
systemctl status xorg-kiosk space-vision-player --no-pager

# ログ追跡
journalctl -u xorg-kiosk -u space-vision-player -f

# Player だけ再起動
sudo systemctl restart space-vision-player
```

`VISION_ID` 未指定時は `vision_players/_local/` が使われる。
`vision_players/` に複数の実機ディレクトリがある環境では、
service override で `VISION_ID` を必ず指定する。

## Stability tips (Raspberry Pi + Xorg + mpv)
- まず `SVP_MPV_GPU_CONTEXT=x11egl`（既定）で運用し、`mpv -> Xorg -> DRM` に固定する。
- `/boot/config.txt` は `dtoverlay=vc4-kms-v3d` を維持し、必要なら `max_framebuffers=1` を検討。
- 監視ログ:
```
grep -E "drmSetMaster failed|VT switch|AIGLX" /var/log/Xorg.0.log
```
- `AIGLX: Suspending AIGLX clients for VT switch` が出る環境では、display manager 由来の VT 切替を止める。

## Updating behavior
`state/media_updating.flag` が存在する間、
全 lane で `system_media/updating.mp4` をループ再生する。

## Notes
- `xorg-kiosk` は X サーバー担当、`space-vision-player` は mpv 再生担当（役割は別）
- lane = 1 mpv プロセス
- 1 item = 1 mpv 起動（ただし item が 1 つで loop の場合は mpv 自体を loop 起動）
- mpv のウィンドウ位置・サイズは起動時のみ指定

## References
- playlist spec: `vision_players/_local/output/playlists/README.md`
