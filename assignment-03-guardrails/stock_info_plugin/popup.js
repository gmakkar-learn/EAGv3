const SERVER_URL = "http://127.0.0.1:5001";
const REQUEST_TIMEOUT_MS = 120_000; // 2 min — agent can be slow

const queryInput   = document.getElementById("queryInput");
const searchBtn    = document.getElementById("searchBtn");
const loadingState = document.getElementById("loadingState");
const errorState   = document.getElementById("errorState");
const errorMsg     = document.getElementById("errorMsg");
const resultSection = document.getElementById("resultSection");
const resultText   = document.getElementById("resultText");
const logsContent  = document.getElementById("logsContent");
const logsDetails  = document.getElementById("logsDetails");

// ── UI state ──────────────────────────────────────────────

function showState(state) {
  loadingState.classList.add("hidden");
  errorState.classList.add("hidden");
  resultSection.classList.add("hidden");

  if (state === "loading") loadingState.classList.remove("hidden");
  else if (state === "error") errorState.classList.remove("hidden");
  else if (state === "result") resultSection.classList.remove("hidden");
}

function setSearchEnabled(enabled) {
  searchBtn.disabled = !enabled;
  queryInput.disabled = !enabled;
}

// ── Fetch with timeout ────────────────────────────────────

async function fetchWithTimeout(url, options, ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

// ── Main search ───────────────────────────────────────────

async function search() {
  const query = queryInput.value.trim();
  if (!query) {
    queryInput.focus();
    return;
  }

  setSearchEnabled(false);
  logsDetails.removeAttribute("open"); // collapse logs between searches
  showState("loading");

  try {
    const response = await fetchWithTimeout(
      `${SERVER_URL}/query`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      },
      REQUEST_TIMEOUT_MS
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      showError(data.error || "An unexpected error occurred.");
      // Still populate logs if available
      if (data.logs) logsContent.textContent = data.logs;
      return;
    }

    resultText.textContent = data.answer || "(no answer returned)";
    logsContent.textContent = data.logs || "(no logs captured)";
    showState("result");

  } catch (err) {
    if (err.name === "AbortError") {
      showError("Request timed out. The agent took too long to respond.");
    } else {
      showError(
        "Could not reach the backend server.\n" +
        "Make sure server.py is running: python server.py"
      );
    }
  } finally {
    setSearchEnabled(true);
    queryInput.focus();
  }
}

function showError(message) {
  errorMsg.textContent = message;
  showState("error");
}

// ── Event listeners ───────────────────────────────────────

searchBtn.addEventListener("click", search);

queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});
