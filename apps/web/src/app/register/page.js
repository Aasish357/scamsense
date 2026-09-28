'use client';

import { useState } from 'react';
import apiRequest from '../../lib/apiClient';

export default function RegisterPage() {
  const [isLogin, setIsLogin] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatus(null);

    try {
      if (isLogin) {
        const response = await apiRequest('/login', 'POST', {
          username,
          password,
        });
        setStatus({ type: 'success', text: response?.msg || 'Logged in successfully!' });
      } else {
        const response = await apiRequest('/register', 'POST', {
          username,
          email,
          password,
        });
        setStatus({ type: 'success', text: response?.msg || 'Registered successfully! You can now log in.' });
        setIsLogin(true);
      }
    } catch (error) {
      console.error('Auth request failed:', error.message);
      setStatus({ type: 'error', text: error.message || 'Authentication failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '480px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          {isLogin ? 'Welcome Back' : 'Create an Account'}
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '0.95rem' }}>
          {isLogin ? 'Sign in to access your personal detection history' : 'Register to preserve risk analyses and reports'}
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
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              placeholder="e.g. johndoe"
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

          {!isLogin && (
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Email Address
              </label>
              <input
                type="email"
                value={email}
                placeholder="e.g. john@example.com"
                required
                onChange={(e) => setEmail(e.target.value)}
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
          )}

          <div style={{ marginBottom: '1.75rem' }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              placeholder="��������"
              required
              onChange={(e) => setPassword(e.target.value)}
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

          <button
            type="submit"
            disabled={loading}
            className="cta-button"
            style={{ width: '100%', justifyContent: 'center', padding: '0.85rem', fontSize: '1rem', opacity: loading ? 0.7 : 1 }}
          >
            {loading ? 'Processing...' : (isLogin ? 'Sign In ?' : 'Register Account ?')}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem', borderTop: '1px solid var(--card-border)', paddingTop: '1rem' }}>
          <button
            type="button"
            onClick={() => { setIsLogin(!isLogin); setStatus(null); }}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#60a5fa',
              fontSize: '0.875rem',
              cursor: 'pointer'
            }}
          >
            {isLogin ? "Don't have an account yet? Register" : "Already have an account? Sign In"}
          </button>
        </div>
      </div>
    </div>
  );
}
