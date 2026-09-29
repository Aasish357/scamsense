/**
 * ScamSense browser extension - background service worker (MV3).
 *
 * Turns whatever the user is looking at (a selection, a link, the page) into a
 * ScamSense analysis, badges the toolbar icon with the risk score, and keeps
 * the last verdict for the popup. Nothing is sent anywhere except the
 * configured ScamSense API; the extension has no analytics and no third-party
 * hosts in its permissions.
 */
const DEFAULT_SETTINGS = {
  apiBase: 'http://127.0.0.1:8000',
  frontendBase: 'http://localhost:3000',
};

const MENU_ITEMS = [
  { id: 'check-selection', title: 'Check selection with ScamSense', contexts: ['selection'] },
  { id: 'check-link', title: 'Check this link with ScamSense', contexts: ['link'] },
  { id: 'check-page', title: 'Check this page with ScamSense', contexts: ['page'] },
];

const BADGE_COLORS = {
  very_high: '#ef4444',
  high: '#f97316',
  suspicious: '#f59e0b',
  caution: '#eab308',
  low: '#22c55e',
};

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

async function saveSettings(patch) {
  const clean = {};
  if (patch && typeof patch.apiBase === 'string') clean.apiBase = patch.apiBase.trim().replace(/\/$/, '');
  if (patch && typeof patch.frontendBase === 'string') {
    clean.frontendBase = patch.frontendBase.trim().replace(/\/$/, '');
  }
  await chrome.storage.sync.set(clean);
  return getSettings();
}

async function getLastResult() {
  const stored = await chrome.storage.local.get('lastResult');
  return stored.lastResult || null;
}

function badgeColorFor(level) {
  return BADGE_COLORS[level] || '#64748b';
}

async function paintBadge(score, level) {
  const text = typeof score === 'number' && Number.isFinite(score)
    ? String(Math.max(0, Math.min(99, Math.round(score))))
    : '!';
  try {
    await chrome.action.setBadgeText({ text });
    await chrome.action.setBadgeBackgroundColor({ color: badgeColorFor(level) });
  } catch (error) {
    // Badging is cosmetic; never fail a check because of it.
  }
}

/**
 * Run one analysis. Returns {ok: true, result, content} or {ok: false, error}.
 */
export async function runCheck({ text = '', url = '', source = 'manual' } = {}) {
  const content = [String(text || '').trim(), String(url || '').trim()].filter(Boolean).join('\n');
  if (!content) {
    return { ok: false, error: 'Nothing to check. Select some text, or open the page you want to check.' };
  }

  const { apiBase } = await getSettings();
  let response;
  try {
    response = await fetch(`${apiBase}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        question: 'Check this for scam signals',
        modality: 'text',
      }),
    });
  } catch (error) {
    return {
      ok: false,
      error: `Could not reach the ScamSense API at ${apiBase}. Check it is running and, for a remote API, that you granted the extension access to it.`,
    };
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    return { ok: false, error: detail.detail || `ScamSense API error (${response.status}).` };
  }

  const result = await response.json();
  const record = { result, content, source, at: Date.now() };
  await chrome.storage.local.set({ lastResult: record });
  await paintBadge(result.risk_score, result.risk_level);
  return { ok: true, result, content };
}

function createMenus() {
  chrome.contextMenus.removeAll(() => {
    for (const item of MENU_ITEMS) chrome.contextMenus.create(item);
  });
}

chrome.runtime.onInstalled.addListener(createMenus);
chrome.runtime.onStartup.addListener(createMenus);

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'check-selection') {
    runCheck({ text: info.selectionText, url: info.pageUrl, source: 'selection' });
  } else if (info.menuItemId === 'check-link') {
    runCheck({ text: info.linkUrl, url: info.pageUrl, source: 'link' });
  } else if (info.menuItemId === 'check-page') {
    runCheck({ text: (tab && tab.url) || '', url: info.pageUrl, source: 'page' });
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== 'string') return false;
  if (message.type === 'scamsense:check') {
    runCheck(message).then(sendResponse);
    return true;
  }
  if (message.type === 'scamsense:last') {
    getLastResult().then(sendResponse);
    return true;
  }
  if (message.type === 'scamsense:settings') {
    getSettings().then(sendResponse);
    return true;
  }
  if (message.type === 'scamsense:save-settings') {
    saveSettings(message.settings).then(sendResponse);
    return true;
  }
  return false;
});

export { getSettings, getLastResult };