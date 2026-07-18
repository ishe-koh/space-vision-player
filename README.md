# space-vision-player

Raspberry PiでLEDビジョン用メディアを再生するplayer。
`space-media-server` から同期された `vision_players/<VISION_ID>/output/` を読む。

## 役割
- 曜日ごとのplaylistを選ぶ
- laneごとに `mpv` を起動する
- `active_time` に従って再生を止める・再開する
- 同期中は `system_media/updating.mp4` を表示する

## 用語
- `VISION_ID`: このplayerが読むデータID。`vision_players/<VISION_ID>/` のディレクトリ名。例: `akiba_02`

## ディレクトリ
```text
space-vision-player/
├─ app/
├─ system_media/
├─ systemd/
└─ vision_players/
   └─ <VISION_ID>/
      ├─ config/
      │  └─ vision_config.json
      └─ output/
         ├─ media/
         └─ playlists/
```

`vision_players/<VISION_ID>/` は media-server から同期される。
初回にplayer側で空mkdirする必要はない。

## 初回セットアップ
以下は OSユーザー `pi`、配置先 `/home/pi/space-vision-player` の前提。

### 1. OS初期設定
- Raspberry Pi OS Lite 64-bit 推奨
- Raspberry Pi Imagerでユーザー `pi`、Wi-Fi、SSH、hostnameを設定
- hostname例: `EventVisionPlayer`

### 2. 必要パッケージ
```sh
sudo apt-get update
sudo apt-get install -y git python3 mpv rsync xserver-xorg
```

### 3. repo配置
```sh
cd /home/pi
git clone <REPOSITORY_URL> space-vision-player
cd /home/pi/space-vision-player
```

確認:
```sh
test "$(pwd)" = /home/pi/space-vision-player
test "$(stat -c %U .)" = pi
```

### 4. systemd unitを入れる
```sh
sudo cp systemd/xorg-kiosk.service /etc/systemd/system/
sudo cp systemd/space-vision-player.service /etc/systemd/system/
sudo systemctl daemon-reload
```

`systemd/space-vision-player.service` は `pi` と `/home/pi/space-vision-player` 前提。
通常は `VISION_ID` だけoverrideする。

```sh
sudo systemctl edit space-vision-player
```

入力内容:
```ini
[Service]
Environment=VISION_ID=akiba_02
```

確認:
```sh
sudo systemctl daemon-reload
systemctl cat space-vision-player
```

### 5. media-serverから初回pushする
player側で `vision_players/akiba_02/` を空作成しない。
media-serverの初回pushが以下を作る。

```text
vision_players/akiba_02/output/media/
vision_players/akiba_02/output/playlists/
```

media-server側で実行:
```sh
./bin/init_vision.py akiba_02
VISION_ID=akiba_02 PLAYER_HOSTNAME=EventVisionPlayer PLAYER_USER=pi ./bin/encode_and_push.sh
```

固定IPでpushする場合:
```sh
VISION_ID=akiba_02 PLAYER_IP=192.168.x.x PLAYER_USER=pi ./bin/encode_and_push.sh
```

初回push前に `space-vision-player` serviceを起動すると、
`vision_players/akiba_02 not found` で失敗する。
初回push後は `push_media.sh` がserviceをrestartする。

### 6. kiosk serviceを有効化する
LightDMやtty1のlogin consoleは専用Xorgと競合するので無効化する。

```sh
sudo systemctl disable --now lightdm 2>/dev/null || true
sudo systemctl disable getty@tty1
sudo systemctl enable xorg-kiosk space-vision-player
sudo reboot
```

再起動後:
```sh
systemctl is-active xorg-kiosk space-vision-player
```

ログ確認:
```sh
journalctl -u xorg-kiosk -u space-vision-player -b --no-pager -n 100
```

## media-serverからpushされる前提
media-serverは `pi` でSSHし、最後に以下を実行する。

```sh
sudo -n systemctl restart space-vision-player
```

そのためplayer側で `pi` にrestartだけpasswordless sudoを許可する。

```sh
echo 'pi ALL=(root) NOPASSWD: /usr/bin/systemctl restart space-vision-player, /bin/systemctl restart space-vision-player' | sudo tee /etc/sudoers.d/space-vision-player-restart
sudo chmod 440 /etc/sudoers.d/space-vision-player-restart
sudo visudo -cf /etc/sudoers.d/space-vision-player-restart
```

media-server側のSSH公開鍵も `pi` に登録しておく。

```sh
ssh-copy-id pi@EventVisionPlayer
```

## playlist仕様
playerが読むplaylistはここ。

```text
vision_players/<VISION_ID>/output/playlists/<weekday>.json
```

曜日ファイルが無ければ `always.json` を使う。

```text
mon.json ... sun.json
always.json
```

### active_time
`active_time` は `mon`〜`sun` の曜日キーだけを見る。
`active_time.always` は見ない。

```json
{
  "active_time": {
    "mon": {"from": "10:00", "until": "20:00"},
    "tue": {"from": "10:00", "until": "20:00"}
  }
}
```

判定:
- `from <= now < until` の間だけ再生する
- 曜日キーが無い場合は常時再生
- 再生中に時間外になるとmpvを止める

### media path
item path と `auto_policy.directory` は `output/media/` 基準の相対パス。

```json
{
  "lanes": {
    "lane0": {
      "items": ["always/lane0/001.mp4"],
      "auto_policy": {
        "directory": "always/lane0",
        "mode": "replace_if_empty"
      }
    }
  }
}
```

`output/media/always/lane0/001.mp4` を読む場合、playlistには `always/lane0/001.mp4` と書く。

詳細仕様:
```text
vision_players/_local/output/playlists/README.md
```

## 手動確認
### service状態
```sh
systemctl status xorg-kiosk space-vision-player --no-pager
journalctl -u space-vision-player -n 100 --no-pager
```

### playlistとmediaの存在確認
```sh
ls -l vision_players/akiba_02/output/playlists/
find vision_players/akiba_02/output/media -maxdepth 3 -type f | head
```

### mpv単体確認
GUI/Xorgが動いている状態で確認する。

```sh
DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority \
mpv --vo=gpu --gpu-context=x11egl vision_players/akiba_02/output/media/always/lane0/*.mp4
```

## updating表示
このファイルがある間、全laneで `system_media/updating.mp4` をループ再生する。

```sh
touch state/media_updating.flag
rm -f state/media_updating.flag
```

通常はmedia-serverのpush処理が自動で作成・削除する。

## RTC設定 任意
RTCを使う場合だけ設定する。

```sh
sudo raspi-config
sudo timedatectl set-timezone Asia/Tokyo
sudo hwclock -w
```

DS3231例:
```ini
dtoverlay=i2c-rtc,ds3231
```

fake-hwclockを使わない場合:
```sh
sudo apt-get remove -y fake-hwclock
sudo systemctl disable fake-hwclock
```

## 備考
- `xorg-kiosk` はXorg担当
- `space-vision-player` はmpv再生担当
- 1 lane = 1 mpv process
- mpvの `pw.conf: can't load config client.conf` はPipeWire設定警告で、media path missingとは別
