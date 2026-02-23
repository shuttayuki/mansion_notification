# セントラルガーデン月島 ザ タワー 予約監視システム

予約サイトの更新を自動監視し、LINE公式アカウントから通知を送信するシステムです。

## 機能

- 予約カレンダーの自動監視（1-3分間隔）
- 更新検知時のLINE通知
- 複数送信先への一括配信
- スクリーンショット保存（デバッグ用）
- ログ記録とエラー通知

## 必要なもの

- Python 3.8以上
- LINE Developers アカウント
- LINE公式アカウント（Messaging API）

## セットアップ

### 1. 環境構築

```bash
# セットアップスクリプトを実行
python setup.py
```

### 2. LINE設定

#### LINE Developers での設定

1. [LINE Developers](https://developers.line.biz/) にログイン
2. プロバイダーを作成
3. Messaging API チャンネルを作成
4. チャネルアクセストークン（長期）を発行

#### 送信先IDの取得

1. Webhook設定を一時的に有効化
2. [webhook.site](https://webhook.site/) でURLを発行
3. LINE公式アカウントを友だち追加
4. テストメッセージを送信
5. webhook.siteで受信したJSONから `userId` を取得

### 3. 設定ファイル

#### .env ファイルを作成

```bash
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here
TARGET_URL=https://www.31sumai.com/attend/X1413/
CHECK_INTERVAL=2
```

#### subscribers.txt に送信先IDを設定

```
U73b80c9d3652f82ba083d455b78c2c39
Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 使用方法

### 単発実行（テスト）

```bash
# 仮想環境をアクティベート
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate     # Windows

# 監視スクリプトを実行
python watch_calendar.py
```

### 定期実行

#### 方法1: スケジューラー（推奨）

```bash
python scheduler.py
```

#### 方法2: cron（Linux/macOS）

```bash
crontab -e

# 2分ごとに実行
*/2 * * * * cd /path/to/project && /path/to/project/venv/bin/python watch_calendar.py >> run.log 2>&1
```

#### 方法3: GitHub Actions（無料・PC不要）

1. リポジトリにコードをプッシュ
2. Settings → Secrets and variables → Actions で `LINE_CHANNEL_ACCESS_TOKEN` を設定
3. `.github/workflows/watch.yml` が自動的に定期実行

## ファイル構成

```
LINE_notify_tsukishima/
├── watch_calendar.py      # メイン監視スクリプト
├── scheduler.py           # 定期実行スケジューラー
├── config.py              # 設定ファイル
├── setup.py               # セットアップスクリプト
├── requirements.txt       # Python依存関係
├── subscribers.txt        # 送信先IDリスト
├── .env                   # 環境変数（要作成）
├── data/                  # データ保存ディレクトリ（自動作成）
└── venv/                  # Python仮想環境（自動作成）
```

## 監視の仕組み

1. **ページアクセス**: Playwrightで対象URLにアクセス
2. **JavaScript描画待ち**: 5秒間待機してカレンダー表示完了
3. **テキスト抽出**: 予約カレンダー部分のテキストを取得
4. **差分検知**: 前回のハッシュ値と比較
5. **通知送信**: 変化があり、かつ「空き」を示すキーワードがある場合にLINE通知

## カスタマイズ

### 監視間隔の変更

`.env` ファイルの `CHECK_INTERVAL` を変更

### 通知条件の調整

`config.py` の `POSITIVE_KEYS` と `NEGATIVE_KEYS` を編集

### カレンダー抽出セレクタの調整

`config.py` の `CALENDAR_SELECTORS` を編集

## トラブルシューティング

### よくある問題

1. **LINE通知が送信されない**
   - チャネルアクセストークンが正しいか確認
   - 送信先IDが正しいか確認
   - 友だち追加済みか確認

2. **カレンダーが抽出できない**
   - スクリーンショットを確認してページ構造を把握
   - `config.py` のセレクタを調整

3. **誤検知が多い**
   - 監視範囲をカレンダー部分のみに限定
   - 通知条件を厳しく設定

### ログの確認

```bash
tail -f data/monitor.log
```

## 注意事項

- 監視間隔は短すぎるとサーバーに負荷がかかる可能性があります
- 初回実行時は必ず通知が送信されます（正常な動作です）
- 会員専用ページに移行した場合はログイン対応が必要です

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## サポート

問題が発生した場合は、以下を確認してください：

1. ログファイル（`data/monitor.log`）
2. スクリーンショット（`data/last_screenshot_*.png`）
3. 設定ファイルの内容
4. Python環境とパッケージのバージョン 