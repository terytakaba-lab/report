import Anthropic from '@anthropic-ai/sdk';
import 'dotenv/config';
import fetch from 'node-fetch';
import { HttpsProxyAgent } from 'https-proxy-agent';
import { SYSTEM_PROMPT } from './prompt.js';

// Node.js 22 の native fetch は HTTPS_PROXY を自動で読まないため、
// https-proxy-agent + node-fetch をカスタム fetch として SDK に渡す
const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
const proxyFetch = (url, init) => fetch(url, { ...init, agent });

const client = new Anthropic({ fetch: proxyFetch });

async function generateStep1(plot) {
  const prompt = `以下のplotに基づいて、小説執筆のための事前分析を行ってください。

【plot情報】
- episode: ${plot.episode}
- title: ${plot.title}
- historicalFact: ${plot.historicalFact}
- misreading: ${plot.misreading}
- blankTheme: ${plot.blankTheme}
- aiHighlight: ${plot.aiHighlight}
- tanakaPhase: ${plot.tanakaPhase}

以下の3点を詳細に分析してください。

## 1. 史実検証
この時期（${plot.historicalFact}）の具体的な史実を検証してください。
関係者の動向、政治的文脈、石田三成と徳川家康の立場を整理する。

## 2. 空白仮説
「${plot.blankTheme}」というテーマに対し、史料に残らない場面・瞬間の仮説を複数提示してください。
特に「${plot.aiHighlight}」という視点から、AI三成が注目すべき「不自然さ」を具体的に描写する。

## 3. 誤読設計
「${plot.misreading}」という誤読が、なぜ論理的に見えたのかを設計してください。
AI三成の思考回路がどのようなデータをどう処理して、この誤った結論に至ったかを段階的に示す。
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

async function generateNovel(plot, step1Output, attempt) {
  const retryNote = attempt > 0
    ? `\n【重要】前回の出力が4,000字に達しませんでした。今回は必ず4,000字以上の本文を出力してください。場面描写、心理描写、対話の間を丁寧に膨らませてください。\n`
    : '';

  const userPrompt = `${retryNote}【Step1分析結果】
${step1Output}

【plot情報】
- episode: ${plot.episode}
- title: ${plot.title}
- historicalFact: ${plot.historicalFact}
- misreading: ${plot.misreading}
- blankTheme: ${plot.blankTheme}
- aiHighlight: ${plot.aiHighlight}
- tanakaPhase: ${plot.tanakaPhase}

上記の分析を踏まえ、AI三成の視点による小説本文を執筆してください。
必ず4,000字以上6,000字以内で仕上げてください。`;

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8000,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userPrompt }],
  });

  const textBlock = response.content.find((b) => b.type === 'text');
  return textBlock ? textBlock.text : '';
}

export async function generate(plot) {
  console.log('\n' + '═'.repeat(50));
  console.log(`Episode ${plot.episode}:「${plot.title}」`);
  console.log('═'.repeat(50) + '\n');

  // Step 1: 史実検証・空白仮説・誤読設計 (Claude Opus)
  console.log('[Step1] 史実検証・空白仮説・誤読設計 (Claude Opus 4.6)...');
  const step1Output = await generateStep1(plot);
  console.log('Step1 完了\n');

  // Step 2: 本文生成 (Claude Sonnet) — 字数不足時は最大2回再生成
  const MAX_RETRIES = 2;
  let novelText = '';

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt === 0) {
      console.log('[Step2] 本文生成 (Claude Sonnet 4.6)...');
    } else {
      console.log(`[Step2] 再生成中 (${attempt}/${MAX_RETRIES})...`);
    }

    novelText = await generateNovel(plot, step1Output, attempt);
    const charCount = novelText.length;
    console.log(`生成字数: ${charCount.toLocaleString()} 字`);

    if (charCount >= 4000) {
      break;
    }

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
}
