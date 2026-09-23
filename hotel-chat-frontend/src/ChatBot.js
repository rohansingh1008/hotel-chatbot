import React, { useState, useRef, useEffect } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";

const API_URL = "https://hotel-chatbot-i4j2.onrender.com/chat/stream";

function ChatBot() {
  const [messages, setMessages] = useState([]); // { role: "user" | "assistant", content: string }
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadId] = useState(() => "guest-" + Math.random().toString(36).slice(2, 10));

  const messagesEndRef = useRef(null);
  const controllerRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setIsStreaming(true);

    // Add an empty assistant message we'll fill in as tokens stream
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await fetchEventSource(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, thread_id: threadId }),
        signal: controller.signal,

        onmessage(ev) {
          if (ev.event === "token") {
            const data = JSON.parse(ev.data);
            setMessages((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: updated[lastIdx].content + data.content,
              };
              return updated;
            });
          } else if (ev.event === "error") {
            const data = JSON.parse(ev.data);
            setMessages((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: updated[lastIdx].content + `\n[Error: ${data.error}]`,
              };
              return updated;
            });
          } else if (ev.event === "done") {
            setIsStreaming(false);
          }
        },

        onerror(err) {
          console.error("SSE error:", err);
          setIsStreaming(false);
          throw err; // stop retrying
        },

        onclose() {
          setIsStreaming(false);
        },
      });
    } catch (err) {
      console.error(err);
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>🏨 Hotel Booking Assistant</div>

      <div style={styles.chatWindow}>
        {messages.length === 0 && (
          <div style={styles.placeholder}>
            Ask me about room availability, check-in time, breakfast, pool, or cancellation policy.
          </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              ...styles.messageRow,
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                ...styles.bubble,
                ...(msg.role === "user" ? styles.userBubble : styles.botBubble),
              }}
            >
              {msg.content || (isStreaming && idx === messages.length - 1 ? "..." : "")}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div style={styles.inputRow}>
        <textarea
          style={styles.textarea}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          disabled={isStreaming}
        />
        <button style={styles.sendButton} onClick={sendMessage} disabled={isStreaming || !input.trim()}>
          {isStreaming ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    maxWidth: 600,
    margin: "40px auto",
    height: "80vh",
    border: "1px solid #ddd",
    borderRadius: 12,
    overflow: "hidden",
    fontFamily: "system-ui, sans-serif",
    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
  },
  header: {
    padding: "16px 20px",
    background: "#1e293b",
    color: "#fff",
    fontWeight: 600,
    fontSize: 16,
  },
  chatWindow: {
    flex: 1,
    overflowY: "auto",
    padding: 16,
    background: "#f8fafc",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  placeholder: {
    color: "#94a3b8",
    fontSize: 14,
    textAlign: "center",
    marginTop: 40,
    padding: "0 20px",
  },
  messageRow: {
    display: "flex",
  },
  bubble: {
    maxWidth: "75%",
    padding: "10px 14px",
    borderRadius: 14,
    fontSize: 14,
    lineHeight: 1.4,
    whiteSpace: "pre-wrap",
  },
  userBubble: {
    background: "#2563eb",
    color: "#fff",
    borderBottomRightRadius: 4,
  },
  botBubble: {
    background: "#e2e8f0",
    color: "#0f172a",
    borderBottomLeftRadius: 4,
  },
  inputRow: {
    display: "flex",
    gap: 8,
    padding: 12,
    borderTop: "1px solid #ddd",
    background: "#fff",
  },
  textarea: {
    flex: 1,
    resize: "none",
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #cbd5e1",
    fontSize: 14,
    fontFamily: "inherit",
    outline: "none",
  },
  sendButton: {
    padding: "0 18px",
    borderRadius: 8,
    border: "none",
    background: "#2563eb",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
};

export default ChatBot;