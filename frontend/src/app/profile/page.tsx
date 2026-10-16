'use client';

import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { changePassword } from '@/lib/api';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { User, Shield, Lock, CheckCircle2, KeyRound } from 'lucide-react';

export default function ProfilePage() {
  const { user } = useAuth();
  const { success, error: toastError } = useToast();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      toastError('Password Mismatch', 'New password and confirmation do not match.');
      return;
    }

    if (newPassword.length < 6) {
      toastError('Password Too Short', 'New password must be at least 6 characters.');
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      success('Password Updated', 'Your account password has been updated successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      toastError('Failed to Change Password', err.message || 'Incorrect current password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      {/* Page Banner */}
      <div className="glass-card p-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <User className="w-6 h-6 text-brand-400" /> Account Settings & Security
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Manage your security credentials and inspect active session RBAC permissions.
        </p>
      </div>

      {/* Profile Info */}
      <div className="glass-card p-8 space-y-6">
        <div className="flex items-center gap-4 border-b border-gray-200 pb-6">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-600 to-brand-400 text-dark-950 font-black text-2xl flex items-center justify-center shadow-xl shadow-brand-500/20">
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-gray-900">{user?.username}</h2>
              <StatusBadge status={user?.role || 'analyst'} size="sm" />
            </div>
            <p className="text-xs text-gray-500 font-mono mt-1">{user?.email}</p>
          </div>
        </div>

        {/* Change Password Form */}
        <div className="space-y-4 pt-2">
          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-brand-400" /> Change Password
          </h3>

          <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
            <div>
              <label className="input-label">Current Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-500 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                  className="input-field pl-10"
                />
              </div>
            </div>

            <div>
              <label className="input-label">New Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-500 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password (min 6 chars)"
                  className="input-field pl-10"
                />
              </div>
            </div>

            <div>
              <label className="input-label">Confirm New Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-500 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
                  className="input-field pl-10"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="btn-primary py-2.5 px-6 text-sm font-semibold flex items-center gap-2"
            >
              {submitting ? 'Updating Password...' : 'Update Password'}
            </button>
          </form>
        </div>

        {/* Security Role Overview */}
        <div className="p-4 rounded-xl bg-brand-500/5 border border-brand-500/20 text-xs text-gray-600 space-y-2 mt-6">
          <h3 className="font-semibold text-brand-400 flex items-center gap-1.5">
            <Shield className="w-4 h-4" /> Account Role Summary
          </h3>
          {user?.role === 'admin' ? (
            <p className="text-gray-500 leading-relaxed">
              You are signed in as an <strong className="text-gray-800">Admin</strong> with privileges to launch simulation scenarios, control valves/pumps, and inspect system telemetry.
            </p>
          ) : (
            <p className="text-gray-500 leading-relaxed">
              You are signed in as an <strong className="text-gray-800">Analyst</strong> with privileges to explore the GIS pipeline map, view active/historical simulation runs, and inspect segment telemetry.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
