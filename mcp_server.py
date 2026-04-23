"""
Dify Workflow DSL MCP Server

Tools:
  list_node_types       - 利用可能なノード種別一覧
  get_node_schema       - 指定ノードの型定義を返す
  get_example           - fixture YAMLサンプルを返す
  list_examples         - サンプル一覧
  validate_dsl          - DSL YAMLの基本バリデーション
"""

import os
import yaml
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Difyソースのパス（環境変数で上書き可能）
DIFY_ROOT = Path(os.environ.get("DIFY_ROOT", str(Path.home() / "Desktop/dify")))

NODES_TS_DIR = DIFY_ROOT / "web/app/components/workflow/nodes"
FIXTURES_DIR = DIFY_ROOT / "api/tests/fixtures/workflow"
WORKFLOW_TYPES = DIFY_ROOT / "web/types/workflow.ts"

mcp = FastMCP("dify-dsl")


# ノード名 → フロントエンドディレクトリ名のマッピング
NODE_DIR_MAP: dict[str, str] = {
    "start": "start",
    "end": "end",
    "answer": "answer",
    "llm": "llm",
    "if-else": "if-else",
    "code": "code",
    "knowledge-retrieval": "knowledge-retrieval",
    "knowledge-base": "knowledge-base",
    "iteration": "iteration",
    "iteration-start": "iteration-start",
    "loop": "loop",
    "loop-start": "loop-start",
    "loop-end": "loop-end",
    "http-request": "http",
    "tool": "tool",
    "template-transform": "template-transform",
    "variable-assigner": "variable-assigner",
    "assigner": "assigner",
    "parameter-extractor": "parameter-extractor",
    "question-classifier": "question-classifier",
    "document-extractor": "document-extractor",
    "list-operator": "list-operator",
    "agent": "agent",
    "human-input": "human-input",
    "trigger-webhook": "trigger-webhook",
    "trigger-schedule": "trigger-schedule",
    "trigger-plugin": "trigger-plugin",
}


@mcp.tool()
def list_node_types() -> str:
    """利用可能なDifyワークフローのノード種別を一覧で返す"""
    available = []
    for node_type, dir_name in NODE_DIR_MAP.items():
        types_file = NODES_TS_DIR / dir_name / "types.ts"
        has_schema = types_file.exists()
        available.append(f"{'✓' if has_schema else '○'} {node_type}")

    return "## ノード種別一覧\n✓=型定義あり  ○=型定義なし\n\n" + "\n".join(available)


@mcp.tool()
def get_node_schema(node_type: str) -> str:
    """
    指定したノード種別の型定義（TypeScript）を返す。
    types.ts が存在しない場合は共通のワークフロー型定義から関連部分を返す。

    Args:
        node_type: ノード種別 (例: "llm", "if-else", "knowledge-retrieval")
    """
    dir_name = NODE_DIR_MAP.get(node_type)
    if not dir_name:
        return f"Error: '{node_type}' は未知のノード種別です。list_node_types() で確認してください。"

    types_file = NODES_TS_DIR / dir_name / "types.ts"
    default_file = NODES_TS_DIR / dir_name / "default.ts"

    result = []

    if types_file.exists():
        result.append(f"## {node_type} - types.ts\n```typescript\n{types_file.read_text()}\n```")
    else:
        result.append(f"## {node_type}\n（types.ts なし）")

    if default_file.exists():
        result.append(f"\n## {node_type} - default.ts（デフォルト値）\n```typescript\n{default_file.read_text()}\n```")

    # 共通型定義から関連部分を補足
    if WORKFLOW_TYPES.exists():
        common = WORKFLOW_TYPES.read_text()
        # CommonNodeType, Memory, ModelConfig など参照される型を抽出
        relevant_lines = []
        capture = False
        for line in common.splitlines():
            if any(kw in line for kw in ["export type CommonNodeType", "export type Memory", "export type ModelConfig", "export enum VarType", "export type Variable", "export type ValueSelector"]):
                capture = True
            if capture:
                relevant_lines.append(line)
                if line.strip() == "}" and capture:
                    relevant_lines.append("")
                    capture = False
        if relevant_lines:
            result.append(f"\n## 共通型定義（参照用）\n```typescript\n" + "\n".join(relevant_lines[:80]) + "\n```")

    return "\n".join(result)


@mcp.tool()
def list_examples() -> str:
    """利用可能なfixture YAMLサンプルの一覧を返す"""
    if not FIXTURES_DIR.exists():
        return f"Error: fixtures ディレクトリが見つかりません: {FIXTURES_DIR}"

    files = sorted(FIXTURES_DIR.glob("*.yml"))
    lines = ["## サンプルDSL一覧\n"]
    for f in files:
        lines.append(f"- {f.stem}")

    return "\n".join(lines)


@mcp.tool()
def get_example(name: str) -> str:
    """
    fixture YAMLサンプルを返す。

    Args:
        name: ファイル名（拡張子なし）例: "basic_chatflow", "conditional_hello_branching_workflow"
    """
    path = FIXTURES_DIR / f"{name}.yml"
    if not path.exists():
        available = [f.stem for f in FIXTURES_DIR.glob("*.yml")]
        return f"Error: '{name}' が見つかりません。\n利用可能: {', '.join(available)}"

    return f"## {name}.yml\n```yaml\n{path.read_text()}\n```"


@mcp.tool()
def validate_dsl(yaml_content: str) -> str:
    """
    DSL YAMLの基本的な構造バリデーションを行う。

    Args:
        yaml_content: バリデーションするYAML文字列
    """
    errors = []
    warnings = []

    # YAMLパース
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return f"Error: YAMLパースエラー\n{e}"

    if not isinstance(data, dict):
        return "Error: ルートがdictではありません"

    # 必須トップレベルキー
    for key in ["app", "kind", "version", "workflow"]:
        if key not in data:
            errors.append(f"必須キー '{key}' がありません")

    if errors:
        return "## バリデーション失敗\n" + "\n".join(f"- {e}" for e in errors)

    # app セクション
    app = data.get("app", {})
    if "mode" not in app:
        errors.append("app.mode がありません")
    if "name" not in app:
        warnings.append("app.name がありません")

    # workflow.graph
    workflow = data.get("workflow", {})
    graph = workflow.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        errors.append("workflow.graph.nodes が空です")

    # ノードIDの重複チェック
    node_ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    if len(node_ids) != len(set(node_ids)):
        errors.append("ノードIDに重複があります")

    # startノードの存在チェック
    node_types = [n.get("data", {}).get("type") for n in nodes if isinstance(n, dict)]
    if "start" not in node_types:
        errors.append("startノードがありません")

    # エッジの参照整合性チェック
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = edge.get("source")
        tgt = edge.get("target")
        if src not in node_ids:
            errors.append(f"エッジのsource '{src}' が存在しないノードIDを参照しています")
        if tgt not in node_ids:
            errors.append(f"エッジのtarget '{tgt}' が存在しないノードIDを参照しています")

    if errors:
        return "## バリデーション失敗\n" + "\n".join(f"- {e}" for e in errors)

    result = f"## バリデーション成功\n- ノード数: {len(nodes)}\n- エッジ数: {len(edges)}\n- モード: {app.get('mode')}"
    if warnings:
        result += "\n\n### 警告\n" + "\n".join(f"- {w}" for w in warnings)
    return result


if __name__ == "__main__":
    mcp.run()
