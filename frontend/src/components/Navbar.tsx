import React from 'react';
import { ShieldCheck, RefreshCw } from 'lucide-react';

interface NavbarProps {
  currentTab: 'dashboard' | 'cases' | 'actions' | 'settings';
  setCurrentTab: (tab: 'dashboard' | 'cases' | 'actions' | 'settings') => void;
  openCasesCount: number;
  isDemoMode: boolean;
  onRefresh: () => void;
  refreshing: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  setCurrentTab,
  openCasesCount,
  isDemoMode,
  onRefresh,
  refreshing,
}) => {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Left: Brand */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => setCurrentTab('dashboard')}>
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow-sm">
                S
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-gray-900 tracking-tight flex items-center gap-1.5">
                  Salvage AI
                  <span className="text-[10px] font-medium uppercase px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                    Agent
                  </span>
                </span>
                <span className="text-[11px] text-gray-500">PayPal Subscription Recovery</span>
              </div>
            </div>

            {/* Nav tabs */}
            <nav className="flex space-x-1 sm:space-x-2">
              <button
                onClick={() => setCurrentTab('dashboard')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentTab === 'dashboard'
                    ? 'bg-gray-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Dashboard
              </button>

              <button
                onClick={() => setCurrentTab('cases')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
                  currentTab === 'cases'
                    ? 'bg-gray-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Cases
                {openCasesCount > 0 && (
                  <span className="bg-blue-600 text-white text-xs px-2 py-0.5 rounded-full font-semibold">
                    {openCasesCount}
                  </span>
                )}
              </button>

              <button
                onClick={() => setCurrentTab('actions')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentTab === 'actions'
                    ? 'bg-gray-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Action Log
              </button>

              <button
                onClick={() => setCurrentTab('settings')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  currentTab === 'settings'
                    ? 'bg-gray-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Demo Controls
                {isDemoMode && (
                  <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                )}
              </button>
            </nav>
          </div>

          {/* Right: Environment chip & Sync */}
          <div className="flex items-center gap-3">
            {isDemoMode ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-600"></span>
                Demo Mode (Sandbox)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5" />
                PayPal Sandbox Active
              </span>
            )}

            <button
              onClick={onRefresh}
              disabled={refreshing}
              title="Refresh Data"
              className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
