// NEXT_PUBLIC_API_URL is the production name (set it on Vercel to the Render backend URL).
// NEXT_PUBLIC_API_BASE_URL is kept so existing setups keep working.
const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'
).replace(/\/$/, '');

const TOKEN_KEY = 'scamsense_token';
const USER_KEY = 'scamsense_user';

export function getToken() {
    if (typeof window === 'undefined') return null;
    return window.localStorage.getItem(TOKEN_KEY);
}

export function getUsername() {
    if (typeof window === 'undefined') return null;
    return window.localStorage.getItem(USER_KEY);
}

export function setSession(token, username) {
    if (typeof window === 'undefined') return;
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    if (username) window.localStorage.setItem(USER_KEY, username);
}

export function clearSession() {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
    };

    const token = getToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : null,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.detail || 'An error occurred');
        error.status = response.status;
        throw error;
    }

    return await response.json();
}

export default apiRequest;