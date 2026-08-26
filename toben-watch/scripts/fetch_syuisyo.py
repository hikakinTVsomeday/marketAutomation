#!/usr/bin/env python3
"""国会の質問主意書・答弁書ペアを取得して JSON 化する（参議院・衆議院両対応）。

使い方:
    python3 scripts/fetch_syuisyo.py sangiin 214 14
    python3 scripts/fetch_syuisyo.py shugiin 198 99
        → data/raw/{house}-{回次}-{番号}.json を生成

URL 構造:
    参議院（UTF-8）  .../syuisyo/{回次}/meisai/m{回次}{番号:03d}.htm ほか
    衆議院（Shift_JIS）.../shitsumon/a{回次}{番号:03d}.htm（質問）
                       .../shitsumon/b{回次}{番号:03d}.htm（答弁）
                       .../shitsumon/{回次}{番号:03d}.htm（経過）

標準ライブラリのみで動く（requests 等は不要）。
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SANGIIN_BASE = "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo"
SHUGIIN_BASE = "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon"

# ページ末尾のフッタ開始行。これ以降は本文ではない。
FOOTER_MARKERS = ("利用案内", "All rights reserved.", "ホームページについて", "経過へ")

# 参議院の明細ページから拾うメタ情報の項目名
META_KEYS = (
    "件名", "提出回次", "提出番号", "提出日", "提出者",
    "備考", "転送日", "答弁書受領日",
)


def fetch(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "toben-watch/0.1 (prototype)"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read()
            break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)
    head = raw[:2000].decode("ascii", errors="ignore")
    m = re.search(r"charset=([a-zA-Z0-9_-]+)", head)
    enc = (m.group(1) if m else "utf-8").lower()
    if enc in ("shift_jis", "shift-jis", "sjis", "x-sjis"):
        enc = "cp932"
    elif enc == "utf-8":
        enc = "utf-8-sig"
    return raw.decode(enc, errors="replace")


def html_to_lines(page: str) -> list[str]:
    """HTML から本文テキストを行のリストとして取り出す。"""
    m = re.search(r"<body.*?>(.*)</body>", page, re.S | re.I)
    body = m.group(1) if m else page
    body = re.sub(r"<(script|style).*?</\1>", "", body, flags=re.S | re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</(p|div|h\d|li|tr|td|th)>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    lines = [ln.strip() for ln in body.split("\n")]
    return [ln for ln in lines if ln]


def cut_footer(lines: list[str]) -> list[str]:
    for i, ln in enumerate(lines):
        if any(ln.startswith(mk) for mk in FOOTER_MARKERS):
            return lines[:i]
    return lines


def extract_main(lines: list[str], start_pattern: str) -> str:
    """ナビゲーション部分を捨て、start_pattern にマッチする行から本文を返す。"""
    for i, ln in enumerate(lines):
        if re.match(start_pattern, ln):
            return "\n".join(cut_footer(lines[i:]))
    # マッチしない場合はナビらしき部分（「トップ >」まで）を落として全部返す
    for i, ln in enumerate(lines):
        if ln.startswith("トップ"):
            return "\n".join(cut_footer(lines[i + 1:]))
    return "\n".join(cut_footer(lines))


def extract_sangiin_meta(lines: list[str]) -> dict:
    lines = cut_footer(lines)
    meta = {}
    for i, ln in enumerate(lines):
        if ln in META_KEYS and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt not in META_KEYS:
                meta[ln] = nxt
    return meta


def extract_shugiin_meta(q_lines: list[str], a_lines: list[str]) -> dict:
    """衆議院には明細ページのメタ表がないため、本文冒頭から拾う。"""
    meta = {}
    for ln in q_lines:
        if re.match(r"^(平成|令和|昭和).+提出$", ln):
            meta["提出日"] = ln.removesuffix("提出")
        m = re.match(r"^提出者\s*(.+)$", ln)
        if m:
            meta["提出者"] = m.group(1).strip()
        m = re.match(r"^質問第([一二三四五六七八九十百〇0-9]+)号$", ln)
        if m:
            meta["提出番号"] = m.group(1)
    for ln in a_lines:
        if re.match(r"^(平成|令和|昭和).+受領$", ln):
            meta["答弁書受領日"] = ln.removesuffix("受領")
    return meta


def main() -> None:
    if len(sys.argv) != 4 or sys.argv[1] not in ("sangiin", "shugiin"):
        sys.exit(f"usage: {sys.argv[0]} <sangiin|shugiin> <回次> <提出番号>")
    house, session, number = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    code = f"{session}{number:03d}"

    if house == "sangiin":
        urls = {
            "meisai": f"{SANGIIN_BASE}/{session}/meisai/m{code}.htm",
            "question": f"{SANGIIN_BASE}/{session}/syuh/s{code}.htm",
            "answer": f"{SANGIIN_BASE}/{session}/touh/t{code}.htm",
        }
        meta = extract_sangiin_meta(html_to_lines(fetch(urls["meisai"])))
        q_lines = html_to_lines(fetch(urls["question"]))
        a_lines = html_to_lines(fetch(urls["answer"]))
        question = extract_main(q_lines, r"^質問第")
        answer = extract_main(a_lines, r"^内閣参質")
    else:
        urls = {
            "meisai": f"{SHUGIIN_BASE}/{code}.htm",
            "question": f"{SHUGIIN_BASE}/a{code}.htm",
            "answer": f"{SHUGIIN_BASE}/b{code}.htm",
        }
        q_lines = html_to_lines(fetch(urls["question"]))
        a_lines = html_to_lines(fetch(urls["answer"]))
        meta = extract_shugiin_meta(q_lines, a_lines)
        question = extract_main(q_lines, r"^(平成|令和|昭和).+提出$")
        answer = extract_main(a_lines, r"^(平成|令和|昭和).+受領$")

    # 件名: 参議院はメタ表、衆議院は本文中の「〜質問主意書」行から
    title = meta.get("件名", "")
    if not title:
        for ln in question.split("\n"):
            if ln.endswith("質問主意書"):
                title = ln
                break

    record = {
        "id": f"{house}-{session}-{number:03d}",
        "house": house,
        "session": session,
        "number": number,
        "title": title,
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
