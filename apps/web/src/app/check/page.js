'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import apiRequest from '../../lib/apiClient';
import { clearSharedPayload, composeSharedText, readSharedPayload } from '../../lib/shareTarget';

// NEXT_PUBLIC_API_URL is the production name (set it on Vercel to the Render backend URL).
// NEXT_PUBLIC_API_BASE_URL is kept so existing setups keep working.
const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'
).replace(/\/$/, '');

const TABS = [
  { id: 'text', label: '💬 Text / URL Check' },
  { id: 'image', label: '📸 Screenshot Upload' },
  { id: 'email', label: '✉️ Email Headers' },
  { id: 'qr', label: '🔳 QR Code' },
];

export default function CheckPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('text'); // 'text' | 'image' | 'email' | 'qr'
  const [inputText, setInputText] = useState('');
  const [emailText, setEmailText] = useState('');
  const [emailFile, setEmailFile] = useState(null);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState('');

  // Share target (PWA "Share to ScamSense") and manifest shortcuts.
  // The service worker parks shared text/links/images in IndexedDB; the
  // server-side /share fallback passes short shares through the query string.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shared = params.get('shared');
    const tab = params.get('tab');
    const prefill = params.get('prefill');
    if (!shared && !tab && !prefill) return undefined;

    const clean = () => window.history.replaceState({}, '', '/check');

    if (tab === 'qr' || tab === 'image' || tab === 'email') {
      setActiveTab(tab);
      clean();
      return undefined;
    }
    if (prefill === '1') {
      // Deep link used by the browser extension's "Open in ScamSense" button.
      const value = (params.get('text') || '').slice(0, 1500);
      if (value) {
        setInputText(value);
        setActiveTab('text');
        setNotice('Loaded from the browser extension. Review it, then send.');
      } else {
        setError('The extension did not pass any content.');
      }
      clean();
      return undefined;
    }
    if (!shared) return undefined;

    const fail = (message) => {
      setError(message);
      clean();
    };

    if (shared === 'empty') {
      fail('Nothing was shared. Paste the message or pick a file below.');
      return undefined;
    }
    if (shared === 'toolong') {
      fail('That shared message was too long to bring over. Paste it into the box below.');
      return undefined;
    }
    if (shared === 'error') {
      fail('ScamSense could not read what was shared. Please paste it instead.');
      return undefined;
    }

    const inline = params.get('text');
    if (inline) {
      setInputText(inline);
      setActiveTab('text');
      setNotice('Loaded from your share. Review it, then send.');
      clean();
      return undefined;
    }

    let cancelled = false;
    readSharedPayload().then(async (payload) => {
      if (cancelled) return;
      if (!payload) {
        fail('The shared content expired. Please share it again.');
        return;
      }
      if (payload.image) {
        const file = new File([payload.image], payload.image.name || 'shared-image.png', {
          type: payload.image.type || 'image/png',
        });
        setFile(file);
        setActiveTab('image');
        setNotice('Loaded the shared image. Review it, then send.');
      } else {
        const text = composeSharedText(payload);
        if (text) {
          setInputText(text);
          setActiveTab('text');
          setNotice('Loaded from your share. Review it, then send.');
        } else {
          fail('That share was empty.');
          return;
        }
      }
      await clearSharedPayload();
      clean();
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // Quick preset buttons for demo testing
  const presets = [
    { label: 'Phishing URL', text: 'Urgent! Your account is suspended. Verify immediately at http://fake-bank-login.xyz' },
    { label: 'Trusted Brand', text: 'Thank you for your order with ExampleBrand. Your receipt is attached.' },
    { label: 'Normal Text', text: 'Hey, are we still meeting tomorrow for coffee?' },
  ];

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    setLoading(true);
    setError(null);

    try {
      // Extract -> RAG retrieval -> local LLM analysis, all server-side.
      setStatus('Sending content to the local AI engine...');
      const data = await apiRequest('/analyze', 'POST', { content: inputText });
      if (data?.analysis_id) {
        setStatus('Analysis complete. Loading results...');
        router.push(`/results/${data.analysis_id}`);
      } else {
        throw new Error('Analysis completed but no ID returned');
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to analyze text content');
      setLoading(false);
      setStatus('');
    }
  };

  const handleImageSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select an image file first');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      // Step 1: extract text + links from the image (OCR / local vision model).
      setStatus('Extracting text and links from the image...');
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${BASE_URL}/screenshot`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to process screenshot');
      }

      const screenshotResult = await res.json();
      const extractedText = (screenshotResult.extracted_text || '').trim();
      const warnings = screenshotResult.warnings || [];

      if (!extractedText) {
        // Nothing was readable. Analysing an empty message would return a low
        // risk score, which reads as "this screenshot is safe" - the opposite
        // of what an unreadable image means.
        setError(
          warnings[0] ||
            'No text could be read from that image. Paste the message text instead.'
        );
        setLoading(false);
        setStatus('');
        return;
      }
      if (warnings.length) setNotice(warnings[0]);

      // Step 2: send the extracted content to the LLM + RAG pipeline.
      setStatus('Sending extracted content to the local AI engine...');
      const checkResult = await apiRequest('/analyze', 'POST', {
        content: extractedText,
        question: 'Analyze this screenshot for scam signals',
        modality: 'screenshot',
      });

      if (checkResult?.analysis_id) {
        setStatus('Analysis complete. Loading results...');
        router.push(`/results/${checkResult.analysis_id}`);
      } else {
        throw new Error('Screenshot analyzed but could not create analysis record');
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to analyze screenshot');
      setLoading(false);
      setStatus('');
    }
  };

  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    if (!emailText.trim() && !emailFile) {
      setError('Paste the raw email (headers included) or choose a .eml file');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      if (emailFile) {
        // .eml upload: headers are parsed server-side and scored before the LLM.
        setStatus('Reading the uploaded email and checking its headers...');
        const formData = new FormData();
        formData.append('file', emailFile);
        const res = await fetch(`${BASE_URL}/analyze/email/upload`, {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.detail || 'Failed to analyze the email file');
        }
        const data = await res.json();
        if (data?.analysis_id) {
          setStatus('Analysis complete. Loading results...');
          router.push(`/results/${data.analysis_id}`);
          return;
        }
        throw new Error('Email analyzed but no analysis ID was returned');
      }

      setStatus('Verifying SPF/DKIM/DMARC and sending to the local AI engine...');
      const data = await apiRequest('/analyze/email', 'POST', { raw_email: emailText });
      if (data?.analysis_id) {
        setStatus('Analysis complete. Loading results...');
        router.push(`/results/${data.analysis_id}`);
      } else {
        throw new Error('Email analyzed but no analysis ID was returned');
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to analyze email');
      setLoading(false);
      setStatus('');
    }
  };

  const handleQrSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select an image containing a QR code first');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      // The QR payload is decoded locally with OpenCV, never uploaded to a
      // third-party scanner.
      setStatus('Decoding the QR code and analyzing the payload...');
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${BASE_URL}/analyze/qr`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to analyze the QR code');
      }

      const data = await res.json();
      if (data?.analysis_id) {
        setStatus('Analysis complete. Loading results...');
        router.push(`/results/${data.analysis_id}`);
      } else {
        throw new Error('QR code analyzed but no analysis ID was returned');
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to analyze QR code');
      setLoading(false);
      setStatus('');
    }
  };

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Run a Scam Check</h1>
        <p style={{ color: '#94a3b8' }}>
          Evaluate suspicious text messages, emails, phishing links, or upload a screenshot. Every send is analyzed by the local LLM with RAG-based scam knowledge.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '0.75rem', flexWrap: 'wrap' }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => { setActiveTab(tab.id); setError(null); }}
            style={{
              background: activeTab === tab.id ? 'var(--primary)' : 'transparent',
              color: activeTab === tab.id ? '#fff' : 'var(--text-muted)',
              border: 'none',
              padding: '0.5rem 1.15rem',
              borderRadius: '0.4rem',
              fontWeight: 600,
              fontSize: '0.9rem'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171',
          padding: '0.85rem 1.25rem',
          borderRadius: '0.5rem',
          marginBottom: '1.5rem',
          fontSize: '0.9rem'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {notice && (
        <div
          style={{
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: '0.5rem',
            padding: '0.75rem 1rem',
            marginBottom: '1.5rem',
            color: '#bfdbfe',
            fontSize: '0.9rem'
          }}
        >
          {notice}
        </div>
      )}

      {loading && (
        <div style={{
          background: 'rgba(59, 130, 246, 0.1)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          color: '#93c5fd',
          padding: '0.85rem 1.25rem',
          borderRadius: '0.5rem',
          marginBottom: '1.5rem',
          fontSize: '0.9rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem'
        }}>
          <span style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            border: '2px solid rgba(147, 197, 253, 0.3)',
            borderTopColor: '#93c5fd',
            animation: 'spin 0.8s linear infinite',
            display: 'inline-block'
          }} />
          {status || 'Working...'}
        </div>
      )}

      {activeTab === 'text' && (
        <div className="card">
          <form onSubmit={handleTextSubmit}>
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Content to Analyze
              </label>
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Paste the suspicious message, email body, or URL here..."
                rows={6}
                required
                style={{
                  width: '100%',
                  background: '#0b0f19',
                  border: '1px solid var(--card-border)',
                  borderRadius: '0.5rem',
                  color: '#fff',
                  padding: '0.85rem',
                  fontSize: '0.95rem',
                  fontFamily: 'inherit',
                  resize: 'vertical'
                }}
              />
            </div>

            {/* Presets */}
            <div style={{ marginBottom: '1.5rem' }}>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8', marginRight: '0.5rem' }}>Try an example:</span>
              <div style={{ display: 'inline-flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                {presets.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => setInputText(preset.text)}
                    style={{
                      background: '#1e293b',
                      border: '1px solid #334155',
                      color: '#cbd5e1',
                      fontSize: '0.75rem',
                      padding: '0.25rem 0.6rem',
                      borderRadius: '0.35rem'
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !inputText.trim()}
              className="cta-button"
              style={{ width: '100%', justifyContent: 'center', padding: '0.85rem', fontSize: '1rem', opacity: loading ? 0.7 : 1 }}
            >
              {loading ? 'Local AI is analyzing...' : 'Send to AI →'}
            </button>
            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.75rem', textAlign: 'center' }}>
              Sent to the local Ollama LLM with RAG-retrieved scam patterns. Falls back to heuristics if the AI is offline.
            </p>
          </form>
        </div>
      )}

      {activeTab === 'image' && (
        <div className="card">
          <form onSubmit={handleImageSubmit}>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Upload Screenshot
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
                style={{
                  width: '100%',
                  background: '#0b0f19',
                  border: '1px dashed var(--card-border)',
                  borderRadius: '0.5rem',
                  color: '#94a3b8',
                  padding: '1.5rem',
                  textAlign: 'center',
                  fontSize: '0.9rem'
                }}
              />
              <p style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.5rem' }}>
                Text and links are extracted on the backend (OCR / local vision model), then the extracted content is sent to the LLM for risk analysis.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading || !file}
              className="cta-button"
              style={{ width: '100%', justifyContent: 'center', padding: '0.85rem', fontSize: '1rem', opacity: loading ? 0.7 : 1 }}
            >
              {loading ? 'Extracting & Analyzing...' : 'Send to AI →'}
            </button>
          </form>
        </div>
      )}

      {activeTab === 'email' && (
        <div className="card">
          <form onSubmit={handleEmailSubmit}>
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Raw Email (headers included)
              </label>
              <textarea
                value={emailText}
                onChange={(e) => setEmailText(e.target.value)}
                placeholder={'From: "Bank Support" <no-reply@bank-alert.xyz>\nReply-To: attacker@fastmail-drop.ru\nAuthentication-Results: spf=fail; dkim=none; dmarc=fail\nSubject: Your account will be limited\n\nDear customer, verify your account immediately...'}
                rows={9}
                style={{
                  width: '100%',
                  background: '#0b0f19',
                  border: '1px solid var(--card-border)',
                  borderRadius: '0.5rem',
                  color: '#fff',
                  padding: '0.85rem',
                  fontSize: '0.95rem',
                  fontFamily: 'inherit',
                  resize: 'vertical'
                }}
              />
              <p style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.5rem' }}>
                Paste the full message starting at the "From:" line. SPF, DKIM, DMARC, Reply-To / Return-Path mismatches, brand spoofing and risky attachments are checked on the backend.
              </p>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Or upload a .eml / .txt file
              </label>
              <input
                type="file"
                accept=".eml,.txt,message/rfc822,text/plain"
                onChange={(e) => setEmailFile(e.target.files?.[0] || null)}
                style={{
                  width: '100%',
                  background: '#0b0f19',
                  border: '1px dashed var(--card-border)',
                  borderRadius: '0.5rem',
                  color: '#94a3b8',
                  padding: '1.25rem',
                  textAlign: 'center',
                  fontSize: '0.9rem'
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading || (!emailText.trim() && !emailFile)}
              className="cta-button"
              style={{ width: '100%', justifyContent: 'center', padding: '0.85rem', fontSize: '1rem', opacity: loading ? 0.7 : 1 }}
            >
              {loading ? 'Analyzing Email...' : 'Analyze Email →'}
            </button>
          </form>
        </div>
      )}

      {activeTab === 'qr' && (
        <div className="card">
          <form onSubmit={handleQrSubmit}>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Upload QR Code Image
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
                style={{
                  width: '100%',
                  background: '#0b0f19',
                  border: '1px dashed var(--card-border)',
                  borderRadius: '0.5rem',
                  color: '#94a3b8',
                  padding: '1.5rem',
                  textAlign: 'center',
                  fontSize: '0.9rem'
                }}
              />
              <p style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.5rem' }}>
                Decoded locally with OpenCV — the image never reaches a third-party QR scanner. The payload is then scored for lookalike domains, suspicious TLDs and "scan to pay" (upi://) codes.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading || !file}
              className="cta-button"
              style={{ width: '100%', justifyContent: 'center', padding: '0.85rem', fontSize: '1rem', opacity: loading ? 0.7 : 1 }}
            >
              {loading ? 'Decoding & Analyzing...' : 'Analyze QR Code →'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}