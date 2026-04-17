'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  apiKey: '',
  questions: [],
  currentIndex: 0,
  answers: [],          // { question, selectedOption, correct, explanation, timeSpent, correctAnswer, correctExplanation, section }
  questionStart: null,
  timerInterval: null,
  timeRemaining: 60,
};

const TIME_BUDGET_MCQ = 60; // seconds

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const { apiKey = '' } = await chrome.storage.sync.get('apiKey');
  state.apiKey = apiKey;
  if (!apiKey) showApiWarning(true);
  bindEvents();
});

function bindEvents() {
  document.getElementById('btn-settings').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });

  document.querySelectorAll('input[name="pdf-source"]').forEach(r => {
    r.addEventListener('change', e => {
      const isUrl = e.target.value === 'url';
      document.getElementById('url-group').classList.toggle('hidden', !isUrl);
      document.getElementById('file-group').classList.toggle('hidden', isUrl);
    });
  });

  document.getElementById('pdf-file').addEventListener('change', e => {
    const f = e.target.files[0];
    document.getElementById('file-label-text').textContent = f ? f.name : 'Choose PDF file…';
  });

  document.getElementById('btn-start').addEventListener('click', startAssessment);
  document.getElementById('btn-submit').addEventListener('click', submitAnswer);
  document.getElementById('btn-restart').addEventListener('click', restartAssessment);
}

// ── Screen helpers ─────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.toggle('active', s.id === `screen-${id}`);
    s.style.display = s.id === `screen-${id}` ? 'block' : 'none';
  });
}

function showApiWarning(show) {
  document.getElementById('api-warning').classList.toggle('hidden', !show);
}

function setLoadingMsg(msg) {
  document.getElementById('loading-msg').textContent = msg;
}

// ── Assessment start ───────────────────────────────────────────────────────
async function startAssessment() {
  const { apiKey = '' } = await chrome.storage.sync.get('apiKey');
  state.apiKey = apiKey;

  if (!apiKey) {
    showApiWarning(true);
    return;
  }
  showApiWarning(false);

  const sourceType = document.querySelector('input[name="pdf-source"]:checked').value;

  let pdfSource;
  if (sourceType === 'url') {
    const url = document.getElementById('pdf-url').value.trim();
    if (!url) { alert('Please enter a PDF URL.'); return; }
    pdfSource = { type: 'url', value: url };
  } else {
    const file = document.getElementById('pdf-file').files[0];
    if (!file) { alert('Please select a PDF file.'); return; }
    try {
      const b64 = await fileToBase64(file);
      pdfSource = { type: 'base64', value: b64 };
    } catch {
      alert('Failed to read the PDF file.');
      return;
    }
  }

  showScreen('loading');
  setLoadingMsg('Analyzing document and generating questions…');

  try {
    state.questions = await generateQuestions(pdfSource);
    state.currentIndex = 0;
    state.answers = [];
    showScreen('quiz');
    renderQuestion();
  } catch (err) {
    showScreen('home');
    alert(`Error: ${err.message}`);
  }
}

// ── PDF helpers ────────────────────────────────────────────────────────────
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// ── Gemini API ─────────────────────────────────────────────────────────────
const GEMINI_MODEL = 'gemini-3.1-flash-lite-preview';
const GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';

async function callGemini(parts) {
  const url = `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent?key=${state.apiKey}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts }] }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || `API error ${res.status}`);
  }
  const data = await res.json();
  return data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
}

async function fetchPdfAsBase64(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not fetch PDF (${res.status}): ${url}`);
  const buf = await res.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

// ── Question generation ────────────────────────────────────────────────────
async function generateQuestions(pdfSource) {
  let base64;
  if (pdfSource.type === 'url') {
    base64 = await fetchPdfAsBase64(pdfSource.value);
  } else {
    base64 = pdfSource.value;
  }

  const prompt = `You are an expert educator. From the provided PDF document, create exactly 5 multiple-choice questions that test DIFFERENT competencies and topics from the material.

Return ONLY a JSON array — no markdown, no prose — using this exact schema:
[
  {
    "id": 1,
    "question": "Full question text?",
    "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
    "correct": "B",
    "section": "Chapter 3 / page 47 (or equivalent reference)",
    "correctExplanation": "Brief explanation of why this answer is correct."
  }
]

Rules:
- Each question must cover a DIFFERENT aspect of the document.
- All four options must be plausible; only one is correct.
- Base every answer strictly on content in the document.
- The "section" field must pinpoint where the answer can be found.`;

  const raw = await callGemini([
    { inlineData: { mimeType: 'application/pdf', data: base64 } },
    { text: prompt },
  ]);

  const match = raw.match(/\[[\s\S]*\]/);
  if (!match) throw new Error('Could not parse questions from the model response.');
  return JSON.parse(match[0]);
}

// ── Quiz rendering ─────────────────────────────────────────────────────────
function renderQuestion() {
  const q = state.questions[state.currentIndex];

  document.getElementById('q-progress').textContent =
    `Question ${state.currentIndex + 1} / ${state.questions.length}`;
  document.getElementById('q-text').textContent = q.question;

  const wrap = document.getElementById('options-wrap');
  wrap.innerHTML = '';
  Object.entries(q.options).forEach(([key, text]) => {
    const btn = document.createElement('button');
    btn.className = 'option-btn';
    btn.dataset.option = key;
    btn.innerHTML = `<span class="option-key">${key}</span>${text}`;
    btn.addEventListener('click', () => selectOption(key));
    wrap.appendChild(btn);
  });

  document.getElementById('explain-input').value = '';
  document.getElementById('btn-submit').disabled = true;
  startTimer();
}

function selectOption(key) {
  document.querySelectorAll('.option-btn').forEach(b => b.classList.remove('selected'));
  document.querySelector(`.option-btn[data-option="${key}"]`).classList.add('selected');
  document.getElementById('btn-submit').disabled = false;
}

// ── Timer ──────────────────────────────────────────────────────────────────
function startTimer() {
  clearInterval(state.timerInterval);
  state.timeRemaining = TIME_BUDGET_MCQ;
  state.questionStart = Date.now();
  updateTimerUI();

  state.timerInterval = setInterval(() => {
    state.timeRemaining -= 1;
    updateTimerUI();
    if (state.timeRemaining <= 0) {
      clearInterval(state.timerInterval);
      autoSubmit();
    }
  }, 1000);
}

function updateTimerUI() {
  const t = state.timeRemaining;
  document.getElementById('timer-text').textContent = `${t}s`;

  const fill = document.getElementById('timer-fill');
  fill.style.width = `${(t / TIME_BUDGET_MCQ) * 100}%`;

  if (t > 30) {
    fill.style.backgroundColor = '#4ade80';
    document.getElementById('timer-text').style.color = '#4ade80';
  } else if (t > 10) {
    fill.style.backgroundColor = '#f59e0b';
    document.getElementById('timer-text').style.color = '#f59e0b';
  } else {
    fill.style.backgroundColor = '#ef4444';
    document.getElementById('timer-text').style.color = '#ef4444';
  }
}

function autoSubmit() {
  // Time's up — record with no selection if nothing was chosen
  const selected = document.querySelector('.option-btn.selected');
  const timeSpent = TIME_BUDGET_MCQ;
  recordAnswer(selected ? selected.dataset.option : null, timeSpent);
}

// ── Answer handling ────────────────────────────────────────────────────────
function submitAnswer() {
  clearInterval(state.timerInterval);
  const selected = document.querySelector('.option-btn.selected');
  if (!selected) return;
  const timeSpent = Math.round((Date.now() - state.questionStart) / 1000);
  recordAnswer(selected.dataset.option, timeSpent);
}

function recordAnswer(selectedOption, timeSpent) {
  const q = state.questions[state.currentIndex];
  const correct = selectedOption === q.correct;
  const explanation = document.getElementById('explain-input').value.trim();

  // Visual feedback
  if (selectedOption) {
    document.querySelector(`.option-btn[data-option="${selectedOption}"]`)
      .classList.add(correct ? 'correct' : 'wrong');
    if (!correct) {
      document.querySelector(`.option-btn[data-option="${q.correct}"]`)
        ?.classList.add('correct');
    }
  }
  document.querySelectorAll('.option-btn').forEach(b => b.disabled = true);
  document.getElementById('btn-submit').disabled = true;

  state.answers.push({
    question: q.question,
    selectedOption,
    correct,
    explanation,
    timeSpent,
    correctAnswer: q.correct,
    correctExplanation: q.correctExplanation,
    section: q.section,
  });

  setTimeout(() => {
    state.currentIndex += 1;
    if (state.currentIndex < state.questions.length) {
      renderQuestion();
    } else {
      computeAndShowResults();
    }
  }, 1200);
}

// ── Scoring ────────────────────────────────────────────────────────────────
async function computeAndShowResults() {
  showScreen('loading');
  setLoadingMsg('Evaluating your responses…');

  let articulationScores = state.answers.map(() => 0);

  try {
    articulationScores = await scoreArticulation(state.answers);
  } catch {
    // Continue with zero articulation scores if Gemini call fails
  }

  const accuracy = calcAccuracy();           // 0–70
  const articulation = calcArticulation(articulationScores); // 0–20
  const timeliness = calcTimeliness();       // 0–10
  const total = Math.round(accuracy + articulation + timeliness);

  showScreen('results');
  renderResults(total, accuracy, articulation, timeliness, articulationScores);
}

function calcAccuracy() {
  const correct = state.answers.filter(a => a.correct).length;
  return (correct / state.answers.length) * 70;
}

function calcArticulation(scores) {
  const sum = scores.reduce((s, v) => s + v, 0);
  const max = 4 * state.answers.length; // max 4 per question
  return (sum / max) * 20;
}

function calcTimeliness() {
  // Linear: 0 s spent → full 1.0; 60 s spent → 0.0
  let total = 0;
  state.answers.forEach(a => {
    const t = Math.min(a.timeSpent, TIME_BUDGET_MCQ);
    total += Math.max(0, 1 - t / TIME_BUDGET_MCQ);
  });
  return (total / state.answers.length) * 10;
}

// ── Articulation scoring via Gemini ───────────────────────────────────────
async function scoreArticulation(answers) {
  const prompt = `Rate each student explanation for quality on a scale of 0–4:
0 = No explanation
1 = Irrelevant or completely wrong
2 = Vague or partially relevant
3 = Correct reasoning, reasonably clear
4 = Clear, accurate, demonstrates strong understanding

Return ONLY a JSON array of integers, one per question, e.g.: [3, 2, 0, 4, 1]

${answers.map((a, i) => `
Q${i + 1}: ${a.question}
Correct answer: ${a.correctAnswer} — ${a.correctExplanation}
Student chose: ${a.selectedOption || 'No answer'}
Student explanation: "${a.explanation || ''}"
`).join('\n')}`;

  const raw = await callGemini([{ text: prompt }]);
  const match = raw.match(/\[[\d,\s]+\]/);
  if (!match) return answers.map(() => 0);
  return JSON.parse(match[0]);
}

// ── Results rendering ──────────────────────────────────────────────────────
function renderResults(total, accuracy, articulation, timeliness) {
  document.getElementById('total-val').textContent = total;

  // Animate bars (as % of their max, scaled to 100% track width)
  requestAnimationFrame(() => {
    document.getElementById('bar-accuracy').style.width = `${(accuracy / 70) * 100}%`;
    document.getElementById('bar-articulation').style.width = `${(articulation / 20) * 100}%`;
    document.getElementById('bar-timeliness').style.width = `${(timeliness / 10) * 100}%`;
  });

  document.getElementById('val-accuracy').textContent = `${Math.round(accuracy)}/70`;
  document.getElementById('val-articulation').textContent = `${Math.round(articulation)}/20`;
  document.getElementById('val-timeliness').textContent = `${Math.round(timeliness)}/10`;

  const list = document.getElementById('suggestions-list');
  list.innerHTML = '';

  state.answers.forEach((a, i) => {
    const q = state.questions[i];
    const userOptionText = a.selectedOption
      ? `${a.selectedOption}: ${escapeHtml(q.options[a.selectedOption])}`
      : 'No answer';

    const div = document.createElement('div');
    div.className = `suggestion-item ${a.correct ? 'item-correct' : 'item-wrong'}`;
    div.innerHTML = `
      <div class="suggestion-q">
        <span class="q-num">Q${i + 1}</span>
        ${escapeHtml(a.question)}
      </div>
      <div class="your-answer ${a.correct ? 'answer-correct' : 'answer-wrong'}">
        ${a.correct ? '✓' : '✗'} Your answer: ${userOptionText}
      </div>
      ${!a.correct ? `
      <div class="suggestion-correct">
        ✓ Correct answer: ${escapeHtml(a.correctAnswer)}: ${escapeHtml(q.options[a.correctAnswer])}
      </div>` : ''}
      <div class="suggestion-explanation">${escapeHtml(a.correctExplanation)}</div>
      ${a.explanation ? `<div class="your-explanation">💬 Your explanation: "${escapeHtml(a.explanation)}"</div>` : ''}
      ${!a.correct ? `<div class="suggestion-section">📖 Review: ${escapeHtml(a.section)}</div>` : ''}
    `;
    list.appendChild(div);
  });
}

// ── Restart ────────────────────────────────────────────────────────────────
function restartAssessment() {
  Object.assign(state, {
    questions: [],
    currentIndex: 0,
    answers: [],
    questionStart: null,
    timerInterval: null,
    timeRemaining: TIME_BUDGET_MCQ,
  });
  clearInterval(state.timerInterval);
  document.getElementById('pdf-url').value = '';
  document.getElementById('pdf-file').value = '';
  document.getElementById('file-label-text').textContent = 'Choose PDF file…';
  showScreen('home');
}

// ── Utils ──────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
