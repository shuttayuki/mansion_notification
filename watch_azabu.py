#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パークコート麻布十番東京 予約サイト監視システム
予約受付開始を検知してLINE公式アカウントから通知を送信

【監視方式】
Phase 1: 受付開始前 → requestsで軽量チェック（"予約を受け付けておりません" の有無）
Phase 2: 受付開始後 → Playwrightでカレンダー詳細を取得して通知
"""

import os
import hashlib
import time
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests

# 環境変数読み込み
load_dotenv()

# 設定
TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
URL = os.getenv("TARGET_URL_AZABU", "https://www.31sumai.com/attend/X2571/")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "2"))

# データ保存ディレクトリ
DATA_DIR = "./data"
SNAP_FILE = os.path.join(DATA_DIR, "snapshot_hash_azabu.txt")
RAW_FILE = os.path.join(DATA_DIR, "last_raw_azabu.txt")
LOG_FILE = os.path.join(DATA_DIR, "monitor_azabu.log")

# 受付停止中のキーワード
NOT_AVAILABLE_KEYWORD = "予約を受け付けておりません"

# カレンダー監視用キーワード
POSITIVE_KEYS = ["○", "余裕", "受付中", "空き"]
NEGATIVE_KEYS = ["×", "満席", "受付終了"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def jst_now():
    """現在時刻をJSTで取得"""
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")


def log_message(message):
    """ログメッセージを記録"""
    timestamp = jst_now()
    log_entry = f"[{timestamp}] {message}\n"
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(log_entry.strip())


def ensure_files():
    """必要なファイルとディレクトリを作成"""
    os.makedirs(DATA_DIR, exist_ok=True)
    for filepath in [SNAP_FILE, RAW_FILE]:
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("")


def digest(text):
    """テキストのハッシュ値を計算"""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def line_broadcast(text):
    """LINE公式アカウントからブロードキャスト通知を送信"""
    if not TOKEN:
        log_message("エラー: LINE_CHANNEL_ACCESS_TOKEN が設定されていません")
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
        log_message("LINE通知送信成功")
        return True
    except requests.exceptions.RequestException as e:
        log_message(f"LINE通知送信失敗: {e}")
        return False


def check_page_with_requests():
    """
    requestsで軽量チェック（Phase 1）
    戻り値: ("not_available" | "available" | "error", ページテキスト)
    """
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        body = resp.text

        if NOT_AVAILABLE_KEYWORD in body:
            return "not_available", body
        else:
            return "available", body

    except requests.RequestException as e:
        log_message(f"ページ取得エラー: {e}")
        return "error", ""


def check_calendar_with_playwright():
    """
    Playwrightでカレンダー詳細を取得（Phase 2）
    予約が開始された後、カレンダーの空き状況を取得する
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        log_message("Playwright未インストール。requestsの結果のみで通知します。")
        return ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                ]
            )
            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                user_agent=HEADERS["User-Agent"]
            )
            page = context.new_page()

            log_message(f"Playwrightでアクセス: {URL}")
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                log_message("networkidle待ちタイムアウト、続行")

            page.wait_for_timeout(5000)

            # スクリーンショット保存
            screenshot_path = os.path.join(DATA_DIR, f"screenshot_azabu_{int(time.time())}.png")
            page.screenshot(path=screenshot_path, full_page=True)
            log_message(f"スクリーンショット保存: {screenshot_path}")

            # カレンダーのテキスト抽出
            calendar_text = extract_calendar(page)

            context.close()
            browser.close()

            return calendar_text

    except Exception as e:
        log_message(f"Playwright処理エラー: {e}")
        return ""


def extract_calendar(page):
    """ページからカレンダー情報を抽出"""
    all_data = []

    # CSSクラスベースの抽出を試行
    try:
        calendar_cells = page.locator(".ui-datepicker-calendar td, .calendar td, table td").all()
        if calendar_cells:
            log_message(f"カレンダーセル発見: {len(calendar_cells)}個")

            current_month = "不明"
            try:
                month_el = page.locator(".ui-datepicker-month").first
                if month_el.is_visible():
                    current_month = month_el.inner_text(timeout=2000)
            except Exception:
                pass

            for cell in calendar_cells[:50]:
                try:
                    cell_text = cell.inner_text(timeout=1000).strip()
                    classes = cell.get_attribute("class") or ""

                    status = ""
                    if "status_1" in classes:
                        status = "×"
                    elif "status_2" in classes:
                        status = "△"
                    elif "status_3" in classes:
                        status = "○"
                    elif "status_4" in classes or "disabled" in classes:
                        status = "-"

                    if cell_text and cell_text.isdigit():
                        all_data.append(f"{current_month} {cell_text}日 {status}")
                except Exception:
                    continue

            if all_data:
                return "\n".join(all_data)
    except Exception as e:
        log_message(f"カレンダー抽出エラー: {e}")

    # フォールバック: ページ全体から関連テキストを抽出
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
        lines = []
        for line in body_text.splitlines():
            line = line.strip()
            if line and any(k in line for k in ["○", "△", "×", "余裕", "満席", "受付", "月", "日", "予約"]):
                lines.append(line)
        if lines:
            return "\n".join(lines)
    except Exception as e:
        log_message(f"フォールバック抽出エラー: {e}")

    return ""


def main():
    """メイン処理"""
    log_message("=" * 50)
    log_message("パークコート麻布十番東京 予約監視開始")
    log_message(f"対象URL: {URL}")
    log_message("=" * 50)

    ensure_files()

    # 前回データ読み込み
    prev_hash = ""
    prev_raw = ""
    try:
        with open(SNAP_FILE, "r", encoding="utf-8") as f:
            prev_hash = f.read().strip()
        with open(RAW_FILE, "r", encoding="utf-8") as f:
            prev_raw = f.read()
    except Exception:
        pass

    # Phase 1: 軽量チェック
    status, page_body = check_page_with_requests()

    if status == "error":
        log_message("ページ取得に失敗しました。次回の実行で再試行します。")
        return

    if status == "not_available":
        log_message("まだ予約受付は開始されていません。")

        # ページ内容のハッシュで微妙な変化も検知
        current_hash = digest(page_body)
        if prev_hash and current_hash != prev_hash:
            log_message("ページに何らかの変化を検知しました（受付はまだ開始されていません）")

        # ハッシュ保存
        with open(SNAP_FILE, "w", encoding="utf-8") as f:
            f.write(current_hash)
        with open(RAW_FILE, "w", encoding="utf-8") as f:
            f.write("not_available")

        log_message("監視完了（受付待ち）")
        return

    # Phase 2: 受付が開始された！
    log_message("★★★ 予約受付が開始されました！ ★★★")

    # まずは即座にLINE通知（速報）
    urgent_message = f"""【速報】パークコート麻布十番東京
予約受付が開始されました！

今すぐアクセスしてください！
{URL}

第1期1次モデルルームご案内会
検知時刻: {jst_now()}

※アクセス集中の可能性があります
※1世帯1枠まで"""

    line_broadcast(urgent_message)

    # Playwrightでカレンダー詳細を取得
    calendar_text = check_calendar_with_playwright()

    if calendar_text:
        # カレンダーの空き状況を通知
        has_availability = any(
            any(s in line for s in ["○", "△"]) and any(d in line for d in ["月", "日"])
            for line in calendar_text.splitlines()
        )

        if has_availability:
            detail_message = f"""【予約枠情報】パークコート麻布十番東京

予約枠の空き状況:
○：余裕あり、△：まもなく満席

{calendar_text}

URL: {URL}
確認時刻: {jst_now()}"""

            line_broadcast(detail_message)
        else:
            log_message("カレンダーは表示されましたが、空き枠（○/△）は見つかりませんでした")
    else:
        log_message("カレンダー詳細は取得できませんでしたが、速報は送信済みです")

    # スナップショット保存
    current_hash = digest(page_body)
    with open(SNAP_FILE, "w", encoding="utf-8") as f:
        f.write(current_hash)
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        f.write(calendar_text if calendar_text else "available_no_calendar")

    log_message("監視完了")


if __name__ == "__main__":
    main()
