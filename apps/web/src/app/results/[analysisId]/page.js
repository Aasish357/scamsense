'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import apiRequest from '../../../lib/apiClient';

const MODALITY_LABELS = {
  text: 'Text / URL',
  screenshot: 'Screenshot',
  email: 'Email',
  qr: 'QR code',
};

export default function ResultPage() {
  const params = useParams();
  const router = useRouter();
  const analysisId = params?.analysisId;

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reportDone, setReportDone] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadAnalysis() {
      if (!analysisId) return;
      try {
        const data = await apiRequest(`/analyses/${analysisId}`);
        if (isMounted) setResult(data);
      } catch (err) {
        if (isMounted) setError(err.message || 'Analysis record not found');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadAnalysis();
    return () => { isMounted = false; };
  }, [analysisId]);

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this analysis?')) return;
    setDeleting(true);
    try {
      await apiRequest(`/analyses/${analysisId}`, 'DELETE');
      router.push('/history');
    } catch (err) {
      alert(err.status === 401 ? 'Sign in to delete saved analyses.' : `Failed to delete: ${err.message}`);
      setDeleting(false);
    }
  };

  const handleReport = async () => {
    setReporting(true);
    try {
      await apiRequest('/reports', 'POST', {
        analysis_id: analysisId,
        reason: 'user_flagged_suspicious',
        message: 'Flagged from the results page for admin review.',
      });
      setReportDone(true);
    } catch (err) {
      alert(`Failed to submit report: ${err.message}`);
    } finally {
      setReporting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
        <p style={{ color: '#94a3b8', fontSize: '1.1rem' }}>Loading analysis results from FastAPI backend...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="card" style={{ maxWidth: '600px', margin: '2rem auto', textAlign: 'center' }}>
        <h2 style={{ color: '#ef4444', marginBottom: '1rem' }}>Analysis Not Found</h2>
        <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
          {error || 'The requested analysis record does not exist or has been removed.'}
        </p>
        <Link href="/check" className="cta-button">Run a New Check</Link>
      </div>
    );
  }

  const badgeClass =
    result.risk_level === 'low'
      ? 'badge-low'
      : result.risk_level === 'caution'
      ? 'badge-caution'
      : result.risk_level === 'suspicious'
      ? 'badge-suspicious'
      : 'badge-high';

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <Link href="/history" style={{ fontSize: '0.85rem', color: '#60a5fa', display: 'inline-block', marginBottom: '0.5rem' }}>
            ? Back to History
          </Link>
          <h1 style={{ fontSize: '2rem', fontWeight: 700 }}>Assessment Overview</h1>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginTop: '0.25rem' }}>
            ID: <code style={{ color: '#cbd5e1' }}>{result.analysis_id}</code> � {result.created_at ? new Date(result.created_at).toLocaleString() : 'Recent'}
          </p>
        </div>

        <button
          onClick={handleDelete}
          disabled={deleting}
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            padding: '0.5rem 1rem',
            borderRadius: '0.4rem',
            fontWeight: 600,
            fontSize: '0.85rem'
          }}
        >
          {deleting ? 'Deleting...' : '??? Delete Record'}
        </button>
      </div>

      {/* Main Score Card */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Risk Level
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.25rem' }}>
              <span className={badgeClass} style={{ padding: '0.35rem 0.85rem', borderRadius: '9999px', fontWeight: 700, fontSize: '1rem', textTransform: 'uppercase' }}>
                {result.risk_level || 'Unknown'}
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>
                Score: {result.risk_score ?? 'N/A'}/100
              </span>
            </div>
          </div>

          <div style={{ textAlign: 'right', fontSize: '0.85rem', color: '#64748b' }}>
            <div>Method: <strong>{result.score_kind || 'heuristic_index'}</strong></div>
            <div>Engine Version: <strong>{result.scoring_version || 'local-1'}</strong></div>
            {result.llm_model ? <div>Local LLM: <strong>{result.llm_model}</strong></div> : null}
            {result.modality && result.modality !== 'text' ? (
              <div>Input: <strong>{MODALITY_LABELS[result.modality] || result.modality}</strong></div>
            ) : null}
            {result.engine === 'heuristic_fallback' && result.score_kind === 'heuristic_index' ? <div>AI offline - heuristic fallback used</div> : null}
          </div>
        </div>

        {/* Progress Bar */}
        <div style={{ width: '100%', height: '8px', background: '#1e293b', borderRadius: '9999px', overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${Math.min(Math.max(result.risk_score || 0, 5), 100)}%`,
              backgroundColor: (result.risk_score || 0) > 60 ? '#ef4444' : ((result.risk_score || 0) > 30 ? '#f59e0b' : '#10b981'),
              transition: 'width 0.5s ease'
            }}
          />
        </div>

        {/* Summary */}
        <div style={{ background: '#0b0f19', padding: '1.25rem', borderRadius: '0.5rem', border: '1px solid var(--card-border)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem', color: '#93c5fd' }}>
            Summary
          </h3>
          <p style={{ color: '#f8fafc', fontSize: '0.95rem' }}>
            {result.summary || 'No summary text available.'}
          </p>
        </div>
      </div>

      {/* Extracted Links (from text or screenshot OCR) */}
      {Array.isArray(result.extracted_links) && result.extracted_links.length > 0 && (
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
            🔗 Extracted Links
          </h3>
          <ul style={{ paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.9rem' }}>
            {result.extracted_links.map((link, idx) => (
              <li key={idx} style={{ marginBottom: '0.35rem', wordBreak: 'break-all' }}>{link}</li>
            ))}
          </ul>
        </div>
      )}

      {/* QR payload and phone numbers decoded from the submitted input */}
      {(Array.isArray(result.qr_payloads) && result.qr_payloads.length > 0) || (Array.isArray(result.extracted_phones) && result.extracted_phones.length > 0) ? (
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
            🔳 Decoded QR Payload / 📞 Contact Numbers
          </h3>
          <ul style={{ paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.9rem' }}>
            {Array.isArray(result.qr_payloads) && result.qr_payloads.map((payload, idx) => (
              <li key={`qr-${idx}`} style={{ marginBottom: '0.35rem', wordBreak: 'break-all' }}>{payload}</li>
            ))}
            {Array.isArray(result.extracted_phones) && result.extracted_phones.map((phone, idx) => (
              <li key={`phone-${idx}`} style={{ marginBottom: '0.35rem' }}>{phone}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* RAG: knowledge retrieved from the local scam-pattern corpus */}
      {Array.isArray(result.rag_context) && result.rag_context.length > 0 && (
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.35rem' }}>
            🧠 Retrieved Knowledge (RAG)
          </h3>
          <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '1rem' }}>
            Scam patterns matched against this content and fed to the local LLM as grounding context.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {result.rag_context.map((match, idx) => (
              <div
                key={idx}
                style={{ background: '#0b0f19', padding: '0.9rem 1rem', borderRadius: '0.5rem', border: '1px solid var(--card-border)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.35rem' }}>
                  <strong style={{ fontSize: '0.9rem', color: '#93c5fd' }}>{match.title}</strong>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    {match.category} · similarity {typeof match.score === 'number' ? match.score.toFixed(2) : match.score}
                  </span>
                </div>
                <p style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{match.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evidence & Recommendation Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>??</span> Supported Evidence
          </h3>
          <div style={{ background: '#0b0f19', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--card-border)', minHeight: '100px' }}>
            {Array.isArray(result.evidence) ? (
              <ul style={{ paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.9rem' }}>
                {result.evidence.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: '0.35rem' }}>{item}</li>
                ))}
              </ul>
            ) : (
              <p style={{ color: '#cbd5e1', fontSize: '0.9rem' }}>
                {result.evidence || 'No specific suspicious signals flagged.'}
              </p>
            )}
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>???</span> Recommended Action
          </h3>
          <div style={{ background: '#0b0f19', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--card-border)', minHeight: '100px' }}>
            {Array.isArray(result.recommendation) ? (
              <ul style={{ paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.9rem' }}>
                {result.recommendation.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: '0.35rem' }}>{item}</li>
                ))}
              </ul>
            ) : (
              <p style={{ color: '#cbd5e1', fontSize: '0.9rem' }}>
                {result.recommendation || 'Proceed with standard caution and verify through known official channels.'}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Report this analysis for admin review */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <button
          type="button"
          onClick={handleReport}
          disabled={reporting || reportDone}
          style={{
            padding: '0.6rem 1.5rem',
            borderRadius: '0.5rem',
            background: reportDone ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.1)',
            border: '1px solid ' + (reportDone ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.3)'),
            color: reportDone ? '#34d399' : '#f87171',
            fontWeight: 600,
            fontSize: '0.9rem'
          }}
        >
          {reportDone ? '✓ Report submitted' : (reporting ? 'Submitting report...' : '🚩 Report this analysis')}
        </button>
      </div>

      {/* Footer Actions */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '1rem' }}>
        <Link href="/check" className="cta-button" style={{ padding: '0.75rem 1.75rem' }}>
          Run Another Analysis
        </Link>
        <Link href="/feedback" style={{
          padding: '0.75rem 1.75rem',
          borderRadius: '0.5rem',
          background: 'var(--card-bg)',
          border: '1px solid var(--card-border)',
          fontWeight: 600
        }}>
          Report Feedback
        </Link>
      </div>
    </div>
  );
}
