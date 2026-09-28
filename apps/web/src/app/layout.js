import './globals.css';
import Link from 'next/link';

export const metadata = {
  title: 'ScamSense | Know Before You Trust',
  description: 'Evidence-grounded heuristic risk assessment for messages, URLs, and screenshots.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="header-container">
          <Link href="/" className="brand-logo">
            <span style={{ fontSize: '1.4rem' }}>🛡️</span>
            <span>ScamSense</span>
            <span className="brand-badge">MVP</span>
          </Link>
          <nav className="nav-links">
            <Link href="/check" className="nav-link">Check</Link>
            <Link href="/history" className="nav-link">History</Link>
            <Link href="/feedback" className="nav-link">Feedback</Link>
            <Link href="/admin" className="nav-link">Admin</Link>
            <Link href="/register" className="nav-link">Account</Link>
            <Link href="/check" className="cta-button">Run Check</Link>
          </nav>
        </header>

        <main className="main-content">
          {children}
        </main>

        <footer className="footer">
          <p>
            ScamSense is a decision-support tool. It returns heuristic indicators and evidence — never a guarantee of safety or fraud.
          </p>
          <p style={{ marginTop: '0.4rem', fontSize: '0.78rem' }}>
            FastAPI Backend: <code style={{ color: '#93c5fd' }}>/api/v1/health</code> · Next.js Client
          </p>
        </footer>
      </body>
    </html>
  );
}
