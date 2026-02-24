#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
セントラルガーデン月島 LINE通知テストスクリプト
"""

import os
from dotenv import load_dotenv
import requests

load_dotenv()


def test_line_notification():
    """LINE通知のテスト"""
    print("セントラルガーデン月島 LINE通知テスト")
    print("=" * 50)

    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        print("LINE_CHANNEL_ACCESS_TOKEN が設定されていません")
        print(".env ファイルに設定してください")
        return False

    print(f"トークン: {token[:20]}...")

    test_message = """【テスト通知】セントラルガーデン月島 ザ タワー

これはテスト通知です。
監視システムが正常に動作していることを確認してください。

対象URL: https://www.31sumai.com/attend/X1413/

監視システムより"""

    print("\nブロードキャスト通知を送信中...")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "messages": [{"type": "text", "text": test_message}]
    }

    try:
        response = requests.post(
            "https://api.line.me/v2/bot/message/broadcast",
            headers=headers,
            json=body,
            timeout=15
        )

        if response.status_code == 200:
            print("送信成功！LINEを確認してください。")
            return True
        else:
            print(f"送信失敗: {response.status_code}")
            print(f"エラー: {response.text}")
            return False

    except Exception as e:
        print(f"送信エラー: {e}")
        return False


def main():
    """メイン処理"""
    print("セントラルガーデン月島 予約監視システム")
    print("LINE通知テスト")
    print("=" * 50)

    if test_line_notification():
        print("\nテスト完了: システムは正常に動作しています")
    else:
        print("\nテスト失敗: 設定を確認してください")
        print("\n確認項目:")
        print("1. .env ファイルに LINE_CHANNEL_ACCESS_TOKEN が設定されているか")
        print("2. LINE公式アカウントが友だち追加されているか")


if __name__ == "__main__":
    main()
