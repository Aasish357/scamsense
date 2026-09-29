'use client';

import { useEffect, useState } from 'react';

// NEXT_PUBLIC_API_URL is the production name (set it on Vercel to the Render backend URL).
// NEXT_PUBLIC_API_BASE_URL is kept so existing setups keep working.
const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'
).replace(/\/$/, '');
const KEY_STORAGE = 'scamsense_admin_key';
const box = { background: '#0b0f19', border: '1px solid var(--card-border)', borderRadius: '0.5rem', padding: '0.7rem 1rem', fontSize: '0.9rem' };

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState('');
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = async (key) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(BASE_URL + '/admin/overview', { headers: { 'x-admin-key': key } });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Admin request failed');
      setOverview(data);
      window.sessionStorage.setItem(KEY_STORAGE, key);
    } catch (err) {
      setOverview(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const stored = typeof window !== 'undefined' ? window.sessionStorage.getItem(KEY_STORAGE) : null;
    if (stored) {
      setAdminKey(stored);
      load(stored);
    }
  }, []);

  const stats = (overview && overview.stats) || {};
  const cards = [
    ['Analyses', stats.analyses],
    ['Feedback', stats.feedback],
    ['Reports', stats.reports],
    ['Avg risk score', stats.average_risk_score == null ? 'n/a' : stats.average_risk_score],
  ];

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Admin Console</h1>
      <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
        Read-only view of analyses, feedback and user reports. Requires the backend ADMIN_API_KEY.
      </p>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={(e) => { e.preventDefault(); load(adminKey.trim()); }} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="Admin API key"
            style={{ flex: 1, minWidth: '240px', background: '#0b0f19', border: '1px solid var(--card-border)', borderRadius: '0.5rem', color: '#fff', padding: '0.75rem' }}
          />
          <button type="submit" className="cta-button" disabled={loading || !adminKey.trim()}>
            {loading ? 'Loading...' : 'Unlock'}
          </button>
        </form>
        {error ? <p style={{ color: '#f87171', fontSize: '0.9rem', marginTop: '0.75rem' }}>{error}</p> : null}
      </div>

      {overview ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
            {cards.map((card) => (
              <div className="card" key={card[0]} style={{ textAlign: 'center', padding: '1.25rem' }}>
                <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#93c5fd' }}>{card[1]}</div>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{card[0]}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1rem' }}>Latest reports</h3>
            {overview.reports.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: '0.9rem' }}>No reports submitted yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {overview.reports.map((item, index) => (
                  <div key={index} style={box}>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                      {(item.created_at || '') + ' · ' + (item.username || 'guest') + ' · ' + (item.reason || '')}
                    </div>
                    <div>{item.message || 'No message provided.'}</div>
                    {item.analysis_id ? <div style={{ fontSize: '0.75rem', color: '#64748b' }}>analysis: {item.analysis_id}</div> : null}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1rem' }}>Latest feedback</h3>
            {overview.feedback.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: '0.9rem' }}>No feedback submitted yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {overview.feedback.map((item, index) => (
                  <div key={index} style={box}>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                      {(item.created_at || '') + ' · ' + (item.username || 'guest')}
                    </div>
                    <div>{item.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1rem' }}>Recent analyses</h3>
            {overview.recent_analyses.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: '0.9rem' }}>No analyses recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {overview.recent_analyses.map((item, index) => (
                  <div key={index} style={box}>
                    <div style={{ fontFamily: 'monospace', color: '#94a3b8', wordBreak: 'break-all' }}>{item.analysis_id}</div>
                    <div>{'score ' + item.risk_score + ' · ' + (item.risk_level || '') + ' · ' + (item.score_kind || '') + ' · ' + (item.owner || 'guest')}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}