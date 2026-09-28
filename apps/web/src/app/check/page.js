'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import apiRequest from '../../lib/apiClient';

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export default function CheckPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('text'); // 'text' | 'image'
  const [inputText, setInputText] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState(null);

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
      const extractedText = screenshotResult.extracted_text || '';

      // Step 2: send the extracted content to the LLM + RAG pipeline.
      setStatus('Sending extracted content to the local AI engine...');
      const checkResult = await apiRequest('/analyze', 'POST', {
        content: extractedText || 'Uploaded screenshot with no readable text',
        question: 'Analyze this screenshot for scam signals',
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

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Run a Scam Check</h1>
        <p style={{ color: '#94a3b8' }}>
          Evaluate suspicious text messages, emails, phishing links, or upload a screenshot. Every send is analyzed by the local LLM with RAG-based scam knowledge.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '0.75rem' }}>
        <button
          type="button"
          onClick={() => { setActiveTab('text'); setError(null); }}
          style={{
            background: activeTab === 'text' ? 'var(--primary)' : 'transparent',
            color: activeTab === 'text' ? '#fff' : 'var(--text-muted)',
            border: 'none',
            padding: '0.5rem 1.15rem',
            borderRadius: '0.4rem',
            fontWeight: 600,
            fontSize: '0.9rem'
          }}
        >
          💬 Text / URL Check
        </button>
        <button
          type="button"
          onClick={() => { setActiveTab('image'); setError(null); }}
          style={{
            background: activeTab === 'image' ? 'var(--primary)' : 'transparent',
            color: activeTab === 'image' ? '#fff' : 'var(--text-muted)',
            border: 'none',
            padding: '0.5rem 1.15rem',
            borderRadius: '0.4rem',
            fontWeight: 600,
            fontSize: '0.9rem'
          }}
        >
          📸 Screenshot Upload
        </button>
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

      {activeTab === 'text' ? (
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
      ) : (
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
    </div>
  );
}