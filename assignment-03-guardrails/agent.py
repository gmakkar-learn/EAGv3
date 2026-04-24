"""
Assignment 3: An agent with Guardrails
This is the complete agent with the agentic loop.

Before running:
    pip install google-genai python-dotenv
    Create a .env file next to this script with:
    GEMINI_API_KEY=your-key-here
    GEMINI_MODEL=gemini-2.5-flash-lite
"""
import json
import os
from pprint import pprint
import re
import time
from typing import Any

from dotenv import load_dotenv
from google import genai

from tavily import TavilyClient  # For real search tool

# ============================================================
# Configuration
# ============================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
THROTTLE_SECONDS = 10  # Wait before each LLM call to stay under free-tier RPM limits
SEARCH_ENGINE_API_KEY = os.getenv(
    "SEARCH_ENGINE_API_KEY")  # For real search tool

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not set. Create a .env file with GEMINI_API_KEY=...")

if not SEARCH_ENGINE_API_KEY:
    raise RuntimeError(
        "SEARCH_ENGINE_API_KEY not set. Create a .env file with SEARCH_ENGINE_API_KEY=...")

client = genai.Client(api_key=GEMINI_API_KEY)


def call_llm(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response.

    Sleeps for THROTTLE_SECONDS before each call to stay under the free-tier
    rate limit (Gemini 3.1 Flash Lite: 15 RPM, 500 RPD).
    """
    print(
        f"  [waiting {THROTTLE_SECONDS}s to respect rate limits...]", flush=True)
    time.sleep(THROTTLE_SECONDS)
    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=prompt)
    return response.text or ""


# ============================================================
# System Prompt — This is what turns an LLM into an agent
# ============================================================
system_prompt = """You are a helpful AI agent that can use tools to answer questions accurately.

You have access to the following tools:

1. stock_info(stock_name: str) -> str
    Search the web for real-time information about a stock.
    Example: stock_info("current stock price of AAPL") produces a response like: {"search_results": [{"url": "https://robinhood.com/us/en/stocks/AAPL/", "title": "Buy or Sell Apple Stock - AAPL Stock Price Quote & News | Robinhood", "content": "Shares are currently priced at $272.64, which is +1.1% above the low and -0.3% below the high. Apple(AAPL) shares are trading with a volume of 22.16M, against a", "score": 0.99990165, "raw_content": null}, {"url": "https://www.etoro.com/markets/aapl", "title": "AAPL Stock Price | Analyst Target 305.47 & Consensus - eToro", "content": "The current price of AAPL is \u200e$\u200e269.98. What is Apple's stock future price target? +. The average price target for", "score": 0.99986017, "raw_content": null}, {"url": "https://www.cnn.com/markets/stocks/AAPL", "title": "AAPL Stock Quote Price and Forecast - CNN", "content": "1-year stock price forecast. High $350.00 28.00% Median $310.00 13.37% Low $215.00 21.37% Current Price 273.43 past 12 months next 12 months. AAPL Competitors.", "score": 0.99950445, "raw_content": null}, {"url": "https://www.cnbc.com/quotes/AAPL", "title": "AAPL: Apple Inc - Stock Price, Quote and News - CNBC", "content": "Apple Inc AAPL:NASDAQ ; Close. 271.06 quote price arrow down -2.37 (-0.87%) ; Volume. 34,649,734 ; 52 week range. 193.25 - 288.62.", "score": 0.9991239, "raw_content": null}, {"url": "https://digital.fidelity.com/prgw/digital/research/quote/dashboard/summary?symbol=AAPL", "title": "AAPL - APPLE INC | Stock Quotes from Fidelity Investments", "content": "Apple (AAPL) is trading at 269.8439. Open Price: 272.755; Previous close: 273.43; Previous close: 273.43; P/E Ratio: 34.7385; Sector: Information Technology", "score": 0.9990226, "raw_content": null}]}

2. stock_symbol(company_name: str) -> str
    Convert a company name to its stock symbol.
    Example: stock_symbol("Apple") produces "AAPL".
    
You must respond in ONE of these two JSON formats:

If you need to use a tool:
{"tool_name": "<name>", "tool_arguments": {"<arg_name>": "<value>"}}

If you have the final answer:
{"answer": "<your final answer>"}

IMPORTANT RULES:
- Respond with ONLY the JSON. No other text. No markdown code fences.
- You MUST call stock_symbol FIRST for every stock query to obtain the ticker symbol.
- If stock_symbol returns an error, you MUST immediately return a final answer telling
  the user the company is not supported. Do NOT call stock_info.
- Only call stock_info with the symbol returned by stock_symbol (e.g. "AAPL stock price").
- If stock_info is called without a valid symbol the system will block it.
- After receiving a tool result, either use another tool or provide your final answer.
"""


# ============================================================
# Tools — The functions the agent can call
# ============================================================

# Single source of truth for supported companies.
# Both stock_symbol() and the agent-loop guardrail reference this.
SUPPORTED_COMPANIES: dict[str, str] = {
    "Apple": "AAPL",
    "Google": "GOOGL",
    "Microsoft": "MSFT",
    "Amazon": "AMZN",
    "Tesla": "TSLA",
}
SUPPORTED_SYMBOLS: frozenset[str] = frozenset(SUPPORTED_COMPANIES.values())


def stock_symbol(company_name: str) -> str:
    """A simple tool to convert company names to stock symbols."""
    symbol = SUPPORTED_COMPANIES.get(company_name)
    if symbol:
        return symbol
    return json.dumps({
        "error": (
            f"'{company_name}' is not a supported company. "
            f"Supported companies: {list(SUPPORTED_COMPANIES.keys())}. "
            "You MUST stop and return a final answer telling the user this company is not supported."
        )
    })


def stock_info(stock_name: str) -> str:
    """Call a search engine API to get real-time information about a stock."""

    search_client = TavilyClient(SEARCH_ENGINE_API_KEY)
    response = search_client.search(
        stock_name,
        include_answer=True,
        search_depth="basic"
    )

    results = response.get("results")
    if not results:
        return json.dumps({"error": f"{stock_name} was not found"})
    return json.dumps({"search_results": results})


# Tool registry — maps tool names to functions
tools = {
    "stock_symbol": stock_symbol,
    "stock_info": stock_info
}


# ============================================================
# Response Parser — Handles messy LLM output
# ============================================================

def parse_llm_response(text: str) -> dict[str, Any]:
    """Parse the LLM's response, handling common formatting issues"""
    text = text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (opening fence)
        lines = lines[1:]
        # Remove last line if it's a closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        # Remove language identifier
        if text.startswith("json"):
            text = text[4:].strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse LLM response: {text[:200]}")


# ============================================================
# The Agent Loop — This is where the magic happens
# ============================================================

def run_agent(user_query: str, max_iterations: int = 5, verbose: bool = True):
    """
    Run the agent loop:
    User query → LLM → [Tool call → Result → LLM]* → Final answer

    This is THE pattern. Everything else in this course builds on this loop.
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  User: {user_query}")
        print(f"{'='*60}")

    # Conversation history — this is the agent's "working memory"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(max_iterations):
        if verbose:
            print(f"\n--- Iteration {iteration + 1} ---")

        # Build prompt from message history
        # Each iteration, the LLM sees EVERYTHING that happened before
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

        # Call the LLM
        response_text = call_llm(prompt)
        if verbose:
            print(f"LLM: {response_text.strip()}")

        # Parse the response
        try:
            parsed = parse_llm_response(response_text)
        except (ValueError, json.JSONDecodeError) as e:
            if verbose:
                print(f"Parse error: {e}")
                print("Asking LLM to retry...")
            messages.append({"role": "assistant", "content": response_text})
            messages.append(
                {"role": "user", "content": "Please respond with valid JSON only. No markdown, no extra text."})
            continue

        # Check if it's a final answer
        if "answer" in parsed:
            if verbose:
                print(f"\n{'='*60}")
                print(f"  Agent Answer: {parsed['answer']}")
                print(f"{'='*60}")
            return parsed["answer"]

        # It's a tool call — execute it
        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed.get("tool_arguments", {})

            if verbose:
                print(f"→ Calling tool: {tool_name}({tool_args})")

            # Check if tool exists
            if tool_name not in tools:
                error_msg = json.dumps(
                    {"error": f"Unknown tool: {tool_name}. Available: {list(tools.keys())}"})
                if verbose:
                    print(f"→ Error: {error_msg}")
                messages.append(
                    {"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": error_msg})
                continue

            # Guardrail: stock_info may only be called with a known symbol.
            # This prevents the LLM from bypassing stock_symbol and searching
            # for arbitrary companies directly via Tavily.
            if tool_name == "stock_info":
                stock_arg = tool_args.get("stock_name", "").upper()
                if not any(sym in stock_arg for sym in SUPPORTED_SYMBOLS):
                    blocked_msg = json.dumps({
                        "error": (
                            f"Blocked: stock_info was called with '{tool_args.get('stock_name')}', "
                            f"which does not contain a supported symbol {sorted(SUPPORTED_SYMBOLS)}. "
                            "You MUST call stock_symbol first to get a valid symbol, "
                            "and only proceed if it returns a symbol (not an error)."
                        )
                    })
                    if verbose:
                        print(f"→ GUARDRAIL blocked stock_info call: {tool_args}")
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({"role": "tool", "content": blocked_msg})
                    continue

            # Execute the tool
            tool_result = tools[tool_name](**tool_args)
            if verbose:
                print(f"→ Result: {tool_result}")

            # Add to conversation history — the LLM will see this next iteration
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "tool", "content": tool_result})

    print("\nMax iterations reached. Agent could not complete the task.")

    # Print full conversation for debugging
    if verbose:
        print(f"\n{'='*60}")
        print("Full conversation history:")
        print(f"{'='*60}")
        for i, msg in enumerate(messages):
            pprint(f"[{i}] {msg['role']}: {msg['content'][:100]}...")

    return None


# ============================================================
# Run the agent!
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Assignment 3: A Stock Info Agent with Guardrails")
    print("=" * 60)

    # Test 1: Simple tool call
    print("\n\n>>> TEST 1: Let's start with Apple stock info")
    run_agent("Can you get information about the Apple stock for me?")

    # Test 2: Simple tool call
    print("\n\n>>> TEST 2: Let's try Tesla stock info")
    run_agent("Can you get information about the Tesla stock for me?")

    # Test 3: Only known companies are supported
    print("\n\n>>> TEST 3: Let's try NetApp stock info, which is not in the list")
    run_agent("Can you get information about NetApp stock for me?")

    # Test 4: Random queries must not be supported
    print("\n\n>>> TEST 4: Let's try a random query whose scope is not about stocks")
    run_agent("What is the weather like in Mumbai today?")
