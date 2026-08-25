# 特許鉱山 ⛏ Patent Mine

期限が切れて誰でも自由に使えるようになった特許を、読める言葉とビジネスアイデアに
掘り起こすカタログサイト。

特許は「真似されないため」の文章であって、事業のヒント集ではない。
でも切れた特許は人類の共有財産で、その中には本物の市場が眠っている——
だから AI に翻訳させて、カタログにした。

## 仕組み

```
data/patents/*.json   ← Google Patents から取得した特許の生データ（全件 Expired 確認済み）
data/ideas/*.json     ← AI が生成した日本語のビジネスアイデアカード
        │
        ▼
scripts/build.mjs     ← 依存ゼロのビルドスクリプト
        │
        ▼
dist/index.html       ← 単一ファイルの完成サイト（そのままどこにでも置ける）
```

## 開発

```sh
node scripts/build.mjs   # dist/index.html を生成
```

依存パッケージなし。Node 18+ があれば動く。生成された `dist/index.html` を
ブラウザで開くだけ。

## 特許の追加

`pipeline/PROMPT.md` に取得手順・カードのスキーマ・生成の原則をまとめてある。
Claude Code のセッションで「USxxxxxxx を追加して」と頼むのが現状のパイプライン。

## デプロイ

`master` に push すると GitHub Actions が GitHub Pages にデプロイする
（リポジトリ設定で Pages のソースを "GitHub Actions" にしておくこと）。

## 免責

このサイトは趣味プロジェクトであり、法的助言ではない。米国での失効は米国での話。
実施の前には対応する日本特許・関連特許・商標・意匠の状態を確認し、弁理士に相談を。
