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

async function generateNovel(plot, step1Output, attempt, prevCharCount = 0) {
  const retryNote = attempt > 0
    ? `\n【重要】前回の出力が${prevCharCount.toLocaleString()}字でした。各層をより詳細に描写して4,000字以上にしてください。\n`
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

以下の4つのセクションを必ず全て書いてください。
各セクションは必ず指定の字数以上で書くこと。

【史実層】（1,000字以上）
${plot.historicalFact}に関する史実を、
日付・人物・記録を引用しながら詳細に描写する。

【分析層】（1,200字以上）
史料をクロス参照し、矛盾や不自然な点を発見する。
「この行動を前後の史料と照合すると——」というフレームで
家康の行動パターンを深く分析する。

【推論層】（1,200字以上）
「記録にはない。しかし私は考える。」というフレームで
${plot.blankTheme}について空白を補完する。
AIの活躍ポイント：${plot.aiHighlight}

【感情層】（800字以上）
分析が感情に滑落する。
体言止め・短い文・沈黙を使って
三成の内面を描写する。
田中フェーズ：${plot.tanakaPhase}

合計4,000字以上6,000字以内で仕上げること。`;

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

  let prevCharCount = 0;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt === 0) {
      console.log('[Step2] 本文生成 (Claude Sonnet 4.6)...');
    } else {
      console.log(`[Step2] 再生成中 (${attempt}/${MAX_RETRIES})...`);
    }

    novelText = await generateNovel(plot, step1Output, attempt, prevCharCount);
    const charCount = novelText.length;
    prevCharCount = charCount;
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
