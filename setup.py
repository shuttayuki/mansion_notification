#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
セットアップスクリプト
必要なパッケージのインストールとPlaywrightのセットアップ
"""

import subprocess
import sys
import os

def run_command(command, description):
    """コマンドを実行"""
    print(f"実行中: {description}")
    print(f"コマンド: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ 成功: {description}")
        if result.stdout:
            print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 失敗: {description}")
        print(f"エラー: {e}")
        if e.stderr:
            print(f"stderr: {e.stderr.strip()}")
        return False

def main():
    """メイン処理"""
    print("=" * 60)
    print("セントラルガーデン月島 予約監視システム セットアップ")
    print("=" * 60)
    
    # Python バージョンチェック
    if sys.version_info < (3, 8):
        print("❌ Python 3.8以上が必要です")
        sys.exit(1)
    
    print(f"✅ Python バージョン: {sys.version}")
    
    # 仮想環境作成
    if not os.path.exists("venv"):
        print("\n仮想環境を作成中...")
        if not run_command("python -m venv venv", "仮想環境作成"):
            sys.exit(1)
    else:
        print("✅ 仮想環境は既に存在します")
    
    # 仮想環境のアクティベート
    if os.name == "nt":  # Windows
        activate_script = "venv\\Scripts\\activate"
        python_path = "venv\\Scripts\\python.exe"
        pip_path = "venv\\Scripts\\pip.exe"
    else:  # macOS/Linux
        activate_script = "venv/bin/activate"
        python_path = "venv/bin/python"
        pip_path = "venv/bin/pip"
    
    # パッケージインストール
    print("\n必要なパッケージをインストール中...")
    
    # requirements.txtからインストール
    if not run_command(f"{pip_path} install -r requirements.txt", "パッケージインストール"):
        sys.exit(1)
    
    # Playwrightのセットアップ
    print("\nPlaywrightをセットアップ中...")
    if not run_command(f"{python_path} -m playwright install chromium", "Playwright Chromiumインストール"):
        sys.exit(1)
    
    # 設定ファイルの確認
    print("\n設定ファイルの確認...")
    
    if not os.path.exists(".env"):
        print("⚠️  .envファイルが存在しません")
        print("以下の内容で.envファイルを作成してください:")
        print("-" * 40)
        print("LINE_CHANNEL_ACCESS_TOKEN=your_token_here")
        print("TARGET_URL=https://www.31sumai.com/attend/X1413/")
        print("CHECK_INTERVAL=2")
        print("-" * 40)
    else:
        print("✅ .envファイルが存在します")
    
    if not os.path.exists("subscribers.txt"):
        print("⚠️  subscribers.txtファイルが存在しません")
        print("送信先のLINE IDを1行1つで記述してください")
    else:
        print("✅ subscribers.txtファイルが存在します")
    
    print("\n" + "=" * 60)
    print("セットアップ完了！")
    print("=" * 60)
    print("\n次のステップ:")
    print("1. .envファイルにLINE_CHANNEL_ACCESS_TOKENを設定")
    print("2. subscribers.txtに送信先IDを設定")
    print("3. テスト実行: python watch_calendar.py")
    print("4. 定期実行開始: python scheduler.py")
    print("\n詳細はREADME.mdを参照してください")

if __name__ == "__main__":
    main() 