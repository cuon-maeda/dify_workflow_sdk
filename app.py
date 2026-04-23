from __future__ import annotations

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
for _p in (_here, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from claude_agent import ClaudeWorkflowAgent, MODELS as CLAUDE_MODELS
from openai_agent import OpenAIWorkflowAgent, MODELS as OPENAI_MODELS
from workflow_builder import build_workflow_yaml

MODELS = {"Claude": CLAUDE_MODELS, "OpenAI": OPENAI_MODELS}

def _make_agent(provider: str, model: str):
    if provider == "Claude":
        return ClaudeWorkflowAgent(model=model)
    return OpenAIWorkflowAgent(model=model)

st.set_page_config(
    page_title="Dify Workflow Designer",
    layout="wide",
    page_icon="🤖",
)

# ── Sidebar: model selection ──────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ モデル設定")

    provider = st.radio(
        "AIプロバイダー",
        options=list(MODELS.keys()),
        index=0,
        horizontal=True,
    )
    model = st.selectbox("モデル（プリセット）", options=MODELS[provider])
    custom = st.text_input("カスタムモデル名（任意）", placeholder="例: gpt-5, o3 など")
    if custom.strip():
        model = custom.strip()

    # API key status
    st.divider()
    if provider == "Claude":
        key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
        st.caption("🔑 ANTHROPIC_API_KEY: " + ("✅ 設定済み" if key_set else "❌ 未設定"))
    else:
        key_set = bool(os.environ.get("OPENAI_API_KEY"))
        st.caption("🔑 OPENAI_API_KEY: " + ("✅ 設定済み" if key_set else "❌ 未設定"))
        if not key_set:
            st.warning("OPENAI_API_KEY が設定されていません。")

    # Recreate agent when provider/model changes
    current_key = f"{provider}/{model}"
    if st.session_state.get("_model_key") != current_key:
        st.session_state._model_key = current_key
        st.session_state.agent = _make_agent(provider, model)
        st.session_state.messages = []
        st.session_state.current_mermaid = None
        st.session_state.current_spec = None
        st.session_state.pop("_yaml_preview", None)

    st.divider()
    st.caption(f"現在: **{provider} / {model}**")
    st.caption("モデルを切り替えると会話がリセットされます。")

# ── Session state init ────────────────────────────────────────────────────────
if "agent" not in st.session_state:
    st.session_state.agent = _make_agent(provider, model)
if "messages" not in st.session_state:
    st.session_state.messages: list[dict] = []
if "current_mermaid" not in st.session_state:
    st.session_state.current_mermaid: str | None = None
if "current_spec" not in st.session_state:
    st.session_state.current_spec: dict | None = None

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🤖 Dify Workflow Designer")
st.caption(f"自然言語でDifyワークフローを設計し、DSL YAMLとしてエクスポートします　｜　使用中: {provider} / {model}")

col1, col2 = st.columns([1, 1], gap="large")

# ── Left column: Chat ─────────────────────────────────────────────────────────
with col1:
    st.subheader("💬 チャット")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input(
        "ワークフローを説明してください…（例：GPT-4oでユーザーの質問に答えるチャットボットを作って）"
    )
    if prompt:
        if not key_set:
            st.error("APIキーが設定されていません。環境変数を確認してください。")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            spinner_label = f"{provider} ({model}) がワークフローを設計中…"
            with st.spinner(spinner_label):
                result = st.session_state.agent.chat(prompt)

            st.session_state.messages.append(
                {"role": "assistant", "content": result["message"]}
            )
            if result.get("mermaid"):
                st.session_state.current_mermaid = result["mermaid"]
            if result.get("workflow_spec"):
                st.session_state.current_spec = result["workflow_spec"]

            st.rerun()

# ── Right column: Diagram & Export ────────────────────────────────────────────
with col2:
    st.subheader("📊 ワークフロー図")

    if st.session_state.current_mermaid:
        _mermaid_src = st.session_state.current_mermaid
        mermaid_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin: 0; background: transparent; }}
  .mermaid {{ background: white; padding: 16px; border-radius: 8px; }}
</style>
</head>
<body>
<div class="mermaid">
{_mermaid_src}
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});
</script>
</body>
</html>"""
        st.components.v1.html(mermaid_html, height=380, scrolling=True)

        with st.expander("Mermaid ソースを表示"):
            st.code(st.session_state.current_mermaid, language="text")

        st.divider()

        if st.session_state.current_spec:
            st.markdown("**YAML エクスポート**")
            workflow_name = st.text_input(
                "ワークフロー名",
                value=st.session_state.current_spec.get("name", "My Workflow"),
                key="wf_name",
            )

            col_preview, col_dl = st.columns([1, 1])

            with col_preview:
                if st.button("YAML を生成", use_container_width=True):
                    try:
                        spec = dict(st.session_state.current_spec)
                        spec["name"] = workflow_name
                        yaml_str = build_workflow_yaml(spec)
                        st.session_state["_yaml_preview"] = yaml_str
                    except Exception as exc:
                        st.error(f"生成エラー: {exc}")

            with col_dl:
                if "_yaml_preview" in st.session_state:
                    fname = workflow_name.replace(" ", "_").replace("/", "_") + ".yaml"
                    st.download_button(
                        "📥 ダウンロード",
                        st.session_state["_yaml_preview"],
                        file_name=fname,
                        mime="text/yaml",
                        use_container_width=True,
                    )

            if "_yaml_preview" in st.session_state:
                with st.expander("YAML プレビュー", expanded=True):
                    st.code(st.session_state["_yaml_preview"], language="yaml")

    else:
        st.info(
            "チャットでワークフローを説明すると、ここに図が表示されます。\n\n"
            "**使用例:**\n"
            "- 「GPT-4oでユーザーの質問に答えるチャットボットを作って」\n"
            "- 「ナレッジベースを参照するRAGワークフローを設計して」\n"
            "- 「質問の種類で処理を分岐させたい。技術的な質問と一般的な質問を分けて」\n"
            "- 「Claudeを使ったカスタマーサポートボットに変更して」"
        )

    if st.session_state.messages:
        st.divider()
        if st.button("🔄 新しいワークフローを設計", use_container_width=True):
            st.session_state.agent.reset()
            st.session_state.messages = []
            st.session_state.current_mermaid = None
            st.session_state.current_spec = None
            st.session_state.pop("_yaml_preview", None)
            st.rerun()
