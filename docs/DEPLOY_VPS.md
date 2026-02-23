## ConoHa VPS へのデプロイ手順（systemd timer 方式）

### 前提
- OS: Ubuntu/Debian 系想定
- リポジトリを VPS にアップロード済み、またはローカルから `rsync/scp` 可能

### かんたんセットアップ
VPS 側で以下を実行（例: 作業ディレクトリ `/opt/LINE_notify_tsukishima`、実行ユーザー `ubuntu`）

```bash
sudo apt update -y && sudo apt install -y git
cd ~
git clone <YOUR_REPO_URL> LINE_notify_tsukishima || true
cd LINE_notify_tsukishima
bash scripts/setup_vps.sh /opt/LINE_notify_tsukishima ubuntu
```

実行後、以下を実施:
- `/opt/LINE_notify_tsukishima/.env` を編集して `LINE_CHANNEL_ACCESS_TOKEN` を設定
- 動作確認: `journalctl -u line-calendar-watch.service -n 100 -f --no-pager`

### 既にディレクトリがある場合
ローカルから rsync:
```bash
rsync -av --delete ./ /opt/LINE_notify_tsukishima/
ssh ubuntu@<VPS> "bash /opt/LINE_notify_tsukishima/scripts/setup_vps.sh /opt/LINE_notify_tsukishima ubuntu"
```

### 手動実行/ログ確認
```bash
systemctl start line-calendar-watch.service
journalctl -u line-calendar-watch.service -n 100 -f --no-pager
tail -n 100 /opt/LINE_notify_tsukishima/data/monitor.log
```

### スケジュール変更
`/etc/systemd/system/line-calendar-watch.timer` の `OnUnitActiveSec` を調整（例: 1 分間隔なら `1min`）。
変更後は `sudo systemctl daemon-reload && sudo systemctl restart line-calendar-watch.timer`。

### 注意事項
- `subscribers.txt` は空だと停止するため、最低 1 行は入れてください（placeholder 可）。
- `.env` の `LINE_CHANNEL_ACCESS_TOKEN` は必須です。
- Playwright の `install-deps` は root によるパッケージ導入が必要です。



