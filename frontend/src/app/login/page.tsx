'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { AuthLayout } from '@/components/AuthLayout';
import { Segmented } from '@/components/ui/Segmented';

// The seeded administrator. Other administrators added on the Users page type their own email.
const DEFAULT_ADMIN_EMAIL = 'admin@sensify.local';

export default function LoginPage() {
  const [selectedRole, setSelectedRole] = useState<'admin' | 'analyst'>('admin');
  const [adminEmail, setAdminEmail] = useState(DEFAULT_ADMIN_EMAIL);
  const [analystEmail, setAnalystEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const { user, login } = useAuth();
  const { success } = useToast();
  const router = useRouter();

  React.useEffect(() => {
    if (user) router.replace('/dashboard');
  }, [user, router]);

  const handleRoleSelect = (role: 'admin' | 'analyst') => {
    setSelectedRole(role);
    setPassword('');
    setFailure(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setFailure(null);
    const email = selectedRole === 'admin' ? adminEmail : analystEmail;
    try {
      await login(email, password);
      success('Signed in');
      router.push('/dashboard');
    } catch (err: any) {
      setFailure(err.message === 'Invalid credentials'
        ? 'That email and password do not match an account.'
        : err.message || 'Could not sign in');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <h1 className="text-[28px] leading-tight text-gray-900">Sign in</h1>
      <p className="mt-1 text-sm text-gray-500">Choose how you use Sensify.</p>

      <form onSubmit={handleSubmit} className="mt-7 space-y-5">
        <Segmented role="group" label="Account type" value={selectedRole} onChange={handleRoleSelect}
          options={[{ value: 'admin', label: 'Administrator' }, { value: 'analyst', label: 'Analyst' }]} />

        <div key={selectedRole} className="space-y-5 animate-fade-in">
          <div>
            <label htmlFor="email" className="input-label">Email</label>
            {selectedRole === 'admin' ? (
              <input id="email" type="email" required value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)}
                autoComplete="username" className="input-field" />
            ) : (
              <input id="email" type="email" required value={analystEmail} onChange={(e) => setAnalystEmail(e.target.value)}
                autoComplete="username" placeholder="you@example.com" className="input-field" />
            )}
          </div>
          <div>
            <label htmlFor="password" className="input-label">Password</label>
            <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password" className="input-field" />
          </div>
        </div>

        {failure && <p className="text-sm text-red-700 animate-fade-in" role="alert">{failure}</p>}

        <button type="submit" disabled={loading} className="btn-primary w-full py-3">
          {loading ? 'Signing in' : selectedRole === 'admin' ? 'Sign in as administrator' : 'Sign in as analyst'}
        </button>
      </form>

      {selectedRole === 'analyst' && (
        <p className="text-sm text-gray-500 mt-6 animate-fade-in">
          New analyst?{' '}
          <Link href="/register" className="font-medium text-brand-600 hover:underline">Create an account</Link>
        </p>
      )}
    </AuthLayout>
  );
}
