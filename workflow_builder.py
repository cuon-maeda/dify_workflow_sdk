from __future__ import annotations

import sys
import os

# Allow running as a standalone script from within the package directory
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
_parent = os.path.dirname(_here)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    from dify_workflow_sdk import Workflow, Start, LLM, Answer, End, IfElse, Code, KnowledgeRetrieval
except ModuleNotFoundError:
    from workflow import Workflow  # type: ignore[no-redef]
    from nodes import Start, LLM, Answer, End, IfElse, Code, KnowledgeRetrieval  # type: ignore[no-redef]

# Node build priority: earlier types must be created first so their IDs
# are in node_map before downstream nodes (LLM, Answer) call resolve_vars().
_NODE_PRIORITY: dict[str, int] = {
    "start": 0,
    "knowledge-retrieval": 1,
    "code": 1,
    "if-else": 2,
    "llm": 3,
    "answer": 4,
    "end": 4,
}


def build_workflow_yaml(spec: dict) -> str:
    name = spec.get("name", "My Workflow")
    mode = spec.get("mode", "advanced-chat")

    wf = Workflow(name=name, mode=mode)
    node_map: dict[str, object] = {}  # symbolic_id -> SDK node

    node_defs = spec.get("nodes", [])
    sorted_defs = sorted(
        node_defs,
        key=lambda n: _NODE_PRIORITY.get(n.get("type", ""), 2),
    )

    def resolve_vars(text: str) -> str:
        for sym_id, sdk_node in node_map.items():
            text = text.replace(f"{{#{sym_id}.", f"{{#{sdk_node.id}.")
        return text

    for node_def in sorted_defs:
        sym_id = node_def.get("id", "")
        node_type = node_def.get("type", "")
        node = _build_node(wf, node_def, node_map, resolve_vars)
        if node is not None and sym_id:
            node_map[sym_id] = node

    _wire_edges(wf, spec, node_map)
    return wf.to_yaml()


def _build_node(wf: Workflow, node_def: dict, node_map: dict, resolve_vars):
    node_type = node_def.get("type", "")

    if node_type == "start":
        return wf.add(Start())

    if node_type == "llm":
        return wf.add(LLM(
            provider=node_def.get("provider", "openai"),
            model=node_def.get("model", "gpt-4o"),
            system_prompt=resolve_vars(node_def.get("system_prompt", "")),
            user_prompt=resolve_vars(node_def.get("user_prompt", "{{#sys.query#}}")),
        ))

    if node_type == "answer":
        content = resolve_vars(node_def.get("content", ""))
        return wf.add(Answer(content=content))

    if node_type == "end":
        node = wf.add(End())
        for out in node_def.get("outputs", []):
            ref_node = node_map.get(out.get("node_id", ""))
            if ref_node:
                node.add_output(
                    variable=out["variable"],
                    node_id=ref_node.id,
                    field_name=out.get("field", "text"),
                    value_type=out.get("value_type", "string"),
                )
        return node

    if node_type == "if-else":
        node = wf.add(IfElse())
        for case in node_def.get("cases", []):
            ref_node = node_map.get(case.get("node_id", ""))
            if ref_node:
                node.add_case(
                    node_id=ref_node.id,
                    field_name=case.get("field", "text"),
                    operator=case.get("operator", "contains"),
                    value=case.get("value", ""),
                    case_id=case.get("case_id", "true"),
                )
        return node

    if node_type == "code":
        return wf.add(Code(
            code=node_def.get("code", ""),
            inputs=node_def.get("inputs", {}),
            outputs=node_def.get("outputs", {}),
        ))

    if node_type == "knowledge-retrieval":
        return wf.add(KnowledgeRetrieval(
            dataset_ids=node_def.get("dataset_ids", []),
        ))

    return None


def _wire_edges(wf: Workflow, spec: dict, node_map: dict) -> None:
    chain = spec.get("chain")
    edges = spec.get("edges")

    if chain:
        chain_nodes = [node_map[s] for s in chain if s in node_map]
        if len(chain_nodes) > 1:
            wf.chain(*chain_nodes)
        return

    if edges:
        seen_edges: set[tuple] = set()
        for edge in edges:
            if len(edge) < 2:
                continue
            src_sym, tgt_sym = edge[0], edge[1]
            handle = "source"

            if "/" in src_sym:
                src_sym, handle = src_sym.split("/", 1)

            src_node = node_map.get(src_sym)
            tgt_node = node_map.get(tgt_sym)

            if src_node and tgt_node:
                key = (src_node.id, tgt_node.id, handle)
                if key not in seen_edges:
                    seen_edges.add(key)
                    wf.connect(src_node, tgt_node, source_handle=handle)
