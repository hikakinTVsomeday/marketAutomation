#!/usr/bin/env node
// 特許鉱山 build — joins data/patents + data/ideas and emits a single-file site
import { readFileSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const readJSON = (p) => JSON.parse(readFileSync(p, "utf8"));

const patents = new Map(
  readdirSync(join(root, "data/patents"))
    .filter((f) => f.endsWith(".json"))
    .map((f) => { const p = readJSON(join(root, "data/patents", f)); return [p.id, p]; })
);

const entries = readdirSync(join(root, "data/ideas"))
  .filter((f) => f.endsWith(".json"))
  .map((f) => readJSON(join(root, "data/ideas", f)))
  .map((idea) => {
    const patent = patents.get(idea.patent_id);
    if (!patent) throw new Error(`no patent data for idea ${idea.patent_id}`);
    return { patent, idea };
  })
  // newest expirations first — the freshest veins on top
  .sort((a, b) => (b.patent.expiration_date || "").localeCompare(a.patent.expiration_date || ""));

const template = readFileSync(join(root, "site/template.html"), "utf8");
const style = readFileSync(join(root, "site/style.css"), "utf8");

const fragment = template
  .replace("/*__STYLE__*/", () => style)
  .replace("/*__DATA__*/[]", () => JSON.stringify(entries));

mkdirSync(join(root, "dist"), { recursive: true });

// full document for GitHub Pages / local file:// — head/body are inferred by the parser
writeFileSync(
  join(root, "dist/index.html"),
  `<!doctype html>\n<html lang="ja">\n<meta charset="utf-8">\n${fragment}\n</html>\n`
);

console.log(`built dist/index.html — ${entries.length} entries`);
