"""
report_generator.py
東南アジア市場レポート 生成モジュール

Claude API で日本語レポートを生成し、同時にネイティブ品質の英語版にリライトする。
themes.json を読み込んで自動実行し、生成結果を reports/ ディレクトリに JSON で保存する。
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

from theme_selector import load_pending_themes, update_theme_status

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DISCLAIMER_JA = """本レポートは一般的な情報提供を目的として作成されており、投資勧誘・法的アドバイス・特定サービスの推奨を行うものではありません。記載内容の正確性・完全性・最新性について保証するものではなく、本レポートを参考にした意思決定によって生じた損失・損害について一切の責任を負いません。投資・事業判断は必ず専門家にご相談ください。"""

DISCLAIMER_EN = """This report is prepared for general informational purposes only and does not constitute investment advice, legal counsel, or endorsement of any specific service. No warranty is made regarding the accuracy, completeness, or timeliness of the information herein. The publisher assumes no liability for any loss or damage arising from decisions made based on this report. Please consult qualified professionals before making investment or business decisions."""


def build_ja_prompt(theme: dict) -> str:
    return f"""東南アジア市場レポートを日本語で執筆してください。

【テーマ】{theme['title_ja']}
【業界】{theme['industry']}
【形式】{theme['format']}
【対象地域】{theme['country']}
【キーワード】{', '.join(theme.get('keywords_ja', []))}

以下の構成で、各セクションの文字数を厳守してください。

=== エグゼクティブサマリー（約300字）===
市場の核心的な機会・課題・アクションポイントを簡潔に。

=== 市場概況（約800字）===
現在の市場規模・成長率・主要プレイヤー・規制環境を具体的な数字とともに。

=== 詳細分析（約1200字）===
競合状況・消費者行動・技術トレンド・ビジネスモデル・参入障壁を深掘り。

=== 今後の展望（約600字）===
3〜5年の成長ドライバー・リスク要因・投資機会・推奨アクションを。

【出力形式】
以下のJSONのみを出力（マークダウン不要）:
{{
  "executive_summary": "エグゼクティブサマリー本文",
  "market_overview": "市場概況本文",
  "detailed_analysis": "詳細分析本文",
  "future_outlook": "今後の展望本文"
}}

数字・固有名詞・事例を豊富に使い、読者が意思決定できる具体的な内容にしてください。"""


def build_en_rewrite_prompt(theme: dict, ja_content: dict) -> str:
    return f"""You are a native English business writer specializing in Southeast Asian market reports for institutional investors and C-suite executives.

Rewrite the following Japanese market report sections into professional, publication-ready English. This is NOT a translation — it's a native English rewrite that:
- Uses precise financial and business terminology
- Maintains the same data points and insights
- Flows naturally for English-speaking readers
- Adopts an authoritative, analytical tone (similar to McKinsey or Bloomberg Intelligence reports)

【Theme】{theme['title_en']}
【Industry】{theme['industry']}
【Format】{theme['format']}
【Region】{theme['country']}
【Keywords】{', '.join(theme.get('keywords_en', []))}

【Source content (Japanese)】
Executive Summary: {ja_content['executive_summary']}

Market Overview: {ja_content['market_overview']}

Detailed Analysis: {ja_content['detailed_analysis']}

Future Outlook: {ja_content['future_outlook']}

Output ONLY the following JSON (no markdown):
{{
  "executive_summary": "Executive Summary text (~200 words)",
  "market_overview": "Market Overview text (~500 words)",
  "detailed_analysis": "Detailed Analysis text (~800 words)",
  "future_outlook": "Future Outlook text (~400 words)"
}}"""


def generate_report(theme: dict) -> dict:
    """1テーマ分の日本語・英語レポートを生成して返す。"""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    logger.info("レポート生成開始: %s", theme["title_ja"])
    update_theme_status(theme["title_ja"], "generating")

    # --- 日本語生成 ---
    logger.info("  日本語レポート生成中...")
    ja_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system="あなたは東南アジア市場の専門アナリストです。データに基づいた実践的なレポートを執筆します。",
        messages=[{"role": "user", "content": build_ja_prompt(theme)}],
    )
    raw_ja = ja_response.content[0].text.strip()
    if "```" in raw_ja:
        raw_ja = raw_ja.split("```")[1]
        if raw_ja.startswith("json"):
            raw_ja = raw_ja[4:]
    ja_content = json.loads(raw_ja)

    # --- 英語リライト ---
    logger.info("  英語版リライト中...")
    en_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system="You are a senior business writer and editor with 20 years of experience in Southeast Asian market research publications.",
        messages=[{"role": "user", "content": build_en_rewrite_prompt(theme, ja_content)}],
    )
    raw_en = en_response.content[0].text.strip()
    if "```" in raw_en:
        raw_en = raw_en.split("```")[1]
        if raw_en.startswith("json"):
            raw_en = raw_en[4:]
    en_content = json.loads(raw_en)

    # --- 結果オブジェクト構築 ---
    now_iso = datetime.now().isoformat()
    slug = (
        theme["title_en"]
        .lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(",", "")
        .replace(":", "")[:60]
    )
    report_date = datetime.now().strftime("%Y年%m月%d日")
    report_date_en = datetime.now().strftime("%B %d, %Y")

    result = {
        "slug": slug,
        "generated_at": now_iso,
        "theme": theme,
        "report_date_ja": report_date,
        "report_date_en": report_date_en,
        "ja": {
            "title": theme["title_ja"],
            "subtitle": f"{theme['country']} | {theme['industry']} | {theme['format']}",
            "executive_summary": ja_content["executive_summary"],
            "market_overview": ja_content["market_overview"],
            "detailed_analysis": ja_content["detailed_analysis"],
            "future_outlook": ja_content["future_outlook"],
            "disclaimer": DISCLAIMER_JA,
        },
        "en": {
            "title": theme["title_en"],
            "subtitle": f"{theme['country']} | {theme['industry']} | {theme['format']}",
            "executive_summary": en_content["executive_summary"],
            "market_overview": en_content["market_overview"],
            "detailed_analysis": en_content["detailed_analysis"],
            "future_outlook": en_content["future_outlook"],
            "disclaimer": DISCLAIMER_EN,
        },
    }

    # JSON 保存
    output_path = REPORTS_DIR / f"{slug}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    update_theme_status(theme["title_ja"], "done")
    logger.info("レポート生成完了: %s -> %s", theme["title_ja"], output_path)
    return result


def run_all_pending() -> list[dict]:
    """themes.json の全 pending テーマのレポートを生成する。"""
    themes = load_pending_themes()
    if not themes:
        logger.info("生成待ちのテーマがありません")
        return []

    results = []
    for theme in themes:
        try:
            report = generate_report(theme)
            results.append(report)
        except Exception as e:
            logger.error("レポート生成失敗: %s - %s", theme.get("title_ja"), e)
            update_theme_status(theme.get("title_ja", ""), "error")
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 単一スラッグ指定モード: python report_generator.py <slug>
        slug = sys.argv[1]
        from pathlib import Path
        themes_json = BASE_DIR / "themes.json"
        with open(themes_json, encoding="utf-8") as f:
            all_themes = json.load(f)
        target = next(
            (t for t in all_themes if slug in t.get("title_en", "").lower().replace(" ", "-")),
            None,
        )
        if target:
            result = generate_report(target)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"テーマが見つかりません: {slug}")
    else:
        results = run_all_pending()
        print(f"{len(results)}件のレポートを生成しました")
