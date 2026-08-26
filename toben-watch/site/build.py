#!/usr/bin/env python3
"""data/analyses/*.json を site/template.html に埋め込み、site/index.html を生成する。

使い方:
    python3 site/build.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    analyses_dir = ROOT / "data" / "analyses"
    cases = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(analyses_dir.glob("*.json"))
    ]
    if not cases:
        raise SystemExit("data/analyses/ に解析 JSON がありません")

    template = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    # </script> でデータブロックが閉じないよう "</" をエスケープして埋め込む
    payload = json.dumps(cases, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("__DATA__", payload)

    out = ROOT / "site" / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({len(cases)} case(s), {out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
