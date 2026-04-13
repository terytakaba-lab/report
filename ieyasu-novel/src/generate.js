import Anthropic from '@anthropic-ai/sdk';
import 'dotenv/config';
import fetch from 'node-fetch';
import { HttpsProxyAgent } from 'https-proxy-agent';
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'fs';
import { SYSTEM_PROMPT } from './prompt.js';

// Node.js 22 の native fetch は HTTPS_PROXY を自動で読まないため、
// https-proxy-agent + node-fetch をカスタム fetch として SDK に渡す
const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
const proxyFetch = (url, init) => fetch(url, { ...init, agent });

const client = new Anthropic({ fetch: proxyFetch });

// ─── サマリーファイル操作 ──────────────────────────────────────────

function getOutputDir() {
  return new URL('../output', import.meta.url).pathname;
}

function readSummaries(outputDir) {
  const path = `${outputDir}/episode_summary.json`;
  if (!existsSync(path)) return { episodes: [] };
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return { episodes: [] };
  }
}

function updateSummaryFile(outputDir, plot, extracted) {
  const data = readSummaries(outputDir);
  // 同話数の既存エントリを上書き
  data.episodes = data.episodes.filter((e) => e.episode !== plot.episode);
  data.episodes.push({
    episode: plot.episode,
    title: plot.title,
    narrator: plot.narrator,
    noticedBy: extracted.noticedBy ?? [],
    properNouns: extracted.properNouns ?? [],
    foreshadowing: extracted.foreshadowing ?? [],
    tanakaState: extracted.tanakaState ?? plot.tanakaPhase,
  });
  data.episodes.sort((a, b) => a.episode - b.episode);
  writeFileSync(`${outputDir}/episode_summary.json`, JSON.stringify(data, null, 2), 'utf-8');
}

// ─── Step0: 生成後サマリー抽出 (Claude Haiku) ────────────────────────

async function extractSummary(plot, novelText) {
  const prompt = `以下の小説テキストを読み、JSON形式のみで情報を抽出してください。語り手はAI${plot.narrator}です。

---
${novelText}
---

以下のJSON形式のみを返してください（コードブロック・説明文不要）：
{
  "noticedBy": ["語り手が新たに気づいた重要なこと（3〜5項目、簡潔に）"],
  "properNouns": ["登場した固有名詞（人名・地名・書状名など）"],
  "foreshadowing": ["生まれた伏線・次話以降に繋がりそうな要素（1〜3項目）"],
  "tanakaState": "田中Makotoの状態（テキスト内の言及を1文で。言及なければ「${plot.tanakaPhase}」）"
}`;

  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 800,
    messages: [{ role: 'user', content: prompt }],
  });

  const text = response.content.find((b) => b.type === 'text')?.text ?? '{}';
  try {
    return JSON.parse(text.replace(/```json\n?|\n?```/g, '').trim());
  } catch {
    return { noticedBy: [], properNouns: [], foreshadowing: [], tanakaState: plot.tanakaPhase };
  }
}

// ─── Step1: 史実検証・空白仮説・誤読設計 (Claude Opus) ───────────────

async function generateStep1(plot) {
  const prompt = `以下のplotに基づいて、小説執筆のための事前分析を行ってください。

【plot情報】
- episode: ${plot.episode}
- narrator: AI${plot.narrator}
- title: ${plot.title}
- historicalFact: ${plot.historicalFact}
- misreading: ${plot.misreading}
- blankTheme: ${plot.blankTheme}
- aiHighlight: ${plot.aiHighlight}
- tanakaPhase: ${plot.tanakaPhase}

以下の3点を詳細に分析してください。

## 1. 史実検証
この時期（${plot.historicalFact}）の具体的な史実を検証してください。
関係者の動向、政治的文脈、AI${plot.narrator}と徳川家康の立場を整理する。

## 2. 空白仮説
「${plot.blankTheme}」というテーマに対し、史料に残らない場面・瞬間の仮説を複数提示してください。
特に「${plot.aiHighlight}」という視点から、AI${plot.narrator}が注目すべき「不自然さ」を具体的に描写する。

## 3. 誤読設計
「${plot.misreading}」という誤読が、なぜ論理的に見えたのかを設計してください。
AI${plot.narrator}の思考回路がどのようなデータをどう処理して、この誤った結論に至ったかを段階的に示す。
田中フェーズ「${plot.tanakaPhase}」の状態も反映すること。`;

  const response = await client.messages.create({
    model: 'claude-opus-4-6',
    max_tokens: 4000,
    thinking: { type: 'adaptive' },
    messages: [{ role: 'user', content: prompt }],
  });

  const textBlock = response.content.find((b) => b.type === 'text');
  return textBlock ? textBlock.text : '';
}

// ─── Step2: 本文生成 (Claude Sonnet) ─────────────────────────────────

async function generateNovel(plot, step1Output, attempt, prevCharCount = 0, previousSummaries = []) {
  const retryNote = attempt > 0
    ? `\n【重要】前回の出力が${prevCharCount.toLocaleString()}字でした。各層をより詳細に描写して4,000字以上にしてください。\n`
    : '';

  const contextNote = previousSummaries.length > 0
    ? `\n【前話までの記録（継続性を保つこと）】\n` +
      previousSummaries.slice(-3).map((e) =>
        `第${e.episode}話「${e.title}」（語り手：AI${e.narrator}）\n` +
        `  気づき: ${e.noticedBy.join('／')}\n` +
        `  伏線: ${e.foreshadowing.join('／')}\n` +
        `  田中の状態: ${e.tanakaState}`
      ).join('\n') + '\n'
    : '';

  const userPrompt = `${retryNote}${contextNote}
【Step1分析結果】
${step1Output}

【plot情報】
- episode: ${plot.episode}
- narrator: AI${plot.narrator}
- title: ${plot.title}
- historicalFact: ${plot.historicalFact}
- misreading: ${plot.misreading}
- blankTheme: ${plot.blankTheme}
- aiHighlight: ${plot.aiHighlight}
- tanakaPhase: ${plot.tanakaPhase}

史実の記述が分析に滑り込み、
分析が気づけば感情になっていて、
感情から逃げるように史実に戻る——
この繰り返しで一続きの文章を書くこと。

ただし全体を通じて以下の要素を必ず含めること：
- 史料の引用・日付・記録（計1,000字相当）
- 史料のクロス参照と矛盾の発見（計1,200字相当）。AIの注目ポイント：${plot.aiHighlight}
- 空白の推論・フィクション補完（計1,200字相当）。テーマ：${plot.blankTheme}
- 感情への滑落・体言止め・短い文（計800字相当）。田中フェーズ：${plot.tanakaPhase}

合計4,000字以上6,000字以内で仕上げること。
セクションヘッダーは一切出力しないこと。
冒頭にタイトル・話数・見出しを書かないこと。本文から直接始めること。
自然な段落の流れで書くこと。

【小説としての品質ルール】

文章リズム：
- 長い分析文の後に短い一文を置く
- 「——」（ダッシュ）を効果的に使う
- 段落の長さに緩急をつける
  （長い段落→短い段落→一行→長い段落）

描写の具体性：
- 抽象的な感情を書かない（描写する）
  ❌「私は恐怖を感じた」
  ✅「手が、止まった」
- 場所・季節・光・音を時折入れる
- 家康の表情・仕草を具体的に描写する

会話・セリフ：
- セリフは短く、余韻を残す
- セリフの後に長い説明を入れない
- 「と、彼は言った」系の説明を避ける

テンポ：
- クライマックス（推論層→感情層）は文を短くしてテンポを上げる
- 冒頭（史実層）は落ち着いたテンポで入る

【呼び方・繰り返しのルール（改訂版）】

家康の呼び方：
- 同じ文脈・同じ感情の中では同じ呼び方を繰り返してよい。
  繰り返しが語り手の執着・強迫観念を表現する。
- 切り替えは感情の転換点でのみ行う：
  分析中：「家康」を繰り返す
  感情に滑落する瞬間：「家康」→「あの男」に切り替わる
  分析に戻る瞬間：「あの男」→「家康」に戻る
  一瞬の敬意・距離感が混じる時のみ：「内府殿」

単語全般の繰り返しも同様：
- 同じ場面・同じ感情の流れの中では同じ単語の繰り返しを許容する
- 変えるのは場面・感情が転換する時だけ
- 機械的な言い換えは不自然になるので禁止

余韻：
- 各話の最後の一文は短く終わる
- 答えを出さずに問いで終わるか、一つの情景で終わる`;

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8000,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userPrompt }],
  });

  const textBlock = response.content.find((b) => b.type === 'text');
  return textBlock ? textBlock.text : '';
}

// ─── メイン生成フロー ─────────────────────────────────────────────

export async function generate(plot) {
  console.log('\n' + '═'.repeat(50));
  console.log(`Episode ${plot.episode}:「${plot.title}」（語り手：AI${plot.narrator}）`);
  console.log('═'.repeat(50) + '\n');

  const outputDir = getOutputDir();
  mkdirSync(outputDir, { recursive: true });

  // 前話までのサマリーを読み込む
  const summaryData = readSummaries(outputDir);
  const previousSummaries = summaryData.episodes.filter((e) => e.episode < plot.episode);
  if (previousSummaries.length > 0) {
    console.log(`前話サマリー読み込み: ${previousSummaries.length}話分\n`);
  }

  // Step 1: 史実検証・空白仮説・誤読設計 (Claude Opus)
  console.log('[Step1] 史実検証・空白仮説・誤読設計 (Claude Opus 4.6)...');
  const step1Output = await generateStep1(plot);
  console.log('Step1 完了\n');

  // Step 2: 本文生成 (Claude Sonnet) — 字数不足時は最大2回再生成
  const MAX_RETRIES = 2;
  let novelText = '';
  let prevCharCount = 0;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt === 0) {
      console.log('[Step2] 本文生成 (Claude Sonnet 4.6)...');
    } else {
      console.log(`[Step2] 再生成中 (${attempt}/${MAX_RETRIES})...`);
    }

    novelText = await generateNovel(plot, step1Output, attempt, prevCharCount, previousSummaries);
    const charCount = novelText.length;
    prevCharCount = charCount;
    console.log(`生成字数: ${charCount.toLocaleString()} 字`);

    if (charCount >= 4000) break;

    if (attempt === MAX_RETRIES) {
      console.warn('警告: 最大再生成回数に達しました。現在の出力を使用します。');
    }
  }

  // ターミナルに出力
  console.log('\n' + '─'.repeat(50));
  console.log('【生成結果】');
  console.log('─'.repeat(50) + '\n');
  console.log(novelText);
  console.log('\n' + '─'.repeat(50));

  // ファイルに保存（免責事項・末尾区切り線をトリム）
  const trimmedText = novelText
    .replace(/\n{1,2}---\n[\s\S]*$/, '')
    .replace(/\n{1,2}※本作は[\s\S]*$/, '')
    .trimEnd();

  const fileName = `ep${String(plot.episode).padStart(2, '0')}_${plot.title}.txt`;
  const fileContent = `# 第${plot.episode}話「${plot.title}」\n\n${trimmedText}`;
  writeFileSync(`${outputDir}/${fileName}`, fileContent, 'utf-8');
  console.log(`保存: output/${fileName}`);

  // Step3: サマリー抽出・episode_summary.json 更新 (Claude Haiku)
  console.log('[Step3] サマリー抽出中 (Claude Haiku)...');
  const extracted = await extractSummary(plot, trimmedText);
  updateSummaryFile(outputDir, plot, extracted);
  console.log('サマリー更新: output/episode_summary.json\n');
}
