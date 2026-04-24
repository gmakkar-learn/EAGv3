"""
Session 3 - Demo 2: code.interact() for debugging agents — GUIDED TOUR
=======================================================================

Run this and follow along. You'll be prompted to press Enter between steps
and given specific commands to try inside the interactive shell.

The goal: see WHY code.interact() is powerful for debugging agent loops.
"""
import code
import json
import time


# ─────────────────────────────────────────────────────────────
# Setup: a simulated agent (no real LLM, responses are hardcoded
# so the demo is deterministic and teaches the concept)
# ─────────────────────────────────────────────────────────────

SIMULATED_RESPONSES = [
    # Iteration 1: LLM decides to call the weather tool
    '{"tool_name": "get_weather", "tool_arguments": {"city": "Mumbai"}}',
    # Iteration 2: LLM has the weather, now gives the final answer
    '{"answer": "The weather in Mumbai is 32°C and humid. Yes, it is hotter than 30°C."}',
]
_response_index = 0


def fake_call_llm(conversation):
    """Pretends to call an LLM. Returns canned responses for the demo."""
    global _response_index
    resp = SIMULATED_RESPONSES[_response_index]
    _response_index += 1
    return resp


def get_weather(city: str) -> str:
    return json.dumps({"weather": "32°C, Humid, Partly Cloudy"})


tools = {"get_weather": get_weather}


# ─────────────────────────────────────────────────────────────
# Helpers for the guided tour
# ─────────────────────────────────────────────────────────────

def pause(message="Press ENTER to continue..."):
    """Wait for user to press enter. Makes the demo interactive."""
    input(f"\n  {message}")


def banner(text, char="="):
    print()
    print(char * 64)
    print(f"  {text}")
    print(char * 64)


def narrator(text):
    """Print a narration block with an arrow to distinguish from agent output."""
    print()
    for line in text.strip().split("\n"):
        print(f"  → {line}")


# ─────────────────────────────────────────────────────────────
# The guided agent loop
# ─────────────────────────────────────────────────────────────

def guided_agent_loop(user_query):
    banner(f"GUIDED TOUR: Debugging an Agent with code.interact()")

    narrator(f"""
This is a SIMULATED agent. The LLM responses are hardcoded so we can
focus on ONE thing: how code.interact() lets you peek inside the loop.

User's query: "{user_query}"

The agent will:
  1. Ask the LLM what to do
  2. Parse the response
  3. Call a tool if needed
  4. Repeat until it has a final answer

At key moments, we'll FREEZE execution and drop into a Python shell
so you can inspect the program's state with your own eyes.
""")

    pause("Press ENTER to start the agent...")

    # Initial conversation state
    conversation = [{"role": "user", "content": user_query}]

    for iteration in range(5):
        banner(f"ITERATION {iteration + 1}", char="─")

        narrator("About to call the LLM. The LLM will see the full conversation\n"
                 "history so far and decide what to do next.")

        pause("Press ENTER to call the LLM...")

        llm_response = fake_call_llm(conversation)

        print(f"\n  LLM returned:  {llm_response}")

        # ─────────────────────────────────────────────
        # BREAKPOINT: freeze and let user inspect
        # ─────────────────────────────────────────────
        narrator(f"""
We're about to process this response. But wait — in REAL agent development,
this is where things go wrong. The LLM might return broken JSON, the wrong
tool name, or weird arguments.

Let's FREEZE the program right here and poke around. I'm going to drop you
into a live Python shell where EVERY variable in scope is available.

Try typing these commands one at a time:

    >>> llm_response
              ...the raw string the LLM returned

    >>> iteration
              ...which loop iteration we're on

    >>> conversation
              ...the full message history so far

    >>> len(conversation)
              ...how many messages deep we are

    >>> tools
              ...what tools this agent can call

    >>> tools["get_weather"]("Delhi")
              ...you can even CALL a tool manually from the shell!

When you're done exploring, press Ctrl+D to exit the shell and continue.
""")

        pause("Press ENTER to drop into the interactive shell...")

        print()
        print("  ┌─────────────────────────────────────────────────────┐")
        print("  │  You're now in the interactive shell (Ctrl+D to exit) │")
        print("  └─────────────────────────────────────────────────────┘")

        code.interact(banner="", local=locals())

        print()
        print("  ┌─────────────────────────────────────────────────────┐")
        print("  │  Back in the agent loop.                            │")
        print("  └─────────────────────────────────────────────────────┘")

        # ─────────────────────────────────────────────
        # Now actually process the LLM response
        # ─────────────────────────────────────────────

        parsed = json.loads(llm_response)

        if "answer" in parsed:
            narrator(f"The LLM gave a FINAL ANSWER. The loop ends here.")
            print(f"\n  FINAL ANSWER:  {parsed['answer']}")
            break

        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed["tool_arguments"]

            narrator(f"The LLM wants to call tool '{tool_name}' with args {tool_args}.\n"
                     f"We'll execute it, then feed the result back to the LLM.")

            pause("Press ENTER to execute the tool...")

            result = tools[tool_name](**tool_args)
            print(f"\n  Tool returned:  {result}")

            conversation.append({"role": "assistant", "content": llm_response})
            conversation.append({"role": "tool", "content": result})

            narrator(f"Added the tool call and result to conversation history.\n"
                     f"conversation is now {len(conversation)} messages long.\n"
                     f"In iteration {iteration + 2}, the LLM will see ALL of this.")


def summary():
    banner("WHAT YOU JUST SAW", char="=")
    narrator("""
You used code.interact() to freeze a running agent and inspect its state.
This is how you debug real agents in production:

  - Your agent gets stuck? Drop code.interact() into the loop.
  - Wrong tool being called? Drop code.interact() BEFORE the tool call.
  - Conversation getting too long? Print len(conversation) in the shell.
  - Want to test a tool manually? Call it from the shell.

code.interact() is your emergency pause button for agents. Use it.

For structured step-by-step debugging (next breakpoint, step into, etc.),
use pdb instead — see 03_pdb_basic.py.
""")


if __name__ == "__main__":
    guided_agent_loop("What is the weather in Mumbai? Is it hotter than 30 degrees?")
    summary()
