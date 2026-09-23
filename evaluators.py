import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langsmith.schemas import Run, Example

load_dotenv()

judge_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)


def _get_field(msg, field):
    return getattr(msg, field, None) or (msg.get(field) if isinstance(msg, dict) else None)


def tool_correctness(run: Run, example: Example) -> dict:
    """Checks whether the graph called the expected tool with matching argument values."""
    expected_tool = example.outputs.get("expected_tool")
    expected_args = example.outputs.get("expected_args", {})

    messages = run.outputs.get("messages", [])
    tool_calls_found = []
    for m in messages:
        calls = _get_field(m, "tool_calls")
        if calls:
            tool_calls_found.extend(calls)

    if not tool_calls_found:
        return {"key": "tool_correctness", "score": 0, "comment": "No tool was called."}

    for call in tool_calls_found:
        name = call.get("name") if isinstance(call, dict) else call["name"]
        args = call.get("args") if isinstance(call, dict) else call["args"]
        if name == expected_tool:
            match = all(str(v).lower() in str(args.get(k, "")).lower() for k, v in expected_args.items())
            if match:
                return {"key": "tool_correctness", "score": 1, "comment": f"Matched {name} with args {args}"}

    return {
        "key": "tool_correctness",
        "score": 0,
        "comment": f"Expected {expected_tool} with {expected_args}, got {tool_calls_found}",
    }


def response_quality(run: Run, example: Example) -> dict:
    """LLM-as-judge: scores the final reply for helpfulness/accuracy, 1-5."""
    question = example.inputs.get("question", "")
    messages = run.outputs.get("messages", [])

    final_reply = ""
    for m in reversed(messages):
        content = _get_field(m, "content")
        msg_type = _get_field(m, "type") or _get_field(m, "role")
        if content and msg_type in ("ai", "assistant"):
            final_reply = content
            break

    prompt = (
        f"You are grading a hotel chatbot's reply.\n\n"
        f"User question: {question}\n"
        f"Chatbot reply: {final_reply}\n\n"
        f"Score the reply from 1-5 on helpfulness and accuracy "
        f"(5 = fully correct and clear, 1 = wrong or unhelpful).\n"
        f"Respond with ONLY a single digit 1-5."
    )

    result = judge_llm.invoke(prompt)
    try:
        score = int(result.content.strip()[0])
    except Exception:
        score = 0

    return {"key": "response_quality", "score": score / 5, "comment": f"LLM judge score: {score}/5"}