# CompetencyAssess

A Chrome extension that helps you evaluate your own understanding of any PDF document — a textbook chapter, a research paper, a course handout, or a technical specification — by generating a personalised multiple-choice quiz powered by the Gemini API.

---

## Why it's useful

Reading material is passive. CompetencyAssess turns it into an active, scored experience in under two minutes:

- **Instant, relevant questions** — questions are generated directly from the document you provide, so they test the actual content rather than generic knowledge.
- **No question repetition** — every session produces a fresh set of questions covering different aspects of the material.
- **Honest feedback** — the score is weighted across three independent dimensions (see [Evaluation Criteria](#evaluation-criteria)), giving you a richer picture than a simple right/wrong tally.
- **Targeted review pointers** — for every question you got wrong, the extension tells you exactly which section of the document to revisit.
- **Zero data retention** — your API key and answers never leave your browser except as direct API calls.

---

## Getting Started

### Prerequisites

- Google Chrome (or any Chromium-based browser)
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key with access to the Gemini API

### Installation

1. Clone or download this repository.
2. Open Chrome and navigate to `chrome://extensions`.
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** and select the `assignment-02-assessment/` folder.
5. The CompetencyAssess icon will appear in your extensions bar.

### Setting your API Key

1. Click the **⚙** (settings) icon in the extension popup, or right-click the extension icon and choose *Options*.
2. Paste your Gemini API key into the field and click **Save**.  
   Your key is stored in `chrome.storage.sync` and is only ever sent directly to `generativelanguage.googleapis.com`.

---

## Usage

### Starting an assessment

1. Open the extension popup.
2. Select **PDF Document** as the assessment type (Topic, Book, and Course modes are planned for future releases).
3. Choose your PDF source:
   - **URL** — paste a publicly accessible link to a PDF.
   - **Local File** — upload a PDF from your computer.
4. Click **Start Assessment**.

The extension fetches and sends the document to Gemini, which analyses the content and returns five multiple-choice questions covering different aspects of the material.

### Taking the quiz

Each question screen shows:

| Element | Detail |
|---|---|
| **Progress** | `Question N / 5` in the top-left |
| **Timer** | 60-second countdown bar (green → amber → red) |
| **Options** | Four labelled choices (A – D) |
| **Explanation box** | Optional free-text field to explain your reasoning |

Select an answer and optionally type your reasoning, then click **Submit Answer**.  
If the timer runs out before you submit, the current state is recorded automatically.

After submitting, correct answers are highlighted in green and incorrect ones in red before the next question loads.

### Reviewing your results

After the fifth question, Gemini scores your explanations and the results screen is displayed.

---

## Evaluation Criteria

Your final score out of 100 is the sum of three weighted components:

| Component | Weight | How it is measured |
|---|---|---|
| **Accuracy** | 70 pts | Number of correct answers ÷ 5 × 70 |
| **Articulation** | 20 pts | Gemini rates each explanation 0 – 4; total ÷ 20 × 20 |
| **Timeliness** | 10 pts | Linear scale per question: instant answer = full credit, 60 s = zero credit |

### Articulation rating scale

| Score | Meaning |
|---|---|
| 0 | No explanation provided |
| 1 | Irrelevant or completely wrong reasoning |
| 2 | Vague or only partially relevant |
| 3 | Correct reasoning, reasonably clear |
| 4 | Clear, accurate, demonstrates strong understanding |

### Improvement pointers

The **Question Review** section at the bottom of the results screen lists every question with:

- **Your answer** (highlighted green ✓ or red ✗)
- **Correct answer** and a brief explanation of why it is right *(wrong answers only)*
- **Your explanation** as you typed it *(if provided)*
- **📖 Review reference** — the chapter, section, or page in the source document where the answer can be found *(wrong answers only)*

Use the review references to go back to the source material before attempting a new session.

---

## Architecture

```
assignment-02-assessment/
├── manifest.json      # Chrome Extension Manifest V3 config
├── popup.html         # Extension popup shell (4 screens)
├── popup.js           # All application logic
├── popup.css          # Popup styles (dark theme)
├── options.html       # Settings page
├── options.js         # API key save / clear logic
└── options.css        # Settings page styles
```

### How it works end-to-end

```
User provides PDF
       │
       ▼
[popup.js] fileToBase64()          ← local file: FileReader API
[popup.js] fetchPdfAsBase64()      ← URL: fetch() → ArrayBuffer → btoa()
       │
       ▼
[Gemini API] generateContent       ← inlineData block (application/pdf) + prompt
       │                              model: gemini-3.1-flash-lite-preview
       ▼
5 MCQ questions (JSON)
       │
       ▼
Quiz loop (5 × question screens)
  • 60 s countdown timer
  • Option selection + optional explanation textarea
  • Answer recorded: { selectedOption, correct, explanation, timeSpent }
       │
       ▼
[Gemini API] generateContent       ← all 5 explanations in one prompt
       │
       ▼
Articulation scores [0–4] × 5
       │
       ▼
Score calculation
  accuracy     = (correct / 5) × 70
  articulation = (sum of ratings / 20) × 20
  timeliness   = avg(1 − timeSpent/60) × 10
       │
       ▼
Results screen with Question Review
```

### Key design decisions

- **No background service worker** — all logic runs in the popup script. Gemini API calls and PDF fetches are made directly from the popup context using `fetch()`, permitted by the `host_permissions` in the manifest.
- **Single Gemini call for articulation** — all five explanations are batched into one API call at the end rather than one call per question, minimising latency and cost.
- **Inline PDF data** — PDFs (both local and remote) are converted to base64 and sent as `inlineData` blocks. This avoids the need for the Gemini Files API and keeps the flow stateless.
- **Session isolation** — all quiz state lives in a plain JS object in memory and is cleared on restart; nothing is persisted to storage beyond the API key.

---

## Planned Features

- **Topic / Book / Course** input modes (UI placeholders already present)
- **Part 2: Design questions** with 5-minute timer and longer-form evaluation
- **Session history** to track score trends over time
