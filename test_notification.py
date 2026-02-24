#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空き枠通知システムのテストスクリプト
実際のサイトを変更せずに通知機能をテスト
"""

import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests

# 環境変数読み込み
load_dotenv()

# 設定
TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

def jst_now():
    """現在時刻をJSTで取得"""
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")

def line_broadcast(text):
    """LINE公式アカウントからブロードキャスト通知を送信"""
    if not TOKEN:
        print("エラー: LINE_CHANNEL_ACCESS_TOKEN が設定されていません")
        return False

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    body = {
        "messages": [{"type": "text", "text": text}]
    }

    try:
        response = requests.post(
            "https://api.line.me/v2/bot/message/broadcast",
            headers=headers,
            json=body,
            timeout=15
        )
        response.raise_for_status()
        print("LINE通知送信成功: 全員")
        return True
    except requests.exceptions.RequestException as e:
        print(f"LINE通知送信失敗: {e}")
        return False

def test_notification_scenarios():
    """通知シナリオのテスト"""
    print("=== 空き枠通知システム テスト開始 ===\n")

    if not TOKEN:
        print("エラー: LINE_CHANNEL_ACCESS_TOKEN が設定されていません")
        return

    # テストシナリオ1: 空き枠が新しくできた場合
    print("【テスト1】空き枠が新しくできた場合の通知")
    print("前回: 9月1日×、9月2日-")
    print("今回: 9月1日○、9月2日△")
    print("期待結果: 通知が送信される")

    # 通知メッセージ作成（実際のシステムと同じ形式）
    message = f"""【予約枠状況更新】{jst_now()}

予約枠に新しく空きまたは空きの可能性があります！
○：余裕あり、△：まもなく満席

URL: https://www.31sumai.com/attend/X1413/

変更内容:
+ 9月 1日 ○
+ 9月 2日 △

現在の状況:
9月 1日 ○
9月 2日 △
9月 3日 -
9月 4日 -
9月 5日 ×

監視システムより自動通知（テスト）"""

    print(f"\n送信するメッセージ:\n{message}")

    # 実際に通知を送信
    print("\n実際に通知を送信しますか？ (y/n): ", end="")
    user_input = input().strip().lower()

    if user_input == 'y':
        print("\n通知を送信中...")
        if line_broadcast(message):
            print("通知テスト成功！LINEでメッセージを確認してください。")
        else:
            print("通知テスト失敗。設定を確認してください。")
    else:
        print("通知の送信をスキップしました。")

    # テストシナリオ2: 空き枠がない場合
    print("\n【テスト2】空き枠がない場合の動作確認")
    print("前回: 9月1日×、9月2日-")
    print("今回: 9月1日×、9月2日-")
    print("期待結果: 通知は送信されない（正しい動作）")

    # テストシナリオ3: 空き枠が減った場合
    print("\n【テスト3】空き枠が減った場合の動作確認")
    print("前回: 9月1日○、9月2日△")
    print("今回: 9月1日×、9月2日-")
    print("期待結果: 通知は送信されない（空き枠の減少は通知対象外）")

    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    test_notification_scenarios()
