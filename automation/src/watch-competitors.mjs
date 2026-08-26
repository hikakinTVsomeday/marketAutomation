#!/usr/bin/env node
// 競合ウォッチ: 公開ページから評価・件数・価格帯・キャンペーン状況を取得し、
// snapshots/YYYY-MM-DD.md に保存する。git commitしておけば差分履歴が競合の動きの記録になる。
import { mkdirSync, writeFileSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { snapshotAll, toMarkdown } from "./lib.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const snapDir = join(root, "snapshots");
mkdirSync(snapDir, { recursive: true });

const results = await snapshotAll();
const md = toMarkdown(results);
const today = new Date().toISOString().slice(0, 10);
const file = join(snapDir, `${today}.md`);
writeFileSync(file, md + "\n");

console.log(md);
console.log(`\n保存: ${file}`);

// 前回スナップショットとの簡易比較
const prev = readdirSync(snapDir)
  .filter((f) => f.endsWith(".md") && f < `${today}.md`)
  .sort()
  .at(-1);
if (prev) {
  const prevText = readFileSync(join(snapDir, prev), "utf8");
  if (prevText.includes("継続中") && !md.includes("継続中")) {
    console.log("\n⚠️ 注目: 前回あったOPEN割引の表記が消えています(反攻タイミングの可能性)");
  }
  console.log(`前回: ${prev} と見比べてください (git diff でも可)`);
}
