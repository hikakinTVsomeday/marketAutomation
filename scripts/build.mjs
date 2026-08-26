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

const upcoming = readdirSync(join(root, "data/upcoming"))
  .filter((f) => f.endsWith(".json"))
  .map((f) => readJSON(join(root, "data/upcoming", f)))
  .sort((a, b) => a.expected_expiration.localeCompare(b.expected_expiration));

const template = readFileSync(join(root, "site/template.html"), "utf8");
const style = readFileSync(join(root, "site/style.css"), "utf8");

const fragment = template
  .replace("/*__STYLE__*/", () => style)
  .replace("/*__DATA__*/[]", () => JSON.stringify(entries))
  .replace("/*__UPCOMING__*/[]", () => JSON.stringify(upcoming));

mkdirSync(join(root, "dist"), { recursive: true });

// full document for GitHub Pages / local file:// — head/body are inferred by the parser
writeFileSync(
  join(root, "dist/index.html"),
  `<!doctype html>\n<html lang="ja">\n<meta charset="utf-8">\n${fragment}\n</html>\n`
);

// --- expiring.ics: subscribable calendar of upcoming expirations (RFC 5545) ---
const icsEscape = (s) => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
// fold long lines at <=70 octets, continuation lines start with a space
const fold = (line) => {
  const bytes = Buffer.from(line, "utf8");
  if (bytes.length <= 70) return line;
  const out = [];
  let cur = "";
  for (const ch of line) {
    if (Buffer.byteLength(cur + ch, "utf8") > 70) { out.push(cur); cur = " " + ch; }
    else cur += ch;
  }
  out.push(cur);
  return out.join("\r\n");
};
const icsDate = (d) => d.replaceAll("-", "");
const nextDay = (d) => {
  const [y, m, day] = d.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, day + 1));
  return t.toISOString().slice(0, 10);
};
const events = upcoming.flatMap((u) => [
  "BEGIN:VEVENT",
  `UID:${u.id}@patent-mine`,
  `DTSTAMP:${icsDate(u.expected_expiration)}T000000Z`,
  `DTSTART;VALUE=DATE:${icsDate(u.expected_expiration)}`,
  `DTEND;VALUE=DATE:${icsDate(nextDay(u.expected_expiration))}`,
  fold(`SUMMARY:${icsEscape(`⛏ ${u.title_ja} が失効（${u.number}）`)}`),
  fold(`DESCRIPTION:${icsEscape(`${u.why_hot}\n原文: ${u.url}\n※満了日は変動し得ます。実施前に最新の法的状況を確認してください。`)}`),
  `URL:${u.url}`,
  "END:VEVENT",
]);
const ics = [
  "BEGIN:VCALENDAR",
  "VERSION:2.0",
  "PRODID:-//patent-mine//expiring-calendar//JA",
  "CALSCALE:GREGORIAN",
  fold("X-WR-CALNAME:特許鉱山｜切れたてカレンダー"),
  "X-WR-TIMEZONE:Asia/Tokyo",
  ...events,
  "END:VCALENDAR",
].join("\r\n") + "\r\n";
writeFileSync(join(root, "dist/expiring.ics"), ics);

console.log(`built dist/index.html — ${entries.length} entries, ${upcoming.length} upcoming (dist/expiring.ics)`);
