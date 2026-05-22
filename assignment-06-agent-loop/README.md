# Assignment 06 — Four-Role Cognitive Agent Loop

## 1. Overview

This project implements a multi-role AI agent that decomposes complex user queries into bounded goals and works through them iteratively. It is the Session 6 assignment of the EAGv3 curriculum.

The core problem it solves is the **single-LLM-call ceiling**. A monolithic agent loop (as in Session 5) fails reliably when a query contains multiple independent goals, ambiguous temporal references, or requires synthesising content from fetched sources. A single LLM call cannot both plan and execute, or both fetch and extract, without drifting or dropping sub-tasks.

The Session 6 architecture addresses this by separating the work across **four typed cognitive roles**:

| Role | Responsibility | LLM? |
|---|---|---|
| **Memory** | Persist and retrieve facts, preferences, tool outcomes across runs | Only for writes (Gemini classifier) |
| **Perception** | Orchestrate the goal list — decompose, track done flags, manage artifact attachment | Yes (Gemini, every iteration) |
| **Decision** | Select the next action for one bounded goal: answer or single tool call | Yes (auto-routed, every iteration) |
| **Action** | Dispatch MCP tool calls; offload large payloads to the artifact store | No |

Every boundary between roles is a **Pydantic v2 contract**. The agent loop in `agent6.py` wires them together and terminates when Perception marks every goal done.

The LLM substrate is the **LLM Gateway V3** (`llm_gatewayV3/`), a locally-running multi-provider router that handles provider failover, tier-based routing, structured output validation, and rate-limit back-off — transparent to the role implementations.

---

## 2. Usage

### Prerequisites

**Start the LLM Gateway** in a separate terminal (keep it running throughout):

```bash
cd assignment-06-agent-loop/llm_gatewayV3
bash run.sh
```

The gateway dashboard is available at `http://localhost:8101` once started.

### Running the agent

From the `assignment-06-agent-loop/` directory:

```bash
uv run python3 agent6.py "<your query>"
```

### Resetting state between runs

```bash
rm -f state/memory.json
```

---

### Example 1 — Wikipedia extraction (artifact attach path)

**Query:**
```
Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.
```

**Run log:**
```
[iter 1] Perception → 2 goals
  g0 [TODO]: Fetch https://en.wikipedia.org/wiki/Claude_Shannon
  g1 [TODO]: Extract birth date, death date, and three key contributions to information theory from the Wikipedia page
  Decision → TOOL fetch_url([('url', 'https://en.wikipedia.org/wiki/Claude_Shannon')])
  Action → artifact 0 (239 chars descriptor)

[iter 2] Perception → 2 goals
  g0 [DONE]: Fetch https://en.wikipedia.org/wiki/Claude_Shannon
  g1 [TODO] attach=0: Extract birth date, death date, and three key contributions to information theory from the Wikipedia page
  Decision → ANSWER

[iter 3] Perception → 2 goals
  g0 [DONE]: Fetch https://en.wikipedia.org/wiki/Claude_Shannon
  g1 [DONE] attach=0: Extract birth date, death date, and three key contributions to information theory from the Wikipedia page

[total iterations: 3, elapsed: 95.2s]
```

**Output:**
```
Based on the Wikipedia article, here are the requested details:

Birth date: April 30, 1916 (born in Petoskey, Michigan, U.S.)

Death date: February 24, 2001 (aged 84, died in Medford, Massachusetts, U.S.)

Three key contributions to information theory:

1. Information theory itself – Shannon is widely recognized as the father of information
   theory, having laid its mathematical foundations in his landmark 1948 paper "A
   Mathematical Theory of Communication." He introduced the concept of entropy as a measure
   of the average information content in a message, which became a cornerstone of the field.

2. Units of information (the "bit") – Shannon formally introduced the binary digit (bit) as
   the fundamental unit of information, providing a rigorous way to quantify the amount of
   information transmitted over a channel.

3. Data compression and channel capacity – Shannon's work defined the fundamental limits of
   data compression (source coding theorem) and the maximum rate at which information can be
   reliably transmitted over a noisy communication channel (channel capacity theorem).
```

---

### Example 2 — Multi-goal planning with weather constraint

**Query:**
```
Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday weather forecast there and tell me which one is most appropriate.
```

**Run log:**
```
[iter 1] Perception → 3 goals
  g0 [TODO]: Find 3 family-friendly activities in Tokyo for this weekend.
  g1 [TODO]: Check the weather forecast for Tokyo this Saturday.
  g2 [TODO]: Recommend the most appropriate activity based on the weather forecast.
  Decision → TOOL web_search
  Action → artifact 0 (237 chars)

[iter 2] Perception → 3 goals
  g0 [DONE] attach=0: Find 3 family-friendly activities in Tokyo for this weekend.
  g1 [TODO]: Check the weather forecast for Tokyo this Saturday.
  g2 [TODO]: Recommend the most appropriate activity based on the weather forecast.
  Decision → TOOL web_search
  Action → artifact 1 (238 chars)

[iter 3] Perception → 3 goals
  g0 [DONE] attach=0: Find 3 family-friendly activities in Tokyo for this weekend.
  g1 [DONE] attach=1: Check the weather forecast for Tokyo this Saturday.
  g2 [TODO] attach=1: Recommend the most appropriate activity based on the weather forecast.
  Decision → ANSWER

[iter 4] Perception → 3 goals
  g0 [DONE]: Find 3 family-friendly activities in Tokyo for this weekend.
  g1 [DONE]: Check the weather forecast for Tokyo this Saturday.
  g2 [DONE]: Recommend the most appropriate activity based on the weather forecast.

[total iterations: 4, elapsed: 34.8s]
```

**Output:**
```
Based on the weather forecast for Tokyo in May 2026, the most appropriate activity would
be to visit indoor attractions or participate in outdoor activities that are not heavily
affected by the weather.

According to the snippets, the weather in Tokyo in May 2026 is expected to be mild, with
average daytime temperatures ranging from 18°C to 25°C. There may be some rain and
humidity, but it's not expected to be extremely hot or crowded.

Considering these conditions, recommended activities include:

1. Visiting museums (Tokyo National Museum or Ghibli Museum) — rich cultural experience
   regardless of weather.
2. Exploring indoor shopping centers (Tokyo Solamachi or Shibuya 109) — fun and dry
   environment for shopping and dining.
3. Strolling in parks or gardens (Shinjuku Gyoen or Imperial Palace East Garden) — 
   beautiful in spring and enjoyable even in light rain.
```

---

### Example 3 — Durable memory across two runs

#### Run 1 — Store fact and create reminders

**Query:**
```
My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
```

**Run log:**
```
[iter 1] Perception → 3 goals
  g0 [TODO]: Calculate the date two weeks before May 15, 2026
  g1 [TODO]: Draft a calendar reminder for May 1, 2026
  g2 [TODO]: Draft a calendar reminder for May 15, 2026
  Decision → TOOL get_time(['UTC'])
  Action → inline (138 chars)

[iter 2] Perception → 3 goals
  g0 [DONE]: Calculate the date two weeks before May 15, 2026
  g1 [TODO]: Draft a calendar reminder for May 1, 2026
  g2 [TODO]: Draft a calendar reminder for May 15, 2026
  Decision → ANSWER

[iter 3] Perception → 3 goals
  g0 [DONE]: Calculate the date two weeks before May 15, 2026
  g1 [DONE]: Draft a calendar reminder for May 1, 2026
  g2 [TODO]: Draft a calendar reminder for May 15, 2026
  Decision → ANSWER

[iter 4] Perception → 3 goals
  g0 [DONE]: Calculate the date two weeks before May 15, 2026
  g1 [DONE]: Draft a calendar reminder for May 1, 2026
  g2 [TODO]: Draft a calendar reminder for May 15, 2026
  Decision → ANSWER

[iter 5] Perception → 3 goals
  g0 [DONE]: Calculate the date two weeks before May 15, 2026
  g1 [DONE]: Draft a calendar reminder for May 1, 2026
  g2 [DONE]: Draft a calendar reminder for May 15, 2026

[total iterations: 5, elapsed: 79.9s]
```

**Output:**
```
Here is a draft calendar reminder for your mother's birthday:

Title: Mom's Birthday
Date: May 15, 2026
Time: All Day
Description: Remember to send a card, call, or plan a special celebration for Mom's birthday!

(Note: Two-week advance reminder set for May 1, 2026.)
```

`state/memory.json` after Run 1 contains a `kind=fact` item:
```json
{
  "kind": "fact",
  "descriptor": "The user's mother's birthday is on May 15, 2026.",
  "value": { "entity": "Mom", "attribute": "birthday", "detail": "15 May 2026" },
  "keywords": ["mom", "birthday", "date"]
}
```

#### Run 2 — Retrieve fact without resetting state

**Query:**
```
When is mom's birthday?
```

**Run log:**
```
  Memory → 1 hits: ['fact']

[iter 1] Perception → 2 goals
  g0 [TODO]: Identify mom's birthday from memory context
  g1 [TODO]: Report the birthday to the user
  Decision → ANSWER

  Memory → 2 hits: ['fact', 'tool_outcome']

[iter 2] Perception → 2 goals
  g0 [DONE]: Identify mom's birthday from memory context
  g1 [DONE]: Report the birthday to the user

[total iterations: 2, elapsed: 9.5s]
```

**Output:**
```
Mom's birthday is on May 15, 2026.
```

---

### Example 4 — Multi-source synthesis

**Query:**
```
Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.
```

**Run log:**
```
[iter 1] Perception → 3 goals
  g0 [TODO]: Search for 'Python asyncio best practices'
  g1 [TODO]: Read the top 3 results for Python asyncio best practices
  g2 [TODO]: Synthesize a numbered list of advice that all three sources agree on
  Decision → TOOL web_search
  Action → artifact 0 (237 chars)

[iter 2] Perception → 3 goals
  g0 [DONE] attach=0: Search for 'Python asyncio best practices'
  g1 [TODO] attach=0: Read the top 3 results for Python asyncio best practices
  g2 [TODO] attach=0: Synthesize a numbered list of advice that all three sources agree on
  Decision → TOOL web_search
  Action → artifact 1 (237 chars)

[iter 3] Perception → 3 goals
  g0 [DONE] attach=0: Search for 'Python asyncio best practices'
  g1 [DONE] attach=1: Read the top 3 results for Python asyncio best practices
  g2 [TODO] attach=1: Synthesize a numbered list of advice that all three sources agree on
  Decision → ANSWER (831 chars)

[iter 4] Perception → 3 goals
  g0 [DONE]: Search for 'Python asyncio best practices'
  g1 [DONE]: Read the top 3 results for Python asyncio best practices
  g2 [DONE]: Synthesize a numbered list of advice that all three sources agree on

[total iterations: 4, elapsed: 44.2s]
```

**Output:**
```
1. Do not block the event loop with synchronous calls – All three sources warn against
   using blocking functions like time.sleep() inside async code, advising instead to use
   await asyncio.sleep() or to offload blocking operations to a thread pool via
   run_in_executor().

2. Use asyncio.create_task() to run independent operations concurrently – Each source
   recommends creating tasks for independent coroutines rather than awaiting them
   sequentially, because this allows the event loop to interleave their execution and
   achieve true concurrency.

3. Handle task cancellation gracefully – The articles consistently advise catching
   asyncio.CancelledError in long-running or cancellable tasks to perform cleanup (e.g.,
   releasing resources), and then re-raising the exception to properly mark the task
   as cancelled.
```

---

## 3. Architecture

### Component map

```
agent6.py  (main loop)
│
├── memory.py          ← typed service: read/write/remember
│   └── state/memory.json   (JSON persistence)
│
├── perception.py      ← orchestrator: goal decomposition + done tracking
│
├── decision.py        ← action selector: answer or single tool call
│
├── action.py          ← pure MCP dispatcher + artifact threshold logic
│   └── artifacts.py        (in-memory byte store, integer IDs)
│
├── schemas.py         ← Pydantic v2 contracts for all role boundaries
│
├── mcp_server.py      ← stdio MCP server (9 tools)
│
└── llm_gatewayV3/     ← multi-provider LLM router (port 8101)
    ├── main.py        ← FastAPI server + routing logic
    ├── providers.py   ← Gemini, OpenAI-compat, Ollama adapters
    ├── router.py      ← tier classification (TINY/LARGE/HUGE)
    └── client.py      ← sync HTTP client used by all roles
```

### Component purposes and design decisions

#### `schemas.py` — Pydantic v2 contracts

All role boundaries use typed models, eliminating free-form dict passing:

- `MemoryItem` — stored item with `kind` discriminator (`fact | preference | tool_outcome | scratchpad`), `keywords`, `value`, optional `artifact_id`
- `Goal` — `id`, `text`, `done: bool`, `attach_artifact_id: str | None = None`
- `Observation` — `goals: list[Goal]` with `all_done` property and `next_unfinished()` helper
- `ToolCall` — `name`, `arguments`
- `DecisionOutput` — exactly one of `answer: str | None` or `tool_call: ToolCall | None`

#### `memory.py` — Durable typed service

Three public functions:

| Function | Cost | LLM? | Purpose |
|---|---|---|---|
| `remember(text, source, run_id)` | Medium | Yes (Gemini) | Extract and persist facts/preferences from user text |
| `read(query, history)` | Cheap | No | Keyword-overlap search over `state/memory.json` |
| `record_outcome(tool_call, result_text, artifact_id, ...)` | Cheap | No | Persist a `tool_outcome` item after every Action dispatch |

`remember()` uses a Gemini structured-output call with a hand-written Gemini-safe JSON schema (no `$ref`, no `anyOf`) to extract `{kind, value, keywords, descriptor}` items. The LLM-at-write-time design makes reads cheap — future calls use stopword-filtered token intersection, no LLM needed.

**Design decision — integer artifact IDs:** Artifact handles are auto-increment integer strings (`"0"`, `"1"`, ...) stored in `artifacts.py`'s in-memory dict. This sidesteps content-addressable hash computation and eliminates the Perception hallucination risk of inventing `art:` prefix strings — the LLM echoes back whichever integer it sees in the memory hits.

#### `perception.py` — Orchestrator

Called on every iteration with: query, memory hits, history, prior goals.

Key behaviours:
- **First iteration** (prior goals empty): decompose query into ordered imperative goals with IDs `g0`, `g1`, ...
- **Subsequent iterations**: preserve goal list shape; update `done` flags and `attach_artifact_id` only
- **Done rule**: a goal is `done=true` only when the RUN HISTORY contains a satisfying answer or tool result — memory hits alone are not sufficient
- **Artifact attachment**: Perception sets `attach_artifact_id` on the first unfinished goal when it needs fetched content; the agent loop calls `artifacts.get_bytes()` and passes bytes to Decision
- **Force-attach guard**: post-LLM post-processing ensures synthesis goals (containing keywords like `synthesize`, `extract`, `list`, `compare`) always receive an artifact attachment if one exists in memory hits

**Design decision — pinned to Gemini:** Perception uses `provider="g"` (bypassing the router) at `temperature=1.0`. Empirically, TINY-tier models hallucinate attachment IDs, drop goals, or produce inconsistent goal identity across iterations. Gemini flash-lite follows the multi-step procedure reliably. Temperature 1.0 prevents the low-temperature looping behaviour observed with Gemini 3.x structured outputs.

#### `decision.py` — Action selector

Called once per iteration for the first unfinished goal.

Two output modes:

1. **Tool call** — gateway response contains `tool_calls[]`; returns first entry wrapped in `ToolCall`
2. **Answer** — gateway response is text; returns it as the answer string

Key behaviours:
- Uses `auto_route="decision"` so the gateway router picks TINY or LARGE tier based on prompt size
- When attached artifact bytes are present AND the goal is a synthesis/extraction task (keywords in `_ANSWER_FORCE_KEYWORDS`), passes `tools=None` and `tool_choice=None` — the model cannot call tools and must answer from the attached content
- For fetch goals with attached context (e.g., "read the top 3 results"), `tool_choice` remains `"auto"` so the model can still call `fetch_url`
- Artifact bytes are placed at the top of the user message with an explicit instruction, before goal/history context
- Truncates artifact content at 25,000 characters (~5,000 tokens) to stay within LARGE-tier limits while capturing Wikipedia infoboxes typically located after character 14,000

#### `action.py` — Pure MCP dispatcher

No LLM calls. Logic:

1. **Artifact handle guard**: if any argument value is a string that exists as a key in `artifacts._store`, return an error — prevents TINY-tier Decision models from passing integer artifact IDs to file/URL tools
2. **MCP dispatch**: `await session.call_tool(name, arguments)` via the stdio MCP session
3. **Threshold check**: if result bytes > 4,096 bytes, call `artifacts.put(data)` and return a short descriptor; otherwise return text inline

#### `mcp_server.py` — Nine-tool MCP server

Runs as a subprocess via `stdio_client` in `agent6.py`. Tools:

| Tool | Purpose |
|---|---|
| `web_search` | Tavily (primary) or DuckDuckGo fallback; capped at 5 results |
| `fetch_url` | Headless Chromium via crawl4ai; returns clean markdown |
| `get_time` | Current time in any IANA timezone |
| `currency_convert` | Live rates via frankfurter.dev |
| `read_file` / `list_dir` | Sandboxed file reads |
| `create_file` / `update_file` / `edit_file` | Sandboxed file writes |

All file tools are sandboxed to `./sandbox/`.

#### `llm_gatewayV3/` — Multi-provider LLM router

A locally-running FastAPI server on port 8101 that:
- Routes requests to Gemini, Groq, NVIDIA, Cerebras, OpenRouter, GitHub, or Ollama
- Runs a router LLM pool to classify prompts as TINY / LARGE / HUGE and pick a provider tier
- Validates structured outputs (JSON schema) with a one-retry correction loop
- Translates Pydantic `$ref` schemas into Gemini-compatible `responseSchema` format
- Handles rate limits with per-provider cooldowns and failover chains

---

## 4. Workflow

### Main loop (agent6.py)

```
run(query)
│
├─ memory.remember(query)          # persist any facts in the query itself
│
└─ for iteration in 1..MAX_ITERATIONS:
     │
     ├─ hits = memory.read(query, history)        # keyword search, no LLM
     │
     ├─ obs = perception.observe(                 # Gemini, structured output
     │        query, hits, history, prior_goals)  # → Observation(goals=[...])
     │
     ├─ if obs.all_done: break
     │
     ├─ goal = obs.next_unfinished()
     │
     ├─ if goal.attach_artifact_id:               # Perception-controlled gate
     │    attached = [(id, artifacts.get_bytes(id))]
     │
     ├─ out = decision.next_step(                 # auto-routed, tools passed
     │        goal, hits, attached, history, tools)  # → DecisionOutput
     │
     ├─ if out.is_answer:
     │    history.append({kind: "answer", text: out.answer, ...})
     │    continue
     │
     └─ result_text, art_id = await action.execute(session, out.tool_call)
          ├─ memory.record_outcome(...)            # persist tool_outcome
          └─ history.append({kind: "action", ...})
```

### Interface protocols

#### Memory → Perception / Decision (`memory.read` return)

```python
[
  {
    "kind": "fact" | "preference" | "tool_outcome" | "scratchpad",
    "descriptor": str,          # one human-readable line
    "value": dict,              # structured payload
    "keywords": list[str],
    "artifact_id": str | None,  # integer string "0", "1", ... or None
  },
  ...
]
```

#### Perception → Loop (`Observation`)

```python
Observation(
  goals=[
    Goal(id="g0", text="...", done=True, attach_artifact_id=None),
    Goal(id="g1", text="...", done=False, attach_artifact_id="0"),
  ]
)
```

#### Decision → Loop (`DecisionOutput`)

```python
# Either:
DecisionOutput(answer="Claude Shannon was born...", tool_call=None)

# Or:
DecisionOutput(answer=None, tool_call=ToolCall(
  name="fetch_url",
  arguments={"url": "https://en.wikipedia.org/wiki/Claude_Shannon"}
))
```

#### Action → Loop

```python
# Large payload:
("[artifact 0, 263507 bytes] preview: ...", "0")

# Small payload:
('{"iso": "2026-05-23T...", "human": "..."}', None)
```

#### Gateway request (all roles)

```python
LLM().chat(
    messages=[{"role": "user", "content": "..."}],
    system="...",
    provider="g",           # Perception / Memory: pin to Gemini
    auto_route="decision",  # Decision: router picks tier
    tools=[...],            # Decision only
    tool_choice="auto",     # Decision only (or None when force-answer)
    response_format={       # Perception / Memory: structured output
        "type": "json_schema",
        "schema": {...},
        "name": "Observation"
    },
    temperature=1.0,        # Perception: prevents low-temp looping
)
```

### Artifact data flow

```
Action.execute()
  └─ result > 4KB → artifacts.put(bytes) → returns "0"
                    ↓
memory.record_outcome(artifact_id="0")
  └─ MemoryItem(artifact_id="0") written to state/memory.json
                    ↓
memory.read() returns hit with artifact_id="0"
                    ↓
Perception sees hit, sets Goal(attach_artifact_id="0")
                    ↓
agent6.py: artifacts.get_bytes("0") → passes bytes to decision.next_step()
                    ↓
Decision receives content in prompt → answers without re-fetching
```

---

## 5. Evaluation of Prompts in Claude.md

The prompts in this project are the system prompts and LLM instructions embedded in `perception.py`, `decision.py`, and `memory.py`. Each is evaluated against the nine criteria in `meta_prompt.md`.

### Perception system prompt

```
Explicit Reasoning Instructions   ⚠ Partial
Structured Output Format          ✅ Strong  — Gemini JSON schema enforces Observation shape
Separation of Reasoning / Tools   ✅ Strong  — clear separation of decompose vs. update vs. attach
Conversation Loop Support         ✅ Strong  — explicitly handles first-call vs. subsequent-call modes
Instructional Framing             ✅ Good    — 6 numbered rules with concrete examples
Internal Self-Checks              ⚠ Partial — force-attach guard exists but no explicit self-verify step
Reasoning Type Awareness          ❌ Missing — no instruction to tag the type of reasoning applied
Error Handling / Fallbacks        ❌ Missing — no guidance for undecomposable queries or empty history
Overall Clarity                   ✅ Strong  — unambiguous rules, well-ordered
```

**Strengths:** The prompt excels at structural clarity. The six numbered rules directly map to the four Perception obligations from the spec. The "MARK DONE only from history, not memory" rule was a critical fix that prevented premature loop termination — it is explicit and testable. The force-attach rule (Rule 5) acts as a programmatic backstop that survived in the post-processing code, showing the prompt-plus-guard pattern.

**Weaknesses:** The prompt does not instruct Gemini to explain *why* it sets a goal as done, which would help debug incorrect done-marking. There is no fallback rule for edge cases such as contradictory goals, ambiguous queries that cannot be decomposed, or queries that have already been answered in a previous run. Adding "If unsure whether a goal is done, set done=false" as an explicit fallback would reduce false-done errors.

### Decision system prompt

```
Explicit Reasoning Instructions   ❌ Missing — no "think step by step" instruction
Structured Output Format          ✅ Strong  — binary choice (answer XOR tool call) is enforced
Separation of Reasoning / Tools   ✅ Strong  — rules 1-5 clearly separate answer vs tool-call paths
Conversation Loop Support         ✅ Good    — history context is provided; rule 4 prevents repeated calls
Instructional Framing             ✅ Good    — 5 numbered rules with exact constraints
Internal Self-Checks              ⚠ Partial — rule 4 ("do not repeat a tool call") is a consistency check
Reasoning Type Awareness          ❌ Missing — model is not asked to classify the type of task
Error Handling / Fallbacks        ⚠ Partial — rule 2 (reject artifact handles) is an explicit guard
Overall Clarity                   ✅ Strong  — concise, each rule addresses a real observed failure
```

**Strengths:** Rule 3 (substantive answers — "at least 3 complete sentences or a numbered list") directly addresses the meta-answer failure mode where models return "the page has been fetched, how would you like to proceed?" rather than doing the actual work. Each rule corresponds to a specific class of model failure observed during development: rule 2 (artifact handles), rule 4 (tool repetition), rule 5 (re-fetch when content is attached). The rules are not generic — they are failure-driven.

**Weaknesses:** The absence of explicit reasoning instructions is notable. For extraction goals with large attached content, instructing the model to "first identify the relevant sections, then extract" would improve accuracy on complex pages. There is no guidance on what to do if no tool is applicable and no confident answer is possible — the model has no fallback path.

### Memory classifier prompt (`remember()`)

```
Explicit Reasoning Instructions   ❌ Missing
Structured Output Format          ✅ Strong  — Gemini JSON schema with enum on kind field
Separation of Reasoning / Tools   N/A       — single-pass extraction task
Conversation Loop Support         ❌ N/A    — single-turn by design
Instructional Framing             ⚠ Weak   — only two sentences of context
Internal Self-Checks              ❌ Missing
Reasoning Type Awareness          ❌ Missing
Error Handling / Fallbacks        ✅ Partial — "return items=[] if nothing memorable" prevents over-extraction
Overall Clarity                   ✅ Good   — adequate for the extraction task
```

**Strengths:** The "return items=[] if nothing memorable" instruction is effective — it prevents the classifier from hallucinating facts from task-oriented queries like "Find 3 activities in Tokyo." The enum constraint on `kind` (`fact | preference`) prevents invalid category values from entering the store.

**Weaknesses:** The prompt is minimal and does not instruct the model to justify what it extracts or to distinguish between durable facts (birthday date) and transient mentions (a date mentioned in a search query). A more explicit example of what qualifies as a fact vs. what should be ignored would improve precision. The lack of explicit reasoning instructions means the model extracts in one pass without verification.

### Summary scorecard

| Criterion | Perception | Decision | Memory Classifier |
|---|---|---|---|
| Explicit reasoning instructions | ⚠ | ❌ | ❌ |
| Structured output format | ✅ | ✅ | ✅ |
| Separation of reasoning / tools | ✅ | ✅ | N/A |
| Conversation loop support | ✅ | ✅ | ❌ |
| Instructional framing | ✅ | ✅ | ⚠ |
| Internal self-checks | ⚠ | ⚠ | ❌ |
| Reasoning type awareness | ❌ | ❌ | ❌ |
| Error handling / fallbacks | ❌ | ⚠ | ✅ |
| Overall clarity | ✅ | ✅ | ✅ |

**Overall assessment:** The prompts are operationally effective — all four target queries pass within iteration bounds. Their strength is specificity: each rule addresses a concrete failure mode observed during development rather than generic best-practice advice. The primary gaps across all three prompts are (1) the absence of explicit step-by-step reasoning instructions, which would improve model reliability on edge cases, and (2) the lack of fallback rules for uncertain or out-of-scope inputs. Adding explicit self-check steps ("verify that your answer references the attached content directly") to Perception and Decision would be the highest-value improvement.
