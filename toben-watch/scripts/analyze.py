#!/usr/bin/env python3
"""質問主意書・答弁書ペアを Claude で解析し、評価 JSON を生成する。

使い方:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...   # または `ant auth login`
    python3 scripts/analyze.py data/raw/sangiin-214-014.json
        → data/analyses/sangiin-214-014.json を生成

モデルは claude-opus-5（適応的思考が既定で有効）。構造化出力
（output_config.format）でスキーマ通りの JSON を受け取るため、
出力のパースは不要。サーバーサイドフォールバックを既定で有効に
しているので、安全システムによる拒否時は自動で代替モデルが応答する。
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import anthropic

MODEL = "claude-opus-5"

# 回避パターンの分類（サイト側の凡例と一致させること）
PATTERNS = """
P1 趣旨不明型: 「お尋ねの趣旨（意味するところ）が明らかではない」として答えない
P2 差し控え型: 「お答えを差し控えたい」として答えない
P3 作業困難型: 「膨大な作業を要する」等を理由に資料・数値を示さない
P4 過去答弁引用型: 過去の答弁の引用のみで、現在の説明・根拠を示さない
P5 まとめ答弁型: 複数の設問を一括りにして個別の論点への回答を薄める
P6 指標すり替え型: 問われた数値・定義と異なるものに断りなく置き換えて答える
P7 仮定不応答型: 「仮定の質問にはお答えできない」として答えない
P8 論点スルー型: 質問者が示した論拠・前提に反論も説明もせず結論だけ述べる
P9 一概困難型: 「個別具体の事情により一概にお答えすることは困難」として基準を示さない
""".strip()

SYSTEM = f"""あなたは国会の質問主意書と政府答弁書を分析する専門アナリストです。
公開された質問・答弁の全文のみに基づき、次の2つを行ってください。

1. わかりやすい解説: 各設問が「何を聞いているのか」、答弁が「何と答えたのか」を、
   前提知識のない読者に伝わる日本語に翻訳する。専門用語は glossary で解説する。

2. 答弁の質の評価: 各設問について、答弁が質問に実質的に答えているかを判定する。
   verdict は answered（回答）/ partial（部分回答）/ evaded（実質回答なし）/
   refused_with_reason（理由を明示した回答拒否）の4値。
   回避の手法は以下のパターン分類でタグ付けする。

{PATTERNS}

評価の原則:
- 政治的立場は評価しない。評価対象は「質問に答えているか」という応答の質のみ。
- 誠実な対応（具体的データの開示、立場の明言、丁寧な理由説明）は good_point として
  積極的にハイライトする。
- 質問側に設計上の問題（曖昧さ、制度理解の誤り）がある場合は question_quality で
  公平に指摘する。答弁の評価はその点を割り引いて行う。
- 引用（excerpt）は原文から正確に抜粋し、創作しない。
- overall.score は 0-100、grade は A（誠実に回答）〜E（ほぼ回答拒否）の5段階。"""


def build_schema() -> dict:
    """解析結果 JSON のスキーマ（data/analyses/*.json と同形）。"""
    pattern = {
        "type": "object",
        "properties": {"code": {"type": "string"}, "label": {"type": "string"}},
        "required": ["code", "label"],
        "additionalProperties": False,
    }
    axis = {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "score": {"type": "integer"},
            "note": {"type": "string"},
        },
        "required": ["label", "score", "note"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {
            "q_id": {"type": "string"},
            "question_excerpt": {"type": "string"},
            "question_plain": {"type": "string"},
            "answer_section": {"type": "string"},
            "answer_excerpt": {"type": "string"},
            "answer_plain": {"type": "string"},
            "verdict": {"enum": ["answered", "partial", "evaded", "refused_with_reason"]},
            "verdict_label": {"type": "string"},
            "patterns": {"type": "array", "items": pattern},
            "responsiveness": {"type": "integer"},
            "commentary": {"type": "string"},
            "good_point": {"type": ["string", "null"]},
        },
        "required": [
            "q_id", "question_excerpt", "question_plain", "answer_section",
            "answer_excerpt", "answer_plain", "verdict", "verdict_label",
            "patterns", "responsiveness", "commentary", "good_point",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "topic_tags": {"type": "array", "items": {"type": "string"}},
            "glossary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"term": {"type": "string"}, "definition": {"type": "string"}},
                    "required": ["term", "definition"],
                    "additionalProperties": False,
                },
            },
            "tldr": {"type": "array", "items": {"type": "string"}},
            "question_overview": {"type": "string"},
            "answer_overview": {"type": "string"},
            "items": {"type": "array", "items": item},
            "overall": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer"},
                    "grade": {"enum": ["A", "B", "C", "D", "E"]},
                    "grade_scale": {"type": "string"},
                    "headline": {"type": "string"},
                    "axes": {
                        "type": "object",
                        "properties": {
                            "responsiveness": axis,
                            "specificity": axis,
                            "evidence": axis,
                            "clarity": axis,
                        },
                        "required": ["responsiveness", "specificity", "evidence", "clarity"],
                        "additionalProperties": False,
                    },
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "grade", "grade_scale", "headline", "axes",
                             "strengths", "weaknesses"],
                "additionalProperties": False,
            },
            "question_quality": {
                "type": "object",
                "properties": {"score": {"type": "integer"}, "comment": {"type": "string"}},
                "required": ["score", "comment"],
                "additionalProperties": False,
            },
        },
        "required": ["topic_tags", "glossary", "tldr", "question_overview",
                     "answer_overview", "items", "overall", "question_quality"],
        "additionalProperties": False,
    }


def analyze(raw: dict) -> dict:
    client = anthropic.Anthropic()
    user_content = (
        f"# 質問主意書（{raw['title']}）\n\n{raw['question_text']}\n\n"
        f"# 答弁書\n\n{raw['answer_text']}"
    )
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": build_schema()}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    if response.stop_reason == "refusal":
        detail = response.stop_details.explanation if response.stop_details else ""
        sys.exit(f"モデルが応答を拒否しました: {detail}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} data/raw/<id>.json")
    raw_path = Path(sys.argv[1])
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    result = analyze(raw)
    meta = raw.get("meta", {})
    # 答弁書冒頭の「内閣総理大臣　石破　茂」等から答弁者を拾う
    m = re.search(r"^(内閣総理大臣)\s*(.+)$", raw["answer_text"], re.M)
    answerer_title = m.group(1) if m else ""
    answerer_name = m.group(2).replace("　", "").strip() if m else ""
    record = {
        "id": raw["id"],
        "source": {
            "title": raw["title"],
            "house_label": "参議院" if raw["house"] == "sangiin" else "衆議院",
            "session": raw["session"],
            "number": raw["number"],
            "submitter": meta.get("提出者", "").replace("　", "").removesuffix("君"),
            "submitted_on": meta.get("提出日", ""),
            "answered_on": meta.get("答弁書受領日", ""),
            "answerer_name": answerer_name,
            "answerer_title": answerer_title,
            "urls": raw["urls"],
        },
        **result,
        "analysis_note": "この解析はAIによる試作評価です。評価は公開された質問・答弁の"
                         "全文のみに基づき、提出者・政党への支持・不支持を意味しません。",
        "analyzed_at": date.today().isoformat(),
        "analyzer": MODEL,
    }

    out_dir = raw_path.resolve().parent.parent / "analyses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{raw['id']}.json"
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}  (grade {record['overall']['grade']}, "
          f"score {record['overall']['score']})")


if __name__ == "__main__":
    main()
