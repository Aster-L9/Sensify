'use client';

import React, { useLayoutEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  LayoutDashboard,
  Map,
  Activity,
  Users,
  User,
  LogOut,
  BellRing,
  FlaskConical,
  BrainCircuit,
  FileSearch,
  Scale,
  X,
  type LucideIcon,
} from 'lucide-react';

interface NavItem { name: string; href: string; icon: LucideIcon }

export function Sidebar({ isOpen, setIsOpen }: { isOpen?: boolean; setIsOpen?: (v: boolean) => void }) {
  const pathname = usePathname();
  const { user, isAdmin, logout } = useAuth();

  const groups: { label: string; items: NavItem[] }[] = [
    {
      label: 'Monitor',
      items: [
        { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
        { name: 'Pipeline map', href: '/map', icon: Map },
        { name: 'Simulation runs', href: '/runs', icon: Activity },
        { name: 'Alerts', href: '/alerts', icon: BellRing },
      ],
    },
    {
      label: 'Investigate',
      items: [
        { name: 'Incidents', href: '/incidents', icon: FileSearch },
        { name: 'Evaluation', href: '/evaluation', icon: Scale },
      ],
    },
    ...(isAdmin
      ? [{
          label: 'Administer',
          items: [
            { name: 'Scenario builder', href: '/scenarios', icon: FlaskConical },
            { name: 'Models', href: '/models', icon: BrainCircuit },
            { name: 'Users', href: '/admin/users', icon: Users },
          ],
        }]
      : []),
  ];

  // The active pill is one element that glides between links, so the change of page reads as movement.
  const navRef = useRef<HTMLElement>(null);
  const [pill, setPill] = useState<{ top: number; height: number } | null>(null);
  const activeHref = [...groups.flatMap((g) => g.items), { name: 'Profile', href: '/profile', icon: User }]
    .find((i) => pathname === i.href || pathname.startsWith(i.href + '/'))?.href;

  useLayoutEffect(() => {
    const nav = navRef.current;
    const el = nav?.querySelector<HTMLElement>(`[data-href="${activeHref}"]`);
    setPill(el && nav ? { top: el.offsetTop, height: el.offsetHeight } : null);
  }, [activeHref, isAdmin]);

  const link = (item: NavItem) => {
    const active = item.href === activeHref;
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        data-href={item.href}
        onClick={() => setIsOpen?.(false)}
        aria-current={active ? 'page' : undefined}
        className={active ? 'sidebar-link-active' : 'sidebar-link'}
      >
        <Icon className={`w-[18px] h-[18px] transition-colors ${active ? 'text-brand-600' : 'text-gray-400'}`} aria-hidden />
        <span>{item.name}</span>
      </Link>
    );
  };

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-gray-900/20 backdrop-blur-[2px] z-[9998] md:hidden animate-fade-in"
          onClick={() => setIsOpen?.(false)}
        />
      )}
      <aside
        className={`w-60 bg-canvas flex flex-col h-screen fixed left-0 top-0 z-[9999] transition-transform duration-300 ease-out md:translate-x-0 ${
          isOpen ? 'translate-x-0 shadow-lift' : '-translate-x-full'
        }`}
      >
        <div className="px-5 pt-6 pb-5 flex items-center gap-3">
          <img src="/sensify-logo.png" alt="" className="w-9 h-9 object-contain" />
          <span className="display text-lg font-semibold tracking-tight text-gray-900">Sensify</span>
          <button className="md:hidden ml-auto btn-ghost p-1.5" onClick={() => setIsOpen?.(false)} aria-label="Close navigation">
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>

        <nav ref={navRef} className="relative flex-1 px-3 overflow-y-auto pb-4" aria-label="Main">
          {pill && (
            <span
              aria-hidden
              className="absolute left-3 right-3 rounded-[10px] bg-white shadow-sheet transition-[top,height] duration-300 ease-out"
              style={{ top: pill.top, height: pill.height }}
            />
          )}
          {groups.map((g) => (
            <div key={g.label} className="mb-5">
              <p className="px-3 mb-1.5 text-xs font-medium text-gray-400">{g.label}</p>
              <div className="space-y-0.5">{g.items.map(link)}</div>
            </div>
          ))}
        </nav>

        <div className="px-3 pb-5 pt-3 border-t border-rule mx-3">
          <div className="flex items-center gap-2">
            <Link
              href="/profile"
              data-href="/profile"
              onClick={() => setIsOpen?.(false)}
              className={`flex-1 min-w-0 flex items-center gap-3 rounded-[10px] px-2 py-2 transition-colors ${
                activeHref === '/profile' ? 'bg-white shadow-sheet' : 'hover:bg-white/60'
              }`}
            >
              <span className="w-8 h-8 shrink-0 rounded-full bg-brand-600 text-white grid place-items-center text-sm font-semibold">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-gray-900 truncate">{user?.username}</span>
                <span className="block text-xs text-gray-500">{user?.role === 'admin' ? 'Administrator' : 'Analyst'}</span>
              </span>
            </Link>
            <button onClick={logout} className="btn-ghost p-2" aria-label="Sign out" title="Sign out">
              <LogOut className="w-4 h-4" aria-hidden />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
