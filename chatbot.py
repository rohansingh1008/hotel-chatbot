from langgraph.checkpoint.sqlite import SqliteSaver
from graph_setup import build_graph_builder

with SqliteSaver.from_conn_string("chatbot_memory.sqlite") as checkpointer:
    graph = build_graph_builder().compile(checkpointer=checkpointer)

    def run_chat():
        thread_id = input("Enter a thread/session id (e.g. 'guest1'): ").strip() or "default"
        config = {"configurable": {"thread_id": thread_id}}

        print(f"\nHotel Booking Assistant ready (thread='{thread_id}'). Type 'exit' to quit.\n")

        while True:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                break

            print("Bot: ", end="", flush=True)

            for msg_chunk, metadata in graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
                stream_mode="messages",
            ):
                if msg_chunk.content and metadata.get("langgraph_node") == "chatbot":
                    print(msg_chunk.content, end="", flush=True)

            print()  # newline after the full reply

    if __name__ == "__main__":
        run_chat()