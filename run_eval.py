from dotenv import load_dotenv
from langsmith.evaluation import evaluate
from langgraph.checkpoint.memory import MemorySaver
from graph_setup import build_graph_builder
from evaluators import tool_correctness, response_quality

load_dotenv()

DATASET_NAME = "hotel-chatbot-eval"

graph = build_graph_builder().compile(checkpointer=MemorySaver())

def target(inputs: dict) -> dict:
    question = inputs["question"]
    config = {"configurable": {"thread_id": f"eval-{abs(hash(question))}"}}
    result = graph.invoke({"messages": [{"role": "user", "content": question}]}, config)
    return {"messages": result["messages"]}

if __name__ == "__main__":
    evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[tool_correctness, response_quality],
        experiment_prefix="hotel-chatbot",
    )
    print("Evaluation complete — view results in your LangSmith dashboard.")