import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

from src.tools.rag import search_hotel_info as _search
from src.tools.reservations import (
    create_reservation as _create,
    get_reservation as _get,
    cancel_reservation as _cancel,
)
from src.prompts import SYSTEM_PROMPT
from src.config import LLM_MODEL

load_dotenv(dotenv_path="../.env")
if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found")

@tool
def search_hotel_info(query: str) -> str:
    """Search the hotel's information document.

    Use for any factual question about the hotel — location, timings, amenities,
    hygiene, safety, dining, policies. Always search before answering; never
    answer from your own knowledge. If nothing relevant is found, say so.
    """
    return _search(query)


@tool
def create_reservation(guest_name: str, email: str, check_in: str,
                       check_out: str, room_type: str = "standard") -> dict:
    """Create a reservation.

    Only call once the guest has given all four: name, email, check-in,
    check-out (YYYY-MM-DD). Ask for anything missing. Never invent values.
    """
    return _create(guest_name, email, check_in, check_out, room_type)


@tool
def get_reservation(reservation_id: str, email: str) -> dict:
    """Look up one reservation.

    Requires both the reservation ID and the email it was booked under; ask for
    whichever is missing. Returns a single reservation only — bulk listing is
    not possible.
    """
    return _get(reservation_id, email)


@tool
def cancel_reservation(reservation_id: str, email: str) -> dict:
    """Cancel a reservation.

    Requires both the reservation ID and the email it was booked under. Confirm
    with the guest before calling.
    """
    return _cancel(reservation_id, email)

def build_agent():

    llm = ChatGroq(model=LLM_MODEL, temperature=0)
    agent = create_react_agent(
        llm,
        tools=[search_hotel_info, create_reservation, get_reservation, cancel_reservation],
        prompt=SYSTEM_PROMPT,
    )

    return agent

if __name__ == "__main__":

    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": "get my reservation with ID 'RES-520558' and email Test@Example.com"}]})
    print(result["messages"][-1].content)