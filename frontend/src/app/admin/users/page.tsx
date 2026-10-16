'use client';

import React, { useEffect, useState } from 'react';
import { getUsers, updateUser } from '@/lib/api';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { LoadingState, ErrorState } from '@/components/ui/States';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { Users, Shield, Search } from 'lucide-react';

export default function UserManagementPage() {
  const { isAdmin } = useAuth();
  const { success, error: toastError } = useToast();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const fetchUserList = async () => {
    try {
      setLoading(true);
      const data = await getUsers();
      setUsers(data || []);
    } catch (e: any) {
      setErr(e.message || 'Failed to load user list');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      fetchUserList();
    }
  }, [isAdmin]);

  if (!isAdmin) {
    return (
      <div className="glass-card p-12 text-center border-red-500/30">
        <Shield className="w-12 h-12 text-red-400 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-gray-900">Access Restricted</h2>
        <p className="text-sm text-gray-500 mt-1">Admin privileges are required to view User Directory.</p>
      </div>
    );
  }

  if (loading && users.length === 0) {
    return <LoadingState message="Fetching system user directory..." />;
  }

  if (err && users.length === 0) {
    return <ErrorState message={err} onRetry={fetchUserList} />;
  }

  const handleToggleRole = async (u: any) => {
    const updatedRole = u.role === 'admin' ? 'analyst' : 'admin';
    try {
      await updateUser(u.id, { role: updatedRole });
      success('Role Updated', `${u.username} is now an ${updatedRole}.`);
      fetchUserList();
    } catch (e: any) {
      toastError('Failed to update role', e.message);
    }
  };

  const handleToggleActive = async (u: any) => {
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      success('Account Status Changed', `${u.username} active state updated.`);
      fetchUserList();
    } catch (e: any) {
      toastError('Failed to update user', e.message);
    }
  };

  const filteredUsers = users.filter(u =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="glass-card p-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Users className="w-6 h-6 text-brand-400" /> User Directory & Role Assignment
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          System directory listing authorized accounts. Account roles and active access can be modified below.
        </p>
      </div>

      {/* Search Bar */}
      <div className="glass-card p-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search users..."
            className="input-field pl-10 py-2 text-xs"
          />
        </div>
      </div>

      {/* User Directory Table */}
      <div className="glass-card p-6">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Account Name</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td className="font-mono text-xs text-gray-500">#{u.id}</td>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center font-bold text-xs text-brand-400">
                        {u.username?.[0]?.toUpperCase()}
                      </div>
                      <div>
                        <p className="font-semibold text-gray-800">{u.username}</p>
                        <p className="text-[11px] text-gray-500 font-mono">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={u.role} size="sm" />
                  </td>
                  <td>
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      u.is_active ? 'text-emerald-400' : 'text-gray-500'
                    }`}>
                      <span className={`w-2 h-2 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-gray-500'}`} />
                      {u.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-gray-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleRole(u)}
                        title="Toggle Role"
                        className="btn-ghost py-1 px-2.5 text-xs"
                      >
                        Toggle Role
                      </button>
                      <button
                        onClick={() => handleToggleActive(u)}
                        title="Toggle Active Status"
                        className="btn-ghost py-1 px-2.5 text-xs"
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
