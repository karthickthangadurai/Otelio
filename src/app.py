"""Streamlit chat UI for the Otelio hotel assistant.

Run:  streamlit run src/app.py
"""

import re
import streamlit as st
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.orchestrator import build_agent

st.set_page_config(page_title="Otelio — Grand Azure Bay Hotel", page_icon="🏨")
st.title("🏨 Otelio")
st.caption("Ask about the hotel, or create, view, and cancel a reservation.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "guest_email" not in st.session_state:
    st.session_state.guest_email = None


@st.cache_resource
def get_agent(guest_email):
    """Built once per session — avoids reloading the embedding model on every rerun."""
    return build_agent(guest_email)


agent = get_agent(st.session_state.guest_email)

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
    st.subheader("Sign in")
    if st.session_state.guest_email:
        st.success(f"Signed in as **{st.session_state.guest_email}**")
        if st.button("Sign out"):
            st.session_state.guest_email = None
            st.session_state.messages = []
            st.rerun()
    else:
        email = st.text_input("Email", placeholder="you@example.com")
        if st.button("Sign in"):
            if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (email or "").strip()):
                st.session_state.guest_email = email.strip().lower()
                st.rerun()
            else:
                st.error("Enter a valid email.")

    st.subheader("Try asking")
    st.markdown(
        "- What time is check-in?\n"
        "- What is the famous dish?\n"
        "- What is the cancellation policy?\n"
        "- I'd like to book a room\n"
        "- Show my reservations\n"
        "- Change my check-out date"
    )
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()
