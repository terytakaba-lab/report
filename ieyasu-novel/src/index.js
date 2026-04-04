import { generate } from './generate.js';

const plot = {
  episode: 1,
  title: '従順',
  historicalFact: '秀吉死去・五大老五奉行体制発足',
  misreading: '家康は制度に従うと思った',
  blankTheme: 'なぜ家康は従順に見えたのか',
  aiHighlight: '弔問の場の顔ぶれの不自然さ',
  tanakaPhase: '無視',
};

generate(plot).catch((err) => {
  console.error('エラーが発生しました:', err.message);
  process.exit(1);
});
