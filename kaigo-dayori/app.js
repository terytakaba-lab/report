'use strict';

const LIMIT = 10;
const STORAGE_KEY = 'kaigodayori_usage';
const HISTORY_KEY = 'kaigodayori_history';
const HISTORY_MAX = 5;

// ── 使用回数管理 ──────────────────────────────────────────

function getUsage() {
  const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  const now = new Date();
  const monthKey = `${now.getFullYear()}-${now.getMonth()}`;
  if (data.month !== monthKey) return { month: monthKey, count: 0 };
  return data;
}

function saveUsage(usage) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(usage));
}

function updateUsageUI() {
  const usage = getUsage();
  const count = usage.count || 0;
  const dots = document.getElementById('usageDots');
  dots.innerHTML = '';
  for (let i = 0; i < LIMIT; i++) {
    const dot = document.createElement('div');
    dot.className = 'dot' + (i < count ? ' used' : '');
    dots.appendChild(dot);
  }
  document.getElementById('usageCount').textContent = `${count} / ${LIMIT}`;
}

// ── 履歴管理 ──────────────────────────────────────────────

function getHistory() {
  return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
}

function saveToHistory(text) {
  const history = getHistory();
  const now = new Date();
  const label = `${now.getMonth() + 1}/${now.getDate()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  history.unshift({ date: label, text });
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, HISTORY_MAX)));
  renderHistory();
}

function renderHistory() {
  const history = getHistory();
  const area = document.getElementById('historyArea');
  const list = document.getElementById('historyList');

  if (history.length === 0) {
    area.classList.remove('visible');
    return;
  }

  list.innerHTML = '';
  history.forEach((item, idx) => {
    const el = document.createElement('div');
    el.className = 'history-item';
    el.innerHTML = `
      <div class="history-meta">${item.date}</div>
      <div class="history-preview">${item.text}</div>
      <button class="history-copy-btn" data-idx="${idx}">📋 コピー</button>
    `;
    list.appendChild(el);
  });

  list.querySelectorAll('.history-copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx, 10);
      navigator.clipboard.writeText(history[idx].text).then(() => {
        btn.textContent = '✅ コピー済';
        setTimeout(() => { btn.textContent = '📋 コピー'; }, 2000);
      });
    });
  });

  area.classList.add('visible');
}

// ── チップ・トーン選択 ────────────────────────────────────

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => chip.classList.toggle('active'));
});

document.querySelectorAll('.tone-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tone-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

function getSelectedStatus() {
  return [...document.querySelectorAll('.chip.active')].map(c => c.dataset.value);
}

function getSelectedTone() {
  const btn = document.querySelector('.tone-btn.active');
  return btn ? btn.dataset.tone : 'やさしく温かく';
}

// ── エラー表示 ────────────────────────────────────────────

function showError(msg) {
  const el = document.getElementById('errorMsg');
  el.textContent = msg;
  el.classList.add('visible');
  setTimeout(() => el.classList.remove('visible'), 4000);
}

// ── 生成 ──────────────────────────────────────────────────

async function generate() {
  const usage = getUsage();
  if ((usage.count || 0) >= LIMIT) {
    document.getElementById('premiumBanner').classList.add('visible');
    return;
  }

  const status = getSelectedStatus();
  const freeText = document.getElementById('freeText').value.trim();
  const tone = getSelectedTone();

  if (status.length === 0 && !freeText) {
    showError('様子を選択するか、伝えたいことを入力してください');
    return;
  }

  if (typeof ANTHROPIC_API_KEY === 'undefined' || !ANTHROPIC_API_KEY) {
    showError('APIキーが設定されていません。config.js を確認してください。');
    return;
  }

  const prompt = `あなたは介護施設または在宅介護をサポートするアシスタントです。
以下の情報をもとに、介護を受けている方のご家族への日次報告文を生成してください。

今日の様子: ${status.length > 0 ? status.join('、') : '特になし'}
${freeText ? `追加情報: ${freeText}` : ''}
文章のトーン: ${tone}

条件:
- 個人名・施設名は使わない
- 200〜300字程度
- 読んだ家族が安心できる内容
- 「拝啓」などの書き出しは不要、自然な文体で
- 文末は「引き続きどうぞよろしくお願いいたします」等でまとめる
- JSON等の記号は使わず、日本語のみ出力`;

  document.getElementById('generateBtn').disabled = true;
  document.getElementById('loading').classList.add('visible');
  document.getElementById('resultArea').classList.remove('visible');

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        messages: [{ role: 'user', content: prompt }]
      })
    });

    const data = await res.json();
    const text = data.content?.[0]?.text || '';

    if (!text) throw new Error('生成に失敗しました');

    document.getElementById('resultText').textContent = text;
    document.getElementById('resultArea').classList.add('visible');

    // 使用回数・履歴を更新
    usage.count = (usage.count || 0) + 1;
    saveUsage(usage);
    updateUsageUI();
    saveToHistory(text);

    if (usage.count >= LIMIT) {
      document.getElementById('premiumBanner').classList.add('visible');
    }

  } catch (e) {
    showError('生成に失敗しました。もう一度お試しください。');
  } finally {
    document.getElementById('generateBtn').disabled = false;
    document.getElementById('loading').classList.remove('visible');
  }
}

function regenerate() {
  document.getElementById('resultArea').classList.remove('visible');
  generate();
}

function copyText() {
  const text = document.getElementById('resultText').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.action-btn.primary');
    btn.textContent = '✅ コピーしました';
    setTimeout(() => { btn.textContent = '📋 コピーする'; }, 2000);
  });
}

// ── 初期化 ────────────────────────────────────────────────

updateUsageUI();
renderHistory();
