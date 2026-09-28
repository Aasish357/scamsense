'use client';

import { useState } from 'react';
import apiRequest from '../../lib/apiClient';

export default function FeedbackPage() {
  const [username, setUsername] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null); // { type: 'success' | 'error', text: '' }

  const submitFeedback = async (e) => {
    e.preventDefault();
    if (!username.trim() || !message.trim()) return;
    setLoading(true);
    setStatus(null);

    try {
      const response = await apiRequest('/feedback', 'POST', {
        username,
        message,
      });
      setStatus({ type: 'success', text: response?.msg || 'Feedback submitted successfully!' });
      setMessage('');
    } catch (error) {
      console.error('Feedback submission failed:', error.message);
      setStatus({ type: 'error', text: error.message || 'Failed to submit feedback' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Submit Feedback</h1>
        <p style={{ color: '#94a3b8' }}>
          Encountered a false positive, false negative, or have a suggestion? Let our team know.
        </p>
      </div>

      {status && (
        <div style={{
          background: status.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
          border: `1px solid ${status.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          color: status.type === 'success' ? '#34d399' : '#f87171',
          padding: '0.85rem 1.25rem',
          borderRadius: '0.5rem',
          marginBottom: '1.5rem',
          fontSize: '0.9rem'
        }}>
          {status.text}
        </div>
      )}

      <div className="card">
        <form onSubmit={submitFeedback}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
              Your Username or Email
            </label>
            <input
              type="text"
              value={username}
              placeholder="e.g. user@example.com"
              required
              onChange={(e) => setUsername(e.target.value)}
              style={{
                width: '100%',
                background: '#0b0f19',
                border: '1px solid var(--card-border)',
                borderRadius: '0.5rem',
                color: '#fff',
                padding: '0.75rem',
                fontSize: '0.95rem'
              }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
              Message & Feedback
            </label>
            <textarea
              value={message}
              placeholder="Describe what occurred, link tested, or feedback..."
              rows={5}
              required
              onChange={(e) => setMessage(e.target.value)}
              style={{
                width: '100%',
                background: '#0b0f19',
                border: '1px solid var(--card-border)',
                borderRadius: '0.5rem',
                color: '#fff',
                padding: '0.75rem',
                fontSize: '0.95rem',
                resize: 'vertical'
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading || !username.trim() || !message.trim()}
            className="cta-button"
            style={{ width: '100%', justifyContent: 'center', padding: '0.85rem', opacity: loading ? 0.7 : 1 }}
          >
            {loading ? 'Submitting to FastAPI backend...' : 'Send Feedback ?'}
          </button>
        </form>
      </div>
    </div>
  );
}
