"""Streamlit chat UI for the Otelio hotel assistant.

Run:  streamlit run src/app.py
"""

import streamlit as st
# import sys, pathlib
# sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.orchestrator import build_agent

st.set_page_config(page_title="Otelio — Grand Azure Bay Hotel", page_icon="🏨")
st.title("🏨 Otelio")
st.caption("Ask about the hotel, or create, view, and cancel a reservation.")


@st.cache_resource
def get_agent():
    """Built once per session — avoids reloading the embedding model on every rerun."""
    return build_agent()


agent = get_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# replay the conversation so far
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("How can I help?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = agent.invoke({"messages": st.session_state.messages})
            reply = result["messages"][-1].content
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

with st.sidebar:
    st.subheader("Try asking")
    st.markdown(
        "- What time is check-in?\n"
        "- What is the famous dish?\n"
        "- What is the cancellation policy?\n"
        "- I'd like to book a room\n"
        "- Show me my reservation"
    )
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()