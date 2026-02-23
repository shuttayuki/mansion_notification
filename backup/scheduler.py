#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定期実行スケジューラー
指定された間隔で監視スクリプトを実行
"""

import time
import schedule
import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta
from config import CHECK_INTERVAL

def jst_now():
    """現在時刻をJSTで取得"""
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")

def run_monitor():
    """監視スクリプトを実行"""
    timestamp = jst_now()
    print(f"[{timestamp}] 監視実行開始")
    
    try:
        # 監視スクリプトを実行
        result = subprocess.run(
            [sys.executable, "watch_calendar.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5分でタイムアウト
        )
        
        if result.returncode == 0:
            print(f"[{timestamp}] 監視完了: 成功")
            if result.stdout:
                print("出力:", result.stdout.strip())
        else:
            print(f"[{timestamp}] 監視失敗: 終了コード {result.returncode}")
            if result.stderr:
                print("エラー:", result.stderr.strip())
                
    except subprocess.TimeoutExpired:
        print(f"[{timestamp}] 監視タイムアウト: 5分を超過")
    except Exception as e:
        print(f"[{timestamp}] 監視実行エラー: {e}")

def main():
    """メイン処理"""
    print(f"監視スケジューラー開始: {jst_now()}")
    print(f"監視間隔: {CHECK_INTERVAL}分")
    print(f"監視スクリプト: {os.path.abspath('watch_calendar.py')}")
    print("Ctrl+C で停止")
    print("-" * 50)
    
    # 初回実行
    run_monitor()
    
    # 定期実行をスケジュール
    schedule.every(CHECK_INTERVAL).minutes.do(run_monitor)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{jst_now()}] スケジューラー停止")
        sys.exit(0)

if __name__ == "__main__":
    main() 