'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { AuthLayout } from '@/components/AuthLayout';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const { register } = useAuth();
  const { success } = useToast();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFailure(null);
    if (password !== confirmPassword) {
      setFailure('The two passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await register(username, email, password);
      success('Account created', 'You are signed in as an analyst.');
      router.push('/dashboard');
    } catch (err: any) {
      setFailure(err.message || 'Could not create the account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <h1 className="text-[28px] leading-tight text-gray-900">Create an analyst account</h1>
      <p className="mt-1 text-sm text-gray-500">Analysts investigate runs and incidents. Administrators are added by an administrator.</p>

      <form onSubmit={handleSubmit} className="mt-7 space-y-4">
        <div>
          <label htmlFor="username" className="input-label">Name</label>
          <input id="username" required value={username} onChange={(e) => setUsername(e.target.value)} maxLength={50}
            autoComplete="name" className="input-field" />
        </div>
        <div>
          <label htmlFor="email" className="input-label">Email</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} maxLength={100}
            autoComplete="email" placeholder="studentID@psu.edu.sa" className="input-field" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="password" className="input-label">Password</label>
            <input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password" className="input-field" />
          </div>
          <div>
            <label htmlFor="confirm" className="input-label">Repeat password</label>
            <input id="confirm" type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password" className="input-field" />
          </div>
        </div>
        <p className="text-xs text-gray-500">At least 6 characters.</p>

        {failure && <p className="text-sm text-red-700 animate-fade-in" role="alert">{failure}</p>}

        <button type="submit" disabled={loading} className="btn-primary w-full py-3">
          {loading ? 'Creating account' : 'Create account'}
        </button>
      </form>

      <p className="text-sm text-gray-500 mt-6">
        Already have an account?{' '}
        <Link href="/" className="font-medium text-brand-600 hover:underline">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
