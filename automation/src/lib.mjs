import { setGlobalDispatcher, EnvHttpProxyAgent } from "undici";

// 管理された実行環境(HTTPS_PROXY経由)でもローカルでも動くようにする
if (process.env.HTTPS_PROXY || process.env.HTTP_PROXY) {
  setGlobalDispatcher(new EnvHttpProxyAgent());
}

export const SPACES = [
  {
    key: "rental-lounge",
    name: "Rental Lounge橋本(自)",
    platform: "spacemarket",
    url: "https://www.spacemarket.com/spaces/rental-lounge-h/",
  },
  {
    key: "u-room-1",
    name: "U-ROOM橋本1",
    platform: "spacemarket",
    url: "https://www.spacemarket.com/spaces/vkfm-r0uuhiyqt6d/",
  },
  {
    key: "u-room-2",
    name: "U-ROOM橋本2",
    platform: "spacemarket",
    url: "https://www.spacemarket.com/spaces/0ha7hs3g-h_9tito/",
  },
  {
    key: "rental-lounge-ib",
    name: "レンタルラウンジ橋本(インスタベース)",
    platform: "instabase",
    url: "https://www.instabase.jp/space/6523901280",
  },
  {
    key: "u-room-1-ib",
    name: "U-ROOM橋本1(インスタベース)",
    platform: "instabase",
    url: "https://www.instabase.jp/space/3146280697",
  },
];

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";

export async function fetchHtml(url, tries = 3) {
  for (let i = 0; ; i++) {
    const res = await fetch(url, {
      headers: { "user-agent": UA, "accept-language": "ja" },
    });
    if (res.ok) return await res.text();
    if (i >= tries - 1) {
      const hint =
        res.status === 429
          ? " (レート制限。クラウド/データセンターIPからはブロックされることがあります。ローカルPCで実行してください)"
          : "";
      throw new Error(`HTTP ${res.status} for ${url}${hint}`);
    }
    await new Promise((r) => setTimeout(r, 3000 * 3 ** i));
  }
}

function extractJsonLd(html) {
  const blocks = [];
  const re =
    /<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g;
  let m;
  while ((m = re.exec(html))) {
    try {
      const parsed = JSON.parse(m[1]);
      blocks.push(...(Array.isArray(parsed) ? parsed : [parsed]));
    } catch {
      // 壊れたJSON-LDは無視
    }
  }
  return blocks;
}

function findDeep(obj, key, out = []) {
  if (!obj || typeof obj !== "object") return out;
  if (obj[key] !== undefined) out.push(obj[key]);
  for (const v of Object.values(obj)) findDeep(v, key, out);
  return out;
}

// 1スペース分のスナップショット。セレクタ非依存(JSON-LD+キーワード)なので壊れにくい
export async function snapshotSpace(space) {
  const html = await fetchHtml(space.url);
  const ld = extractJsonLd(html);

  const rating = findDeep(ld, "aggregateRating")[0];
  const priceRanges = [
    ...findDeep(ld, "priceRange"),
    ...findDeep(ld, "lowPrice"),
    ...findDeep(ld, "highPrice"),
  ];
  const title = (html.match(/<title[^>]*>([^<]+)<\/title>/) || [])[1]?.trim();

  const yenMatches = [...html.matchAll(/[¥￥]\s?([\d,]{3,7})/g)]
    .map((m) => Number(m[1].replaceAll(",", "")))
    .filter((n) => n >= 200 && n <= 20000);

  return {
    key: space.key,
    name: space.name,
    url: space.url,
    fetchedAt: new Date().toISOString(),
    title: title ?? null,
    rating: rating
      ? {
          value: rating.ratingValue ?? null,
          count: rating.reviewCount ?? rating.ratingCount ?? null,
        }
      : null,
    priceRange: priceRanges.length ? priceRanges : null,
    minYenSeen: yenMatches.length ? Math.min(...yenMatches) : null,
    maxYenSeen: yenMatches.length ? Math.max(...yenMatches) : null,
    openDiscountActive: /OPEN割引|オープン割引/.test(html),
    campaignKeywords: ["直前割", "早割", "夏割", "先着"].filter((k) =>
      html.includes(k)
    ),
  };
}

export async function snapshotAll() {
  const results = [];
  for (const space of SPACES) {
    try {
      results.push(await snapshotSpace(space));
    } catch (e) {
      results.push({ key: space.key, name: space.name, url: space.url, error: String(e) });
    }
    // 行儀よく: 連続アクセスの間隔を空ける
    await new Promise((r) => setTimeout(r, 1500));
  }
  return results;
}

export function toMarkdown(results) {
  const lines = [
    `# 橋本 競合スナップショット ${new Date().toISOString().slice(0, 10)}`,
    "",
    "| スペース | 評価 | 件数 | 最低額表示 | OPEN割 | キャンペーン語 |",
    "|---|---|---|---|---|---|",
  ];
  for (const r of results) {
    if (r.error) {
      lines.push(`| ${r.name} | 取得失敗 | - | - | - | ${r.error} |`);
      continue;
    }
    lines.push(
      `| ${r.name} | ${r.rating?.value ?? "-"} | ${r.rating?.count ?? "-"} | ` +
        `${r.minYenSeen ? "¥" + r.minYenSeen : "-"} | ` +
        `${r.openDiscountActive ? "継続中" : "なし"} | ${r.campaignKeywords?.join("・") || "-"} |`
    );
  }
  lines.push("", "詳細タイトル:");
  for (const r of results) {
    if (r.title) lines.push(`- ${r.name}: ${r.title}`);
  }
  return lines.join("\n");
}
