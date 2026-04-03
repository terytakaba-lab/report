"""
pdf_generator.py
東南アジア市場レポート PDF生成モジュール

HTMLテンプレートにレポート内容を差し込み、WeasyPrintでA4 PDFを生成する。
カラー: ダークネイビー × ホワイト × アクセントゴールド
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
PDF_DIR = BASE_DIR / "pdfs"
PDF_DIR.mkdir(exist_ok=True)
TEMPLATE_FILE = BASE_DIR / "template.html"


def render_html(report: dict, lang: str) -> str:
    """Jinja2 でHTMLをレンダリングして返す。lang は 'ja' または 'en'。"""
    env = Environment(
        loader=FileSystemLoader(str(BASE_DIR)),
        autoescape=True,
    )
    template = env.get_template("template.html")

    content = report[lang]
    theme = report["theme"]

    context = {
        "lang": lang,
        "title": content["title"],
        "subtitle": content["subtitle"],
        "report_date": report["report_date_ja"] if lang == "ja" else report["report_date_en"],
        "industry": theme["industry"],
        "country": theme["country"],
        "format_type": theme["format"],
        "keywords": theme.get("keywords_ja" if lang == "ja" else "keywords_en", []),
        "executive_summary": content["executive_summary"],
        "market_overview": content["market_overview"],
        "detailed_analysis": content["detailed_analysis"],
        "future_outlook": content["future_outlook"],
        "disclaimer": content["disclaimer"],
        # セクションラベル
        "label_executive_summary": "エグゼクティブサマリー" if lang == "ja" else "Executive Summary",
        "label_market_overview": "市場概況" if lang == "ja" else "Market Overview",
        "label_detailed_analysis": "詳細分析" if lang == "ja" else "Detailed Analysis",
        "label_future_outlook": "今後の展望" if lang == "ja" else "Future Outlook",
        "label_disclaimer": "免責事項" if lang == "ja" else "Disclaimer",
        "label_keywords": "キーワード" if lang == "ja" else "Keywords",
        "footer_text": "東南アジア市場インサイト" if lang == "ja" else "Southeast Asia Market Insights",
        "confidential_text": "本レポートは情報提供目的のみ" if lang == "ja" else "For informational purposes only",
    }
    return template.render(**context)


def generate_pdf(report: dict, lang: str) -> Path:
    """
    レポートデータからPDFを生成してパスを返す。
    lang: 'ja' または 'en'
    """
    slug = report["slug"]
    suffix = "ja" if lang == "ja" else "en"
    output_path = PDF_DIR / f"{slug}_{suffix}.pdf"

    logger.info("PDF生成中: %s (%s)", slug, lang)

    html_str = render_html(report, lang)

    # WeasyPrint で PDF 変換
    html_obj = HTML(string=html_str, base_url=str(BASE_DIR))
    html_obj.write_pdf(str(output_path))

    logger.info("PDF生成完了: %s", output_path)
    return output_path


def generate_both_pdfs(report: dict) -> dict[str, Path]:
    """日本語・英語両方のPDFを生成してパス辞書を返す。"""
    paths = {}
    for lang in ("ja", "en"):
        try:
            path = generate_pdf(report, lang)
            paths[lang] = path
        except Exception as e:
            logger.error("PDF生成失敗 (%s, %s): %s", report.get("slug"), lang, e)
            raise
    return paths


def generate_from_json(json_path: Path) -> dict[str, Path]:
    """JSONファイルを読み込んで両言語PDFを生成する。"""
    with open(json_path, encoding="utf-8") as f:
        report = json.load(f)
    return generate_both_pdfs(report)


def generate_all_reports() -> list[dict]:
    """reports/ ディレクトリの全JSONからPDFを生成する。"""
    results = []
    json_files = list(REPORTS_DIR.glob("*.json"))
    if not json_files:
        logger.info("生成対象のレポートJSONが見つかりません")
        return results

    for json_path in sorted(json_files):
        try:
            paths = generate_from_json(json_path)
            results.append({"json": json_path, "pdfs": paths})
        except Exception as e:
            logger.error("PDF生成失敗: %s - %s", json_path.name, e)
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.exists():
            paths = generate_from_json(target)
            for lang, path in paths.items():
                print(f"[{lang}] {path}")
        else:
            print(f"ファイルが見つかりません: {target}")
    else:
        results = generate_all_reports()
        print(f"{len(results)}件のレポートからPDFを生成しました")
        for r in results:
            for lang, path in r["pdfs"].items():
                print(f"  [{lang}] {path}")
