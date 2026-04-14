import { generate } from './generate.js';
import { plots } from './plots.js';

// 引数で話数を指定: node src/index.js 2
// 指定なしの場合は1話
const epArg = parseInt(process.argv[2], 10);
const episode = Number.isFinite(epArg) ? epArg : 1;

const plot = plots.find((p) => p.episode === episode);
if (!plot) {
  console.error(`エラー: episode ${episode} のプロットが見つかりません`);
  process.exit(1);
}

generate(plot).catch((err) => {
  console.error('エラーが発生しました:', err.message);
  process.exit(1);
});
