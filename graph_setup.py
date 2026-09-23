import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from typing import Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage

load_dotenv()

DB_PATH = "hotel.db"


def resolve_hotel_id(cur, hotel_name: str):
    """Case-insensitive partial match on hotel name. Returns hotel_id or None."""
    cur.execute(
        "SELECT hotel_id, name FROM hotels WHERE LOWER(name) LIKE ?",
        (f"%{hotel_name.lower().strip()}%",),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0][0], rows[0][1]
    return None, None

class AvailabilityQuery(BaseModel):
    hotel_name: str = Field(description="Name of the hotel (can be partial, e.g. 'Sunrise')")
    room_type: str = Field(description="Type of room: single, double, triple, or suite")
    check_in: str = Field(description="Check-in date in YYYY-MM-DD format")
    check_out: str = Field(description="Check-out date in YYYY-MM-DD format")
    rooms_needed: int = Field(default=1, description="Number of rooms requested")


class CapacityQuery(BaseModel):
    hotel_name: str = Field(description="Name of the hotel (can be partial, e.g. 'Sunrise')")
    guests: int = Field(description="Number of guests that need to fit in one room")


class InfoQuery(BaseModel):
    topic: str = Field(
        description="One of: check_in_time, pool, breakfast, cancellation_policy, wifi, parking"
    )

@tool
def check_room_availability(hotel_name: str, room_type: str, check_in: str, check_out: str, rooms_needed: int = 1) -> str:
    """Check how many rooms of a given type are available at a specific hotel between
    check_in and check_out dates. Dates must be YYYY-MM-DD. hotel_name is required."""
    try:
        query = AvailabilityQuery(
            hotel_name=hotel_name,
            room_type=room_type.lower().strip(),
            check_in=check_in,
            check_out=check_out,
            rooms_needed=rooms_needed,
        )
        datetime.strptime(query.check_in, "%Y-%m-%d")
        datetime.strptime(query.check_out, "%Y-%m-%d")
    except Exception as e:
        return f"Invalid input: {e}"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    hotel_id, matched_name = resolve_hotel_id(cur, query.hotel_name)
    if hotel_id is None:
        conn.close()
        return f"Could not find a unique hotel matching '{query.hotel_name}'. Please confirm the exact hotel name."

    cur.execute(
        "SELECT total_rooms, price_per_night FROM rooms WHERE hotel_id = ? AND room_type = ?",
        (hotel_id, query.room_type),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return f"No '{query.room_type}' room type at {matched_name}. Available types: single, double, triple, suite."

    total_rooms, price = row

    cur.execute(
        """
        SELECT COALESCE(SUM(rooms_booked), 0)
        FROM bookings
        WHERE hotel_id = ? AND room_type = ?
          AND NOT (check_out <= ? OR check_in >= ?)
        """,
        (hotel_id, query.room_type, query.check_in, query.check_out),
    )
    booked = cur.fetchone()[0]
    conn.close()

    available = total_rooms - booked

    if available >= query.rooms_needed:
        return (
            f"Yes — {matched_name} has {available} {query.room_type} room(s) available "
            f"from {query.check_in} to {query.check_out} at ${price}/night each."
        )
    else:
        return (
            f"Sorry, {matched_name} only has {available} {query.room_type} room(s) available "
            f"from {query.check_in} to {query.check_out} (you requested {query.rooms_needed})."
        )


@tool
def find_room_by_capacity(hotel_name: str, guests: int) -> str:
    """Find which room type at a specific hotel can accommodate a given number of guests.
    hotel_name is required."""
    try:
        query = CapacityQuery(hotel_name=hotel_name, guests=guests)
    except Exception as e:
        return f"Invalid input: {e}"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    hotel_id, matched_name = resolve_hotel_id(cur, query.hotel_name)
    if hotel_id is None:
        conn.close()
        return f"Could not find a unique hotel matching '{query.hotel_name}'. Please confirm the exact hotel name."

    cur.execute(
        "SELECT room_type, capacity, price_per_night FROM rooms WHERE hotel_id = ? AND capacity >= ? ORDER BY capacity ASC",
        (hotel_id, query.guests),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return f"No room type at {matched_name} accommodates {query.guests} guests."

    room_type, capacity, price = rows[0]
    return (
        f"At {matched_name}, a {room_type} room fits up to {capacity} guests and costs "
        f"${price}/night — suitable for {query.guests} guest(s)."
    )


@tool
def get_hotel_info(topic: str) -> str:
    """Look up general hotel information/FAQ answers that apply to all hotels. Valid topics:
    check_in_time, pool, breakfast, cancellation_policy, wifi, parking."""
    try:
        query = InfoQuery(topic=topic.lower().strip())
    except Exception as e:
        return f"Invalid input: {e}"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT answer FROM hotel_info WHERE topic = ?", (query.topic,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return f"No info found for topic '{query.topic}'."
    return row[0]


TOOLS = [check_room_availability, find_room_by_capacity, get_hotel_info]

class State(TypedDict):
    messages: Annotated[list, add_messages]

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3,
)
llm_with_tools = llm.bind_tools(TOOLS)

SYSTEM_PROMPT = SystemMessage(content=(
    "You are a hotel booking assistant handling multiple hotels. Room types are: "
    "single, double, triple, suite.\n\n"
    "- For availability questions, you MUST have: hotel_name, room_type (or number of "
    "adults, if room_type isn't given yet), check_in date, and check_out date (YYYY-MM-DD) "
    "before calling check_room_availability. If any are missing, ask the user for them one "
    "at a time — do not guess or assume a hotel or dates.\n"
    "- If the user tells you the number of adults/guests instead of a room type, first call "
    "find_room_by_capacity (which also requires hotel_name) to determine the right room_type, "
    "then use that room_type when calling check_room_availability.\n"
    "- For general questions like check-in time, pool, breakfast, cancellation policy, wifi, "
    "or parking, use get_hotel_info with the matching topic — these answers are the same "
    "across all hotels, so no hotel_name is needed for these.\n"
    "- Never call check_room_availability or find_room_by_capacity without a hotel_name — "
    "always ask the user which hotel they mean first if it's not clear.\n\n"
    "BOOKING CONFIRMATION FLOW:\n"
    "- Once check_room_availability confirms a room IS available, do NOT immediately say the "
    "booking is done. Instead, summarize the details (hotel name, room type, check-in date, "
    "check-out date, number of rooms, and price) and ask the user: "
    "'Shall I proceed with this booking?'\n"
    "- Only after the user replies with a clear yes/confirmation, respond with a booking "
    "confirmation message stating the booking is done, restating the same details.\n"
    "- Do not call any tool again to finalize the booking — just confirm it in your reply "
    "once the user says yes.\n\n"
    "Always answer using tool results — do not make up hotel facts, prices, or availability."
))


def chatbot_node(state: State):
    messages = [SYSTEM_PROMPT] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def build_graph_builder() -> StateGraph:
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("tools", ToolNode(TOOLS))
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")
    return graph_builder