import os
import logging
from dotenv import load_dotenv
# from langchain_core.tools import tool
# from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from src.tools.rag import search_hotel_info as _search
from src.tools.reservations import (
    create_reservation as _create,
    get_reservation as _get,
    cancel_reservation as _cancel,
    list_reservations as _list,
    modify_reservation as _modify,
)
from src.prompts import SYSTEM_PROMPT
from src.config import LLM_MODEL, LOG_PATH
from src.utils.pii import mask_payload

from langchain.tools import tool
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langchain.messages import ToolMessage,SystemMessage, HumanMessage

from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found")

log = logging.getLogger("otelio")
if not log.handlers:
    _handler = logging.FileHandler(LOG_PATH)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    ))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)

EMAIL_TOOLS = {
    "create_reservation", "list_my_reservations", "get_reservation",
    "cancel_reservation", "modify_reservation",
}

# Step 1: Define tools and model

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
def list_my_reservations(email: str) -> dict:
    """List all reservations for a guest email.

    Use when the guest asks to see their bookings. Requires the guest's email.
    """
    return _list(email)


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


@tool
def modify_reservation(reservation_id: str, email: str, check_in: str = None,
                       check_out: str = None, room_type: str = None) -> dict:
    """Update dates and/or room type on an active reservation.

    Requires reservation ID and email. Pass only fields the guest wants to change
    (check_in, check_out, room_type). Confirm before calling.
    """
    return _modify(reservation_id, email, check_in, check_out, room_type)


# Augment the LLM with tools

model = ChatGroq(model=LLM_MODEL, temperature=0)
tools = [search_hotel_info, create_reservation, list_my_reservations,
         get_reservation, cancel_reservation, modify_reservation]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)

# Step 2: Define state

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int

def build_agent(guest_email=None):

    # llm = ChatGroq(model=LLM_MODEL, temperature=0)
    # agent = create_react_agent(
    #     llm,
    #     tools=[search_hotel_info, create_reservation, get_reservation, cancel_reservation],
    #     prompt=SYSTEM_PROMPT,
    # )

    prompt = SYSTEM_PROMPT
    if guest_email:
        # no raw email in the prompt — tool_node fills it in
        prompt += (
            "\nThe guest is signed in. For reservation tools, pass email as "
            "'session'. Do not ask for their email again.\n"
        )
    
    # Step 3: Define model node

    def llm_call(state: AgentState):
        """LLM decides whether to call a tool or not"""
    
        last = state["messages"][-1]
        if isinstance(last, dict) and last.get("role") == "user":
            log.info("user asked: %s", mask_payload(last["content"]))

        response = model_with_tools.invoke(
            [SystemMessage(content=prompt)] + state["messages"]
        )

        if not response.tool_calls:
            log.info("model answered: %s", mask_payload(response.content or "")[:300])

        return {
            "messages": [response],
            "llm_calls": state.get('llm_calls', 0) + 1
        }

    # Step 4: Define tool node
    def tool_node(state: AgentState):
        """Performs the tool call"""

        result = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            args = dict(tool_call["args"])
            if guest_email and tool_call["name"] in EMAIL_TOOLS:
                args["email"] = guest_email
            observation = tool.invoke(args)
            # one line per tool: name + args + result
            log.info(
                "tool %s | args=%s | result=%s",
                tool_call["name"],
                mask_payload(args),
                mask_payload(observation),
            )
            result.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))
        return {"messages": result}

    # Step 5: Define logic to determine whether to end
    # Conditional edge function to route to the tool node or end based upon whether the LLM made a tool call
    def should_continue(state: AgentState) -> Literal["tool_node",  "__end__"]:
        """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

        messages = state["messages"]
        last_message = messages[-1]

        # If the LLM makes a tool call, then perform an action
        if last_message.tool_calls:
            return "tool_node"

        # Otherwise, we stop (reply to the user)
        return END

    # Step 6: Build agent

    # Build workflow
    agent_builder = StateGraph(AgentState)

    # Add nodes
    agent_builder.add_node("llm_call", llm_call)
    agent_builder.add_node("tool_node", tool_node)

    # Add edges to connect nodes
    agent_builder.add_edge(START, "llm_call")
    agent_builder.add_conditional_edges(
        "llm_call",
        should_continue,
        ["tool_node", END]
    )
    agent_builder.add_edge("tool_node", "llm_call")

    # Compile the agent
    agent = agent_builder.compile()

    return agent

if __name__ == "__main__":

    agent = build_agent()

    messages = [HumanMessage(content="what is the famous dish in the hotel?")]
    messages = agent.invoke({"messages": messages})

    print(messages['messages'][-1].content)

    # result = agent.invoke({"messages": [{"role": "user", "content": "get my reservation with ID 'RES-520558' and email Test@Example.com"}]})
    # print(result["messages"][-1].content)
