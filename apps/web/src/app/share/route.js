import { NextResponse } from 'next/server';

/**
 * Server-side fallback for the PWA share target.
 *
 * The service worker normally intercepts the POST and parks the payload (files
 * included) in IndexedDB. This handler covers the cases where it cannot: the
 * first share before the worker is installed, or a platform that posts the
 * share straight to the network. Only short text/URL shares can travel in a
 * redirect, so anything longer is handed back to the user to paste.
 */
const MAX_INLINE_CHARS = 1500;

export async function POST(request) {
  let text = '';
  let url = '';
  try {
    const form = await request.formData();
    const readField = (name) => {
      const value = form.get(name);
      return typeof value === 'string' ? value : '';
    };
    text = readField('text') || readField('title');
    url = readField('url');
  } catch (error) {
    return NextResponse.redirect(new URL('/check?shared=error', request.url), { status: 303 });
  }

  const combined = [text.trim(), url.trim()].filter(Boolean).join('\n');
  if (!combined) {
    return NextResponse.redirect(new URL('/check?shared=empty', request.url), { status: 303 });
  }
  if (combined.length > MAX_INLINE_CHARS) {
    return NextResponse.redirect(new URL('/check?shared=toolong', request.url), { status: 303 });
  }

  const target = new URL('/check', request.url);
  target.searchParams.set('shared', '1');
  target.searchParams.set('text', combined);
  return NextResponse.redirect(target, { status: 303 });
}

export async function GET(request) {
  return NextResponse.redirect(new URL('/check', request.url), { status: 303 });
}