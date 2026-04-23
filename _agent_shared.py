from __future__ import annotations

import json
import os
import re
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

try:
    from mcp_server import list_node_types, get_node_schema, list_examples, get_example, validate_dsl
    _MCP_AVAILABLE = True
except Exception:
    _MCP_AVAILABLE = False

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "list_node_types",
        "description": "Difyワークフローで利用可能なノード種別の一覧を返す。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_node_schema",
        "description": "指定したノード種別のTypeScript型定義を返す。複雑なノードを使う前に必ず確認する。",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_type": {"type": "string", "description": "例: llm, if-else, knowledge-retrieval, code, iteration"}
            },
            "required": ["node_type"],
        },
    },
    {
        "name": "list_examples",
        "description": "利用可能なDify DSL YAMLサンプルの一覧を返す。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_example",
        "description": "実際のDify DSL YAMLサンプルを返す。類似パターンを参照するときに使う。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "例: basic_chatflow, conditional_hello_branching_workflow"}
            },
            "required": ["name"],
        },
    },
    {
        "name": "validate_dsl",
        "description": "生成したDSL YAMLの構造を検証する。",
        "input_schema": {
            "type": "object",
            "properties": {
                "yaml_content": {"type": "string", "description": "検証するYAML文字列"}
            },
            "required": ["yaml_content"],
        },
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
あなたはDifyワークフローデザイナーアシスタントです。
ユーザーが自然言語でDifyワークフローを設計できるよう支援します。
毎回のレスポンスで、JSON形式の設計仕様とMermaid図を必ず返してください。

# ツールの使い方
- `list_node_types`: 利用可能なノード種別を確認するとき
- `get_node_schema`: ノードの正確なフィールド構造を調べるとき（複雑なノードを使う前に必ず確認）
- `get_example`: 類似パターンのサンプルを参照するとき
- `validate_dsl`: 生成したYAMLの構造を検証するとき

# Difyワークフロー概要

## ワークフローモード
- `advanced-chat`: チャット形式。Answerノードで応答を返す。
- `workflow`: バッチ処理。Endノードで終了する。

# 主要ノードタイプ

## Start / Answer / End
- Start: 固定ID `start`。ワークフローの入口。
- Answer: 固定ID `answer`。チャットモードでの出力。
- End: 固定ID `end`。ワークフローモードでの出力。

## LLM
- `provider`: "openai" / "anthropic" など
- `model`: "gpt-4o" / "claude-sonnet-4-6" など
- `system_prompt`: モデルへの指示
- `user_prompt`: デフォルト `"{{#sys.query#}}"`
- 出力参照: `{{#<node_id>.text#}}`

## KnowledgeRetrieval
- `dataset_ids`: 検索対象データセットIDリスト
- 出力参照: `{{#<node_id>.result#}}`

## IfElse（必ずtrue/falseの2分岐のみ）
- `cases[].case_id`: 必ず `"true"`
- `cases[].operator`: contains / == / != / starts with / ends with / is empty / is not empty
- エッジ: `["if1/true", "next"]` / `["if1/false", "fallback"]`

## Code
- `code`: Python関数（main関数を定義）
- `inputs` / `outputs`: 変数定義

# 変数参照構文
`{{#<symbolic_id>.<field>#}}`
- `{{#sys.query#}}` — advanced-chatでのユーザー入力
- `{{#llm1.text#}}` — LLMノード"llm1"の出力
- `{{#kr1.result#}}` — KnowledgeRetrievalノード"kr1"の出力

# レスポンス形式（必須）

ツール呼び出し後、最終レスポンスは必ず以下のJSONのみを返す：

```json
{
  "message": "日本語での説明（3〜5文）",
  "mermaid": "graph LR\\n  Start([Start]) --> LLM[LLM]\\n  LLM --> Answer([Answer])",
  "workflow_spec": {
    "name": "ワークフロー名",
    "mode": "advanced-chat",
    "nodes": [...],
    "chain": ["start", "llm1", "answer"]
  }
}
```

分岐ありの場合は `chain` の代わりに `edges` を使う：
```json
"edges": [
  ["start", "llm1"],
  ["llm1", "if1"],
  ["if1/true", "llm2"],
  ["if1/false", "answer"],
  ["llm2", "answer"]
]
```

## Mermaid図スタイル（graph LR）
- Start/Answer/End: `Start([Start])` 丸角
- LLM: `LLM[LLM: gpt-4o]` 長方形
- IfElse: `Cond{条件}` ひし形
- KnowledgeRetrieval: `KR[(Knowledge)]` シリンダー
- Code: `Code[Code]` 長方形

# 設計原則
1. 複雑なノードを使う前に必ず `get_node_schema` でスキーマを確認する
2. 類似パターンがあれば `get_example` でサンプルを参照する
3. IfElseは2分岐のみ。3カテゴリ以上はKR/LLMノードを並列配置する
4. 多ターン対話では毎回完全な `workflow_spec` を返す
5. 最終JSONの外側に説明文を置かない
"""

# ── Tool executor ─────────────────────────────────────────────────────────────

def _execute_tool(name: str, inputs: dict) -> str:
    if not _MCP_AVAILABLE:
        return "Error: mcp_server が利用できません"
    try:
        if name == "list_node_types":
            return list_node_types()
        if name == "get_node_schema":
            return get_node_schema(inputs["node_type"])
        if name == "list_examples":
            return list_examples()
        if name == "get_example":
            return get_example(inputs["name"])
        if name == "validate_dsl":
            return validate_dsl(inputs["yaml_content"])
        return f"Error: 未知のツール {name}"
    except Exception as e:
        return f"Error: {e}"


def _parse_response(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    json_str = match.group(1) if match else text.strip()
    try:
        data = json.loads(json_str)
        return {
            "message": data.get("message", ""),
            "mermaid": data.get("mermaid"),
            "workflow_spec": data.get("workflow_spec"),
        }
    except json.JSONDecodeError:
        return {"message": text, "mermaid": None, "workflow_spec": None}
