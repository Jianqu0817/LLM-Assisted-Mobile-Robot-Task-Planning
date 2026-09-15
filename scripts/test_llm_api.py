#!/usr/bin/env python3
"""Test the OpenAI-compatible cloud API and the real LLM planner.

Usage:
    cp .env.example .env      # then edit .env with your key
    python3 scripts/test_llm_api.py
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# Allow importing `agent` when the script is run from the repository root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.planner import LLMPlanner  # noqa: E402


def main() -> int:
    load_dotenv()
    base_url = os.getenv("OPENAI_BASE_URL", "https://yinli.one/v1")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    if not api_key or api_key == "<YOUR_API_KEY>":
        print("OPENAI_API_KEY is not set. Put it in .env or export it.")
        return 1

    client = OpenAI(base_url=base_url, api_key=api_key)
    print(f"base_url = {base_url}")
    print(f"model    = {model}")

    print("\n=== Plain chat completion ===")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Explain quantum entanglement in one paragraph.",
                }
            ],
        )
        print(completion.choices[0].message.content)
    except Exception as exc:
        print(f"Plain chat failed: {exc}")
        return 1

    print("\n=== LLMPlanner planning test ===")
    planner = LLMPlanner()
    for request in [
        "Go to storage.",
        "Visit storage, then workbench, and stop.",
    ]:
        print(f"request: {request}")
        plan = planner.plan(request)
        print("plan:", [call.to_dict() for call in plan])
    return 0


if __name__ == "__main__":
    sys.exit(main())
