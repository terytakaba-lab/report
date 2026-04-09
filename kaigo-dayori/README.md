# 介護だより

介護家族向けの「今日の様子報告文ジェネレーター」

## セットアップ

1. `config.example.js` を `config.js` にコピーする
2. `config.js` の `ANTHROPIC_API_KEY` に Anthropic API キーを入力する
3. `index.html` をブラウザで開くか、Xserver に FTP でアップロードする

```bash
cp config.example.js config.js
# config.js を編集して API キーを入力
```

## ファイル構成

```
kaigo-dayori/
├── index.html          # メインHTML
├── style.css           # スタイル
├── app.js              # アプリロジック（履歴・使用回数管理）
├── config.js           # APIキー設定（gitignore対象、要作成）
├── config.example.js   # config.js のテンプレート
├── .env                # 環境変数メモ（gitignore対象）
└── .gitignore
```

## 機能

- 今日の様子をチップで選択（複数選択可）
- 自由記述の追加情報
- 文章トーン選択（温かく／丁寧に／簡潔に）
- Claude API で報告文を自動生成
- 月10回の無料制限（localStorage管理）
- 生成履歴を最新5件まで保存・表示（コピー可）
- 個人情報の保存なし

## 技術スタック

- HTML / CSS / Vanilla JS
- Anthropic Claude API（claude-sonnet-4-20250514）
- デプロイ：Xserver（FTPアップロード）
