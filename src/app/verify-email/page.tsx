'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { CheckCircle, XCircle, Loader2, ArrowRight } from 'lucide-react';
import { API_BASE_URL } from '../config';

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Missing verification token in URL.');
      return;
    }

    const verify = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/auth/verify-email?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Email verification failed.');
        setStatus('success');
        setMessage(data.message || 'Email successfully verified!');
      } catch (err: any) {
        setStatus('error');
        setMessage(err.message || 'Failed to verify email address.');
      }
    };

    verify();
  }, [token]);

  return (
    <div className="min-h-screen bg-[#0A0D14] text-white flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#111827]/80 border border-slate-800 rounded-3xl p-8 shadow-2xl text-center space-y-6">
        {status === 'loading' && (
          <div className="space-y-4">
            <Loader2 className="w-12 h-12 text-emerald-400 animate-spin mx-auto" />
            <h1 className="text-xl font-bold text-white">Verifying Email Address...</h1>
            <p className="text-xs text-slate-400 font-mono">Communicating with verification server...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-4">
            <CheckCircle className="w-16 h-16 text-emerald-400 mx-auto" />
            <h1 className="text-2xl font-bold text-white">Email Verified!</h1>
            <p className="text-sm text-slate-300">{message}</p>
            <button
              onClick={() => router.push('/login')}
              className="w-full py-3 bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-slate-950 font-bold rounded-xl shadow-lg transition flex items-center justify-center gap-2"
            >
              <span>Continue to Login</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <XCircle className="w-16 h-16 text-rose-400 mx-auto" />
            <h1 className="text-2xl font-bold text-white">Verification Failed</h1>
            <p className="text-sm text-slate-300">{message}</p>
            <button
              onClick={() => router.push('/login')}
              className="w-full py-3 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-200 font-bold rounded-xl transition"
            >
              Back to Login
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0A0D14] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
