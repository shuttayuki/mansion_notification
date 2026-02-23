#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定ファイル
環境変数が設定されていない場合のデフォルト値を定義
"""

import os
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# LINE設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

# 監視対象URL
TARGET_URL = os.getenv("TARGET_URL", "https://www.31sumai.com/attend/X1413/")

# 監視間隔（分）
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "1"))

# データ保存ディレクトリ
DATA_DIR = "./data"

# 監視対象のキーワード（現在は○のみ使用）
POSITIVE_KEYS = ["○", "余裕", "受付中", "空き"]
NEGATIVE_KEYS = ["×", "満席", "受付終了"]

# カレンダー抽出セレクタ（優先順位順）
CALENDAR_SELECTORS = [
    "section:has-text('予約') table",
    "table[aria-label*=予約]",
    "div[class*=calendar] table",
    "main table",
    "table"
]

# ブラウザ設定
BROWSER_ARGS = [
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-web-security",
    "--disable-features=VizDisplayCompositor"
]

# タイムアウト設定（秒）
PAGE_LOAD_TIMEOUT = 30
NETWORK_IDLE_TIMEOUT = 15
ELEMENT_TIMEOUT = 3
JS_WAIT_TIME = 5 