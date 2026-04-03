"""
theme_selector.py
東南アジア市場レポート テーマ選定モジュール

スタートアップ思考ペルソナで週3〜4テーマを選定し、重複を防ぎながら themes.json に出力する。
"""

import json
import os
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from anthropic import Anthropic

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
THEMES_JSON = BASE_DIR / "themes.json"
HISTORY_JSON = BASE_DIR / "themes_history.json"

# 対象業界
INDUSTRIES = [
    "フィンテック",
    "Eコマース",
    "EV・モビリティ",
    "ヘルスケア",
    "教育テック",
    "不動産",
    "会計・規制",
    "農業テック",
]

# レポート形式
FORMATS = ["市場分析", "今後の展望"]

# 対象国・地域
COUNTRIES = [
    "東南アジア全域",
    "ベトナム",
    "タイ",
    "インドネシア",
    "フィリピン",
    "マレーシア",
    "シンガポール",
    "ミャンマー",
    "カンボジア",
]

SYSTEM_PROMPT = """あなたは東南アジア市場に精通したスタートアップ投資家・アナリストです。
最新のトレンド、規制動向、投資機会に敏感で、実践的かつデータドリブンな視点を持っています。
市場の課題と機会を同時に把握し、投資家・起業家・事業開発担当者が意思決定に使えるテーマを提案します。"""


def load_history() -> list[dict]:
    """履歴JSONを読み込む。存在しなければ空リストを返す。"""
    if HISTORY_JSON.exists():
        with open(HISTORY_JSON, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history: list[dict]) -> None:
    """履歴JSONを保存する。"""
    with open(HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_recent_themes(history: list[dict], weeks: int = 8) -> list[str]:
    """直近N週間のテーマタイトル一覧を返す（重複防止用）。"""
    cutoff = datetime.now() - timedelta(weeks=weeks)
    recent = []
    for entry in history:
        entry_date = datetime.fromisoformat(entry.get("selected_at", "2000-01-01"))
        if entry_date >= cutoff:
            recent.append(entry.get("title_ja", ""))
    return recent


def build_selection_prompt(
    recent_themes: list[str],
    count: int = 4,
) -> str:
    """Claude に渡すテーマ選定プロンプトを構築する。"""
    recent_str = "\n".join(f"- {t}" for t in recent_themes) if recent_themes else "なし"

    return f"""東南アジア市場レポートのテーマを{count}件選定してください。

【対象業界】
{chr(10).join(f'- {i}' for i in INDUSTRIES)}

【レポート形式】
- 市場分析（現状の規模・競合・課題を深掘り）
- 今後の展望（3〜5年の成長ドライバー・リスク・投資機会）

【対象地域】（各テーマで異なる国・地域を選ぶこと）
{chr(10).join(f'- {c}' for c in COUNTRIES)}

【直近8週間に選定済みのテーマ（重複禁止）】
{recent_str}

【出力形式】
以下のJSON配列のみを出力してください（マークダウン不要）:
[
  {{
    "title_ja": "日本語タイトル",
    "title_en": "English Title",
    "industry": "業界名",
    "format": "市場分析 または 今後の展望",
    "country": "対象国・地域",
    "rationale": "このテーマを選んだ理由（50字以内）",
    "keywords_ja": ["キーワード1", "キーワード2", "キーワード3"],
    "keywords_en": ["keyword1", "keyword2", "keyword3"]
  }}
]

スタートアップ投資家・事業開発担当者が「今すぐ読みたい」と思うタイムリーで具体的なテーマを選んでください。"""


def select_themes(count: int = 4) -> list[dict]:
    """Claude API を使ってテーマを選定し、themes.json に保存する。"""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    history = load_history()
    recent_themes = get_recent_themes(history)

    # 実際のcount: 3〜4でランダム
    actual_count = count if count else random.randint(3, 4)

    logger.info("テーマ選定開始: %d件 (直近除外: %d件)", actual_count, len(recent_themes))

    prompt = build_selection_prompt(recent_themes, actual_count)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # JSONブロックがある場合は抽出
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    themes = json.loads(raw)

    # メタデータ付与
    now_iso = datetime.now().isoformat()
    for theme in themes:
        theme["selected_at"] = now_iso
        theme["status"] = "pending"  # pending / generating / done / error

    # themes.json 保存（今週分）
    with open(THEMES_JSON, "w", encoding="utf-8") as f:
        json.dump(themes, f, ensure_ascii=False, indent=2)

    # 履歴に追加
    history.extend(themes)
    save_history(history)

    logger.info("テーマ選定完了: %s", [t["title_ja"] for t in themes])
    return themes


def load_pending_themes() -> list[dict]:
    """themes.json から status=pending のテーマを返す。"""
    if not THEMES_JSON.exists():
        return []
    with open(THEMES_JSON, encoding="utf-8") as f:
        themes = json.load(f)
    return [t for t in themes if t.get("status") == "pending"]


def update_theme_status(title_ja: str, status: str) -> None:
    """themes.json の特定テーマのステータスを更新する。"""
    if not THEMES_JSON.exists():
        return
    with open(THEMES_JSON, encoding="utf-8") as f:
        themes = json.load(f)
    for theme in themes:
        if theme.get("title_ja") == title_ja:
            theme["status"] = status
            break
    with open(THEMES_JSON, "w", encoding="utf-8") as f:
        json.dump(themes, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    themes = select_themes(count)
    print(json.dumps(themes, ensure_ascii=False, indent=2))
