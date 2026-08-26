# market-automation

レンタルラウンジ橋本の運営自動化ツール。

## 構成

| ファイル | 役割 |
|---|---|
| `src/watch-competitors.mjs` | 競合ウォッチ。自スペース+U-ROOM橋本1・2の公開ページから評価・レビュー件数・価格表示・OPEN割引の継続状況を取得し `snapshots/日付.md` に保存 |
| `src/mcp-server.mjs` | Claude Code / Claude Desktop から使うMCPサーバー。`market_snapshot` / `space_detail`(公開情報、資格情報不要)と、`login` / `dashboard_screenshot`(実験的、要資格情報) |
| `src/lib.mjs` | 共通処理(取得・抽出) |

## セットアップ(ローカルPC)

```bash
cd automation
npm install
npm run watch        # 競合スナップショットを取得
```

スナップショットをコミットしておくと、`git diff` がそのまま競合の動きの履歴になる。

## MCPサーバーの登録(Claude Code)

```bash
claude mcp add market-automation \
  -e SPACEMARKET_EMAIL=あなたのメール \
  -e SPACEMARKET_PASSWORD=... \
  -e INSTABASE_EMAIL=... \
  -e INSTABASE_PASSWORD=... \
  -- node /絶対パス/marketAutomation/automation/src/mcp-server.mjs
```

公開情報ツール(`market_snapshot` など)だけ使うなら `-e` は全部省略してよい。

## 資格情報の扱い(重要)

- **パスワードをチャットに直接貼らない。** 上記のように環境変数で渡すか、Claude Code on the web の場合は環境設定の環境変数に設定する。
- 自分のアカウント・自分の掲載の運用に限って使うこと。プラットフォームの規約上、自動アクセスはグレーなので、実行頻度は人間相当(1日数回まで)に抑える。
- 大きな作業をさせた後はパスワードを変更しておくと安全。
- 初回ログインはCAPTCHA・メール認証コードで止まる可能性が高い。その場合は対話セッションでコードを入力して突破し、`.auth/*.json`(セッション保存、gitignore済み)を作ってから自動化する。

## 既知の制約

- スペースマーケットはクラウド/データセンターIPからの取得を429でブロックすることがある。ローカルPCからの実行を推奨(インスタベースはどこからでも取得可)。
- `login` / `dashboard_screenshot` は実験的。実際の画面でセレクタ調整が必要になったら、Claudeとの対話セッションで画面を見ながら育てる想定。掲載編集(タイトル・料金・定員変更)ツールはログイン導線が確立してから追加する。
