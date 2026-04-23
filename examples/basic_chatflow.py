"""
advanced-chat: Start → LLM → Answer
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dify_workflow_sdk import Workflow, Start, LLM, Answer

wf = Workflow(name="Basic Chatflow", mode="advanced-chat", description="Simple chatflow with one LLM node")

start = wf.add(Start())
llm = wf.add(LLM(
    provider="openai",
    model="gpt-4o",
    system_prompt="You are a helpful assistant.",
    user_prompt="{{#sys.query#}}",
))
answer = wf.add(Answer(content="{{#" + llm.id + ".text#}}"))

wf.chain(start, llm, answer)

print(wf.to_yaml())
wf.export("basic_chatflow.yml")
