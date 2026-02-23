#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE通知テストスクリプト
設定が正しく動作するかテスト
"""

import os
from dotenv import load_dotenv
import requests

# 環境変数読み込み
load_dotenv()

def test_line_notification():
    """LINE通知のテスト"""
    print("LINE通知テスト開始")
    print("=" * 50)
    
    # 設定確認
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        print("❌ LINE_CHANNEL_ACCESS_TOKEN が設定されていません")
        print("   .env ファイルに設定してください")
        return False
    
    print(f"✅ トークン: {token[:20]}...")
    
    # 送信先確認
    if not os.path.exists("subscribers.txt"):
        print("❌ subscribers.txt が存在しません")
        return False
    
    with open("subscribers.txt", "r", encoding="utf-8") as f:
        subscribers = [line.strip() for line in f 
                     if line.strip() and not line.startswith("#")]
    
    if not subscribers:
        print("❌ subscribers.txt に送信先IDが設定されていません")
        return False
    
    print(f"✅ 送信先数: {len(subscribers)}")
    for sub in subscribers:
        print(f"   - {sub}")
    
    # テスト通知送信
    print("\nテスト通知を送信中...")
    
    test_message = """【テスト通知】予約監視システム

これはテスト通知です。
システムが正常に動作していることを確認してください。

時刻: テスト実行時
URL: https://www.31sumai.com/attend/X1413/

監視システムより"""

    success_count = 0
    for subscriber in subscribers:
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            body = {
                "to": subscriber,
                "messages": [{"type": "text", "text": test_message}]
            }
            
            response = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers=headers,
                json=body,
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"✅ 送信成功: {subscriber}")
                success_count += 1
            else:
                print(f"❌ 送信失敗: {subscriber} - {response.status_code}")
                print(f"   エラー: {response.text}")
                
        except Exception as e:
            print(f"❌ 送信エラー: {subscriber} - {e}")
    
    print(f"\nテスト結果: {success_count}/{len(subscribers)} 件成功")
    
    if success_count == len(subscribers):
        print("🎉 すべての送信先に通知が送信されました！")
        return True
    else:
        print("⚠️  一部の送信先に通知が送信できませんでした")
        return False

def main():
    """メイン処理"""
    print("セントラルガーデン月島 予約監視システム")
    print("LINE通知テスト")
    print("=" * 50)
    
    if test_line_notification():
        print("\n✅ テスト完了: システムは正常に動作しています")
        print("\n次のステップ:")
        print("1. 監視開始: python watch_calendar.py")
        print("2. 定期実行: python scheduler.py")
    else:
        print("\n❌ テスト失敗: 設定を確認してください")
        print("\n確認項目:")
        print("1. .env ファイルに LINE_CHANNEL_ACCESS_TOKEN が設定されているか")
        print("2. subscribers.txt に正しい送信先IDが設定されているか")
        print("3. LINE公式アカウントが友だち追加されているか")

if __name__ == "__main__":
    main() 