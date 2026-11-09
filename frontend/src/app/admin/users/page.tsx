'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createUser, getUsers, updateUser } from '@/lib/api';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { Segmented } from '@/components/ui/Segmented';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/Toast';
import { Search, Shield, UserPlus, X } from 'lucide-react';

interface DirectoryUser {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

type Role = 'analyst' | 'admin';
const ROLE_LABEL: Record<string, string> = { admin: 'Administrator', analyst: 'Analyst' };
// Mirrors the server's rule (app/services/accounts.py); the server has the final say.
const EMAIL_RE = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export default function UserManagementPage() {
  const { isAdmin, user: me } = useAuth();
  const { success, error: toastError } = useToast();
  const [users, setUsers] = useState<DirectoryUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const fetchUserList = async () => {
    try {
      setLoading(true);
      setUsers((await getUsers()) || []);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || 'Could not load the user list');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) fetchUserList();
  }, [isAdmin]);

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? users.filter((u) => u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)) : users;
  }, [users, search]);

  if (!isAdmin) {
    return (
      <div className="glass-card p-12 text-center">
        <Shield className="w-10 h-10 text-gray-400 mx-auto mb-3" aria-hidden />
        <h1 className="text-xl font-semibold text-gray-900">Administrators only</h1>
        <p className="text-sm text-gray-500 mt-1">Ask an administrator if you need to manage accounts.</p>
      </div>
    );
  }

  if (loading && users.length === 0 && !err) return <LoadingState message="Loading users" />;
  if (err && users.length === 0) return <ErrorState message={err} onRetry={fetchUserList} />;

  const change = async (u: DirectoryUser, data: { role?: Role; is_active?: boolean }, done: string) => {
    setBusyId(u.id);
    try {
      await updateUser(u.id, data);
      success(done, data.role ? `${u.username} is now ${data.role === 'admin' ? 'an administrator' : 'an analyst'}.` : undefined);
      await fetchUserList();
    } catch (e: any) {
      toastError(`Could not update ${u.username}`, e.message);
    } finally {
      setBusyId(null);
    }
  };

  const clearSearch = () => {
    setSearch('');
    searchRef.current?.focus();
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 pt-2">
        <div>
          <h1 className="text-[28px] leading-tight text-gray-900">Users</h1>
          <p className="text-sm text-gray-500 mt-1">Add accounts, change roles and switch access on or off. Accounts are never deleted.</p>
        </div>
        {!adding && (
          <button onClick={() => setAdding(true)} className="btn-primary self-start md:self-auto">
            <UserPlus className="w-4 h-4" aria-hidden /> Add user
          </button>
        )}
      </header>

      {adding && (
        <AddUserForm
          onCancel={() => setAdding(false)}
          onCreated={async (created) => {
            setAdding(false);
            success('User added', `${created.username} can sign in now as ${created.role === 'admin' ? 'an administrator' : 'an analyst'}.`);
            await fetchUserList();
          }}
        />
      )}

      <section className="glass-card" aria-label="User directory">
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-rule">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden />
            <input
              ref={searchRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && clearSearch()}
              placeholder="Search by name or email"
              aria-label="Search users"
              className="input-field pl-9 pr-9"
            />
            {search && (
              <button onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-gray-400 hover:text-gray-800 hover:bg-gray-100" aria-label="Clear search">
                <X className="w-4 h-4" aria-hidden />
              </button>
            )}
          </div>
          <p className="text-sm text-gray-500 tabular" aria-live="polite">
            {search.trim() ? `${filteredUsers.length} of ${users.length} users` : `${users.length} users`}
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Role</th>
                <th>Access</th>
                <th>Added</th>
                <th>Last sign-in</th>
                <th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => {
                const self = u.id === me?.id;
                const busy = busyId === u.id;
                return (
                  <tr key={u.id} className={u.is_active ? '' : 'opacity-70'}>
                    <td>
                      <div className="flex items-center gap-3">
                        <span className="w-8 h-8 shrink-0 rounded-full bg-gray-100 text-gray-700 grid place-items-center text-sm font-semibold">
                          {u.username?.[0]?.toUpperCase()}
                        </span>
                        <span className="min-w-0">
                          <span className="block font-medium text-gray-900">{u.username}{self && <span className="ml-1.5 text-xs font-normal text-gray-500">(you)</span>}</span>
                          <span className="block text-xs text-gray-500">{u.email}</span>
                        </span>
                      </div>
                    </td>
                    <td>
                      {ROLE_LABEL[u.role] ? (
                        <label className="sr-only" htmlFor={`role-${u.id}`}>Role for {u.username}</label>
                      ) : null}
                      {ROLE_LABEL[u.role] && !self ? (
                        <select
                          id={`role-${u.id}`}
                          value={u.role}
                          disabled={busy}
                          onChange={(e) => change(u, { role: e.target.value as Role }, 'Role changed')}
                          className="rounded-lg border-0 bg-transparent py-1 pl-0 pr-7 text-sm font-medium text-gray-900 hover:bg-gray-100 focus:ring-2 focus:ring-brand-500/30 cursor-pointer"
                        >
                          <option value="analyst">Analyst</option>
                          <option value="admin">Administrator</option>
                        </select>
                      ) : (
                        <StatusBadge status={u.role} size="sm" label={ROLE_LABEL[u.role] ?? `Unsupported role: ${u.role}`} />
                      )}
                    </td>
                    <td>
                      <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${u.is_active ? 'text-gray-900' : 'text-gray-500'}`}>
                        <span className={`w-2 h-2 rounded-full ${u.is_active ? 'bg-brand-500' : 'border border-gray-400'}`} aria-hidden />
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    <td className="text-gray-500 tabular">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="text-gray-500 tabular">{u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</td>
                    <td className="text-right">
                      {!self && (
                        <button onClick={() => change(u, { is_active: !u.is_active }, u.is_active ? 'Access switched off' : 'Access switched on')}
                          disabled={busy} className={`btn-ghost py-1.5 ${u.is_active ? 'hover:text-red-700 hover:bg-red-50' : ''}`}>
                          {u.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Empty states: no match for a search is different from an empty directory. */}
        {filteredUsers.length === 0 && users.length > 0 && (
          <EmptyState
            icon="search"
            title="No users match"
            message={`Nobody's name or email contains “${search.trim()}”. Check the spelling or clear the search to see all ${users.length} users.`}
            action={<button onClick={clearSearch} className="btn-secondary">Clear search</button>}
          />
        )}
        {users.length === 0 && (
          <EmptyState title="No users yet" message="Add the first account with Add user." />
        )}
      </section>
    </div>
  );
}

function AddUserForm({ onCancel, onCreated }: {
  onCancel: () => void;
  onCreated: (u: { username: string; role: string }) => void;
}) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>('analyst');
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const problems = {
    username: !username.trim() ? 'Enter a username' : null,
    email: !EMAIL_RE.test(email.trim()) ? 'Enter a valid email address, such as name@example.com' : null,
    password: password.length < 6 ? 'Use at least 6 characters' : null,
  };
  const valid = !problems.username && !problems.email && !problems.password;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    setServerError(null);
    if (!valid) return;
    setSaving(true);
    try {
      const created = await createUser({ username: username.trim(), email: email.trim(), password, role });
      onCreated(created);
    } catch (err: any) {
      setServerError(err.message || 'Could not add the user');
    } finally {
      setSaving(false);
    }
  };

  const field = (name: keyof typeof problems) => (touched && problems[name] ? problems[name] : null);

  return (
    <form onSubmit={submit} noValidate className="glass-card p-5 md:p-6 animate-expand" aria-label="Add a user">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="sheet-title">Add a user</h2>
          <p className="text-sm text-gray-500 mt-0.5">They sign in with this email and password. Share the password with them separately.</p>
        </div>
        <button type="button" onClick={onCancel} className="btn-ghost p-2" aria-label="Close">
          <X className="w-4 h-4" aria-hidden />
        </button>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <div>
          <label htmlFor="new-username" className="input-label">Username</label>
          <input id="new-username" className="input-field" value={username} onChange={(e) => setUsername(e.target.value)}
            autoComplete="off" maxLength={50} aria-invalid={!!field('username')} aria-describedby="new-username-err" autoFocus />
          {field('username') && <p id="new-username-err" className="mt-1 text-xs text-red-700">{field('username')}</p>}
        </div>
        <div>
          <label htmlFor="new-email" className="input-label">Email</label>
          <input id="new-email" type="email" className="input-field" value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="off" maxLength={100} placeholder="studentID@psu.edu.sa" aria-invalid={!!field('email')} aria-describedby="new-email-err" />
          {field('email') && <p id="new-email-err" className="mt-1 text-xs text-red-700">{field('email')}</p>}
        </div>
        <div>
          <label htmlFor="new-password" className="input-label">Password</label>
          <input id="new-password" type="password" className="input-field" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password" aria-invalid={!!field('password')} aria-describedby="new-password-err" />
          {field('password') && <p id="new-password-err" className="mt-1 text-xs text-red-700">{field('password')}</p>}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-700" id="new-role-label">Role</span>
          <Segmented role="group" label="Role" value={role} onChange={setRole}
            options={[{ value: 'analyst', label: 'Analyst' }, { value: 'admin', label: 'Administrator' }]} />
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onCancel} className="btn-ghost">Cancel</button>
          <button type="submit" disabled={saving} className="btn-primary">
            <UserPlus className="w-4 h-4" aria-hidden /> {saving ? 'Adding' : 'Add user'}
          </button>
        </div>
      </div>
      {role === 'admin' && (
        <p className="mt-3 text-sm text-gray-600 animate-fade-in">Administrators can launch scenarios, see what was injected, train models and manage users.</p>
      )}
      {serverError && <p className="mt-3 text-sm text-red-700 animate-fade-in" role="alert">{serverError}</p>}
    </form>
  );
}
