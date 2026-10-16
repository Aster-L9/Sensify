'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { getRuns } from '@/lib/api';
import {
  LogOut,
  User as UserIcon,
  ChevronRight,
  Activity,
  Play,
  Bell,
  Shield,
  Layers,
  Menu
} from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

interface Run {
  id: number;
  name: string;
  status: string;
}

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    getRuns('active')
      .then((runs) => {
        if (runs && runs.length > 0) {
          setActiveRun(runs[0]);
        } else {
          setActiveRun(null);
        }
      })
      .catch(() => setActiveRun(null));
  }, [pathname]);

  const pathSegments = pathname.split('/').filter(Boolean);

  return (
    <header className="h-16 bg-white/80 backdrop-blur-xl border-b border-gray-200 px-6 flex items-center justify-between sticky top-0 z-[9997] md:ml-64">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs font-medium text-gray-500">
        <button className="md:hidden mr-2 p-1 text-gray-500 hover:text-gray-900 transition-colors" onClick={onMenuClick}>
          <Menu className="w-5 h-5" />
        </button>
        <Link href="/dashboard" className="hover:text-gray-800 transition-colors flex items-center gap-1 hidden sm:flex">
          <Layers className="w-3.5 h-3.5 text-brand-400" />
          <span>System</span>
        </Link>
        {pathSegments.map((segment, index) => {
          const href = `/${pathSegments.slice(0, index + 1).join('/')}`;
          const isLast = index === pathSegments.length - 1;
          return (
            <React.Fragment key={href}>
              {/* Only show separator on larger screens if it's the first segment, to simplify mobile topbar */}
              <ChevronRight className={`w-3.5 h-3.5 text-gray-500 ${index === 0 ? 'hidden sm:block' : ''}`} />
              {isLast ? (
                <span className="text-gray-900 font-semibold capitalize truncate max-w-[120px] sm:max-w-none">{segment.replace('-', ' ')}</span>
              ) : (
                <Link href={href} className="hover:text-gray-700 transition-colors capitalize hidden sm:block">
                  {segment.replace('-', ' ')}
                </Link>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Active Run Indicator Widget */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-50 border border-gray-200 text-xs">
          <Activity className="w-3.5 h-3.5 text-brand-500 animate-pulse" />
          <span className="text-gray-600">Active Run:</span>
          {activeRun ? (
            <Link href={`/runs/${activeRun.id}`} className="font-semibold text-brand-600 hover:underline font-mono">
              #{activeRun.id} {activeRun.name}
            </Link>
          ) : (
            <span className="text-gray-500 font-mono italic">No Active Run</span>
          )}
        </div>

        {/* User Menu Dropdown */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-gray-100 border border-transparent hover:border-gray-200 transition-all"
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-brand-500 to-brand-300 text-white font-bold flex items-center justify-center text-xs">
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <span className="text-xs font-medium text-gray-700 hidden md:inline">{user?.username}</span>
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 glass-card border-gray-200 shadow-xl py-1 z-50 animate-fade-in bg-white">
              <div className="px-4 py-2 border-b border-gray-100">
                <p className="text-xs font-semibold text-gray-900">{user?.username}</p>
                <p className="text-[10px] text-gray-500 truncate">{user?.email}</p>
              </div>
              <Link
                href="/profile"
                onClick={() => setUserMenuOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-xs text-gray-700 hover:bg-gray-50 hover:text-brand-600 transition-colors"
              >
                <UserIcon className="w-3.5 h-3.5" />
                Profile Settings
              </Link>
              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  logout();
                }}
                className="w-full flex items-center gap-2 px-4 py-2 text-xs text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
