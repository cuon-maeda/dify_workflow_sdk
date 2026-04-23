from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any


def _new_id(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:8]
    return f"{prefix}_{short}" if prefix else short


@dataclass
class BaseNode:
    title: str = ""
    desc: str = ""
    _id: str = field(default_factory=_new_id, init=False)
    _node_type: str = field(default="", init=False)

    @property
    def id(self) -> str:
        return self._id

    def to_dict(self, x: float, y: float) -> dict:
        return {
            "id": self._id,
            "type": "custom",
            "data": self._data(),
            "position": {"x": x, "y": y},
            "positionAbsolute": {"x": x, "y": y},
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "height": 90,
            "width": 244,
        }

    def _data(self) -> dict:
        return {
            "type": self._node_type,
            "title": self.title or self._node_type.capitalize(),
            "desc": self.desc,
            "selected": False,
        }


@dataclass
class Start(BaseNode):
    variables: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._node_type = "start"
        self._id = "start_node"
        if not self.title:
            self.title = "Start"

    def add_text_input(self, name: str, label: str = "", required: bool = True) -> "Start":
        self.variables.append({
            "variable": name,
            "label": label or name,
            "type": "text-input",
            "required": required,
            "options": [],
            "max_length": None,
        })
        return self

    def _data(self) -> dict:
        d = super()._data()
        d["variables"] = self.variables
        return d


@dataclass
class LLM(BaseNode):
    provider: str = ""
    model: str = ""
    system_prompt: str = ""
    user_prompt: str = "{{#start_node.query#}}"

    def __post_init__(self):
        self._node_type = "llm"
        self._id = f"llm_{uuid.uuid4().hex[:6]}"
        if not self.title:
            self.title = "LLM"

    def _data(self) -> dict:
        d = super()._data()
        d.update({
            "model": {
                "provider": self.provider,
                "name": self.model,
                "mode": "chat",
                "completion_params": {"temperature": 0.7},
            },
            "prompt_template": [
                {"role": "system", "text": self.system_prompt},
                {"role": "user", "text": self.user_prompt},
            ],
            "memory": {
                "enabled": False,
                "window": {"enabled": False, "size": 50},
            },
            "context": {"enabled": False, "variable_selector": []},
            "vision": {"enabled": False, "configs": {"variable_selector": []}},
            "variables": [],
            "structured_output": {"enabled": False},
            "retry_config": {
                "enabled": False,
                "max_retries": 1,
                "retry_interval": 1000,
                "exponential_backoff": {"enabled": False, "multiplier": 2, "max_interval": 10000},
            },
        })
        return d


@dataclass
class Answer(BaseNode):
    content: str = ""

    def __post_init__(self):
        self._node_type = "answer"
        self._id = "answer_node"
        if not self.title:
            self.title = "Answer"

    def _data(self) -> dict:
        d = super()._data()
        d["answer"] = self.content
        d["variables"] = []
        return d


@dataclass
class End(BaseNode):
    outputs: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._node_type = "end"
        self._id = "end_node"
        if not self.title:
            self.title = "End"

    def add_output(self, variable: str, node_id: str, field_name: str, value_type: str = "string") -> "End":
        self.outputs.append({
            "variable": variable,
            "value_selector": [node_id, field_name],
            "value_type": value_type,
        })
        return self

    def _data(self) -> dict:
        d = super()._data()
        d["outputs"] = self.outputs
        return d


@dataclass
class IfElse(BaseNode):
    cases: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._node_type = "if-else"
        self._id = f"ifelse_{uuid.uuid4().hex[:6]}"
        if not self.title:
            self.title = "Condition"

    def add_case(
        self,
        node_id: str,
        field_name: str,
        operator: str,
        value: Any,
        case_id: str = "true",
        logical_operator: str = "and",
    ) -> "IfElse":
        self.cases.append({
            "case_id": case_id,
            "logical_operator": logical_operator,
            "conditions": [{
                "variable_selector": [node_id, field_name],
                "comparison_operator": operator,
                "value": value,
                "varType": "string",
            }],
        })
        return self

    def _data(self) -> dict:
        d = super()._data()
        d["cases"] = self.cases
        return d


@dataclass
class Code(BaseNode):
    code: str = ""
    language: str = "python3"
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)

    def __post_init__(self):
        self._node_type = "code"
        self._id = f"code_{uuid.uuid4().hex[:6]}"
        if not self.title:
            self.title = "Code"

    def _data(self) -> dict:
        d = super()._data()
        d.update({
            "code": self.code,
            "code_language": self.language,
            "inputs": self.inputs,
            "outputs": self.outputs,
        })
        return d


@dataclass
class KnowledgeRetrieval(BaseNode):
    dataset_ids: list[str] = field(default_factory=list)
    query_variable_selector: list[str] = field(default_factory=lambda: ["start_node", "query"])
    retrieval_mode: str = "single"

    def __post_init__(self):
        self._node_type = "knowledge-retrieval"
        self._id = f"kr_{uuid.uuid4().hex[:6]}"
        if not self.title:
            self.title = "Knowledge Retrieval"

    def _data(self) -> dict:
        d = super()._data()
        d.update({
            "query_variable_selector": self.query_variable_selector,
            "dataset_ids": self.dataset_ids,
            "retrieval_mode": self.retrieval_mode,
            "single_retrieval_config": {
                "model": {"provider": "", "name": "", "mode": "chat", "completion_params": {"temperature": 0.2}},
            },
        })
        return d
