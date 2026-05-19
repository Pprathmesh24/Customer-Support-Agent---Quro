'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';

const DEMO_ADMIN_EMAIL = process.env.NEXT_PUBLIC_DEMO_ADMIN_EMAIL ?? '';
const DEMO_ADMIN_PASSWORD = process.env.NEXT_PUBLIC_DEMO_ADMIN_PASSWORD ?? '';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setLoading(true);
    setFormError(null);

    const { error } = await createClient().auth.signInWithPassword({ email, password });
    if (error) {
      setFormError(error.message);
      setLoading(false);
      return;
    }
    router.push('/chat');
  }

  async function handleAdminDemo(): Promise<void> {
    setDemoLoading(true);
    setDemoError(null);

    const { error } = await createClient().auth.signInWithPassword({
      email: DEMO_ADMIN_EMAIL,
      password: DEMO_ADMIN_PASSWORD,
    });

    if (error) {
      setDemoError(error.message);
      setDemoLoading(false);
      return;
    }
    router.push('/admin/documents');
  }

  const adminReady = Boolean(DEMO_ADMIN_EMAIL && DEMO_ADMIN_PASSWORD);

  return (
    <div className="w-full max-w-sm">
      {/* Admin demo shortcut */}
      {adminReady && (
        <div className="mb-5 rounded-2xl border border-blue-100 bg-blue-50 p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </span>
            <div>
              <p className="text-sm font-semibold text-blue-900">Admin Demo</p>
              <p className="text-xs text-blue-600">Upload docs · View escalations · Knowledge gaps</p>
            </div>
          </div>

          {demoError && (
            <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{demoError}</p>
          )}

          <button
            onClick={() => void handleAdminDemo()}
            disabled={demoLoading}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {demoLoading ? 'Signing in…' : 'Login as Admin →'}
          </button>
        </div>
      )}

      {/* Divider */}
      <div className="relative mb-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-gray-50 px-3 text-xs text-gray-400">or sign in with your account</span>
        </div>
      </div>

      {/* Regular login */}
      <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-900">Welcome back</h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to your Quro account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {formError && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{formError}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-gray-500">
          {"Don't have an account? "}
          <Link href="/signup" className="font-medium text-blue-600 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
