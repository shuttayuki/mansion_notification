#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パークコート麻布十番東京 予約サイト監視システム
予約受付開始を検知し、その後も枠の変化を継続監視してLINE通知を送信

【監視方式】
Phase 1: 受付開始前 → requestsで軽量チェック（"予約を受け付けておりません" の有無）
Phase 2: 受付開始直後 → 速報通知 + Playwrightでカレンダー詳細取得
Phase 3: 継続監視 → Playwrightでカレンダーを定期チェックし、枠の変化を通知
"""

import os
import hashlib
import time
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests
import glob as glob_module

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
STATE_FILE = os.path.join(DATA_DIR, "state_azabu.txt")  # "not_available" or "available"
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
    for filepath in [SNAP_FILE, RAW_FILE, STATE_FILE]:
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("")


def load_state():
    """前回の状態を読み込み"""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def save_state(state):
    """状態を保存"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(state)


def cleanup_screenshots():
    """古いスクリーンショットを削除（最新1つ以外）"""
    try:
        files = glob_module.glob(os.path.join(DATA_DIR, "screenshot_azabu_*.png"))
        if len(files) > 1:
            files.sort(key=os.path.getmtime)
            for old in files[:-1]:
                os.remove(old)
    except Exception:
        pass


def diff_summary(old_text, new_text):
    """予約枠の差分を人間にわかりやすく要約"""
    old_lines = old_text.strip().splitlines() if old_text else []
    new_lines = new_text.strip().splitlines() if new_text else []

    # 日付→ステータスの辞書を作成
    def parse_slots(lines):
        slots = {}
        for line in lines:
            line = line.strip()
            if line:
                slots[line.rsplit(" ", 1)[0] if " " in line else line] = line
        return slots

    old_slots = parse_slots(old_lines)
    new_slots = parse_slots(new_lines)

    changes = []

    # 新規追加
    for key in new_slots:
        if key not in old_slots:
            changes.append(f"【新規】{new_slots[key]}")

    # 変更
    for key in new_slots:
        if key in old_slots and old_slots[key] != new_slots[key]:
            changes.append(f"【変更】{old_slots[key]} → {new_slots[key]}")

    # 削除
    for key in old_slots:
        if key not in new_slots:
            changes.append(f"【削除】{old_slots[key]}")

    return "\n".join(changes[:20]) if changes else ""


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


def test_notification():
    """LINE通知の疎通確認用テストメッセージを送信"""
    log_message("テスト通知モードで実行")
    message = f"""【テスト通知】パークコート麻布十番東京 監視システム

この通知は疎通確認用のテストメッセージです。
LINE通知が正常に動作しています。

対象URL: {URL}
送信時刻: {jst_now()}"""

    success = line_broadcast(message)
    if success:
        log_message("テスト通知の送信に成功しました")
    else:
        log_message("テスト通知の送信に失敗しました")


def test_simulate():
    """予約受付開始を模擬し、本番と同じ通知フローをテスト"""
    log_message("シミュレーションモードで実行（予約開始を模擬）")

    # 速報通知（本番と同じメッセージ）
    urgent_message = f"""【⚠️テスト】【速報】パークコート麻布十番東京
予約受付が開始されました！

今すぐアクセスしてください！
{URL}

第1期1次モデルルームご案内会
検知時刻: {jst_now()}

※これはシミュレーションです（実際の受付開始ではありません）
※アクセス集中の可能性があります
※1世帯1枠まで"""

    success = line_broadcast(urgent_message)
    if not success:
        log_message("速報通知の送信に失敗しました")
        return

    # カレンダー詳細通知（ダミーデータ）
    dummy_calendar = [
        "3月 8日 ○",
        "3月 9日 △",
        "3月 15日 ×",
        "3月 16日 ○",
        "3月 22日 ×",
    ]

    message_parts = [
        "【⚠️テスト】【予約枠情報】パークコート麻布十番東京",
        "",
        "▼ 現在の空き状況:",
        "○：余裕あり △：まもなく満席 ×：満席",
        "",
        "【空きあり】",
        "3月 8日 ○",
        "3月 9日 △",
        "3月 16日 ○",
        "",
        "【満席】",
        "3月 15日 ×",
        "3月 22日 ×",
        "",
        f"URL: {URL}",
        f"確認時刻: {jst_now()}",
        "",
        "※これはシミュレーションです（ダミーデータ）",
    ]

    success = line_broadcast("\n".join(message_parts))
    if success:
        log_message("シミュレーション通知の送信に成功しました")
    else:
        log_message("カレンダー通知の送信に失敗しました")


def main():
    """メイン処理"""
    # テストモード
    test_mode = os.getenv("TEST_MODE", "").lower()
    if test_mode in ("true", "1", "yes"):
        test_notification()
        return
    if test_mode == "simulate":
        test_simulate()
        return

    log_message("=" * 50)
    log_message("パークコート麻布十番東京 予約監視開始")
    log_message(f"対象URL: {URL}")
    log_message("=" * 50)

    ensure_files()

    # 前回データ読み込み
    prev_state = load_state()  # "not_available", "available", or ""
    prev_hash = ""
    prev_raw = ""
    try:
        with open(SNAP_FILE, "r", encoding="utf-8") as f:
            prev_hash = f.read().strip()
        with open(RAW_FILE, "r", encoding="utf-8") as f:
            prev_raw = f.read()
    except Exception:
        pass

    log_message(f"前回の状態: {prev_state or '初回実行'}")

    # ── Phase 1: 軽量チェック（受付開始前か後か判定）──
    status, page_body = check_page_with_requests()

    if status == "error":
        log_message("ページ取得に失敗しました。次回の実行で再試行します。")
        return

    # ── まだ受付開始前 ──
    if status == "not_available":
        log_message("まだ予約受付は開始されていません。")

        current_hash = digest(page_body)
        if prev_hash and current_hash != prev_hash:
            log_message("ページに何らかの変化を検知（受付はまだ未開始）")

        with open(SNAP_FILE, "w", encoding="utf-8") as f:
            f.write(current_hash)
        with open(RAW_FILE, "w", encoding="utf-8") as f:
            f.write("not_available")
        save_state("not_available")

        log_message("監視完了（受付待ち）")
        return

    # ── 受付が開始されている！ ──
    is_first_detection = (prev_state != "available")

    # ── Phase 2: 初回検知 → 速報通知 ──
    if is_first_detection:
        log_message("★★★ 予約受付が開始されました！ ★★★")

        urgent_message = f"""【速報】パークコート麻布十番東京
予約受付が開始されました！

今すぐアクセスしてください！
{URL}

第1期1次モデルルームご案内会
検知時刻: {jst_now()}

※アクセス集中の可能性があります
※1世帯1枠まで"""

        line_broadcast(urgent_message)
    else:
        log_message("受付中（継続監視）")

    # ── Phase 3: Playwrightでカレンダー詳細を取得 ──
    calendar_text = check_calendar_with_playwright()

    if not calendar_text:
        log_message("カレンダー詳細を取得できませんでした")
        if is_first_detection:
            log_message("速報は送信済みです")
        save_state("available")
        with open(RAW_FILE, "w", encoding="utf-8") as f:
            f.write(prev_raw)  # 前回データを維持
        return

    # カレンダーの変化を検知
    current_hash = digest(calendar_text)
    changed = (current_hash != prev_hash)

    log_message(f"カレンダー変化: {'あり' if changed else 'なし'}")

    if is_first_detection or changed:
        # 差分を計算
        diff = ""
        if not is_first_detection and prev_raw and prev_raw != "not_available":
            diff = diff_summary(prev_raw, calendar_text)

        # 空き枠の有無を確認
        available_lines = [
            line for line in calendar_text.splitlines()
            if any(s in line for s in ["○", "△"]) and any(d in line for d in ["月", "日"])
        ]
        full_lines = [
            line for line in calendar_text.splitlines()
            if "×" in line and any(d in line for d in ["月", "日"])
        ]

        # 通知メッセージ作成
        if is_first_detection:
            header = "【予約枠情報】パークコート麻布十番東京"
        else:
            header = "【予約枠更新】パークコート麻布十番東京"

        message_parts = [header, ""]

        if diff:
            message_parts.append("▼ 変更点:")
            message_parts.append(diff)
            message_parts.append("")

        message_parts.append("▼ 現在の空き状況:")
        message_parts.append("○：余裕あり △：まもなく満席 ×：満席")
        message_parts.append("")

        if available_lines:
            message_parts.append("【空きあり】")
            message_parts.extend(available_lines[:15])
        else:
            message_parts.append("現在、空き枠はありません")

        if full_lines:
            message_parts.append("")
            message_parts.append("【満席】")
            message_parts.extend(full_lines[:10])

        message_parts.extend([
            "",
            f"URL: {URL}",
            f"確認時刻: {jst_now()}"
        ])

        line_broadcast("\n".join(message_parts))
    else:
        log_message("カレンダーに変化なし。通知はスキップします。")

    # スナップショット保存
    with open(SNAP_FILE, "w", encoding="utf-8") as f:
        f.write(current_hash)
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        f.write(calendar_text)
    save_state("available")
    cleanup_screenshots()

    log_message("監視完了")


if __name__ == "__main__":
    main()
