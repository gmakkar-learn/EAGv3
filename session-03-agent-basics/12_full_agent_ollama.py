"""
Session 3 - Demo 12: The Full Agent — running on LOCAL Ollama (gemma4:26b)
=============================================================================

This is the EXACT same agent as 10_full_agent.py. Same system prompt, same
tools, same parser, same loop, same tests. The ONLY thing that changed is
the LLM backend — instead of calling Google's Gemini API, we call a model
running locally via Ollama.

Why this matters:
  - No API key needed. No rate limits. No internet dependency.
  - Your data never leaves your machine.
  - Prove the point: an agent is (router + tools). The router can be
    ANY LLM. Cloud, local, open, closed — doesn't matter.

Setup:
  1. Install Ollama from https://ollama.com
  2. Pull the model:       ollama pull gemma4:26b
  3. Start Ollama server:  ollama serve   (usually runs in background)
  4. Install dependency:   pip install requests python-dotenv
  5. Run this file:        python 12_full_agent_ollama.py

Configuration (optional, via .env):
  OLLAMA_HOST=http://localhost:11434
  OLLAMA_MODEL=gemma4:26b
"""
import requests
import json
import re
import math
import os
import inspect
from dotenv import load_dotenv

# ============================================================
# Configuration
# ============================================================
load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")


def call_llm(prompt: str) -> str:
    """
    Send a prompt to local Ollama and return the text response.

    This is the ONLY function that differs from 10_full_agent.py.
    Everything else — tools, parser, loop — is identical.

    We use Ollama's /api/generate endpoint with format="json" so the model
    is forced to return valid JSON (local models can be less disciplined
    about output formatting than Gemini/Claude).
    """
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,          # we want the full response at once
                "format": "json",         # force structured JSON output
                "options": {
                    "temperature": 0.1,   # low temp for consistent tool calls
                },
            },
            timeout=120,  # local inference can be slow on big models
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.ConnectionError:
        raise RuntimeError(
            f"Can't reach Ollama at {OLLAMA_HOST}. "
            f"Is it running? Try: ollama serve"
        )
    except requests.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error: {e}. "
            f"Did you pull the model? Try: ollama pull {OLLAMA_MODEL}"
        )


# ============================================================
# System Prompt — identical to 10_full_agent.py
# ============================================================
system_prompt = """You are a helpful AI agent that can use tools to answer questions accurately.

You have access to the following tools:

1. calculate(expression: str) -> str
   Evaluate a mathematical expression using Python syntax.
   Examples: calculate("2**10"), calculate("math.sqrt(144)"), calculate("sum(math.exp(x) for x in [1,1,2,3,5,8])")

2. get_weather(city: str) -> str
   Get the current weather for a city.
   Examples: get_weather("Mumbai"), get_weather("London")

3. search_notes(query: str) -> str
   Search through user's notes for relevant information.
   Examples: search_notes("meeting"), search_notes("project ideas")

You must respond in ONE of these two JSON formats:

If you need to use a tool:
{"tool_name": "<name>", "tool_arguments": {"<arg_name>": "<value>"}}

If you have the final answer:
{"answer": "<your final answer>"}

CONCRETE EXAMPLES (follow this format EXACTLY):

User: What is the weather in Mumbai?
Response: {"tool_name": "get_weather", "tool_arguments": {"city": "Mumbai"}}

Tool Result: {"weather": {"temp": "32°C", "condition": "Humid"}}
Response: {"answer": "The weather in Mumbai is 32°C and humid."}

User: What is 5 plus 7?
Response: {"tool_name": "calculate", "tool_arguments": {"expression": "5 + 7"}}

Tool Result: {"result": "12"}
Response: {"answer": "5 plus 7 is 12."}

User: What is the capital of France?
Response: {"answer": "The capital of France is Paris."}

IMPORTANT RULES:
- The key for arguments is EXACTLY "tool_arguments" (not "tool_agents", not "args").
- tool_arguments is an OBJECT like {"city": "Mumbai"}, NEVER a raw string.
- Respond with ONLY the JSON. No other text. No markdown code fences.
- Use tools when you need real data or precise calculations.
- After receiving a tool result, either use another tool or provide your final answer.
- ALWAYS use the calculate tool for math — do NOT try to compute in your head.
"""


# ============================================================
# Tools — identical to 10_full_agent.py
# ============================================================

def calculate(expression: str) -> str:
    try:
        allowed = {
            "math": math, "abs": abs, "round": round, "pow": pow,
            "sum": sum, "min": min, "max": max, "range": range, "list": list,
        }
        result = eval(expression, {"__builtins__": {}}, allowed)
        return json.dumps({"result": str(result)})
    except Exception as e:
        return json.dumps({"error": f"Calculation failed: {str(e)}"})


def get_weather(city: str) -> str:
    weather_data = {
        "Mumbai": {"temp": "32°C", "condition": "Humid, Partly Cloudy", "humidity": "78%"},
        "Delhi": {"temp": "28°C", "condition": "Clear Sky", "humidity": "45%"},
        "London": {"temp": "15°C", "condition": "Rainy", "humidity": "85%"},
        "New York": {"temp": "22°C", "condition": "Sunny", "humidity": "55%"},
        "Tokyo": {"temp": "26°C", "condition": "Windy", "humidity": "60%"},
        "San Francisco": {"temp": "18°C", "condition": "Foggy", "humidity": "72%"},
    }
    if city in weather_data:
        return json.dumps({"weather": weather_data[city]})
    return json.dumps({"error": f"Weather data not available for {city}"})


def search_notes(query: str) -> str:
    notes = [
        {"title": "Meeting Agenda", "content": "Discuss Q3 targets, review agent architecture, plan MCP integration"},
        {"title": "Shopping List", "content": "Milk, eggs, bread, coffee, batteries"},
        {"title": "Project Ideas", "content": "Build a stock monitoring agent, voice-based assistant, browser automation tool"},
        {"title": "Travel Plans", "content": "Tokyo trip in December, need to book flights and hotel by November"},
        {"title": "Learning Notes", "content": "Finish transformer session, practice async Python, read MCP docs"},
    ]
    results = [
        n for n in notes
        if query.lower() in n["title"].lower() or query.lower() in n["content"].lower()
    ]
    if results:
        return json.dumps({"results": results})
    return json.dumps({"results": "No notes found matching your query"})


tools = {
    "calculate": calculate,
    "get_weather": get_weather,
    "search_notes": search_notes,
}


# ============================================================
# Response Parser — identical to 10_full_agent.py
# ============================================================

def extract_tool_args(parsed: dict, tool_name: str) -> dict:
    """
    Local models are sloppy about the exact argument key/shape. Gemma might
    emit 'tool_args', 'arguments', 'tool_agents' (typo!), or even put args
    at the top level of the response. Normalize all of these into a proper
    kwargs dict for the target tool.

    This is the kind of defensive plumbing you'll see everywhere when you
    work with smaller open models. Cloud models (Gemini, Claude) are more
    disciplined, but local models need babysitting.
    """
    # Possible key aliases the model might have invented
    CANDIDATE_KEYS = (
        "tool_arguments", "tool_args", "arguments", "args",
        "parameters", "params", "tool_agents",  # yes, Gemma said 'tool_agents'
        "input", "inputs",
    )

    raw = None
    for key in CANDIDATE_KEYS:
        if key in parsed:
            raw = parsed[key]
            break

    # Nothing matched — maybe the args are at the top level (sibling of tool_name)
    if raw is None:
        extras = {k: v for k, v in parsed.items()
                  if k not in ("tool_name", "answer", "name")}
        if extras:
            raw = extras

    # Already a dict — great, return as-is
    if isinstance(raw, dict):
        return raw

    # Got a raw string/number — wrap it using the tool's parameter name
    if raw is not None and tool_name in tools:
        sig = inspect.signature(tools[tool_name])
        params = [p for p in sig.parameters if p != "self"]
        if len(params) == 1:
            return {params[0]: raw}

    return {}


def parse_llm_response(text: str) -> dict:
    """Parse the LLM's response, handling common formatting issues"""
    text = text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse LLM response: {text[:200]}")


# ============================================================
# The Agent Loop — identical to 10_full_agent.py
# ============================================================

def run_agent(user_query: str, max_iterations: int = 5, verbose: bool = True):
    """
    User query → LLM → [Tool call → Result → LLM]* → Final answer

    Same loop. Same pattern. Just a different model on a different machine.
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  User: {user_query}")
        print(f"{'='*60}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n--- Iteration {iteration + 1} ---")

        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += msg["content"] + "\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n\n"
            elif msg["role"] == "tool":
                prompt += f"Tool Result: {msg['content']}\n\n"

        response_text = call_llm(prompt)
        if verbose:
            print(f"LLM: {response_text.strip()}")

        try:
            parsed = parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError) as e:
            if verbose:
                print(f"Parse error: {e}")
                print("Asking LLM to retry...")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        if "answer" in parsed:
            if verbose:
                print(f"\n{'='*60}")
                print(f"  Agent Answer: {parsed['answer']}")
                print(f"{'='*60}")
            return parsed["answer"]

        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            # Use the forgiving extractor instead of parsed["tool_arguments"]
            tool_args = extract_tool_args(parsed, tool_name)

            if verbose:
                print(f"→ Calling tool: {tool_name}({tool_args})")

            if tool_name not in tools:
                error_msg = json.dumps({"error": f"Unknown tool: {tool_name}. Available: {list(tools.keys())}"})
                if verbose:
                    print(f"→ Error: {error_msg}")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": error_msg})
                continue

            try:
                tool_result = tools[tool_name](**tool_args)
            except TypeError as e:
                # Wrong / missing arguments — feed the error back so LLM retries
                error_msg = json.dumps({
                    "error": f"Bad arguments for {tool_name}: {e}. "
                             f"Expected format: {{'tool_name': '{tool_name}', "
                             f"'tool_arguments': {{...}}}}."
                })
                if verbose:
                    print(f"→ Error: {error_msg}")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": error_msg})
                continue

            if verbose:
                print(f"→ Result: {tool_result}")

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "tool", "content": tool_result})

    print("\nMax iterations reached. Agent could not complete the task.")
    return None


# ============================================================
# Connectivity check — fail fast with a clear message
# ============================================================

def _check_ollama():
    """Ping Ollama and verify the model is available before running tests."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        print(f"\nCan't reach Ollama at {OLLAMA_HOST}.")
        print("Start it with:  ollama serve")
        return False

    models = [m["name"] for m in r.json().get("models", [])]
    if not any(m.startswith(OLLAMA_MODEL.split(":")[0]) for m in models):
        print(f"\nModel '{OLLAMA_MODEL}' not found in Ollama.")
        print(f"Installed models: {', '.join(models) if models else '(none)'}")
        print(f"Pull it with:  ollama pull {OLLAMA_MODEL}")
        return False

    return True


# ============================================================
# Run it!
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print(f"  SESSION 3: FULL AGENT on LOCAL OLLAMA ({OLLAMA_MODEL})")
    print(f"  Same agent as 10_full_agent.py — different brain.")
    print("=" * 60)

    if not _check_ollama():
        raise SystemExit(1)

    # Test 1: Simple tool call
    print("\n\n>>> TEST 1: Simple weather query")
    run_agent("What is the weather in Mumbai?")

    # Test 2: Calculation
    print("\n\n>>> TEST 2: Math that LLMs get wrong")
    run_agent("What is 2 raised to the power of 10, plus the square root of 144?")

    # Test 3: Multi-step — needs multiple tool calls
    print("\n\n>>> TEST 3: Multi-step reasoning")
    run_agent(
        "Search my notes for travel plans, then check the weather in "
        "the city I'm planning to visit."
    )

    # Test 4: The classic — sum of exponentials of Fibonacci
    print("\n\n>>> TEST 4: Sum of exponentials of Fibonacci")
    run_agent(
        "Calculate the sum of exponential values (e^x) of the "
        "first 6 Fibonacci numbers: 1, 1, 2, 3, 5, 8"
    )

    # Test 5: Something that doesn't need tools
    print("\n\n>>> TEST 5: No tools needed")
    run_agent("What is the capital of France?")
