"""
RAG chatflow: Start → KnowledgeRetrieval → LLM → Answer
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dify_workflow_sdk import Workflow, Start, LLM, Answer, KnowledgeRetrieval

wf = Workflow(name="RAG Chatflow", mode="advanced-chat", description="RAG chatflow using knowledge base")

start = wf.add(Start())

kr = wf.add(KnowledgeRetrieval(
    dataset_ids=["your-dataset-id-here"],
    query_variable_selector=["start_node", "sys.query"],
))

llm = wf.add(LLM(
    provider="openai",
    model="gpt-4o",
    system_prompt="Answer the user's question based on the context below.\n\nContext:\n{{#" + kr.id + ".result#}}",
    user_prompt="{{#sys.query#}}",
))

answer = wf.add(Answer(content="{{#" + llm.id + ".text#}}"))

wf.chain(start, kr, llm, answer)

print(wf.to_yaml())
wf.export("rag_chatflow.yml")
