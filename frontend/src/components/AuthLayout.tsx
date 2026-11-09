import React from 'react';

const STATIONS = ['SEG-01', 'SEG-02', 'SEG-03', 'SEG-04', 'SEG-05', 'SEG-06'];

/** Sign-in and sign-up: the form on the right, the line it watches on the left. */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] bg-canvas">
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-brand-950 text-white p-12">
        <div className="flex items-center gap-3">
          <img src="/sensify-logo.png" alt="" className="w-10 h-10 object-contain brightness-125" />
          <span className="display text-xl font-semibold">Sensify</span>
        </div>

        <div>
          <p className="display text-[40px] leading-[1.08] font-semibold max-w-md">
            Know which readings look wrong, and which ones you can&apos;t trust.
          </p>
          <p className="mt-4 text-brand-200 max-w-md">
            Six segments from Dhahran to Jubail, simulated and scored as they play, with every finding traced back to its evidence.
          </p>

          <svg viewBox="0 0 520 70" className="mt-12 w-full max-w-lg" aria-hidden>
            <line x1="10" y1="24" x2="510" y2="24" stroke="#3b3584" strokeWidth="10" strokeLinecap="round" className="schematic-draw" pathLength={1000} />
            <line x1="10" y1="24" x2="510" y2="24" stroke="#a9a3e6" strokeWidth="3" strokeLinecap="round" className="schematic-flow" />
            {STATIONS.map((code, i) => {
              const x = 10 + 50 + i * 80;
              return (
                <g key={code} className="schematic-node" style={{ animationDelay: `${400 + i * 90}ms` }}>
                  <circle cx={x} cy={24} r={7} fill="#1b1940" stroke="#c7c2ef" strokeWidth="2" />
                  <text x={x} y={58} textAnchor="middle" fill="#a9a3e6" style={{ font: '500 11px Archivo, sans-serif' }}>{code}</text>
                </g>
              );
            })}
          </svg>
        </div>

        <p className="text-sm text-brand-300">Pipeline incident investigation, Sprint 3</p>
      </aside>

      <main className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-[400px] animate-page-in">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <img src="/sensify-logo.png" alt="" className="w-9 h-9 object-contain" />
            <span className="display text-lg font-semibold text-gray-900">Sensify</span>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
