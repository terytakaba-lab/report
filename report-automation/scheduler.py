"""
scheduler.py
東南アジア市場レポート スケジューラー

週3〜4本を自動実行: [1]テーマ選定 → [2]レポート生成 → [3]PDF生成 → [4]アップロード
APScheduler を使って毎週月・水・金曜日の朝9時に実行する。
"""

import json
import logging
import os
import random
import sys
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# .env ロード
load_dotenv(Path(__file__).parent / ".env")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from theme_selector import select_themes
from report_generator import run_all_pending as generate_all_reports
from pdf_generator import generate_all_reports as generate_all_pdfs
from uploader import upload_all_pending

# ログ設定
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"scheduler_{datetime.now().strftime('%Y%m')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

RUN_LOG = Path(__file__).parent / "run_log.json"


# ---------------------------------------------------------------------------
# ログ管理
# ---------------------------------------------------------------------------

def load_run_log() -> list[dict]:
    if RUN_LOG.exists():
        with open(RUN_LOG, encoding="utf-8") as f:
            return json.load(f)
    return []


def append_run_log(entry: dict) -> None:
    log = load_run_log()
    log.append(entry)
    with open(RUN_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# パイプライン実行
# ---------------------------------------------------------------------------

def run_pipeline(theme_count: int | None = None) -> dict:
    """
    [1] テーマ選定 → [2] レポート生成 → [3] PDF生成 → [4] アップロード
    を順番に実行し、実行ログを返す。
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    count = theme_count or random.randint(3, 4)
    run_entry = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "theme_count": count,
        "steps": {},
        "status": "running",
    }

    logger.info("=" * 60)
    logger.info("パイプライン開始: run_id=%s, テーマ数=%d", run_id, count)
    logger.info("=" * 60)

    # Step 1: テーマ選定
    try:
        logger.info("[Step 1/4] テーマ選定...")
        themes = select_themes(count)
        run_entry["steps"]["theme_selection"] = {
            "status": "success",
            "themes": [t["title_ja"] for t in themes],
        }
        logger.info("  完了: %d件のテーマを選定", len(themes))
    except Exception as e:
        logger.error("[Step 1/4] テーマ選定失敗: %s", e)
        logger.error(traceback.format_exc())
        run_entry["steps"]["theme_selection"] = {"status": "error", "error": str(e)}
        run_entry["status"] = "failed"
        run_entry["finished_at"] = datetime.now().isoformat()
        append_run_log(run_entry)
        return run_entry

    # Step 2: レポート生成
    try:
        logger.info("[Step 2/4] レポート生成...")
        reports = generate_all_reports()
        run_entry["steps"]["report_generation"] = {
            "status": "success",
            "count": len(reports),
            "slugs": [r.get("slug") for r in reports],
        }
        logger.info("  完了: %d件のレポートを生成", len(reports))
    except Exception as e:
        logger.error("[Step 2/4] レポート生成失敗: %s", e)
        logger.error(traceback.format_exc())
        run_entry["steps"]["report_generation"] = {"status": "error", "error": str(e)}
        run_entry["status"] = "failed"
        run_entry["finished_at"] = datetime.now().isoformat()
        append_run_log(run_entry)
        return run_entry

    # Step 3: PDF生成
    try:
        logger.info("[Step 3/4] PDF生成...")
        pdf_results = generate_all_pdfs()
        pdf_paths = []
        for r in pdf_results:
            for lang, path in r.get("pdfs", {}).items():
                pdf_paths.append(str(path))
        run_entry["steps"]["pdf_generation"] = {
            "status": "success",
            "count": len(pdf_results),
            "pdfs": pdf_paths,
        }
        logger.info("  完了: %d件のPDFを生成", len(pdf_results) * 2)
    except Exception as e:
        logger.error("[Step 3/4] PDF生成失敗: %s", e)
        logger.error(traceback.format_exc())
        run_entry["steps"]["pdf_generation"] = {"status": "error", "error": str(e)}
        run_entry["status"] = "failed"
        run_entry["finished_at"] = datetime.now().isoformat()
        append_run_log(run_entry)
        return run_entry

    # Step 4: アップロード
    try:
        logger.info("[Step 4/4] アップロード...")
        upload_results = upload_all_pending()
        run_entry["steps"]["upload"] = {
            "status": "success",
            "count": len(upload_results),
            "results": upload_results,
        }
        logger.info("  完了: %d件をアップロード", len(upload_results))
    except Exception as e:
        logger.error("[Step 4/4] アップロード失敗: %s", e)
        logger.error(traceback.format_exc())
        run_entry["steps"]["upload"] = {"status": "error", "error": str(e)}
        run_entry["status"] = "partial"  # ここまでは成功

    run_entry["status"] = "success" if run_entry["status"] == "running" else run_entry["status"]
    run_entry["finished_at"] = datetime.now().isoformat()
    append_run_log(run_entry)

    logger.info("=" * 60)
    logger.info("パイプライン完了: run_id=%s, status=%s", run_id, run_entry["status"])
    logger.info("=" * 60)
    return run_entry


# ---------------------------------------------------------------------------
# スケジューラー設定
# ---------------------------------------------------------------------------

def start_scheduler():
    """
    スケジューラーを起動する。
    デフォルトスケジュール: 月・水・金曜日 09:00 JST (UTC+9)
    環境変数 SCHEDULE_DAYS / SCHEDULE_HOUR / SCHEDULE_MINUTE で上書き可能。
    """
    scheduler = BlockingScheduler(timezone="Asia/Tokyo")

    days = os.environ.get("SCHEDULE_DAYS", "mon,wed,fri")
    hour = int(os.environ.get("SCHEDULE_HOUR", "9"))
    minute = int(os.environ.get("SCHEDULE_MINUTE", "0"))
    theme_count = os.environ.get("THEME_COUNT")  # None = random 3〜4

    logger.info("スケジューラー設定: days=%s, %02d:%02d JST", days, hour, minute)

    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(day_of_week=days, hour=hour, minute=minute),
        kwargs={"theme_count": int(theme_count) if theme_count else None},
        id="weekly_report_pipeline",
        name="東南アジア市場レポート 週次パイプライン",
        misfire_grace_time=3600,  # 1時間以内の遅延は許容
        coalesce=True,
    )

    logger.info("スケジューラー起動（Ctrl+C で停止）")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("スケジューラーを停止しました")
        scheduler.shutdown()


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="東南アジア市場レポート スケジューラー")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="スケジューリングせずに今すぐパイプラインを1回実行する",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="生成するテーマ数 (デフォルト: 3〜4のランダム)",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("即時実行モード")
        result = run_pipeline(theme_count=args.count)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        start_scheduler()
