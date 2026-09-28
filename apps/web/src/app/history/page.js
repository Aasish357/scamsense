'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import apiRequest from '../../lib/apiClient';

export default function HistoryPage() {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnalyses = async () => {
    try {
      const data = await apiRequest('/api/v1/me/analyses');
      setAnalyses(data || []);
    } catch (err) {
      console.error('Error fetching history:', err);
      setError(err.status === 401 ? 'signin' : (err.message || 'Failed to fetch history'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalyses();
  }, []);

  const handleDelete = async (e, analysisId) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Are you sure you want to remove this analysis from history?')) return;

    try {
      await apiRequest(`/analyses/${analysisId}`, 'DELETE');
      setAnalyses((prev) => prev.filter((item) => item.analysis_id !== analysisId));
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.25rem' }}>Analysis History</h1>
          <p style={{ color: '#94a3b8' }}>
            Browse through your saved scam checks, indicators, and risk scores.
          </p>
        </div>
        <Link href="/check" className="cta-button" style={{ fontSize: '0.9rem' }}>
          + New Check
        </Link>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ color: '#94a3b8' }}>Loading past analyses from FastAPI...</p>
        </div>
      )}

      {error === 'signin' && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>🔒</div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>History is saved to your account</h3>
          <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
            Sign in to see the analyses you have saved.
          </p>
          <Link href="/register" className="cta-button">Sign In</Link>
        </div>
      )}

      {error && error !== 'signin' && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171',
          padding: '1rem',
          borderRadius: '0.5rem',
          marginBottom: '1.5rem'
        }}>
          Failed to load history: {error}
        </div>
      )}

      {!loading && !error && analyses.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '3.5rem 1.5rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>??</div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>No checks saved yet</h3>
          <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
            Run your first message, link, or screenshot check to see results populated here.
          </p>
          <Link href="/check" className="cta-button">Run First Check</Link>
        </div>
      )}

      {!loading && !error && analyses.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {analyses.map((analysis) => {
            const badgeClass =
              analysis.risk_level === 'low'
                ? 'badge-low'
                : analysis.risk_level === 'caution'
                ? 'badge-caution'
                : analysis.risk_level === 'suspicious'
                ? 'badge-suspicious'
                : 'badge-high';

            return (
              <div
                key={analysis.analysis_id}
                className="card"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '1.25rem 1.5rem',
                  gap: '1rem',
                  flexWrap: 'wrap'
                }}
              >
                <div style={{ flex: 1, minWidth: '240px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.35rem' }}>
                    <span className={badgeClass} style={{ padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase' }}>
                      {analysis.risk_level || 'Unknown'}
                    </span>
                    <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                      {analysis.created_at ? new Date(analysis.created_at).toLocaleDateString() : ''}
                    </span>
                  </div>

                  <p style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '0.25rem' }}>
                    {analysis.summary || 'Analysis Result'}
                  </p>
                  <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    ID: {analysis.analysis_id}
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>SCORE</span>
                    <span style={{ fontSize: '1.35rem', fontWeight: 700, color: (analysis.risk_score || 0) > 60 ? '#ef4444' : ((analysis.risk_score || 0) > 30 ? '#f59e0b' : '#10b981') }}>
                      {analysis.risk_score ?? 'N/A'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <Link
                      href={`/results/${analysis.analysis_id}`}
                      style={{
                        padding: '0.45rem 0.9rem',
                        borderRadius: '0.35rem',
                        background: '#1e293b',
                        color: '#93c5fd',
                        fontSize: '0.85rem',
                        fontWeight: 600
                      }}
                    >
                      View Report ?
                    </Link>
                    <button
                      onClick={(e) => handleDelete(e, analysis.analysis_id)}
                      title="Delete record"
                      style={{
                        background: 'transparent',
                        border: '1px solid #334155',
                        color: '#94a3b8',
                        padding: '0.45rem 0.65rem',
                        borderRadius: '0.35rem',
                        fontSize: '0.85rem'
                      }}
                    >
                      ???
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
