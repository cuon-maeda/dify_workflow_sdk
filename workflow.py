from __future__ import annotations
from typing import Literal
import yaml

from .nodes import BaseNode

AppMode = Literal["workflow", "advanced-chat", "chat", "agent-chat", "completion"]

_X_STEP = 304
_Y_CENTER = 227


class Workflow:
    def __init__(
        self,
        name: str,
        mode: AppMode = "advanced-chat",
        description: str = "",
        icon: str = "🤖",
        icon_background: str = "#FFEAD5",
    ):
        self.name = name
        self.mode = mode
        self.description = description
        self.icon = icon
        self.icon_background = icon_background
        self._nodes: list[BaseNode] = []
        self._edges: list[dict] = []

    def add(self, node: BaseNode) -> BaseNode:
        self._nodes.append(node)
        return node

    def connect(self, source: BaseNode, target: BaseNode, source_handle: str = "source") -> "Workflow":
        edge_id = f"{source.id}-{target.id}"
        self._edges.append({
            "id": edge_id,
            "source": source.id,
            "target": target.id,
            "sourceHandle": source_handle,
            "targetHandle": "target",
            "type": "custom",
            "zIndex": 0,
            "data": {
                "sourceType": source._node_type,
                "targetType": target._node_type,
                "isInIteration": False,
                "isInLoop": False,
            },
        })
        return self

    def chain(self, *nodes: BaseNode) -> "Workflow":
        for i in range(len(nodes) - 1):
            self.connect(nodes[i], nodes[i + 1])
        return self

    def _build_graph(self) -> dict:
        node_dicts = []
        for i, node in enumerate(self._nodes):
            x = 30 + i * _X_STEP
            node_dicts.append(node.to_dict(x=x, y=_Y_CENTER))
        return {"nodes": node_dicts, "edges": self._edges, "viewport": {"x": 0, "y": 0, "zoom": 0.7}}

    def _build_features(self) -> dict:
        base: dict = {
            "file_upload": {"enabled": False},
            "opening_statement": "",
            "retriever_resource": {"enabled": False},
            "sensitive_word_avoidance": {"enabled": False},
            "speech_to_text": {"enabled": False},
            "suggested_questions": [],
            "suggested_questions_after_answer": {"enabled": False},
            "text_to_speech": {"enabled": False},
        }
        if self.mode == "advanced-chat":
            base["retriever_resource"] = {"enabled": True}
        return base

    def to_dict(self) -> dict:
        return {
            "app": {
                "description": self.description,
                "icon": self.icon,
                "icon_background": self.icon_background,
                "mode": self.mode,
                "name": self.name,
                "use_icon_as_answer_icon": False,
            },
            "dependencies": [],
            "kind": "app",
            "version": "0.6.0",
            "workflow": {
                "conversation_variables": [],
                "environment_variables": [],
                "features": self._build_features(),
                "graph": self._build_graph(),
            },
        }

    def export(self, path: str) -> None:
        data = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"Exported: {path}")

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), allow_unicode=True, default_flow_style=False, sort_keys=False)
