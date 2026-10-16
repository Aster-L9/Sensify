'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  LayoutDashboard,
  Map,
  Activity,
  Users,
  User,
  Shield,
  Database,
  Radio,
  BellRing,
  FlaskConical,
  BrainCircuit
} from 'lucide-react';

export function Sidebar({ isOpen, setIsOpen }: { isOpen?: boolean; setIsOpen?: (v: boolean) => void }) {
  const pathname = usePathname();
  const { user, isAdmin } = useAuth();

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Pipeline Map', href: '/map', icon: Map },
    { name: 'Simulation Runs', href: '/runs', icon: Activity },
    { name: 'Alerts', href: '/alerts', icon: BellRing },
    ...(isAdmin
      ? [
          { name: 'Scenario Builder', href: '/scenarios', icon: FlaskConical },
          { name: 'Models', href: '/models', icon: BrainCircuit },
          { name: 'User Management', href: '/admin/users', icon: Users },
        ]
      : []),
    { name: 'My Profile', href: '/profile', icon: User },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[9998] md:hidden transition-opacity"
          onClick={() => setIsOpen?.(false)}
        />
      )}
      <aside className={`w-64 bg-white border-r border-gray-200 flex flex-col h-screen fixed left-0 top-0 z-[9999] shadow-sm transition-transform duration-300 ease-in-out md:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
      {/* Brand Header */}
      <div className="p-5 border-b border-gray-100 flex items-center gap-3">
        <img src="/sensify-logo.png" alt="Sensify" className="w-10 h-10 rounded-xl object-contain" />
        <div>
          <h1 className="font-bold text-gray-900 tracking-wide text-sm leading-none">
            Sensify
          </h1>
          <span className="text-[10px] text-gray-500 font-mono">v1.1.0</span>
        </div>
      </div>

      {/* Live System Indicator */}
      <div className="mx-4 my-4 p-3 rounded-xl bg-gray-50 border border-gray-100 flex items-center gap-3">
        <div className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand-500"></span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-gray-700 truncate flex items-center gap-1">
            <Radio className="w-3 h-3 text-brand-500" /> Pipeline Telemetry
          </p>
          <p className="text-[10px] text-gray-500 truncate font-mono">Sensify Pipeline Network</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 space-y-1.5 overflow-y-auto py-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={isActive
                ? 'flex items-center gap-3 px-4 py-2.5 rounded-xl bg-brand-50 text-brand-600 text-sm font-bold shadow-sm shadow-brand-500/10'
                : 'sidebar-link'}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-brand-500' : 'text-gray-500'}`} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* User Role Card Footer */}
      <div className="p-4 border-t border-gray-100">
        <div className="glass-card p-3 flex items-center gap-3 bg-gray-50">
          <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center font-bold text-xs text-brand-500">
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-gray-800 truncate">{user?.username || 'Guest'}</p>
            <div className="flex items-center gap-1 mt-0.5">
              <Shield className="w-3 h-3 text-brand-500" />
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold font-mono">
                {user?.role || 'Analyst'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
    </>
  );
}
