#!/usr/bin/env python3
"""参議院の質問主意書・答弁書ペアを取得して JSON 化する。

使い方:
    python3 scripts/fetch_syuisyo.py 214 14
        → data/raw/sangiin-214-014.json を生成

参議院サイトの URL 構造:
    明細:     .../syuisyo/{回次}/meisai/m{回次}{番号:03d}.htm
    質問本文: .../syuisyo/{回次}/syuh/s{回次}{番号:03d}.htm
    答弁本文: .../syuisyo/{回次}/touh/t{回次}{番号:03d}.htm

標準ライブラリのみで動く（requests 等は不要）。
"""

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo"

# ページ末尾のフッタ開始行。これ以降は本文ではない。
FOOTER_MARKERS = ("利用案内", "All rights reserved.")

# 明細ページから拾うメタ情報の項目名
META_KEYS = (
    "件名", "提出回次", "提出番号", "提出日", "提出者",
    "備考", "転送日", "答弁書受領日",
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "toben-watch/0.1 (prototype)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8-sig", errors="replace")


def html_to_lines(page: str) -> list[str]:
    """HTML から本文テキストを行のリストとして取り出す。"""
    m = re.search(r"<body.*?>(.*)</body>", page, re.S | re.I)
    body = m.group(1) if m else page
    body = re.sub(r"<(script|style).*?</\1>", "", body, flags=re.S | re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</(p|div|h\d|li|tr|td|th)>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    lines = [ln.strip().replace("　", "　") for ln in body.split("\n")]
    return [ln for ln in lines if ln]


def cut_footer(lines: list[str]) -> list[str]:
    for i, ln in enumerate(lines):
        if any(ln.startswith(mk) for mk in FOOTER_MARKERS):
            return lines[:i]
    return lines


def extract_main(lines: list[str], start_pattern: str) -> str:
    """ナビゲーション部分を捨て、start_pattern にマッチする行から本文を返す。"""
    lines = cut_footer(lines)
    for i, ln in enumerate(lines):
        if re.match(start_pattern, ln):
            return "\n".join(lines[i:])
    # マッチしない場合はナビらしき部分（「トップ >」まで）を落として全部返す
    for i, ln in enumerate(lines):
        if ln.startswith("トップ"):
            return "\n".join(lines[i + 1:])
    return "\n".join(lines)


def extract_meta(lines: list[str]) -> dict:
    lines = cut_footer(lines)
    meta = {}
    for i, ln in enumerate(lines):
        if ln in META_KEYS and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt not in META_KEYS:
                meta[ln] = nxt
    return meta


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <回次> <提出番号>   例: {sys.argv[0]} 214 14")
    session, number = int(sys.argv[1]), int(sys.argv[2])
    code = f"{session}{number:03d}"
    urls = {
        "meisai": f"{BASE}/{session}/meisai/m{code}.htm",
        "question": f"{BASE}/{session}/syuh/s{code}.htm",
        "answer": f"{BASE}/{session}/touh/t{code}.htm",
    }

    meta = extract_meta(html_to_lines(fetch(urls["meisai"])))
    question = extract_main(html_to_lines(fetch(urls["question"])), r"^質問第")
    answer = extract_main(html_to_lines(fetch(urls["answer"])), r"^内閣参質")

    record = {
        "id": f"sangiin-{session}-{number:03d}",
        "house": "sangiin",
        "session": session,
        "number": number,
        "title": meta.get("件名", ""),
        "meta": meta,
        "urls": urls,
        "question_text": question,
        "answer_text": answer,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    out_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{record['id']}.json"
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}  ({len(question)} chars question / {len(answer)} chars answer)")


if __name__ == "__main__":
    main()
