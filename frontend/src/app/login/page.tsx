'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { Lock, Mail, ArrowRight, ShieldCheck } from 'lucide-react';

export default function LoginPage() {
  const [selectedRole, setSelectedRole] = useState<'admin' | 'analyst'>('admin');
  const [analystEmail, setAnalystEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, login } = useAuth();
  const { error, success } = useToast();
  const router = useRouter();

  React.useEffect(() => {
    if (user) {
      router.replace('/dashboard');
    }
  }, [user, router]);

  const handleRoleSelect = (role: 'admin' | 'analyst') => {
    setSelectedRole(role);
    setPassword('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    // Admin signs in to the pre-seeded admin account; analysts use their own email
    const email = selectedRole === 'admin' ? 'admin@sensify.local' : analystEmail;

    try {
      await login(email, password);
      success('Logged in successfully', `Authenticated as ${selectedRole === 'admin' ? 'System Administrator' : 'Telemetry Analyst'}`);
      router.push('/dashboard');
    } catch (err: any) {
      error('Authentication Failed', err.message || 'Incorrect password for selected account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-white ">
      {/* Background Ambient Glows */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/10 rounded-full blur-[128px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[128px] pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <img src="/sensify-logo.png" alt="Sensify" className="w-16 h-16 mx-auto mb-4 rounded-2xl" />
          <h1 className="text-2xl font-bold text-gray-900 tracking-wide">
            Sensify
          </h1>
          <p className="text-xs text-gray-500 mt-1 font-mono">
            Pipeline Intelligence & Real-time Monitoring Platform
          </p>
        </div>

        {/* Login Glass Card */}
        <div className="glass-card p-8 shadow-2xl border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-brand-400" /> Account Authentication
          </h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Account Selector */}
            <div>
              <label className="input-label">Select Account Role</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => handleRoleSelect('admin')}
                  className={`p-3.5 rounded-xl border text-left transition-all ${selectedRole === 'admin'
                      ? 'bg-brand-500/10 border-brand-500 text-gray-900 shadow-lg shadow-brand-500/10'
                      : 'bg-gray-50 border-gray-200 text-gray-500 hover:border-gray-200 hover:text-gray-600'
                    }`}
                >
                  <p className="font-semibold text-sm">Administrator</p>
                  <p className="text-[10px] text-gray-500 font-mono mt-0.5">Full System Access</p>
                </button>

                <button
                  type="button"
                  onClick={() => handleRoleSelect('analyst')}
                  className={`p-3.5 rounded-xl border text-left transition-all ${selectedRole === 'analyst'
                      ? 'bg-brand-500/10 border-brand-500 text-gray-900 shadow-lg shadow-brand-500/10'
                      : 'bg-gray-50 border-gray-200 text-gray-500 hover:border-gray-200 hover:text-gray-600'
                    }`}
                >
                  <p className="font-semibold text-sm">Analyst</p>
                  <p className="text-[10px] text-gray-500 font-mono mt-0.5">View & Monitor</p>
                </button>
              </div>
            </div>

            {/* Email Input (analyst accounts only) */}
            {selectedRole === 'analyst' && (
              <div>
                <label className="input-label">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-gray-500 absolute left-3.5 top-3.5" />
                  <input
                    type="email"
                    required
                    value={analystEmail}
                    onChange={(e) => setAnalystEmail(e.target.value)}
                    placeholder="analyst@sensify.local"
                    className="input-field pl-10"
                  />
                </div>
              </div>
            )}

            {/* Password Input */}
            <div>
              <label className="input-label">Account Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-500 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter account password"
                  className="input-field pl-10"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 flex items-center justify-center gap-2 mt-6 text-sm font-semibold"
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>Sign In as {selectedRole === 'admin' ? 'Admin' : 'Analyst'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {selectedRole === 'analyst' && (
            <p className="text-xs text-center text-gray-500 mt-6">
              Don&apos;t have an account?{' '}
              <Link href="/register" className="text-brand-400 hover:underline font-semibold">
                Sign Up
              </Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
