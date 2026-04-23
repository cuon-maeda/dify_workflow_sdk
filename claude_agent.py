from __future__ import annotations

import json
import os
import re
import sys

import anthropic

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
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]


class ClaudeWorkflowAgent:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.model = model
        self.history: list[dict] = []
        self._client: anthropic.Anthropic | None = None

    @property
    def _anthropic(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def chat(self, user_message: str) -> dict:
        self.history.append({"role": "user", "content": user_message})
        text = self._run()
        self.history.append({"role": "assistant", "content": text})
        return _parse_response(text)

    def reset(self) -> None:
        self.history = []

    def _run(self) -> str:
        messages = list(self.history)
        while True:
            response = self._anthropic.messages.create(
                model=self.model,
                max_tokens=8192,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS if _MCP_AVAILABLE else [],
                messages=messages,
            )
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                return next((b.text for b in response.content if b.type == "text"), "")

            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                {"type": "tool_result", "tool_use_id": tu.id, "content": _execute_tool(tu.name, tu.input)}
                for tu in tool_uses
            ]
            messages.append({"role": "user", "content": tool_results})
