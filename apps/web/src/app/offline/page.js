import Link from 'next/link';

export const metadata = {
  title: 'Offline | ScamSense',
};

export default function OfflinePage() {
  return (
    <div className="card" style={{ maxWidth: '560px', margin: '3rem auto', textAlign: 'center' }}>
      <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📡</div>
      <h1 style={{ fontSize: '1.4rem', marginBottom: '0.75rem' }}>You are offline</h1>
      <p style={{ color: '#94a3b8', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
        ScamSense needs a connection to run an analysis - the risk engine and the local AI
        both run on a device that is online. Anything you already checked stays in your
        history once you reconnect.
      </p>
      <Link href="/check" className="cta-button" style={{ display: 'inline-block' }}>
        Try again
      </Link>
    </div>
  );
}