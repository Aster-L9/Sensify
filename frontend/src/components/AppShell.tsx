'use client';

import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingState } from './ui/States';
import { DemoGuide } from './DemoGuide';
import { usePathname } from 'next/navigation';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const isPublicPage = pathname === '/' || pathname === '/login' || pathname === '/register';

  React.useEffect(() => {
    if (!loading && !user && !isPublicPage) {
      if (typeof window !== 'undefined') {
        window.location.href = '/';
      }
    }
  }, [user, loading, isPublicPage]);

  if (loading && !isPublicPage) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingState message="Checking your session" />
      </div>
    );
  }

  if (!user && !isPublicPage) {
    return null;
  }

  if (isPublicPage) {
    return <main className="min-h-screen">{children}</main>;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      <TopBar onMenuClick={() => setIsSidebarOpen(true)} />
      <main className="md:ml-60 flex-1 px-4 pb-10 pt-2 md:px-8">
        {/* Keyed by route: each page arrives with one short rise, the answer to the click that opened it. */}
        <div key={pathname} className="max-w-[1280px] mx-auto space-y-6 animate-page-in">
          {children}
        </div>
      </main>
      <DemoGuide />
    </div>
  );
}
