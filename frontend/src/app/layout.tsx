import type { Metadata } from 'next';
import 'leaflet/dist/leaflet.css';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { ToastProvider } from '@/components/ui/Toast';
import { AppShell } from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Sensify | Pipeline Intelligence Platform',
  description: 'Sensify — Pipeline Telemetry, Physics Simulation & Real-time Monitoring Dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-canvas text-gray-900 font-sans antialiased">
        <AuthProvider>
          <ToastProvider>
            <AppShell>{children}</AppShell>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}