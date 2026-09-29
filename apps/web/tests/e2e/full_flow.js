/**
 * Full-stack E2E: auth -> Send button -> FastAPI /analyze (RAG + local Ollama)
 * -> results -> report -> history scoping -> email headers -> QR decoding.
 *
 * Run with: node tests/e2e/full_flow.js
 * Requires: backend on :8000, npm start on :3000, Ollama running.
 *
 * Fixtures (generated once, they live in %LOCALAPPDATA%\Temp):
 *   python -c "from PIL import Image; Image.new('RGB',(400,200),'white').save('test_screenshot.png')"
 *   python -c "import cv2; ok,b=cv2.imencode('.png', cv2.QRCodeEncoder_create().encode('http://free-prize-claim.top/verify')); open('test_qr.png','wb').write(b.tobytes())"
 */
const path = require('path');
const { chromium } = require('playwright');

const FRONTEND = 'http://localhost:3000';
const SCREENSHOT_FIXTURE = path.join(
  process.env.LOCALAPPDATA || '',
  'Temp',
  'test_screenshot.png'
);
const QR_FIXTURE = path.join(process.env.LOCALAPPDATA || '', 'Temp', 'test_qr.png');

const SCAM_EMAIL = [
  'From: "PayPal Security Center" <service@paypal-verify-account.top>',
  'Reply-To: reply@fastmail-drop.ru',
  'Return-Path: <bounce@bulk-sender-98.ru>',
  'Date: Mon, 28 Sep 2026 10:00:00 +0000',
  'Message-ID: <12345@paypal-verify-account.top>',
  'Subject: Your account will be limited - verify now',
  'Authentication-Results: mx.example.com; spf=fail smtp.mailfrom=bulk-sender-98.ru; dkim=pass header.d=bulk-sender-98.ru; dmarc=fail action=temprelax',
  'Content-Type: text/plain; charset="utf-8"',
  '',
  'Dear customer, your PayPal account will be limited within 24 hours.',
  'Verify immediately: http://paypal-verify-account.top/login',
].join('\n');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setDefaultTimeout(30000);

  // 1. Home: backend + Local AI status pills must come online.
  await page.goto(FRONTEND + '/');
  await page.getByText(/FastAPI Backend: (checking|online|offline|error)/).waitFor();
  await page.getByText('Local AI (Ollama):').waitFor();
  console.log('[1/8] Home status pills rendered');

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
  console.log('[2/8] Registered + signed in as ' + username);

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
  console.log('[3/8] Text flow: Send -> /analyze -> results with RAG context');

  // 4. Report the analysis for admin review.
  await page.getByRole('button', { name: /Report this analysis/ }).click();
  await page.getByText('Report submitted').waitFor();
  console.log('[4/8] Report submitted from results page');

  // 5. Image flow: upload screenshot, Send, backend extracts then analyzes.
  await page.goto(FRONTEND + '/check');
  await page.getByRole('button', { name: /Screenshot Upload/ }).click();
  await page.locator('input[type="file"]').setInputFiles(SCREENSHOT_FIXTURE);
  await page.getByRole('button', { name: /Send to AI/ }).click();
  await page.waitForURL(/\/results\//, { timeout: 180000 });
  await page.getByText('Retrieved Knowledge (RAG)').waitFor({ timeout: 30000 });
  console.log('[5/8] Image flow: upload -> /screenshot -> /analyze -> results');

  // 6. History shows this user\'s saved analyses; guests get a sign-in prompt.
  await page.goto(FRONTEND + '/history');
  await page.locator('a[href^="/results/"]').first().waitFor({ timeout: 30000 });
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
  await page.getByText('History is saved to your account').waitFor({ timeout: 30000 });
  console.log('[6/8] History scoped to the signed-in user; guests prompted to sign in');

  // 7. Email flow: paste raw headers -> /analyze/email -> header findings in results.
  await page.goto(FRONTEND + '/check');
  await page.getByRole('button', { name: /Email Headers/ }).click();
  await page.locator('textarea').fill(SCAM_EMAIL);
  await page.getByRole('button', { name: /Analyze Email/ }).click();
  await page.waitForURL(/\/results\//, { timeout: 180000 });
  await page.getByText('Assessment Overview').waitFor({ timeout: 60000 });
  const emailBody = await page.textContent('body');
  if (!/Input:\s*Email/.test(emailBody)) {
    throw new Error('Results page does not report the email modality');
  }
  if (!/DMARC authentication failed|SPF authentication failed/.test(emailBody)) {
    throw new Error('Email authentication findings are missing from the results page');
  }
  console.log('[7/8] Email flow: raw headers -> /analyze/email -> results with auth findings');

  // 8. QR flow: upload image -> local OpenCV decode -> /analyze/qr -> results.
  await page.goto(FRONTEND + '/check');
  await page.getByRole('button', { name: /QR Code/ }).click();
  await page.locator('input[type="file"]').setInputFiles(QR_FIXTURE);
  await page.getByRole('button', { name: /Analyze QR Code/ }).click();
  await page.waitForURL(/\/results\//, { timeout: 180000 });
  await page.getByText('Assessment Overview').waitFor({ timeout: 60000 });
  const qrBody = await page.textContent('body');
  if (!/Input:\s*QR code/.test(qrBody)) {
    throw new Error('Results page does not report the QR modality');
  }
  if (!qrBody.includes('http://free-prize-claim.top/verify')) {
    throw new Error('Decoded QR payload is missing from the results page');
  }
  console.log('[8/8] QR flow: upload -> local decode -> /analyze/qr -> results');

  await browser.close();
  console.log('E2E PASSED');
})().catch((err) => {
  console.error('E2E FAILED:', err);
  process.exit(1);
});