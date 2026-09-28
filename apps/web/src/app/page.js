'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import apiRequest from '../lib/apiClient';

export default function Home() {
  const [backendStatus, setBackendStatus] = useState('checking');

  useEffect(() => {
    let isMounted = true;
    async function checkHealth() {
      try {
        const res = await apiRequest('/health');
        if (isMounted) {
          setBackendStatus(res?.status === 'ok' ? 'online' : 'error');
        }
      } catch (err) {
        if (isMounted) {
          setBackendStatus('offline');
        }
      }
    }
    checkHealth();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3rem' }}>
      {/* Hero */}
      <section style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto', paddingTop: '1.5rem' }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.35rem 0.85rem',
          borderRadius: '9999px',
          background: 'rgba(59, 130, 246, 0.1)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          marginBottom: '1.5rem',
          fontSize: '0.85rem'
        }}>
          <span style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: backendStatus === 'online' ? '#10b981' : (backendStatus === 'checking' ? '#f59e0b' : '#ef4444')
          }}></span>
          <span>FastAPI Backend: <strong>{backendStatus}</strong></span>
        </div>

        <h1 style={{ fontSize: '2.8rem', fontWeight: 800, lineHeight: 1.15, letterSpacing: '-0.03em', marginBottom: '1.25rem' }}>
          Know Before <span style={{ color: '#60a5fa' }}>You Trust</span>.
        </h1>
        <p style={{ fontSize: '1.15rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: '2rem' }}>
          ScamSense helps you evaluate suspicious messages, phishing links, and screenshot captures with clear, evidence-based indicators.
        </p>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link href="/check" className="cta-button" style={{ padding: '0.75rem 1.6rem', fontSize: '1rem' }}>
            Evaluate Message or Link →
          </Link>
          <Link href="/history" style={{
            padding: '0.75rem 1.6rem',
            borderRadius: '0.5rem',
            background: 'var(--card-bg)',
            border: '1px solid var(--card-border)',
            fontWeight: 600,
            fontSize: '1rem'
          }}>
            View History
          </Link>
        </div>
      </section>

      {/* Feature Grid */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        <div className="card">
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>💬</div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '0.5rem' }}>Text & Message Analysis</h3>
          <p style={{ color: '#94a3b8', fontSize: '0.925rem' }}>
            Instant scan for urgency cues, impersonation, credential harvesting triggers, and suspicious keywords.
          </p>
        </div>

        <div className="card">
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>🔗</div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '0.5rem' }}>URL & Domain Scrutiny</h3>
          <p style={{ color: '#94a3b8', fontSize: '0.925rem' }}>
            Passive lexical inspection detecting spoofed domains, suspicious TLDs, and homoglyphs before you click.
          </p>
        </div>

        <div className="card">
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>📸</div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '0.5rem' }}>Screenshot OCR</h3>
          <p style={{ color: '#94a3b8', fontSize: '0.925rem' }}>
            Upload suspicious chat screenshots or email captures to extract text and analyze risk patterns automatically.
          </p>
        </div>
      </section>

      {/* Architecture note */}
      <section className="card" style={{ background: '#0f172a', borderColor: '#1e293b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.25rem' }}>FastAPI Backend Connected</h4>
            <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
              Endpoints active: <code>/check</code>, <code>/screenshot</code>, <code>/brand/{'{name}'}</code>, <code>/analyses/{'{id}'}</code>, <code>/api/v1/me/analyses</code>.
            </p>
          </div>
          <Link href="/check" style={{ color: '#60a5fa', fontWeight: 600, fontSize: '0.9rem' }}>
            Start analyzing →
          </Link>
        </div>
      </section>
    </div>
  );
}
