#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
セントラルガーデン月島 ザ タワー 予約サイト監視システム
予約カレンダーの更新を検知してLINE公式アカウントから通知を送信
"""

import os
import hashlib
import time
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import requests
import glob

# 環境変数読み込み
load_dotenv()

# 設定
TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
URL = os.getenv("TARGET_URL", "https://www.31sumai.com/attend/X1413/")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "2"))

# データ保存ディレクトリ
DATA_DIR = "./data"
SNAP_FILE = os.path.join(DATA_DIR, "snapshot_hash.txt")
RAW_FILE = os.path.join(DATA_DIR, "last_raw.txt")
LOG_FILE = os.path.join(DATA_DIR, "monitor.log")

# 監視対象のキーワード
POSITIVE_KEYS = ["○", "余裕", "受付中", "空き"]
NEGATIVE_KEYS = ["×", "満席", "受付終了"]

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
    
    # スナップショットファイル
    if not os.path.exists(SNAP_FILE):
        with open(SNAP_FILE, "w", encoding="utf-8") as f:
            f.write("")
    
    # 生データファイル
    if not os.path.exists(RAW_FILE):
        with open(RAW_FILE, "w", encoding="utf-8") as f:
            f.write("")

def digest(text):
    """テキストのハッシュ値を計算"""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def line_broadcast(text):
    """LINE公式アカウントからプッシュ通知を送信"""
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
        log_message("LINE通知送信成功: 全員")
        return True
    except requests.exceptions.RequestException as e:
        log_message(f"LINE通知送信失敗: 全員 - {e}")
        return False

def cleanup_screenshots():
    """古いスクリーンショットを削除（最新の1つ以外）"""
    try:
        screenshot_files = glob.glob(os.path.join(DATA_DIR, "last_screenshot_*.png"))
        if len(screenshot_files) > 1:
            # 最新のファイル以外を削除
            screenshot_files.sort(key=os.path.getmtime)
            for old_file in screenshot_files[:-1]:
                os.remove(old_file)
                log_message(f"古いスクリーンショット削除: {os.path.basename(old_file)}")
    except Exception as e:
        log_message(f"スクリーンショット削除エラー: {e}")

def filter_calendar_content(text):
    """カレンダーテキストから凡例を除外"""
    lines = text.splitlines()
    filtered_lines = []
    
    for line in lines:
        # 完全に一致する説明行のみを除外（凡例は含める）
        if line.strip() in [
            "ご予約日程のご入力",
            "お客様情報のご入力", 
            "入力内容のご確認",
            "受付完了"
        ]:
            continue
        
        # 空行は除外
        if not line.strip():
            continue
            
        # それ以外の行は全て抽出（カレンダー内容として扱う）
        filtered_lines.append(line)
    
    result = "\n".join(filtered_lines)
    log_message(f"フィルタリング結果: {len(filtered_lines)}行抽出")
    if filtered_lines:
        log_message(f"抽出内容: {filtered_lines[:3]}...")  # 最初の3行をログに出力
    return result

def pick_calendar_text(page):
    """予約カレンダーのテキストを抽出（CSSクラスベース・2ヶ月対応）"""
    
    all_calendar_data = []
    
    # 方法1: CSSクラスベースで予約状況を抽出（2ヶ月対応）
    try:
        # 現在の月を取得
        current_month_element = page.locator(".ui-datepicker-month").first
        if current_month_element.is_visible():
            current_month = current_month_element.inner_text(timeout=2000)
            log_message(f"監視対象月: {current_month}")
        else:
            current_month = "不明"
            log_message("月の表示が見つかりません")
        
        # カレンダーの日付セルを探す
        calendar_cells = page.locator(".ui-datepicker-calendar td, .calendar td, table td").all()
        
        if calendar_cells:
            log_message(f"カレンダーセル発見: {len(calendar_cells)}個")
            
            month_data = []
            for i, cell in enumerate(calendar_cells[:50]):  # 最大50個まで
                try:
                    # セルのテキスト（日付）
                    cell_text = cell.inner_text(timeout=1000).strip()
                    
                    # CSSクラスで予約状況を判定
                    classes = cell.get_attribute("class") or ""
                    
                    status = ""
                    if "status_1" in classes:
                        status = "×"  # 満席
                    elif "status_2" in classes:
                        status = "△"  # まもなく満席
                    elif "status_3" in classes:
                        status = "○"  # 余裕あり
                    elif "status_4" in classes or "disabled" in classes:
                        status = "-"  # 受付不可
                    
                    if cell_text and cell_text.isdigit():  # 日付の場合
                        month_data.append(f"{current_month} {cell_text}日 {status}")
                        log_message(f"セル {i}: {current_month} {cell_text}日 {status} (クラス: {classes})")
                        
                except Exception as e:
                    continue
            
            if month_data:
                all_calendar_data.extend(month_data)
                log_message(f"{current_month}の抽出成功: {len(month_data)}日分")
                
    except Exception as e:
        log_message(f"CSSクラスベース抽出失敗: {e}")
    
    # 2ヶ月のデータを統合
    if all_calendar_data:
        result = "\n".join(all_calendar_data)
        log_message(f"2ヶ月統合抽出成功: {len(all_calendar_data)}日分")
        return result
    
    # 方法2: 従来のテーブル抽出（フォールバック）
    selectors = [
        "table",  # まずは全てのテーブルを試す
        "table tbody",  # テーブルの本文部分
        "div table",  # div内のテーブル
        "main table",  # main内のテーブル
        "section table"  # section内のテーブル
    ]
    
    for selector in selectors:
        try:
            element = page.locator(selector).first
            text = element.inner_text(timeout=1500).strip()
            log_message(f"セレクタ {selector} で抽出: {len(text)}文字")
            if any(key in text for key in ["○", "△", "×", "余裕", "満席", "受付"]):
                log_message(f"カレンダー抽出成功: {selector}")
                log_message(f"抽出内容（最初の200文字）: {text[:200]}...")
                # 凡例行を除外して実際のカレンダー部分のみを返す
                return filter_calendar_content(text)
        except PWTimeout:
            log_message(f"セレクタ {selector} でタイムアウト")
            continue
    
    # フォールバック: ページ全体から関連テキストを抽出
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
        log_message(f"ページ全体テキスト: {len(body_text)}文字")
        
        # より包括的な条件で抽出
        lines = []
        for line in body_text.splitlines():
            line = line.strip()
            if line:
                # ○△×、日付、予約関連のキーワードを含む行を抽出
                if any(key in line for key in ["○", "△", "×", "余裕", "満席", "受付", "202", "月", "日", "曜日", "予約", "カレンダー"]):
                    lines.append(line)
        
        if lines:
            log_message(f"フォールバック抽出成功: {len(lines)}行")
            raw_text = "\n".join(lines)
            log_message(f"フィルタリング前のテキスト: {raw_text[:300]}...")  # 最初の300文字をログに出力
            return filter_calendar_content(raw_text)
        else:
            log_message("フォールバック抽出: 条件に合う行が見つかりませんでした")
    except Exception as e:
        log_message(f"フォールバック抽出失敗: {e}")
    
    return ""

def diff_summary(old_text, new_text):
    """テキストの差分を要約"""
    old_lines = set(old_text.splitlines())
    new_lines = set(new_text.splitlines())
    
    added = [f"+ {line}" for line in (new_lines - old_lines)]
    removed = [f"- {line}" for line in (old_lines - new_lines)]
    
    # 各10行までに制限
    summary = []
    if added:
        summary.extend(added[:10])
    if removed:
        summary.extend(removed[:10])
    
    if not summary:
        return "(差分の要約が空でした)"
    
    return "\n".join(summary)

def run_once():
    """1回分の監視チェックを実行。戻り値: 次回も継続するかどうか (True/False)"""
    ensure_files()

    # 前回のスナップショット読み込み
    prev_hash = ""
    prev_raw = ""
    try:
        with open(SNAP_FILE, "r", encoding="utf-8") as f:
            prev_hash = f.read().strip()
        with open(RAW_FILE, "r", encoding="utf-8") as f:
            prev_raw = f.read()
    except Exception as e:
        log_message(f"前回データ読み込みエラー: {e}")

    # Playwrightでページ監視
    for attempt in range(1, 4):
        try:
            with sync_playwright() as p:
                # ブラウザ起動（最小限の安定設定）
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                        "--disable-software-rasterizer",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                        "--disable-ipc-flooding-protection",
                        "--disable-hang-monitor",
                        "--disable-breakpad",
                        "--disable-component-extensions-with-background-pages",
                        "--disable-component-update",
                        "--disable-default-apps",
                        "--disable-extensions",
                        "--disable-popup-blocking",
                        "--disable-prompt-on-repost",
                        "--disable-search-engine-choice-screen",
                        "--disable-service-autorun",
                        "--no-default-browser-check",
                        "--no-first-run",
                        "--no-startup-window",
                        "--metrics-recording-only",
                        "--password-store=basic",
                        "--use-mock-keychain",
                        "--force-color-profile=srgb",
                        "--enable-use-zoom-for-dsf=false",
                        "--use-angle",
                        "--hide-scrollbars",
                        "--mute-audio",
                        "--disable-background-networking",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-back-forward-cache",
                        "--disable-client-side-phishing-detection",
                        "--disable-features=ImprovedCookieControls,LazyFrameLoading,GlobalMediaControls,DestroyProfileOnBrowserClose,MediaRouter,DialMediaRouteProvider,AcceptCHFrame,AutoExpandDetailsElement,CertificateTransparencyComponentUpdater,AvoidUnnecessaryBeforeUnloadCheckSync,Translate,HttpsUpgrades",
                        "--allow-pre-commit-input",
                        "--disable-popup-blocking",
                        "--disable-prompt-on-repost",
                        "--disable-search-engine-choice-screen",
                        "--disable-service-autorun",
                        "--export-tagged-pdf",
                        "--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4"
                    ]
                )

                context = browser.new_context(
                    viewport={"width": 1366, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )

                page = context.new_page()

                # ページ読み込み
                log_message(f"ページアクセス: {URL}")
                page.goto(URL, wait_until="domcontentloaded", timeout=30000)

                # JavaScript描画完了待ち
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PWTimeout:
                    log_message("ネットワークアイドル待ちタイムアウト、明示待ちに切り替え")

                # 追加の遅延（画像・JS遅延対策）
                page.wait_for_timeout(5000)

                # 月次切り替え処理を無効化（安定性最優先）
                try:
                    # 現在の月を確認のみ
                    current_month = page.locator(".ui-datepicker-month").first.inner_text(timeout=3000)
                    log_message(f"監視対象月: {current_month}")
                    log_message("月切り替え処理は無効化されています（現在の月のみ監視）")

                except Exception as e:
                    log_message(f"月の確認でエラー: {e}")
                    log_message("月の確認に失敗しましたが、監視は継続します")

                # スクリーンショット保存（デバッグ用）
                screenshot_path = os.path.join(DATA_DIR, f"last_screenshot_{int(time.time())}.png")
                page.screenshot(path=screenshot_path, full_page=True)
                log_message(f"スクリーンショット保存: {screenshot_path}")
                # 古いスクリーンショットを削除
                cleanup_screenshots()

                # カレンダーテキスト抽出
                calendar_text = pick_calendar_text(page)
                if not calendar_text:
                    raise RuntimeError("カレンダー領域の抽出に失敗しました")

                # 変化検知
                current_hash = digest(calendar_text)
                changed = (current_hash != prev_hash)

                # トリガー条件チェック
                positive = any(key in calendar_text for key in POSITIVE_KEYS)
                negative = any(key in calendar_text for key in NEGATIVE_KEYS)

                # 通知送信（実際の予約枠に○または△がある場合）
                has_actual_availability = any(
                    any(status in line for status in ["○", "△"]) and any(date_indicator in line for date_indicator in ["202", "月", "日"])
                    for line in calendar_text.splitlines()
                )

                log_message(f"予約枠の状況確認: {has_actual_availability}, 変化: {changed}")

                # 実際の予約枠に○がある場合のみ通知（変化があった場合のみ）
                if has_actual_availability and changed:
                    # 差分要約
                    summary = diff_summary(prev_raw, calendar_text)

                    # 通知メッセージ作成
                    message = f"""【予約枠状況更新】{jst_now()}

予約枠に新しく空きまたは空きの可能性があります！
○：余裕あり、△：まもなく満席

URL: {URL}

変更内容:
{summary}

現在の状況:
{calendar_text}

監視システムより自動通知"""

                    # 全送信先に通知
                    success_count = 0
                    if line_broadcast(message):
                        success_count = 1

                    log_message(f"通知完了: {success_count} 件成功")

                # スナップショット保存
                with open(SNAP_FILE, "w", encoding="utf-8") as f:
                    f.write(current_hash)
                with open(RAW_FILE, "w", encoding="utf-8") as f:
                    f.write(calendar_text)

                # クリーンアップ
                context.close()
                browser.close()

                log_message("チェック完了")
                return True  # ループ継続

        except Exception as e:
            log_message(f"試行 {attempt}/3 失敗: {e}")
            if attempt < 3:
                wait_time = 5 * (2 ** (attempt - 1))
                log_message(f"{wait_time}秒待機してから再試行...")
                time.sleep(wait_time)
            else:
                log_message("最大試行回数に達しました")
                error_message = f"【監視エラー】{jst_now()}\n\nエラー: {e}\n\n監視システムが正常に動作していません。\n\n次回のチェックで再試行されます。"
                line_broadcast(error_message)

    return True  # エラーでもループ継続


# ループ設定
LOOP_DURATION_MIN = 350  # ループ継続時間（分）≒約5時間50分
LOOP_INTERVAL_SEC = CHECK_INTERVAL * 60  # チェック間隔（秒）


def test_notification():
    """LINE通知の疎通確認用テストメッセージを送信"""
    log_message("テスト通知モードで実行")
    message = f"""【テスト通知】セントラルガーデン月島 ザ タワー 監視システム

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
    """予約枠変化を模擬し、本番と同じ通知フローをテスト"""
    log_message("シミュレーションモードで実行（予約枠変化を模擬）")

    dummy_calendar = [
        "9月 1日 ○",
        "9月 2日 △",
        "9月 3日 ×",
        "9月 4日 ○",
        "9月 5日 ×",
    ]

    summary = "+ 9月 1日 ○\n+ 9月 2日 △\n+ 9月 4日 ○"

    message = f"""【テスト】【予約枠状況更新】{jst_now()}

予約枠に新しく空きまたは空きの可能性があります！
○：余裕あり、△：まもなく満席

URL: {URL}

変更内容:
{summary}

現在の状況:
{chr(10).join(dummy_calendar)}

※これはシミュレーションです（ダミーデータ）
監視システムより自動通知"""

    success = line_broadcast(message)
    if success:
        log_message("シミュレーション通知の送信に成功しました")
    else:
        log_message("シミュレーション通知の送信に失敗しました")


def main():
    """メイン処理: 55分間ループしながら定期チェック"""
    # テストモード
    test_mode = os.getenv("TEST_MODE", "").lower()
    if test_mode in ("true", "1", "yes"):
        test_notification()
        return
    if test_mode == "simulate":
        test_simulate()
        return

    log_message("=" * 50)
    log_message("セントラルガーデン月島 予約監視開始")
    log_message(f"対象URL: {URL}")
    log_message(f"ループ: {LOOP_DURATION_MIN}分間、{CHECK_INTERVAL}分間隔")
    log_message("=" * 50)

    start_time = time.time()
    end_time = start_time + LOOP_DURATION_MIN * 60
    check_count = 0

    while time.time() < end_time:
        check_count += 1
        log_message(f"--- チェック #{check_count} ---")

        try:
            should_continue = run_once()
            if not should_continue:
                log_message("監視を終了します")
                break
        except Exception as e:
            log_message(f"チェック中にエラー: {e}")

        # 残り時間があればスリープ
        remaining = end_time - time.time()
        if remaining > LOOP_INTERVAL_SEC:
            log_message(f"次のチェックまで{CHECK_INTERVAL}分待機...")
            time.sleep(LOOP_INTERVAL_SEC)
        elif remaining > 0:
            log_message(f"残り{int(remaining)}秒、最終チェックへ")
            time.sleep(remaining)
        else:
            break

    log_message(f"監視ループ終了（{check_count}回チェック実施）")
                    

if __name__ == "__main__":
    main() 