"""
Session 3 - Demo 11: The Fake Agent (a.k.a. "Arcturus Jr.")
============================================================

This is NOT a real AI agent. There's no LLM here. It's a regex-based router
with a fake personality — but it looks and feels remarkably close to a real
agent because it:

  1. Routes queries to tools (just like a real agent)
  2. Calls real APIs over the internet
  3. Has conversational personality ("let me check that for you...")
  4. Handles small talk (how are you, what can you do, etc.)

The LESSON:
  A real AI agent is EXACTLY this structure — router + tools. The ONLY
  difference is the router. This fake agent uses regex. A real agent uses
  an LLM. Watch how this agent FAILS on queries slightly outside the
  regex patterns, and then compare with the LLM-powered agent (10_full_agent.py).

Before running:
  pip install requests
"""

import re
import random
import time
import json
import math
import datetime
import requests

# ============================================================
# The Agent's Persona
# ============================================================

AGENT_NAME = "Arcturus Jr."
AGENT_VERSION = "0.1 (no LLM, just regex + vibes)"

# Random filler phrases — makes responses feel alive instead of canned
FILLERS = {
    "thinking": [
        "Hmm, let me think...",
        "One moment...",
        "Give me a sec...",
        "Let me see...",
    ],
    "searching": [
        "Let me look that up for you.",
        "Checking the internet...",
        "Searching...",
        "On it!",
        "Looking that up now.",
    ],
    "calculating": [
        "Crunching the numbers...",
        "Let me calculate that...",
        "Working it out...",
    ],
    "got_it": [
        "Here you go:",
        "Got it!",
        "Here's what I found:",
        "Okay, here:",
        "Check this out:",
    ],
    "sorry_tool_failed": [
        "Hmm, that didn't work. The internet might be acting up.",
        "Sorry, I couldn't reach that service right now.",
        "Oof, something went wrong on my end.",
        "The API is being moody. Try again?",
    ],
}

def _say(key):
    """Pick a random filler phrase."""
    return random.choice(FILLERS[key])

# ============================================================
# Small helpers — make the agent feel alive
# ============================================================

def _type_out(text, delay=0.01):
    """Print text with a tiny delay between characters to feel 'alive'."""
    for char in text:
        print(char, end="", flush=True)
        time.sleep(delay)
    print()


def _think(message="thinking", seconds=1.2):
    """
    Show a spinning / blinking animation while the agent 'thinks'.
    Overwrites itself on the same line, then clears when done.
    """
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end = time.time() + seconds
    i = 0
    while time.time() < end:
        frame = spinner[i % len(spinner)]
        print(f"\r{AGENT_NAME}: {frame} {message}...   ", end="", flush=True)
        time.sleep(0.08)
        i += 1
    # Clear the line so the real response replaces the animation
    print(f"\r{' ' * 80}\r", end="", flush=True)


def _dots(message="one sec", seconds=1.0):
    """Simpler blinking dots animation — fallback if spinner looks weird."""
    end = time.time() + seconds
    dots = 0
    while time.time() < end:
        print(f"\r{AGENT_NAME}: {message}{'.' * (dots + 1)}   ", end="", flush=True)
        dots = (dots + 1) % 3
        time.sleep(0.35)
    print(f"\r{' ' * 80}\r", end="", flush=True)

def _reply(text, filler_key=None):
    """
    Return a formatted reply. If filler_key given, prepend a random filler.
    """
    if filler_key:
        return f"{_say(filler_key)}\n\n{text}"
    return text


# ============================================================
# SMALL TALK HANDLERS (no tools, just personality)
# ============================================================

def hello(match):
    greetings = [
        f"Hey there! I'm {AGENT_NAME}. What can I do for you?",
        f"Hi! {AGENT_NAME} here. How can I help?",
        f"Hello! I'm {AGENT_NAME}, nice to meet you. What do you need?",
    ]
    return random.choice(greetings)

def how_are_you(match):
    moods = [
        "I'm doing great, thanks for asking! Ready to help. What's on your mind?",
        "Pretty good for a regex-based agent! How about you?",
        "Feeling chatty today. What can I do for you?",
        "Functioning at 100% — no LLM, no problems. How about you?",
    ]
    return random.choice(moods)

def about_me(match):
    return (
        f"I'm {AGENT_NAME}, version {AGENT_VERSION}. "
        f"I'm a teaching assistant for EAG V3 Session 3. "
        f"I look like a real AI agent, but I'm actually just Python regex + some API calls. "
        f"My job is to show you what the 'skeleton' of an agent looks like before we add an LLM brain."
    )

def who_made_you(match):
    return (
        "I was built by Rohan Shravan for The School of AI. "
        "Actually, I was mostly built by Claude, but don't tell Rohan."
    )

def are_you_human(match):
    return (
        "Nope, I'm a program! And unlike ChatGPT, I'm not even an LLM — "
        "I'm literally just a pile of if-statements wearing a trench coat."
    )

def capabilities(match):
    return (
        "Here's what I can do:\n"
        "  - weather in <city>\n"
        "  - calculate <expression>  (or 'what is 2+2')\n"
        "  - what time is it / what's the date\n"
        "  - tell me about <topic>  (Wikipedia)\n"
        "  - define <word>\n"
        "  - tell me a joke\n"
        "  - cat fact / dog fact\n"
        "  - give me a quote\n"
        "  - search <query>  (DuckDuckGo)\n"
        "  - convert 100 USD to INR\n"
        "  - my ip / where am i\n"
        "  - random number between X and Y\n"
        "  - flip a coin / roll a die\n"
        "\n"
        "Try me! And when I fail, remember — THAT is why we need LLMs."
    )

def thanks(match):
    responses = [
        "You're welcome!",
        "Anytime!",
        "Glad I could help!",
        "No problem at all.",
        "Happy to help!",
    ]
    return random.choice(responses)

def compliment(match):
    return "Aww, thanks! You're pretty great yourself."

def bored(match):
    options = [
        "Want me to tell you a joke? Just say 'tell me a joke'.",
        "I can tell you a cat fact. Or give you an inspirational quote. Your call.",
        "I know — ask me something weird and let's see if my regex can handle it.",
    ]
    return random.choice(options)

def time_greeting(match):
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning! What can I do for you today?"
    elif hour < 17:
        return "Good afternoon! How can I help?"
    else:
        return "Good evening! What's up?"

# Special marker returned when user wants to exit
GOODBYE = "__GOODBYE__"

def goodbye(match):
    farewells = [
        "Bye! Come back soon.",
        "See you later! Remember — I'm just regex. The LLM agent is cooler.",
        "Take care!",
        "Goodbye! Don't forget to run 10_full_agent.py to see the real thing.",
    ]
    print(f"\n{AGENT_NAME}: {random.choice(farewells)}\n")
    return GOODBYE


# ============================================================
# TOOL HANDLERS (these actually hit the internet)
# ============================================================

def _safe_get(url, timeout=10, **kwargs):
    """Wrapper around requests.get with friendly error handling."""
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def weather(match):
    city = match.group("city").strip().rstrip("?.").strip()
    _think(f"checking weather in {city.title()}", seconds=1.4)
    r = _safe_get(f"https://wttr.in/{city}?format=3")
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    return _reply(r.text.strip(), "got_it")


def calculate(match):
    expr = match.group("expr").strip()
    _think("crunching the numbers", seconds=0.8)
    try:
        allowed = {"math": math, "abs": abs, "round": round, "pow": pow,
                   "sum": sum, "min": min, "max": max, "pi": math.pi, "e": math.e}
        result = eval(expr, {"__builtins__": {}}, allowed)
        return _reply(f"{expr} = {result}", "got_it")
    except Exception as e:
        return f"That expression confused me: {e}"


def what_time(match):
    _think("checking the clock", seconds=0.6)
    now = datetime.datetime.now()
    return f"It's {now.strftime('%I:%M %p')} right now ({now.strftime('%A')})."


def what_date(match):
    _think("checking the calendar", seconds=0.6)
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%A, %B %d, %Y')}."


def wikipedia(match):
    topic = match.group("topic").strip().rstrip("?.").strip()
    _think(f"looking up '{topic}' on Wikipedia", seconds=1.4)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}"
    r = _safe_get(url, headers={"User-Agent": "ArcturusJr/0.1"})
    if r is None or r.status_code != 200:
        return f"Couldn't find anything on Wikipedia for '{topic}'. Try a different phrasing?"
    data = r.json()
    extract = data.get("extract", "No summary available.")
    return _reply(f"{data.get('title', topic)}:\n\n{extract}", "got_it")


def define(match):
    word = match.group("word").strip()
    _think(f"finding the definition of '{word}'", seconds=1.2)
    r = _safe_get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
    if r is None or r.status_code != 200:
        return f"I couldn't find a definition for '{word}'. Maybe check your spelling?"
    data = r.json()
    try:
        meaning = data[0]["meanings"][0]
        definition = meaning["definitions"][0]["definition"]
        pos = meaning.get("partOfSpeech", "")
        return _reply(f"{word} ({pos}): {definition}", "got_it")
    except (KeyError, IndexError):
        return f"I got a response but couldn't parse it. Weird word, '{word}'."


def joke(match):
    _think("finding a good one", seconds=1.2)
    r = _safe_get("https://official-joke-api.appspot.com/random_joke")
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    data = r.json()
    return f"{data['setup']}\n\n...\n\n{data['punchline']}"


def cat_fact(match):
    _think("digging up a cat fact", seconds=1.0)
    r = _safe_get("https://catfact.ninja/fact")
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    return r.json().get("fact", "Cats are great.")


def dog_fact(match):
    _think("finding a dog fact", seconds=1.0)
    r = _safe_get("https://dogapi.dog/api/v2/facts")
    if r is None or r.status_code != 200:
        return "Dogs are the best. That's the fact. My API is down."
    try:
        return r.json()["data"][0]["attributes"]["body"]
    except (KeyError, IndexError):
        return "Dogs are good boys and girls. Official fact."


def quote(match):
    _think("finding a good quote", seconds=1.2)
    r = _safe_get("https://zenquotes.io/api/random")
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    try:
        q = r.json()[0]
        return f'"{q["q"]}"\n     — {q["a"]}'
    except (KeyError, IndexError):
        return _say("sorry_tool_failed")


def search(match):
    query = match.group("query").strip().rstrip("?.").strip()
    _think(f"searching for '{query}'", seconds=1.5)
    r = _safe_get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": 1}
    )
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    data = r.json()
    abstract = data.get("AbstractText") or data.get("Answer")
    if abstract:
        source = data.get("AbstractSource", "")
        return _reply(f"{abstract}" + (f"\n(via {source})" if source else ""), "got_it")
    related = data.get("RelatedTopics", [])
    if related:
        first = related[0]
        if isinstance(first, dict) and first.get("Text"):
            return _reply(first["Text"], "got_it")
    return f"DuckDuckGo didn't have an instant answer for '{query}'. Try rephrasing?"


def currency_convert(match):
    amount = float(match.group("amount"))
    src = match.group("src").upper()
    dst = match.group("dst").upper()
    _think("checking exchange rates", seconds=1.2)
    r = _safe_get(f"https://api.frankfurter.app/latest?amount={amount}&from={src}&to={dst}")
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    data = r.json()
    try:
        converted = data["rates"][dst]
        return _reply(f"{amount} {src} = {converted} {dst}", "got_it")
    except (KeyError, TypeError):
        return f"I couldn't convert {src} to {dst}. Are those real currency codes?"


def my_ip(match):
    _think("locating you", seconds=1.2)
    r = _safe_get("https://ipapi.co/json/")
    if r is None or r.status_code != 200:
        return _say("sorry_tool_failed")
    data = r.json()
    return _reply(
        f"You're at {data.get('ip', '?')}\n"
        f"Looks like you're in {data.get('city', '?')}, "
        f"{data.get('region', '?')}, {data.get('country_name', '?')}.",
        "got_it"
    )


def random_number(match):
    low = int(match.group("low"))
    high = int(match.group("high"))
    if low > high:
        low, high = high, low
    _think("rolling the dice", seconds=0.6)
    return f"Your random number is {random.randint(low, high)}."


def flip_coin(match):
    _think("flipping", seconds=1.0)
    return f"It's {random.choice(['Heads', 'Tails'])}!"


def roll_die(match):
    _think("rolling", seconds=1.0)
    return f"You rolled a {random.randint(1, 6)}."


# ============================================================
# THE ROUTER — the heart of this "agent"
# ============================================================
#
# This is the part that matters. Look at it. Really look.
#
# Every line below is a REGEX pattern mapped to a handler function.
# The "intelligence" of this agent is entirely in these patterns.
# If the user's query doesn't match any pattern EXACTLY, the agent
# fails. This is WHY we need LLMs — they replace this brittle
# pattern matching with actual understanding.

ROUTES = [
    # --- Small talk (order matters — check these before tools) ---
    (r"^(hi|hello|hey|yo|sup)\b", hello),
    (r"good (morning|afternoon|evening)", time_greeting),
    (r"how are you|how'?s it going|how are you doing|how do you do", how_are_you),
    (r"who are you|what('?s| is) your name|tell me about yourself|what are you", about_me),
    (r"who (made|created|built) you|who('?s| is) your (creator|maker)", who_made_you),
    (r"are you (a )?human|are you (an )?ai|are you real|are you a bot", are_you_human),
    (r"what can you do|help$|capabilities|what (are|do) you (know|capable)", capabilities),
    (r"\b(thanks|thank you|thx|appreciate it)\b", thanks),
    (r"you('?re| are) (awesome|cool|great|smart|amazing|the best)|i love you", compliment),
    (r"i('?m| am) bored|entertain me|surprise me", bored),
    (r"^(bye|goodbye|see (you|ya)|cya|exit|quit|stop)\b", goodbye),

    # --- Tools (order matters: MORE SPECIFIC patterns FIRST) ---

    # Weather — check BEFORE calculate. Also handle "temperature", "hot", "cold"
    (r"(?:what(?:'?s| is) )?(?:the )?(?:weather|temperature|temp|forecast|climate)\s+"
     r"(?:in |for |at |of |like in )?(?P<city>[\w\s,]+?)(?:\s+(?:today|now|right now))?(?:\?|\.|$)",
     weather),
    (r"(?:is it|how)\s+(?:hot|cold|warm|cool|raining|sunny|cloudy)\s+"
     r"(?:in |at |out in )?(?P<city>[\w\s,]+?)(?:\s+(?:today|now|right now))?(?:\?|\.|$)",
     weather),
    (r"weather\s+(?:in |for |at )?(?P<city>[\w\s,]+?)(?:\?|\.|$)", weather),

    # Calculate — require at least one DIGIT so "what's the temperature" doesn't match
    (r"(?:calculate|compute|evaluate|solve)\s+(?P<expr>.+)", calculate),

    (r"what(?:'?s| is) the time|what time is it|current time|time now", what_time),
    (r"what(?:'?s| is) (?:the |today'?s )?date|what day is it|today'?s date", what_date),

    (r"tell me about (?P<topic>.+?)(?:\?|$)", wikipedia),
    (r"who (?:is|was) (?P<topic>.+?)(?:\?|$)", wikipedia),
    (r"what (?:is|was) (?P<topic>[A-Z][\w\s]+?)(?:\?|$)", wikipedia),  # capitalized = proper noun

    (r"define (?P<word>\w+)|meaning of (?P<word2>\w+)|what does (?P<word3>\w+) mean", define),

    (r"tell me a joke|make me laugh|joke please|got a joke", joke),
    (r"cat fact|fact about cats|random cat", cat_fact),
    (r"dog fact|fact about dogs|random dog", dog_fact),
    (r"(?:give me |tell me )?(?:an? )?(?:inspirational |random )?quote", quote),

    (r"search (?:for |the web (?:for )?)?(?P<query>.+?)(?:\?|$)", search),
    (r"(?:look up|google) (?P<query>.+?)(?:\?|$)", search),

    (r"convert\s+(?P<amount>[\d.]+)\s*(?P<src>[A-Za-z]{3})\s+(?:to|in|into)\s+(?P<dst>[A-Za-z]{3})", currency_convert),
    (r"(?P<amount>[\d.]+)\s+(?P<src>[A-Za-z]{3})\s+(?:to|in|into)\s+(?P<dst>[A-Za-z]{3})", currency_convert),

    (r"(?:what(?:'?s| is) )?my ip|where am i", my_ip),

    (r"random number (?:between )?(?P<low>-?\d+)\s+(?:and|to|-)\s+(?P<high>-?\d+)", random_number),
    (r"flip a coin|heads or tails|coin flip", flip_coin),
    (r"roll a die|roll a dice|roll the dice", roll_die),
]


def _fix_define_groups(match):
    """The define pattern has three optional groups — normalize to 'word'."""
    word = match.group("word") or match.group("word2") or match.group("word3")
    class Fake:
        def group(self, name):
            return word if name == "word" else None
    return Fake()


def route(query):
    """
    THE ROUTING BRAIN.
    Try each regex in order. First match wins. Call the handler.
    Return the response, or None if nothing matched.
    """
    # Special case: pure math expression like "what is 2+2" or "2+2".
    # MUST contain a digit AND a math operator AND nothing but math chars.
    math_match = re.match(
        r"^\s*(?:what(?:'?s| is)?\s*)?(?P<expr>[-+*/().\d\s]+)\s*\??\s*$",
        query, re.IGNORECASE,
    )
    if (math_match
            and any(c.isdigit() for c in query)
            and any(c in query for c in "+-*/")):
        return calculate(math_match)

    for pattern, handler in ROUTES:
        if handler is None:  # skip placeholders
            continue
        m = re.search(pattern, query, re.IGNORECASE)
        if m:
            # Handle the multi-group 'define' pattern specially
            if handler is define and not m.groupdict().get("word"):
                return define(_fix_define_groups(m))
            return handler(m)
    return None


def handle_unknown(query):
    """When nothing matches — the WHOLE POINT of this demo."""
    responses = [
        f"Hmm, I don't know how to answer '{query}'. My regex didn't match anything.",
        f"Sorry, I don't understand '{query}'. I'm just regex — I need exact patterns.",
        f"I'm stumped by '{query}'. This is exactly where an LLM would help.",
    ]
    response = random.choice(responses)
    response += "\n\nType 'help' to see what I CAN do."
    response += "\n(And remember: an LLM-powered agent would handle this easily.)"
    return response


# ============================================================
# INTERACTIVE CHAT LOOP
# ============================================================

def chat():
    print("=" * 64)
    print(f"  {AGENT_NAME} — {AGENT_VERSION}")
    print("  (A fake agent with personality. No LLM inside.)")
    print("=" * 64)
    print()

    opener = (
        f"Hey! I'm {AGENT_NAME}. I look like an AI agent, "
        f"but I'm secretly just Python regex.\n"
        f"Type 'help' to see what I can do, or just chat with me.\n"
        f"Type 'bye' when you're done."
    )
    _type_out(f"{AGENT_NAME}: {opener}", delay=0.005)
    print()

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{AGENT_NAME}: Goodbye!")
            break

        if not user:
            continue

        response = route(user)
        if response is None:
            response = handle_unknown(user)
        elif response == GOODBYE:
            break

        print(f"{AGENT_NAME}: {response}")
        print()


# ============================================================
# DEMO MODE — run a bunch of canned queries for classroom demo
# ============================================================

DEMO_QUERIES = [
    "hello",
    "how are you?",
    "what can you do?",
    "what's the weather in Mumbai?",
    "what is 2**10 + 5",
    "tell me a joke",
    "cat fact",
    "define serendipity",
    "tell me about Alan Turing",
    "convert 100 USD to INR",
    "give me a quote",
    "flip a coin",
    "random number between 1 and 100",
    # Now the failures — these are the teaching moments
    "what's hot in Mumbai right now?",           # fails — regex can't infer 'hot' = weather
    "should I bring an umbrella tomorrow?",      # fails — needs reasoning
    "who's the guy that invented the computer?", # might fail — not strict pattern
    "find me a good joke, but make it clean",   # fails — extra constraint
    "bye",
]


def demo():
    """Run canned queries to show the agent in action (and in failure)."""
    print("=" * 64)
    print(f"  DEMO MODE — {AGENT_NAME}")
    print("  Watch what this agent CAN and CAN'T do.")
    print("=" * 64)
    print()

    for q in DEMO_QUERIES:
        print(f"You: {q}")
        response = route(q)
        if response is None:
            response = handle_unknown(q)
        elif response == GOODBYE:
            print(f"{AGENT_NAME}: See you!")
            break
        print(f"{AGENT_NAME}: {response}")
        print()
        time.sleep(0.3)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        chat()
