/**
 * ScamSense extension popup.
 *
 * Shows the last verdict, lets the user check the current page, and links into
 * the full web app for the detail the popup has no room for.
 */
const els = {
  empty: document.getElementById('empty-state'),
  result: document.getElementById('result'),
  score: document.getElementById('score'),
  level: document.getElementById('level'),
  engine: document.getElementById('engine'),
  summary: document.getElementById('summary'),
  evidence: document.getElementById('evidence'),
  recommendation: document.getElementById('recommendation'),
  error: document.getElementById('error'),
  settings: document.getElementById('settings'),
  apiBase: document.getElementById('api-base'),
  frontendBase: document.getElementById('frontend-base'),
};

let lastContent = '';
let lastResult = null;

function send(message) {
  return new Promise((resolve) => chrome.runtime.sendMessage(message, resolve));
}

function showError(message) {
  els.error.textContent = message;
  els.error.classList.toggle('hidden', !message);
}

function asList(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (value) return [String(value)];
  return [];
}

function render(record) {
  if (!record || !record.result) {
    els.result.classList.add('hidden');
    els.empty.classList.remove('hidden');
    return;
  }

  const result = record.result;
  lastResult = result;
  lastContent = record.content || '';

  els.empty.classList.add('hidden');
  els.result.classList.remove('hidden');

  const score = typeof result.risk_score === 'number' ? result.risk_score : null;
  els.score.textContent = score === null ? '--' : `${score}/100`;
  els.level.textContent = (result.risk_level || 'unknown').replace(/_/g, ' ');
  els.engine.textContent = result.engine === 'ollama_rag' ? 'Local AI + RAG' : 'Heuristic engine';
  els.summary.textContent = result.summary || '';

  els.evidence.innerHTML = '';
  const evidence = asList(result.evidence).slice(0, 5);
  const items = evidence.length ? evidence : ['No specific signals were flagged.'];
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    els.evidence.appendChild(li);
  }

  const recommendations = asList(result.recommendation);
  els.recommendation.textContent = recommendations.length
    ? recommendations.join(' ')
    : 'Verify through official channels before acting.';
}

async function check(text, source) {
  showError('');
  const response = await send({ type: 'scamsense:check', text, source });
  if (!response || !response.ok) {
    showError((response && response.error) || 'The check could not be completed.');
    return;
  }
  render({ result: response.result, content: response.content });
}

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

document.getElementById('check-page').addEventListener('click', async () => {
  const tab = await activeTab();
  if (!tab || !tab.url) {
    showError('No page is available to check.');
    return;
  }
  await check(tab.url, 'page');
});

document.getElementById('recheck').addEventListener('click', async () => {
  const tab = await activeTab();
  await check(lastContent || (tab && tab.url) || '', 'recheck');
});

document.getElementById('open-full').addEventListener('click', async () => {
  const settings = await send({ type: 'scamsense:settings' });
  const base = (settings && settings.frontendBase) || 'http://localhost:3000';
  const target = lastResult
    ? `${base}/check?prefill=1&text=${encodeURIComponent(lastContent.slice(0, 1500))}`
    : `${base}/check`;
  await chrome.tabs.create({ url: target });
  window.close();
});

document.getElementById('settings-toggle').addEventListener('click', async () => {
  const hidden = els.settings.classList.toggle('hidden');
  if (!hidden) {
    const settings = await send({ type: 'scamsense:settings' });
    els.apiBase.value = settings.apiBase || '';
    els.frontendBase.value = settings.frontendBase || '';
  }
});

document.getElementById('save-settings').addEventListener('click', async () => {
  await send({
    type: 'scamsense:save-settings',
    settings: { apiBase: els.apiBase.value, frontendBase: els.frontendBase.value },
  });
  showError('');
  els.settings.classList.add('hidden');
});

(async function init() {
  const record = await send({ type: 'scamsense:last' });
  render(record);
})();