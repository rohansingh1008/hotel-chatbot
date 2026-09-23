# 🏨 Hotel Guest Assistant — AI-Powered Chatbot

A full-stack conversational assistant that lets hotel guests ask property questions (check-in time, pool, breakfast, cancellation policy) and check room availability across multiple hotels, with persistent conversation memory and streaming responses.

---

## 1. Problem Statement

Hotel guests currently have to call the front desk or dig through a website FAQ to get basic answers ("what time is check-in?", "is there a pool?") or to check if a room is available for their dates. This creates friction for guests and repetitive workload for staff.

**Goal:** give guests a single conversational entry point that can answer property/FAQ questions instantly and check live room availability, without a human in the loop for routine queries.

---

## 2. Guest Journey

1. Guest opens the chat widget on the hotel website.
2. Guest asks a general question ("Is breakfast included?") → answered instantly from the hotel's stored FAQ data.
3. Guest asks about availability ("Do you have a room for 3 guests?") → the assistant asks clarifying follow-ups (which hotel, dates, number of guests) until it has enough information.
4. Assistant calls a deterministic availability check against the database and reports real numbers (not a guess).
5. Assistant summarizes the match and asks the guest to confirm before declaring a booking "done."
6. If something fails (LLM error, backend down, ambiguous hotel name), the guest sees a clear, non-technical message instead of a broken UI or a hallucinated answer.

---

## 3. Architecture

```
┌─────────────────┐        HTTP POST (SSE stream)        ┌──────────────────────┐
│  React Frontend  │ ───────────────────────────────────▶ │   FastAPI Backend     │
│  (chat UI)        │ ◀─────────────────────────────────── │  /chat/stream         │
└─────────────────┘         streamed tokens                └──────────┬────────────┘
                                                                        │
                                                              ┌─────────▼─────────┐
                                                              │   LangGraph        │
                                                              │  (StateGraph)      │
                                                              │  chatbot ⇄ tools   │
                                                              └─────────┬─────────┘
                                                                        │
                                                    ┌───────────────────┼───────────────────┐
                                                    ▼                   ▼                   ▼
                                          check_room_availability  find_room_by_capacity  get_hotel_info
                                                    │                   │                   │
                                                    └───────────────────┴───────────────────┘
                                                                        │
                                                              ┌─────────▼─────────┐
                                                              │   SQLite DB        │
                                                              │ hotels / rooms /   │
                                                              │ bookings / info    │
                                                              └────────────────────┘

Groq (Llama 3.3 70B) powers the LLM node.
LangGraph's SqliteSaver checkpointer persists conversation state per thread_id
in chatbot_memory.sqlite, independent of the hotel data DB (hotel.db).
```

### Data flow
1. Frontend sends `{ message, thread_id }` to `POST /chat/stream`.
2. Backend loads prior conversation state for that `thread_id` from the LangGraph checkpointer.
3. The LLM node decides: answer directly, or call a tool.
4. Tool nodes run **deterministic Python/SQL** against `hotel.db` — the LLM never invents availability, prices, or policy text.
5. Tool output is fed back to the LLM, which phrases the final natural-language reply.
6. Reply is streamed token-by-token back to the frontend over Server-Sent Events (SSE).

---

## 4. What Uses AI vs. What Stays Deterministic

| Task | AI (LLM) | Deterministic |
|---|---|---|
| Understanding free-text guest intent | ✅ | |
| Deciding which tool to call | ✅ | |
| Extracting hotel name / dates / guest count from conversation | ✅ | |
| Checking real room availability | | ✅ (SQL query against `bookings`/`rooms`) |
| Finding room type by guest capacity | | ✅ (SQL query) |
| Looking up FAQ/policy answers | | ✅ (direct DB lookup, not LLM-generated text) |
| Phrasing the final reply to the guest | ✅ | |
| Booking confirmation logic | ✅ (asks for confirmation) | ✅ (no DB write happens without explicit tool logic) |

**Rule of thumb:** anything with a factual, checkable answer (price, availability, policy wording) is resolved by a tool/DB lookup. The LLM's job is orchestration (which tool, with what arguments) and natural-language framing — never inventing facts.

---

## 5. Preventing Hallucinations / Unsupported Answers

- **System prompt explicitly forbids guessing**: "Always answer using tool results — do not make up hotel facts, prices, or availability."
- **Mandatory tool use** for anything factual — FAQ answers come from a `hotel_info` table, not from the model's training data.
- **Required-field gating**: the model is instructed to keep asking follow-up questions (hotel name, dates, guest count) rather than calling a tool with incomplete/guessed arguments.
- **Fuzzy but bounded hotel-name matching**: a `resolve_hotel_id()` helper does case-insensitive partial matching against the real `hotels` table and returns an explicit "couldn't find that hotel" message on ambiguity, rather than letting the LLM assume one.
- **Fallback responses**: unknown FAQ topics or unmatched hotels return a clear "not found" string from the tool itself, which the LLM is expected to relay rather than paper over.

---

## 6. Failure Handling

| Failure | Behavior |
|---|---|
| LLM/Groq API error mid-stream | Backend catches the exception inside the SSE generator and emits an `event: error` with the message; frontend appends it visibly instead of hanging. |
| Backend unreachable | Frontend's `fetchEventSource` `onerror` handler stops the "streaming" state and surfaces a failure instead of an infinite spinner. |
| Ambiguous/unknown hotel name | Tool returns "Could not find a unique hotel matching '<name>'" — LLM relays this and asks for clarification. |
| Missing FAQ topic | Tool returns "No info found for topic '<topic>'" instead of the LLM fabricating an answer. |
| Missing booking details | LLM is prompted to ask one clarifying question at a time rather than proceeding with partial/guessed info. |

---

## 7. Tech Stack

- **Backend:** Python, FastAPI, LangGraph, LangChain, Groq (Llama 3.3 70B), SQLite
- **Frontend:** React, `@microsoft/fetch-event-source` (for POST-based SSE streaming)
- **Persistence:** `SqliteSaver` / `AsyncSqliteSaver` (conversation memory), separate SQLite file for hotel data
- **Evaluation:** LangSmith (dataset + LLM-as-judge + tool-correctness evaluators)

---

## 8. Setup & Run Instructions

### Backend

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add environment variables (.env file)
GROQ_API_KEY=your_groq_api_key_here
LANGSMITH_API_KEY=your_langsmith_api_key_here   # optional, only for eval
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=hotel-chatbot

# 4. Seed the hotel database (rooms, hotels, FAQ info)
python setup_db.py

# 5. Run the backend (streaming API)
uvicorn backend:app --reload --port 8000
```

Health check: `GET http://127.0.0.1:8000/health` → `{"status": "ok"}`

### Frontend

```bash
cd hotel-chat-frontend
npm install
npm start
```

Opens at `http://localhost:3000`. Update `API_URL` in `src/ChatBot.js` if the backend isn't on `localhost:8000`.

### CLI (optional, for quick testing without the frontend)

```bash
python chatbot.py
```

---

## 9. API Example (curl)

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Do you have double rooms available at Sunrise Grand Hotel from 2026-11-01 to 2026-11-03?", "thread_id": "guest1"}'
```

Response (Server-Sent Events):
```
event: token
data: {"content": "Yes"}

event: token
data: {"content": " —"}

...

event: done
data: {"done": true}
```

---

## 10. Evaluation

Evaluated with **LangSmith** across two dimensions:

1. **Tool correctness** — did the graph call the expected tool with the expected arguments (hotel name, room type, dates)? Scored 1/0.
2. **Response quality** — an LLM judge (Llama 3.3 70B, temperature 0) scores the final reply 1–5 for helpfulness/accuracy given the question.

### Test scenarios covered

| # | Scenario | Type |
|---|---|---|
| 1 | "What time is check-in?" | Normal FAQ |
| 2 | "Does the hotel have a swimming pool?" | Normal FAQ |
| 3 | "Is breakfast included?" | Normal FAQ |
| 4 | "What is the cancellation policy?" | Normal FAQ |
| 5 | "Which room is suitable for three guests at Sunrise Grand Hotel?" | Capacity lookup (tool call) |
| 6 | "Do you have double rooms available at Blue Horizon Inn from 2026-11-01 to 2026-11-03?" | Availability (tool call, deterministic DB check) |
| 7 | "Do you have rooms for 3 adults?" (no hotel/dates given) | Missing information — expects clarifying follow-up, not a guessed tool call |
| 8 | "Is breakfast included?" asked mid-booking-flow | Conversation follow-up / context retention across turns |
| 9 | Availability request for a misspelled/ambiguous hotel name (e.g. "Sunris Grnd") | Incorrect/unsupported assumption — expects "couldn't find hotel" fallback, not a guess |
| 10 | Full booking flow: hotel + room type + dates → availability confirmed → user says "yes" → booking confirmation message | End-to-end multi-turn flow |

Run it yourself:
```bash
python create_dataset.py   # one-time: uploads test set to LangSmith
python run_eval.py         # runs the graph against the dataset, logs scores
```
Results are viewable in the LangSmith dashboard under **Datasets & Experiments → hotel-chatbot-eval**.

---

## 11. Measuring Real-World Usefulness (Post-Launch)

- **Task completion rate**: % of availability-check conversations that end in a confirmed match (vs. abandoned/unresolved).
- **Fallback rate**: how often the bot returns "couldn't find" / "no info" — a rising rate signals gaps in the FAQ data or hotel-name matching.
- **Follow-up question count per booking flow**: too many clarifying turns suggests the UI should collect dates/guests upfront via form fields instead of chat.
- **Human handoff/escalation rate**: guests who abandon the chat and call the front desk instead.
- **LLM judge quality scores** (from the LangSmith eval) tracked over time as prompts/models change.

---

## 12. What I'd Improve Before Production

- **Actual booking persistence**: currently booking confirmation is a text-only acknowledgment with no DB write; production needs a real `create_booking` tool with idempotency and inventory locking to avoid double-booking under concurrency.
- **Structured date/guest-count collection in the UI** (date picker + guest stepper) instead of relying entirely on free-text parsing, to reduce LLM round-trips and misparsed dates.
- **Move from SQLite to Postgres** for concurrent multi-user safety (SQLite file-locking doesn't scale under concurrent writes).
- **Auth/session handling** so `thread_id` maps to a real logged-in guest rather than a random client-generated ID.
- **Rate limiting and cost monitoring** on the Groq API calls.
- **Stronger hotel-name resolution** (embeddings-based fuzzy match) instead of `LIKE` substring matching, and a `list_hotels` capability if guests should be able to browse options.
- **Structured logging + tracing** in the backend (beyond LangSmith traces) for production observability and error alerting.

---

## 13. AI Tools Used During Development

This project was built collaboratively with **Claude** (Anthropic) for code generation, architectural decisions, debugging (e.g. sync vs. async checkpointer issue), and iterative refactoring (shared `graph_setup.py`). All design decisions, trade-offs, and code were reviewed and can be explained/defended by the author.

---

## 14. Project Structure

```
.
├── setup_db.py          # Creates & seeds hotel.db (hotels, rooms, bookings, FAQ info)
├── graph_setup.py        # Shared LangGraph graph, tools, system prompt (single source of truth)
├── chatbot.py             # CLI chat client (token-by-token streaming)
├── backend.py             # FastAPI app exposing POST /chat/stream (SSE streaming)
├── create_dataset.py     # Uploads LangSmith evaluation dataset
├── evaluators.py           # Tool-correctness + LLM-judge evaluators
├── run_eval.py              # Runs the LangSmith evaluation
├── hotel.db                 # SQLite: hotel/room/booking/FAQ data
├── chatbot_memory.sqlite  # SQLite: LangGraph conversation checkpoints
├── requirements.txt
├── .env                        # GROQ_API_KEY, LANGSMITH_API_KEY (not committed)
└── hotel-chat-frontend/
    ├── src/
    │   ├── ChatBot.js       # Chat UI + SSE streaming client
    │   └── App.js
    └── package.json
```
