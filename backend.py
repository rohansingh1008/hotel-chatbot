import json
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph_setup import build_graph_builder

graph = None
_checkpointer_cm = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph, _checkpointer_cm
    _checkpointer_cm = AsyncSqliteSaver.from_conn_string("chatbot_memory.sqlite")
    checkpointer = await _checkpointer_cm.__aenter__()
    graph = build_graph_builder().compile(checkpointer=checkpointer)
    yield
    await _checkpointer_cm.__aexit__(None, None, None)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hotel-chatbot-zhg5.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_generator():
        try:
            async for msg_chunk, metadata in graph.astream(
                {"messages": [{"role": "user", "content": req.message}]},
                config,
                stream_mode="messages",
            ):
                if msg_chunk.content and metadata.get("langgraph_node") == "chatbot":
                    yield {"event": "token", "data": json.dumps({"content": msg_chunk.content})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        yield {"event": "done", "data": json.dumps({"done": True})}

    return EventSourceResponse(event_generator())


@app.get("/health")
def health():
    return {"status": "ok"}