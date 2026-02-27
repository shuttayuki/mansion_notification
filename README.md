# マンション予約監視システム

三井不動産の予約サイトを自動監視し、LINE公式アカウントから通知を送信するシステムです。

## 監視対象物件

| 物件 | スクリプト | ワークフロー |
|------|-----------|-------------|
| パークコート麻布十番東京 | `watch_azabu.py` | `watch_azabu.yml` |

## 機能

- 予約受付開始の即時検知
- 予約カレンダーの自動監視（2分間隔）
- 更新検知時のLINE通知
- 友だち全員へのブロードキャスト配信
- スクリーンショット保存（デバッグ用）
- ログ記録とエラー通知

## 必要なもの

- Python 3.8以上
- LINE Developers アカウント
- LINE公式アカウント（Messaging API）

## セットアップ

### 1. 環境構築

```bash
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

### 2. LINE設定

#### LINE Developers での設定

1. [LINE Developers](https://developers.line.biz/) にログイン
2. プロバイダーを作成
3. Messaging API チャンネルを作成
4. チャネルアクセストークン（長期）を発行

### 3. 設定ファイル

#### .env ファイルを作成

```bash
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here
TARGET_URL_AZABU=https://www.31sumai.com/attend/X2571/
CHECK_INTERVAL=2
```

## 使用方法

### 単発実行（テスト）

```bash
# 監視実行
python watch_azabu.py

# LINE通知テスト
python test_line_azabu.py
```

### テストモード（GitHub Actions）

手動実行時に以下のモードを選択可能:
- `false`: 通常の監視実行
- `true`: LINE疎通確認テスト通知を送信
- `simulate`: 予約開始を模擬したシミュレーション通知を送信

### 定期実行（GitHub Actions）

1. リポジトリにコードをプッシュ
2. Settings → Secrets and variables → Actions で `LINE_CHANNEL_ACCESS_TOKEN` を設定
3. `.github/workflows/watch_azabu.yml` が自動的に6時間ごとに実行

## ファイル構成

```
mansion_notification/
├── watch_azabu.py         # 監視スクリプト
├── test_line_azabu.py     # LINE通知テスト
├── requirements.txt       # Python依存関係
├── .env                   # 環境変数（要作成）
├── .github/workflows/
│   └── watch_azabu.yml    # GitHub Actions
├── data/                  # データ保存ディレクトリ（自動作成）
└── venv/                  # Python仮想環境（自動作成）
```

## 監視の仕組み

### パークコート麻布十番東京（watch_azabu.py）
1. **Phase 1（受付開始前）**: requestsで軽量チェック。「予約を受け付けておりません」の有無を確認
2. **Phase 2（受付開始後）**: キーワードが消えたら即座にLINE速報通知を送信
3. **カレンダー取得**: Playwrightで予約カレンダーの詳細（空き状況）を取得して追加通知

## トラブルシューティング

### よくある問題

1. **LINE通知が送信されない**
   - チャネルアクセストークンが正しいか確認
   - LINE公式アカウントが友だち追加済みか確認

2. **カレンダーが抽出できない**
   - スクリーンショットを確認してページ構造を把握

### ログの確認

```bash
tail -f data/monitor_azabu.log
```

## 注意事項

- 監視間隔は短すぎるとサーバーに負荷がかかる可能性があります
- 初回実行時は必ず通知が送信されます（正常な動作です）
- 会員専用ページに移行した場合はログイン対応が必要です

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。
