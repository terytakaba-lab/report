# 東南アジア市場レポート 自動生成・販売システム

Claude API を使って東南アジア市場レポートを週3〜4本自動生成し、Note（日本語）と Gumroad（英語）に投稿するシステム。

---

## システム構成

```
report-automation/
├── theme_selector.py      # [1] テーマ選定
├── report_generator.py    # [2] レポート生成（日本語 + 英語）
├── pdf_generator.py       # [3] PDF生成（WeasyPrint）
├── uploader.py            # [4] Note / Gumroad へアップロード
├── scheduler.py           # [5] 週次スケジューラー
├── template.html          # PDFテンプレート
├── themes.json            # 今週の選定テーマ（自動生成）
├── themes_history.json    # テーマ履歴（重複防止）
├── upload_log.json        # アップロード履歴（自動生成）
├── run_log.json           # 実行ログ（自動生成）
├── reports/               # 生成レポートJSON（自動生成）
├── pdfs/                  # 生成PDF（自動生成）
├── logs/                  # スケジューラーログ（自動生成）
├── .env                   # 環境変数（要作成）
└── .env.example           # 環境変数テンプレート
```

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install anthropic weasyprint jinja2 python-dotenv apscheduler requests
```

WeasyPrint のシステム依存（GTK/Cairo）も必要です：

```bash
# macOS
brew install pango

# Ubuntu/Debian
sudo apt-get install python3-weasyprint libpango-1.0-0 libpangoft2-1.0-0
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集してAPIキー等を設定
```

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API キー | ✅ |
| `NOTE_SESSION_COOKIE` | Note セッションCookie | ✅ |
| `GUMROAD_ACCESS_TOKEN` | Gumroad アクセストークン | ✅ |
| `GUMROAD_DEFAULT_PRICE` | Gumroad 販売価格（USD） | 任意（デフォルト: 9） |
| `SCHEDULE_DAYS` | 実行曜日（デフォルト: mon,wed,fri） | 任意 |
| `SCHEDULE_HOUR` | 実行時刻・時 JST（デフォルト: 9） | 任意 |
| `SCHEDULE_MINUTE` | 実行時刻・分（デフォルト: 0） | 任意 |

---

## 使い方

### 今すぐ全パイプラインを1回実行

```bash
python scheduler.py --run-now
```

テーマ数を指定する場合：

```bash
python scheduler.py --run-now --count 3
```

### 週次スケジューラーを起動（常駐）

```bash
python scheduler.py
```

デフォルトで月・水・金曜日 09:00 JST に実行されます。

---

## 各モジュールの単独実行

### [1] テーマ選定のみ

```bash
python theme_selector.py        # 4件選定（デフォルト）
python theme_selector.py 3      # 3件選定
```

出力: `themes.json`

### [2] レポート生成のみ

```bash
python report_generator.py      # themes.json の全 pending テーマを処理
```

出力: `reports/<slug>.json`

### [3] PDF生成のみ

```bash
python pdf_generator.py                         # reports/ 内の全JSONを処理
python pdf_generator.py reports/<slug>.json     # 単一ファイルを処理
```

出力: `pdfs/<slug>_ja.pdf`, `pdfs/<slug>_en.pdf`

### [4] アップロードのみ

```bash
python uploader.py              # 未アップロードの全PDFを処理
python uploader.py <slug>       # 単一スラッグを処理
```

---

## パイプライン詳細

```
[1] theme_selector.py
    └─ Claude API でスタートアップ思考ペルソナが週3〜4テーマ選定
    └─ 直近8週間の重複を防ぐ履歴管理
    └─ themes.json に出力

[2] report_generator.py
    └─ themes.json を読み込んで pending テーマを順次処理
    └─ Claude API で日本語レポート生成（約3000字）
    └─ 同じ Claude API でネイティブ英語にリライト
    └─ reports/<slug>.json に保存

[3] pdf_generator.py
    └─ Jinja2 で template.html にデータを差し込みレンダリング
    └─ WeasyPrint で A4 PDF 変換
    └─ 日本語版・英語版それぞれ生成
    └─ pdfs/<slug>_ja.pdf / pdfs/<slug>_en.pdf に保存

[4] uploader.py
    └─ 日本語PDF を Note に有料ノートとして投稿（ドラフト）
    └─ 英語PDF を Gumroad に商品として登録（非公開）
    └─ タイトル・説明文・ハッシュタグも Claude API で自動生成
    └─ upload_log.json に記録
```

---

## レポート構成

| セクション | 日本語 | 英語（目安） |
|-----------|--------|-------------|
| エグゼクティブサマリー | 約300字 | ~200 words |
| 市場概況 | 約800字 | ~500 words |
| 詳細分析 | 約1200字 | ~800 words |
| 今後の展望 | 約600字 | ~400 words |

---

## デザイン仕様

- **カラー**: ダークネイビー (`#0D1B2A`) × ホワイト × アクセントゴールド (`#C9A84C`)
- **用紙**: A4
- **構成**: 表紙 + 本文（セクション分割）+ 免責事項
- **フォント**: Noto Sans JP / Noto Serif JP（日本語）、Inter（英語）

---

## 対象業界・地域

**業界**: フィンテック / Eコマース / EV・モビリティ / ヘルスケア / 教育テック / 不動産 / 会計・規制 / 農業テック

**地域**: 東南アジア全域 / ベトナム / タイ / インドネシア / フィリピン / マレーシア / シンガポール / ミャンマー / カンボジア

---

## 注意事項

- Note への投稿は **ドラフト状態**で作成されます。確認後に手動で公開してください。
- Gumroad への登録も **非公開状態**で作成されます。確認後に手動で公開してください。
- Note API は非公式のため、Cookie 認証が切れた場合は再取得が必要です。
- API コスト: 1テーマあたり Claude Opus 4 を3回呼び出します（テーマ選定は1バッチで1回）。
