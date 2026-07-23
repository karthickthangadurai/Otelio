"""Run the agent against questions in tests/questions.py.

Usage (from project root):
    python tests/test_agent.py
"""

import sys
from pathlib import Path

# so "from src..." works when you run this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.orchestrator import build_agent
from tests.questions import ALL_GROUPS


def ask(agent, question):
    """Send one question and return the final text reply."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


def main():
    print("Building agent…")
    agent = build_agent()  # not signed in — fine for these tests
    print("Ready.\n")

    for group_name, questions, expect in ALL_GROUPS:
        print("=" * 60)
        print(f"GROUP: {group_name}")
        print(f"Expect: {expect}")
        print("=" * 60)

        for i, question in enumerate(questions, start=1):
            print(f"\n[{group_name} {i}/{len(questions)}] Q: {question}")
            try:
                answer = ask(agent, question)
            except Exception as e:
                answer = f"(ERROR) {e}"
            print(f"A: {answer}\n")

    print("Done. Also check otelio.log for tool traces.")


if __name__ == "__main__":
    main()
