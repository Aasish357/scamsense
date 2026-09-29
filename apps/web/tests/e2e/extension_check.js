/**
 * Browser extension integration test (apps/extension loaded into real Chromium).
 *
 * Messages are sent from a real extension page - the popup - so the test walks
 * the same path a user does: popup -> service worker -> ScamSense API, then it
 * asserts the verdict the popup actually renders and the badge the toolbar shows.
 *
 * Run with: node tests/e2e/extension_check.js
 * Requires: the ScamSense backend on http://127.0.0.1:8000.
 */
const os = require('os');
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const EXTENSION_PATH = path.join(__dirname, '..', '..', '..', 'extension');
const LOCAL_API = 'http://127.0.0.1:8000';
const SCAM_TEXT =
  'URGENT: your PayPal account is blocked. Verify now at http://paypal-verify-account.top/login or lose access.';
const CLEAN_TEXT = 'Hey, are we still meeting tomorrow for coffee?';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

(async () => {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'scamsense-ext-'));
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    args: [
      `--disable-extensions-except=${EXTENSION_PATH}`,
      `--load-extension=${EXTENSION_PATH}`,
    ],
  });

  try {
    let [worker] = context.serviceWorkers();
    if (!worker) worker = await context.waitForEvent('serviceworker', { timeout: 30000 });
    const extensionId = new URL(worker.url()).host;

    const page = await context.newPage();
    await page.goto(`chrome-extension://${extensionId}/popup.html`);
    const send = (message) =>
      page.evaluate((payload) => chrome.runtime.sendMessage(payload), message);
    console.log('extension loaded:', extensionId);

    // 1. The worker is listening and defaults to the local backend.
    const settings = await send({ type: 'scamsense:settings' });
    assert(settings && settings.apiBase === LOCAL_API, `Unexpected default API base: ${JSON.stringify(settings)}`);
    console.log('[1/5] Popup -> service worker messaging works; default API base is local');

    // 2. A scam message is flagged, badged and stored.
    const scam = await send({ type: 'scamsense:check', text: SCAM_TEXT, source: 'test' });
    assert(scam && scam.ok, `Scam check failed: ${scam && scam.error}`);
    assert(typeof scam.result.risk_score === 'number', 'No risk score returned');
    assert(scam.result.risk_score >= 50, `Expected a high score, got ${scam.result.risk_score}`);
    assert(scam.result.modality === 'text', 'Unexpected modality');
    const badge = await page.evaluate(() => chrome.action.getBadgeText({}));
    assert(badge === String(Math.round(scam.result.risk_score)), `Badge "${badge}" does not match the score`);
    console.log(`[2/5] Scam text scored ${scam.result.risk_score}/100 (${scam.result.risk_level}), badge "${badge}"`);

    // 3. The popup renders that verdict on open.
    await page.reload();
    await page.waitForSelector('#result:not(.hidden)');
    const popupText = await page.textContent('body');
    assert(popupText.includes(`${Math.round(scam.result.risk_score)}/100`), 'Popup does not show the score');
    assert(/Heuristic engine|Local AI/.test(popupText), 'Popup does not name the scoring engine');
    const evidenceCount = await page.locator('#evidence li').count();
    assert(evidenceCount > 0, 'Popup lists no evidence');
    console.log(`[3/5] Popup renders the verdict with ${evidenceCount} evidence item(s)`);

    // 4. A benign message scores materially lower.
    const clean = await send({ type: 'scamsense:check', text: CLEAN_TEXT, source: 'test' });
    assert(clean && clean.ok, `Clean check failed: ${clean && clean.error}`);
    assert(clean.result.risk_score < scam.result.risk_score, 'Benign text scored as high as a scam');
    console.log(`[4/5] Benign text scored ${clean.result.risk_score}/100 (${clean.result.risk_level})`);

    // 5. An unreachable API fails gracefully, then settings restore.
    await send({ type: 'scamsense:save-settings', settings: { apiBase: 'http://127.0.0.1:9' } });
    const broken = await send({ type: 'scamsense:check', text: SCAM_TEXT, source: 'test' });
    assert(broken && !broken.ok, 'An unreachable API should not report success');
    assert(/Could not reach the ScamSense API/.test(broken.error), `Unhelpful error: ${broken.error}`);
    await send({ type: 'scamsense:save-settings', settings: { apiBase: LOCAL_API } });
    const restored = await send({ type: 'scamsense:settings' });
    assert(restored.apiBase === LOCAL_API, 'Settings were not restored');
    console.log('[5/5] Unreachable API reported as a clear error, not a crash');

    await context.close();
    console.log('EXTENSION TEST PASSED');
  } catch (error) {
    await context.close();
    console.error('EXTENSION TEST FAILED:', error);
    process.exit(1);
  }
})();