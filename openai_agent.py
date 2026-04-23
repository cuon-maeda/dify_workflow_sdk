from __future__ import annotations

import json
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

try:
    from mcp_server import list_node_types, get_node_schema, list_examples, get_example, validate_dsl
    _MCP_AVAILABLE = True
except Exception:
    _MCP_AVAILABLE = False

from _agent_shared import TOOLS, SYSTEM_PROMPT, _execute_tool, _parse_response

MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "o3-mini",
    "o1",
    "gpt-4-turbo",
]

# OpenAI tool format (slightly different from Anthropic)
_OAI_TOOLS = [
    {"type": "function", "function": {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["input_schema"],
    }}
    for t in TOOLS
]


class OpenAIWorkflowAgent:
    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model
        self.history: list[dict] = []
        self._client = None

    @property
    def _openai(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except ImportError as exc:
                raise RuntimeError("openai パッケージが必要です: pip install openai") from exc
        return self._client

    def chat(self, user_message: str) -> dict:
        self.history.append({"role": "user", "content": user_message})
        text = self._run()
        self.history.append({"role": "assistant", "content": text})
        return _parse_response(text)

    def reset(self) -> None:
        self.history = []

    def _run(self) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *self.history]
        while True:
            kwargs: dict = {"model": self.model, "max_tokens": 8192, "messages": messages}
            if _MCP_AVAILABLE:
                kwargs["tools"] = _OAI_TOOLS
                kwargs["tool_choice"] = "auto"

            response = self._openai.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                return msg.content or ""

            # Feed tool results back
            messages.append(msg)
            for tc in tool_calls:
                inputs = json.loads(tc.function.arguments)
                result = _execute_tool(tc.function.name, inputs)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
