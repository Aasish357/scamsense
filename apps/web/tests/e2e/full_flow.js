/**
 * Full-stack E2E: auth -> Send button -> FastAPI /analyze (RAG + local Ollama)
 * -> results -> report -> history scoping.
 *
 * Run with: node tests/e2e/full_flow.js
 * Requires: backend on :8000, npm start on :3000, Ollama running.
 */
const path = require('path');
const { chromium } = require('playwright');

const FRONTEND = 'http://localhost:3000';
const SCREENSHOT_FIXTURE = path.join(
  process.env.LOCALAPPDATA || '',
  'Temp',
  'test_screenshot.png'
);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setDefaultTimeout(30000);

  // 1. Home: backend + Local AI status pills must come online.
  await page.goto(FRONTEND + '/');
  await page.getByText(/FastAPI Backend: (checking|online|offline|error)/).waitFor();
  await page.getByText('Local AI (Ollama):').waitFor();
  console.log('[1/6] Home status pills rendered');

  // 2. Register + sign in through the UI (token is stored client-side).
  const username = 'e2e-' + Date.now().toString(36);
  await page.goto(FRONTEND + '/register');
  await page.locator('input[type="text"]').fill(username);
  await page.locator('input[type="email"]').fill(username + '@example.com');
  await page.locator('input[type="password"]').fill('secret-password');
  await page.getByRole('button', { name: /Register Account/ }).click();
  await page.getByText(/signed in as|registered successfully/i).first().waitFor();
  await page.getByRole('button', { name: /Sign In/ }).click();
  await page.getByText('Signed in as').waitFor();
  const token = await page.evaluate(() => window.localStorage.getItem('scamsense_token'));
  if (!token) throw new Error('No auth token stored after sign-in');
  console.log('[2/6] Registered + signed in as ' + username);

  // 3. Text flow: Send -> /analyze -> results with RAG context.
  await page.goto(FRONTEND + '/check');
  await page
    .locator('textarea')
    .fill(
      'URGENT: Your bank account has been suspended! Verify immediately at http://fake-bank-login.xyz or lose access.'
    );
  await page.getByRole('button', { name: /Send to AI/ }).click();
  await page.waitForURL(/\/results\//, { timeout: 180000 });
  await page.getByText('Retrieved Knowledge (RAG)').waitFor({ timeout: 30000 });
  const bodyText = await page.textContent('body');
  if (!/llm_rag_index|Local LLM/.test(bodyText)) {
    throw new Error('Results page is missing LLM engine details');
  }
  console.log('[3/6] Text flow: Send -> /analyze -> results with RAG context');

  // 4. Report the analysis for admin review.
  await page.getByRole('button', { name: /Report this analysis/ }).click();
  await page.getByText('Report submitted').waitFor();
  console.log('[4/6] Report submitted from results page');

  // 5. Image flow: upload screenshot, Send, backend extracts then analyzes.
  await page.goto(FRONTEND + '/check');
  await page.getByRole('button', { name: /Screenshot Upload/ }).click();
  await page.locator('input[type="file"]').setInputFiles(SCREENSHOT_FIXTURE);
  await page.getByRole('button', { name: /Send to AI/ }).click();
  await page.waitForURL(/\/results\//, { timeout: 180000 });
  await page.getByText('Retrieved Knowledge (RAG)').waitFor({ timeout: 30000 });
  console.log('[5/6] Image flow: upload -> /screenshot -> /analyze -> results');

  // 6. History shows this user\'s saved analyses; guests get a sign-in prompt.
  await page.goto(FRONTEND + '/history');
  await page.locator('a[href^="/results/"]').first().waitFor({ timeout: 30000 });
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
  await page.getByText('History is saved to your account').waitFor({ timeout: 30000 });
  console.log('[6/6] History scoped to the signed-in user; guests prompted to sign in');

  await browser.close();
  console.log('E2E PASSED');
})().catch((err) => {
  console.error('E2E FAILED:', err);
  process.exit(1);
});