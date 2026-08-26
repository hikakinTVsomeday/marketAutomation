#!/usr/bin/env node
// レンタルラウンジ橋本 運営用MCPサーバー (stdio)
//
// Claude Code への登録例:
//   claude mcp add market-automation \
//     -e SPACEMARKET_EMAIL=... -e SPACEMARKET_PASSWORD=... \
//     -e INSTABASE_EMAIL=... -e INSTABASE_PASSWORD=... \
//     -- node <このリポジトリ>/automation/src/mcp-server.mjs
//
// 資格情報はチャットに貼らず、環境変数で渡すこと。
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { SPACES, snapshotAll, snapshotSpace, toMarkdown } from "./lib.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const authDir = join(root, ".auth");

const server = new McpServer({ name: "market-automation", version: "0.1.0" });

const text = (t) => ({ content: [{ type: "text", text: t }] });

server.tool(
  "market_snapshot",
  "橋本エリアの自スペースと競合(U-ROOM橋本1・2)の公開情報スナップショットを取得する(評価・レビュー件数・価格表示・OPEN割引の継続状況)",
  {},
  async () => text(toMarkdown(await snapshotAll()))
);

server.tool(
  "space_detail",
  "1スペースの公開ページ詳細スナップショット(JSON)を取得する",
  { key: z.enum(SPACES.map((s) => s.key)).describe("対象スペースのキー") },
  async ({ key }) => {
    const space = SPACES.find((s) => s.key === key);
    return text(JSON.stringify(await snapshotSpace(space), null, 2));
  }
);

// ---- ここから下はログインが必要な実験的ツール ----
// 初回はセレクタ調整が必要になる可能性が高い。失敗時は debug-*.png を確認。

const PLATFORMS = {
  spacemarket: {
    loginUrl: "https://www.spacemarket.com/signin/",
    dashboardUrl: "https://www.spacemarket.com/dashboard/",
    emailEnv: "SPACEMARKET_EMAIL",
    passwordEnv: "SPACEMARKET_PASSWORD",
  },
  instabase: {
    loginUrl: "https://www.instabase.jp/login",
    dashboardUrl: "https://www.instabase.jp/host",
    emailEnv: "INSTABASE_EMAIL",
    passwordEnv: "INSTABASE_PASSWORD",
  },
};

async function launchBrowser() {
  const { chromium } = await import("playwright");
  return chromium.launch({ headless: true });
}

async function loginAndSave(platformKey) {
  const p = PLATFORMS[platformKey];
  const email = process.env[p.emailEnv];
  const password = process.env[p.passwordEnv];
  if (!email || !password) {
    return `環境変数 ${p.emailEnv} / ${p.passwordEnv} が未設定です。MCP登録時に -e で渡してください。`;
  }
  mkdirSync(authDir, { recursive: true });
  const browser = await launchBrowser();
  try {
    const ctx = await browser.newContext({ locale: "ja-JP" });
    const page = await ctx.newPage();
    await page.goto(p.loginUrl, { waitUntil: "domcontentloaded" });
    await page.fill('input[type="email"], input[name*="email" i]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
    const shot = join(root, `debug-${platformKey}-after-login.png`);
    await page.screenshot({ path: shot, fullPage: false });
    await ctx.storageState({ path: join(authDir, `${platformKey}.json`) });
    const url = page.url();
    const captcha = (await page.content()).match(/captcha|recaptcha|認証コード/i);
    return [
      `ログイン試行完了。遷移先: ${url}`,
      captcha ? "⚠️ CAPTCHA/追加認証らしき要素を検出。手動での初回ログインが必要かもしれません。" : null,
      `スクリーンショット: ${shot}`,
      `セッション保存: .auth/${platformKey}.json (以後のツールで再利用)`,
    ]
      .filter(Boolean)
      .join("\n");
  } finally {
    await browser.close();
  }
}

server.tool(
  "login",
  "【実験的】ホストアカウントにログインしてセッションを .auth/ に保存する。CAPTCHAや2段階認証があると失敗し、debugスクリーンショットを残す",
  { platform: z.enum(["spacemarket", "instabase"]) },
  async ({ platform }) => {
    try {
      return text(await loginAndSave(platform));
    } catch (e) {
      return text(`ログイン失敗: ${e}\ndebug-${platform}-after-login.png を確認してください。`);
    }
  }
);

server.tool(
  "dashboard_screenshot",
  "【実験的】保存済みセッションでホスト管理画面を開きスクリーンショットを保存する(予約状況・閲覧数などの目視確認用)",
  {
    platform: z.enum(["spacemarket", "instabase"]),
    url: z.string().optional().describe("開くURL。省略時は管理画面トップ"),
  },
  async ({ platform, url }) => {
    const p = PLATFORMS[platform];
    const statePath = join(authDir, `${platform}.json`);
    const browser = await launchBrowser();
    try {
      const ctx = await browser.newContext({ storageState: statePath, locale: "ja-JP" });
      const page = await ctx.newPage();
      await page.goto(url ?? p.dashboardUrl, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
      const shot = join(root, `debug-${platform}-dashboard.png`);
      await page.screenshot({ path: shot, fullPage: true });
      return text(`URL: ${page.url()}\nスクリーンショット: ${shot}`);
    } catch (e) {
      return text(`失敗: ${e}\n先に login ツールでセッションを作成してください。`);
    } finally {
      await browser.close();
    }
  }
);

await server.connect(new StdioServerTransport());
