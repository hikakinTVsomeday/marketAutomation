# 特許 → ビジネスアイデアカード 変換仕様

新しい特許を追加するときの手順と、アイデアカード生成のプロンプト仕様。
Claude Code のセッションで「US1234567 を追加して」と頼めば、この仕様に沿って生成される。

## 手順

1. **特許データの取得** — `https://patents.google.com/patent/<番号>/en` を WebFetch で読み、
   `data/patents/<id>.json` に保存する（スキーマは既存ファイル参照）。
   - **必須条件**: ステータスが `Expired`（Expired - Lifetime / Expired - Fee Related）であること。
     生きている特許は絶対に収録しない。
2. **アイデアカードの生成** — 下の仕様で `data/ideas/<id>.json` を生成する。
3. **ビルド** — `node scripts/build.mjs` で `dist/index.html` を再生成する。

## アイデアカードのスキーマ

```jsonc
{
  "patent_id": "us1234567a",        // data/patents の id と一致
  "category": "tech",               // tech | commerce | food | pet | mobility | hardware | goods（新設可）
  "category_label": "テック",
  "title_ja": "特許の内容の日本語名",
  "catch": "カードの見出し。物語性のある一文",
  "one_liner": "何の特許か+失効年を1〜2文で",
  "plain": "やさしい解説。専門用語を使わず、何がどう動くのかを2〜4文で",
  "why_gold": "なぜ今ビジネスチャンスなのか。市場の空白・追い風を具体的に",
  "story": "背景トリビア。訴訟・失敗・失効後に起きたことなど、事実ベースの物語",
  "ideas": [                        // 2〜3個
    {
      "title": "アイデア名",
      "desc": "何をどう売るか具体的に",
      "target": "誰に",
      "revenue": "どう儲けるか"
    }
  ],
  "difficulty": 3,                  // 採掘難易度 1(週末で試せる)〜5(資本と年単位が要る)
  "capital": "低（〜50万円）など目安",
  "caveats": ["注意点。商標・後続特許・規制など最低2つ"],
  "sourcing": {                     // 任意。海外量産できるモノ系のみ。付けると「⚑ 量産ルート」バッジが出る
    "route": "どこでどう作るか（Alibaba/1688、OEM、金型の要否など）",
    "unit_cost": "FOB単価の目安（あくまで相場観、要見積もり明記）",
    "moq": "最小ロットの目安",
    "keywords": ["Alibaba等で使う検索ワード"],
    "regs": ["輸入・販売時の規制/認証（ST・PSE・技適・食品衛生・PL保険など）"]
  }
}
```

category は現在 `tech / commerce / food / pet / mobility / hardware / goods / toy` を使用中（新設可）。

## 切れたてカレンダー（data/upcoming/）

まだ生きているが失効が近い有名特許は `data/upcoming/<id>.json` に登録する。
ビルド時にサイトの「COMING SOON」欄と、購読可能な `dist/expiring.ics` が生成される。

```jsonc
{
  "id": "us1234567b2",
  "number": "US1234567B2",
  "url": "https://patents.google.com/patent/...",
  "title": "原題",
  "title_ja": "日本語の呼び名",
  "original_assignee": "権利者",
  "expected_expiration": "2027-06-01",   // Google Patents表示のadjusted expiration
  "status_checked": "Active（YYYY-MM-DD に Google Patents で確認）",
  "why_hot": "切れたら何が自由になるか"
}
```

- **必ずGoogle Patentsの現ステータスがActiveであることを確認して登録する**（ネットの失効情報はガセが多い。AeroPressで実証済み）。
- 失効日を過ぎたら通常の手順で本収録し、upcomingから削除する。

## 生成の原則

- **誇張しない**。story は確認できる事実のみ。曖昧なものは書かない。
- **アイデアは個人〜小チームで始められる粒度**に落とす。「大企業がやれば」は禁止。
- **caveats は必ず入れる**。期限切れ＝何でも自由ではない。商標・意匠・後続特許・
  業法規制のうち該当しそうなものを具体的に挙げる。
- 文体はですます調。カタカナ語の乱用を避ける。

## データソース調査メモ（2026-08 時点）

| ソース | 状態 |
|---|---|
| Google Patents（WebFetch経由） | ✅ 使える。Expired 表示も取れる。現行の取得経路 |
| patents.google.com（コンテナから直接） | ❌ Google が自動アクセスを遮断（503） |
| PatentsView API / bulk | ❌ ネットワークポリシーで遮断。APIキーも必要 |
| USPTO Open Data Portal (api.uspto.gov) | 🔑 到達可能だが無料APIキーの登録が必要。大量取得はここが本命 |
| bulkdata.uspto.gov | ❌ ネットワークポリシーで遮断 |
| Hugging Face datasets | ✅ 到達可能。BigPatent/HUPD などの一括データ候補 |
