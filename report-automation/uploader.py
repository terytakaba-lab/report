"""
uploader.py
東南アジア市場レポート アップロードモジュール

- 日本語PDF → Note（Note API）
- 英語PDF → Gumroad（Gumroad API）
タイトル・説明文も自動生成して投稿する。
"""

import json
import logging
import os
from pathlib import Path
from anthropic import Anthropic
import requests

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
PDF_DIR = BASE_DIR / "pdfs"
UPLOAD_LOG = BASE_DIR / "upload_log.json"

# Note API
NOTE_API_BASE = "https://note.com/api/v2"
NOTE_SESSION_COOKIE = os.environ.get("NOTE_SESSION_COOKIE", "")

# Gumroad API
GUMROAD_API_BASE = "https://api.gumroad.com/v2"
GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "")

# デフォルト価格（USD）
GUMROAD_DEFAULT_PRICE = int(os.environ.get("GUMROAD_DEFAULT_PRICE", "9"))


# ---------------------------------------------------------------------------
# 説明文生成
# ---------------------------------------------------------------------------

def generate_note_description(report: dict) -> dict:
    """Note 投稿用の日本語タイトル・本文を生成する。"""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    ja = report["ja"]
    theme = report["theme"]

    prompt = f"""以下のレポートをNote（日本語ブログ）に投稿するための紹介文を作成してください。

【レポートタイトル】{ja['title']}
【対象地域・業界】{theme['country']} / {theme['industry']}
【エグゼクティブサマリー】{ja['executive_summary'][:300]}

以下のJSONのみ出力（マークダウン不要）:
{{
  "note_title": "Noteの投稿タイトル（40字以内、読者を惹きつける）",
  "hashtags": ["ハッシュタグ1", "ハッシュタグ2", "ハッシュタグ3", "ハッシュタグ4", "ハッシュタグ5"],
  "body_intro": "Note本文の導入部（200字程度）。読者がレポートを購入・閲覧したくなる内容。",
  "price_description": "有料パートの内容説明（100字以内）"
}}"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def generate_gumroad_description(report: dict) -> dict:
    """Gumroad 商品用の英語タイトル・説明文を生成する。"""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    en = report["en"]
    theme = report["theme"]

    prompt = f"""Create a compelling Gumroad product listing for the following market research report.

Report Title: {en['title']}
Region/Industry: {theme['country']} / {theme['industry']}
Executive Summary: {en['executive_summary'][:400]}

Output ONLY the following JSON (no markdown):
{{
  "product_name": "Gumroad product title (max 60 chars, compelling)",
  "description": "Product description (300-400 words). Include: what's inside, who it's for, key insights covered, why buy now. Use bullet points for key topics covered.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "custom_permalink": "url-slug-for-product"
}}"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Note アップロード
# ---------------------------------------------------------------------------

def upload_to_note(report: dict, pdf_path: Path) -> dict:
    """
    Note APIを使って日本語PDFを投稿する。
    Note の有料ノート（ファイル添付）として投稿。
    """
    if not NOTE_SESSION_COOKIE:
        raise ValueError("NOTE_SESSION_COOKIE が設定されていません")

    logger.info("Note へアップロード中: %s", report["slug"])

    meta = generate_note_description(report)
    ja = report["ja"]

    headers = {
        "Cookie": f"_note_session={NOTE_SESSION_COOKIE}",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }

    # Step 1: ファイルアップロード
    with open(pdf_path, "rb") as f:
        file_response = requests.post(
            f"{NOTE_API_BASE}/attachments",
            headers={"Cookie": f"_note_session={NOTE_SESSION_COOKIE}"},
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=60,
        )
    file_response.raise_for_status()
    attachment_key = file_response.json().get("attachment", {}).get("key", "")

    # Step 2: ノート作成
    body_html = f"""<p>{meta['body_intro']}</p>
<h2>{ja['title']}</h2>
<p><strong>対象地域：</strong>{report['theme']['country']}</p>
<p><strong>業界：</strong>{report['theme']['industry']}</p>
<p><strong>レポート形式：</strong>{report['theme']['format']}</p>
<h3>エグゼクティブサマリー</h3>
<p>{ja['executive_summary'][:200]}...</p>
<p>※ 全文（PDF）は有料パートでダウンロードできます。</p>
<p><em>{meta['price_description']}</em></p>"""

    payload = {
        "note": {
            "title": meta["note_title"],
            "body": body_html,
            "status": "draft",  # 確認後に公開
            "price": 500,  # 円
            "hashtag_list": meta["hashtags"],
            "attachments": [{"key": attachment_key}] if attachment_key else [],
        }
    }

    create_response = requests.post(
        f"{NOTE_API_BASE}/notes",
        headers=headers,
        json=payload,
        timeout=30,
    )
    create_response.raise_for_status()
    note_data = create_response.json()

    result = {
        "platform": "note",
        "slug": report["slug"],
        "note_id": note_data.get("note", {}).get("id"),
        "note_key": note_data.get("note", {}).get("key"),
        "title": meta["note_title"],
        "status": "draft",
        "url": f"https://note.com/notes/{note_data.get('note', {}).get('key', '')}",
    }
    logger.info("Note アップロード完了: %s", result["url"])
    return result


# ---------------------------------------------------------------------------
# Gumroad アップロード
# ---------------------------------------------------------------------------

def upload_to_gumroad(report: dict, pdf_path: Path) -> dict:
    """
    Gumroad API を使って英語PDFを商品として登録する。
    """
    if not GUMROAD_ACCESS_TOKEN:
        raise ValueError("GUMROAD_ACCESS_TOKEN が設定されていません")

    logger.info("Gumroad へアップロード中: %s", report["slug"])

    meta = generate_gumroad_description(report)

    # Step 1: 商品作成
    product_payload = {
        "access_token": GUMROAD_ACCESS_TOKEN,
        "name": meta["product_name"],
        "description": meta["description"],
        "price": GUMROAD_DEFAULT_PRICE * 100,  # セント単位
        "tags": ",".join(meta.get("tags", [])),
        "custom_permalink": meta.get("custom_permalink", report["slug"])[:30],
        "published": False,  # 確認後に公開
        "currency": "usd",
    }

    create_response = requests.post(
        f"{GUMROAD_API_BASE}/products",
        data=product_payload,
        timeout=30,
    )
    create_response.raise_for_status()
    product = create_response.json().get("product", {})
    product_id = product.get("id")

    # Step 2: PDFファイルをアップロード
    with open(pdf_path, "rb") as f:
        file_response = requests.post(
            f"{GUMROAD_API_BASE}/products/{product_id}/product_files",
            data={"access_token": GUMROAD_ACCESS_TOKEN},
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=120,
        )
    file_response.raise_for_status()

    result = {
        "platform": "gumroad",
        "slug": report["slug"],
        "product_id": product_id,
        "title": meta["product_name"],
        "price_usd": GUMROAD_DEFAULT_PRICE,
        "status": "draft",
        "url": product.get("short_url", f"https://gumroad.com/l/{meta.get('custom_permalink', report['slug'])}"),
    }
    logger.info("Gumroad アップロード完了: %s", result["url"])
    return result


# ---------------------------------------------------------------------------
# アップロードログ管理
# ---------------------------------------------------------------------------

def load_upload_log() -> list[dict]:
    if UPLOAD_LOG.exists():
        with open(UPLOAD_LOG, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_upload_log(log: list[dict]) -> None:
    with open(UPLOAD_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def append_upload_log(entry: dict) -> None:
    log = load_upload_log()
    log.append(entry)
    save_upload_log(log)


# ---------------------------------------------------------------------------
# メイン実行
# ---------------------------------------------------------------------------

def upload_report(slug: str) -> dict:
    """
    指定スラッグのレポートをNote（日本語）とGumroad（英語）にアップロードする。
    """
    json_path = REPORTS_DIR / f"{slug}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"レポートJSONが見つかりません: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        report = json.load(f)

    pdf_ja = PDF_DIR / f"{slug}_ja.pdf"
    pdf_en = PDF_DIR / f"{slug}_en.pdf"

    if not pdf_ja.exists() or not pdf_en.exists():
        raise FileNotFoundError(f"PDFが見つかりません: {pdf_ja} / {pdf_en}")

    results = {"slug": slug, "uploads": []}
    import datetime
    results["uploaded_at"] = datetime.datetime.now().isoformat()

    # Note (日本語)
    try:
        note_result = upload_to_note(report, pdf_ja)
        results["uploads"].append(note_result)
    except Exception as e:
        logger.error("Note アップロード失敗: %s", e)
        results["uploads"].append({"platform": "note", "error": str(e)})

    # Gumroad (英語)
    try:
        gumroad_result = upload_to_gumroad(report, pdf_en)
        results["uploads"].append(gumroad_result)
    except Exception as e:
        logger.error("Gumroad アップロード失敗: %s", e)
        results["uploads"].append({"platform": "gumroad", "error": str(e)})

    append_upload_log(results)
    return results


def upload_all_pending() -> list[dict]:
    """PDF が存在するがアップロードログにない全スラッグをアップロードする。"""
    log = load_upload_log()
    uploaded_slugs = {entry["slug"] for entry in log}

    results = []
    for pdf_path in sorted(PDF_DIR.glob("*_ja.pdf")):
        slug = pdf_path.stem.replace("_ja", "")
        if slug in uploaded_slugs:
            logger.info("スキップ（アップロード済み）: %s", slug)
            continue
        try:
            result = upload_report(slug)
            results.append(result)
        except Exception as e:
            logger.error("アップロード失敗: %s - %s", slug, e)
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = upload_report(sys.argv[1])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        results = upload_all_pending()
        print(f"{len(results)}件をアップロードしました")
