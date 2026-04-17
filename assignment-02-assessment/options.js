'use strict';

const input = document.getElementById('api-key-input');
const btnToggle = document.getElementById('btn-toggle');
const btnSave = document.getElementById('btn-save');
const btnClear = document.getElementById('btn-clear');
const statusMsg = document.getElementById('status-msg');

// Load saved key
document.addEventListener('DOMContentLoaded', async () => {
  const { apiKey = '' } = await chrome.storage.sync.get('apiKey');
  if (apiKey) input.value = apiKey;
});

// Toggle visibility
btnToggle.addEventListener('click', () => {
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btnToggle.textContent = show ? '🙈' : '👁';
});

// Save
btnSave.addEventListener('click', async () => {
  const key = input.value.trim();
  if (!key) {
    showStatus('Please enter an API key.', 'error');
    return;
  }
  await chrome.storage.sync.set({ apiKey: key });
  showStatus('API key saved.', 'success');
});

// Clear
btnClear.addEventListener('click', async () => {
  await chrome.storage.sync.remove('apiKey');
  input.value = '';
  showStatus('API key cleared.', 'success');
});

function showStatus(msg, type) {
  statusMsg.textContent = msg;
  statusMsg.className = `status-msg ${type}`;
  statusMsg.classList.remove('hidden');
  setTimeout(() => statusMsg.classList.add('hidden'), 3000);
}
