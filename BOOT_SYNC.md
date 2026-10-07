# 起動時にMediaServerから取得する

Piの起動時に一度だけ、MediaServerの変換済みoutputを取得してから再生します。毎時の同期はありません。取得に失敗した場合は15秒ごとに再試行し、完了するまで再生を始めません。RAM上への保存はそのままです。取得用の一時領域と入れ替え前の素材が同時に存在するため、一時的に必要容量は増えます。

この設定例はPlayerがishii、/home/ishii/space-vision-player、Pi5が192.168.10.2の構成です。実機のsystemctl cat space-vision-playerでUserとWorkingDirectoryを確認し、異なる場合は同期サービスも合わせてください。

## 先にPi5で全反映する

起動時同期はエンコードしません。管理画面で「素材と再生設定を反映」を完了させ、Pi5側のoutputを用意します。同期中にPi5でエンコード・公開操作をしないでください。公開中の出力を完全なスナップショットとして固定する機構はまだありません。

## PiからPi5への鍵を登録

これまでのPi5→Piとは逆方向の鍵が必要です。Piのishiiで以下を実行します。既存の鍵は上書きしません。新規作成時のパスフレーズは空にします。

```sh
test -f ~/.ssh/id_ed25519 || ssh-keygen -t ed25519
ssh-copy-id ishii@192.168.10.2
ssh -o BatchMode=yes ishii@192.168.10.2 whoami
```

初回のホスト鍵は接続先を確認して登録してください。Pi5・Piの双方にrsyncが必要です。設定と鍵は読み取り専用化前に保存します。

## 起動設定を追加（Pi側）

リポジトリを更新してから実行します。

```sh
cd /home/ishii/space-vision-player
sudo tee /etc/space-vision-boot-sync.env >/dev/null <<'EOF'
MEDIA_SERVER_HOST=192.168.10.2
MEDIA_SERVER_USER=ishii
MEDIA_SERVER_ROOT=/srv/space-media-server
VISION_ID=akiba_01
EOF
sudo cp systemd/space-vision-boot-sync.service /etc/systemd/system/
sudo mkdir -p /etc/systemd/system/space-vision-player.service.d
sudo cp systemd/space-vision-player-boot-sync.conf /etc/systemd/system/space-vision-player.service.d/boot-sync.conf
sudo systemctl daemon-reload
sudo systemctl enable space-vision-boot-sync
sudo systemctl stop space-vision-player
sudo systemctl start --no-block space-vision-player
sudo journalctl -u space-vision-boot-sync -f
```

complete; playback may startが出たら取得完了です。ログの追跡はCtrl+Cで終了できます。通常のPlayer再起動では同期を繰り返しません。再起動試験で取得と再生を確認してからOverlayを有効にしてください。

## 同期をやめる

```sh
sudo rm /etc/systemd/system/space-vision-player.service.d/boot-sync.conf
sudo systemctl disable --now space-vision-boot-sync
sudo systemctl daemon-reload
sudo systemctl restart space-vision-player
```
