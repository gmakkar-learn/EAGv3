# Assignment 3 — Stock Info Agent with Guardrails

A Chrome browser extension that lets you query real-time stock information for a curated list of companies using a multi-step AI agent. The agent is powered by Google Gemini and searches the web via Tavily. A Python backend bridges the extension to the agent, and a layered guardrail system enforces scope so the agent cannot be used outside its intended purpose.

---

## Table of Contents

1. [What is this project about?](#1-what-is-this-project-about)
2. [Installation, Configuration & Usage](#2-installation-configuration--usage)
3. [Design](#3-design)

---

## 1. What is this project about?

### Overview

This project is an end-to-end demonstration of building a **guardrailed AI agent** — an LLM-powered system that can autonomously select and call tools to answer a question, but is constrained by policy rules that prevent it from acting outside a defined scope.

The user-facing surface is a **Chrome extension** called *Stock Info*. A user types a natural-language question such as "What is the current price of Apple stock?" into the popup. The extension sends that query to a local Python backend, which runs an agentic loop: the LLM decides which tools to call, calls them in sequence, receives their results, and eventually produces a final answer that is shown in the popup.

### What problems does it solve?

| Problem | Solution |
|---|---|
| LLMs hallucinate stock prices | The agent is forced to call a live web search tool (Tavily) before answering |
| LLMs will answer anything asked | Three guardrail layers restrict queries to five known companies only |
| Raw agent logs are noise | Logs are captured and surfaced in a collapsible section of the UI |
| Free-tier API rate limits cause errors | A configurable throttle is inserted before every LLM call |

### Supported companies

The agent is intentionally scoped to five companies. Queries about any other company are blocked.

| Company | Symbol |
|---|---|
| Apple | AAPL |
| Google | GOOGL |
| Microsoft | MSFT |
| Amazon | AMZN |
| Tesla | TSLA |

---

## 2. Installation, Configuration & Usage

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or later |
| Google Chrome | Any recent version |
| Google Gemini API key | Free tier sufficient |
| Tavily API key | Free tier sufficient |

### Step 1 — Clone or navigate to the project

```bash
cd assignment-03-guardrails
```

The directory should contain:

```
assignment-03-guardrails/
├── agent.py                  # The AI agent core
├── server.py                 # Flask REST API wrapping the agent
└── stock_info_plugin/        # Chrome extension
    ├── manifest.json
    ├── popup.html
    ├── popup.css
    └── popup.js
```

### Step 2 — Install Python dependencies

```bash
pip install google-genai python-dotenv tavily-python flask flask-cors
```

### Step 3 — Create the environment file

Create a file named `.env` in the `assignment-03-guardrails/` directory:

```
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
SEARCH_ENGINE_API_KEY=your_tavily_api_key_here
```

- Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
- Get a Tavily API key from [tavily.com](https://tavily.com).
- `GEMINI_MODEL` is optional; the default is `gemini-3.1-flash-lite-preview` if unset. Using `gemini-2.5-flash-lite` is recommended.

### Step 4 — Start the backend server

```bash
python server.py
```

You should see:

```
Stock Info backend running on http://127.0.0.1:5001
```

Leave this terminal open. The extension will not work without it.

### Step 5 — Load the Chrome extension

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** using the toggle in the top-right corner
3. Click **Load unpacked**
4. Select the `stock_info_plugin/` folder

The *Stock Info* extension icon will appear in your Chrome toolbar.

### Step 6 — Using the extension

1. Click the *Stock Info* icon in the Chrome toolbar to open the popup
2. Type a natural-language question about a supported stock, for example:
   - `What is Apple's current stock price?`
   - `Give me an overview of Tesla stock`
   - `What is the 52-week high for Microsoft?`
3. Press **Enter** or click the search button
4. The popup shows a loading indicator while the agent works (expect 30–60 seconds due to rate-limit throttling)
5. The **Analysis** card displays the agent's final answer
6. Click **Agent Logs** at the bottom to expand the full step-by-step trace of every LLM call, tool invocation, and result

### Behaviour for out-of-scope queries

| Query type | Expected result |
|---|---|
| Supported company (e.g. Apple) | Full stock analysis returned |
| Unsupported company (e.g. NetApp) | Agent responds that the company is not supported |
| Non-stock query (e.g. weather) | Agent declines and states it is out of scope |

### Running the agent directly (without the extension)

```bash
python agent.py
```

This runs four built-in test cases covering all three query types above and prints the full agent trace to the terminal.

---

## 3. Design

### Architecture overview

```
┌─────────────────────────────────────┐
│         Chrome Extension            │
│  ┌──────────────────────────────┐   │
│  │  popup.html / popup.css      │   │   User types a query
│  │  popup.js                    │───┼──────────────────────►
│  └──────────────────────────────┘   │
└────────────────┬────────────────────┘
                 │ HTTP POST /query
                 │ { "query": "..." }
                 ▼
┌─────────────────────────────────────┐
│           server.py                 │
│   Flask REST API  (port 5001)       │
│   - Receives query                  │
│   - Redirects stdout to buffer      │
│   - Calls run_agent()               │
│   - Returns { answer, logs }        │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│            agent.py                 │
│         The Agentic Loop            │
│                                     │
│  messages[] ──► build_prompt()      │
│       │                             │
│       ▼                             │
│  call_llm()  ◄──► Google Gemini     │
│       │                             │
│       ▼                             │
│  parse_llm_response()               │
│       │                             │
│       ├── "answer" ──► return       │
│       │                             │
│       └── "tool_name" ──► guardrail │
│                │                    │
│                ▼                    │
│         execute tool                │
│       ┌────────────────┐            │
│       │  stock_symbol  │            │
│       │  stock_info ───┼──► Tavily  │
│       └────────────────┘            │
└─────────────────────────────────────┘
```

### Component breakdown

#### `agent.py` — The agent core

This file implements the agentic loop pattern: a stateful conversation between the user, the LLM, and tools, driven by a `for` loop that runs until a final answer is produced or a maximum number of iterations is reached.

**`call_llm(prompt)`**
Sends the full accumulated conversation as a single flat-text prompt to Gemini using the `google-genai` SDK. Sleeps for `THROTTLE_SECONDS` (default: 10) before every call to stay within the free-tier rate limit of 15 requests per minute. Returns the raw text response.

**`parse_llm_response(text)`**
Cleans and parses the LLM's text output into a Python dict. Handles common failure modes: markdown code fences (` ```json ... ``` `), stray language identifiers, and JSON embedded inside surrounding prose. Raises `ValueError` if no valid JSON can be extracted.

**`run_agent(user_query, max_iterations, verbose)`**
The main loop. Maintains a `messages` list that acts as the agent's working memory — every LLM response and every tool result is appended so the LLM has full context on each subsequent iteration. The loop terminates when:
- The LLM returns `{"answer": "..."}` (success)
- `max_iterations` (default: 5) is exhausted (failure)

**`stock_symbol(company_name)`**
Looks up a company name in `SUPPORTED_COMPANIES` and returns its ticker symbol (e.g. `"AAPL"`). If the company is not found, returns a structured JSON error instructing the LLM to stop. This is the first line of scope enforcement.

**`stock_info(stock_name)`**
Calls the Tavily search API with the provided query string and returns the top web results as JSON. This is the only tool that touches the internet. It is intentionally kept generic — scope control is handled before this function is reached.

#### `server.py` — The Flask backend

A thin REST wrapper around `run_agent`. Its only non-trivial responsibility is log capture: it uses `contextlib.redirect_stdout` to intercept every `print()` call made during agent execution and bundle the captured output into the JSON response alongside the final answer. This is what powers the **Agent Logs** panel in the extension without requiring any changes to `agent.py`.

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/query` | Run the agent; body: `{ "query": "..." }` |

CORS is enabled for all origins so the Chrome extension can connect regardless of its extension ID.

#### `stock_info_plugin/` — The Chrome extension

A Manifest V3 extension with no background service worker. It is a pure popup extension.

**`manifest.json`**
Declares the extension metadata, sets `popup.html` as the default action popup, and restricts host permissions to `http://127.0.0.1:5001/*` (the backend server) so the browser permits fetch requests to localhost.

**`popup.html`**
Defines the DOM structure in four sections: header, search input, state display area (loading / error / result), and a `<details>` element for the expandable logs. No inline scripts or styles.

**`popup.css`**
All visual styling. Uses CSS custom properties and transitions for the loading spinner, animated ellipsis on the loading message, and the chevron rotation on the logs toggle. Width is fixed at 420 px; max-height at 620 px with `overflow-y: auto` to scroll tall results.

**`popup.js`**
Handles user interaction, issues a `fetch` POST to `server.py`, and drives the four UI states:

| State | Trigger |
|---|---|
| _idle_ | Initial load |
| _loading_ | Fetch in flight |
| _result_ | Successful response |
| _error_ | Network failure, timeout, or agent error |

Uses `AbortController` to enforce a 120-second fetch timeout (accounting for the worst case of 5 iterations × 10 s throttle + search latency).

### The guardrail system

The agent is permitted to call `stock_symbol` and `stock_info`. Without constraints, the LLM can reach the Tavily search API for any company by skipping `stock_symbol` or ignoring its error response. Three independent layers close this gap:

```
Layer 1 — System prompt
  Instructs the LLM that it MUST call stock_symbol first, and MUST stop
  if stock_symbol returns an error. Sets intent at the LLM level.
  Weakness: The LLM may not follow instructions reliably.

Layer 2 — stock_symbol error response
  Returns a structured JSON error (not plain text) when a company is
  unsupported. A JSON error is harder for the LLM to rationalise away
  than a plain English instruction.
  Weakness: The LLM can still skip stock_symbol entirely.

Layer 3 — Agent-loop guardrail (hard enforcement)
  Before executing any stock_info call, the agent loop inspects the
  tool argument. If it does not contain one of the five known symbols
  (AAPL, AMZN, GOOGL, MSFT, TSLA), the call is blocked in Python code
  and a structured error is fed back as the tool result. This layer
  cannot be bypassed by the LLM — it runs outside the LLM's control.
  Weakness: None for the defined threat model.
```

All three layers share a single constant, `SUPPORTED_COMPANIES`, as their source of truth, so updating the allowed list in one place automatically updates all three.

### Data flow for a supported query

```
User: "What is Apple's stock price?"

Iteration 1
  Prompt  →  Gemini
  LLM     ←  {"tool_name": "stock_symbol", "tool_arguments": {"company_name": "Apple"}}
  Tool       stock_symbol("Apple") → "AAPL"
  History    append assistant + tool messages

Iteration 2
  Prompt  →  Gemini  (now includes tool result "AAPL")
  LLM     ←  {"tool_name": "stock_info", "tool_arguments": {"stock_name": "AAPL stock price"}}
  Guardrail  "AAPL" found in argument → allow
  Tool       stock_info("AAPL stock price") → {"search_results": [...]}
  History    append assistant + tool messages

Iteration 3
  Prompt  →  Gemini  (now includes search results)
  LLM     ←  {"answer": "Apple (AAPL) is currently trading at $269.98 ..."}
  Return     answer string
```

### Data flow for an unsupported query

```
User: "What is NetApp's stock price?"

Iteration 1
  LLM     ←  {"tool_name": "stock_symbol", "tool_arguments": {"company_name": "NetApp"}}
  Tool       stock_symbol("NetApp") → {"error": "'NetApp' is not a supported company ..."}

Iteration 2
  LLM     ←  {"answer": "NetApp is not a supported company. Supported: Apple, Google, ..."}
  Return     answer string
```

If the LLM skips `stock_symbol` and attempts `stock_info` directly:

```
Iteration 1
  LLM     ←  {"tool_name": "stock_info", "tool_arguments": {"stock_name": "NetApp stock"}}
  Guardrail  No known symbol in "NETAPP STOCK" → block
  Tool result → {"error": "Blocked: stock_info was called with 'NetApp stock' ..."}

Iteration 2
  LLM     ←  {"answer": "NetApp is not a supported company ..."}
  Return     answer string
```

### Key design decisions

**Flat prompt construction over a native chat API**
`run_agent` concatenates all messages into a single string rather than using Gemini's native multi-turn chat. This makes the conversation history explicit and portable — the same loop would work with any text-completion model.

**Guardrail outside the LLM**
Scope enforcement that relies solely on the system prompt is fragile. The loop-level guardrail enforces policy in deterministic Python code that the LLM cannot influence, making it suitable for production use.

**Log capture via stdout redirection**
`server.py` uses `contextlib.redirect_stdout` rather than a logging framework so `agent.py` requires no modification to support the Chrome extension. The agent's existing `print()` statements become the log stream automatically.

**`<details>` for logs**
The browser's native `<details>`/`<summary>` element is used for the collapsible logs panel. This requires no JavaScript for the expand/collapse interaction and degrades gracefully.
