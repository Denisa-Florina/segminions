import React from 'react';
import { Activity } from 'lucide-react';

/** The centred card shared by the login and registration pages. */
function AuthLayout({ subtitle, children, footer }) {
  return (
    <div className="min-h-screen bg-linear-to-br from-gray-900 via-blue-950 to-gray-900 flex items-center justify-center p-4">
      <main className="bg-gray-800/90 rounded-2xl shadow-2xl p-8 w-full max-w-md border border-gray-700">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-full mb-4">
            <Activity className="w-8 h-8 text-white" aria-hidden="true" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">MedSeg AI</h1>
          <p className="text-gray-400">{subtitle}</p>
        </div>
        {children}
        {footer && <div className="mt-6 text-center text-sm text-gray-400">{footer}</div>}
      </main>
    </div>
  );
}

export const AUTH_INPUT_CLASS =
  'w-full bg-gray-700 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/40 focus:outline-none transition';

export function FormError({ children }) {
  return (
    <div role="alert" className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-sm">
      {children}
    </div>
  );
}

export default AuthLayout;
