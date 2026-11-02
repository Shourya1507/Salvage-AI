import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertCircle, Info } from 'lucide-react';
import { Navbar } from './components/Navbar';
import { DashboardView } from './components/DashboardView';
import { CasesView } from './components/CasesView';
import { CaseDetailModal } from './components/CaseDetailModal';
import { ActionLogView } from './components/ActionLogView';
import { SettingsDemoView } from './components/SettingsDemoView';
import {
  getDashboard,
  getCases,
  getCaseDetail,
  getActionLogs,
  getHealth,
  getDemoState,
} from './api/client';
import type {
  DashboardData,
  CaseItem,
  ActionLogItem,
  HealthState,
  DemoState,
} from './api/client';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'cases' | 'actions' | 'settings'>('dashboard');
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [actionLogs, setActionLogs] = useState<ActionLogItem[]>([]);
  const [health, setHealth] = useState<HealthState | null>(null);
  const [demoState, setDemoState] = useState<DemoState | null>(null);
  const [selectedCaseDetail, setSelectedCaseDetail] = useState<CaseItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast((prev) => (prev?.message === message ? null : prev));
    }, 4500);
  };

  // Load all data
  const loadData = async (isManualRefresh: boolean = false) => {
    if (isManualRefresh) setRefreshing(true);
    try {
      const [dash, casesList, logs, h, demo] = await Promise.all([
        getDashboard().catch(() => null),
        getCases().catch(() => []),
        getActionLogs().catch(() => []),
        getHealth().catch(() => null),
        getDemoState().catch(() => null),
      ]);

      if (dash) setDashboardData(dash);
      setCases(casesList);
      setActionLogs(logs);
      if (h) setHealth(h);
      if (demo) setDemoState(demo);
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      loadData();
    }, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  // Handle case selection
  const handleSelectCase = async (caseId: string) => {
    try {
      const detail = await getCaseDetail(caseId);
      setSelectedCaseDetail(detail);
    } catch (err) {
      console.error('Failed to fetch case detail:', err);
    }
  };

  const handleRefreshCase = async (caseId: string) => {
    try {
      const detail = await getCaseDetail(caseId);
      setSelectedCaseDetail(detail);
      loadData();
    } catch (err) {
      console.error('Failed to reload case:', err);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F8FA] flex flex-col font-sans text-gray-900 antialiased selection:bg-blue-100 selection:text-blue-900">
      {/* Top Navigation */}
      <Navbar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        openCasesCount={dashboardData?.open_cases || 0}
        isDemoMode={demoState?.is_demo_mode ?? true}
        onRefresh={() => loadData(true)}
        refreshing={refreshing}
      />

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentTab === 'dashboard' && (
          <DashboardView
            data={dashboardData}
            demoState={demoState}
            onSelectCase={handleSelectCase}
            onNavigateToCases={() => setCurrentTab('cases')}
            onNavigateToSettings={() => setCurrentTab('settings')}
          />
        )}

        {currentTab === 'cases' && (
          <CasesView
            cases={cases}
            loading={loading}
            onSelectCase={handleSelectCase}
          />
        )}

        {currentTab === 'actions' && (
          <ActionLogView
            logs={actionLogs}
            loading={loading}
          />
        )}

        {currentTab === 'settings' && (
          <SettingsDemoView
            health={health}
            demoState={demoState}
            onRefreshAll={() => loadData(true)}
          />
        )}
      </main>

      {/* Case Detail Modal */}
      {selectedCaseDetail && (
        <CaseDetailModal
          caseData={selectedCaseDetail}
          onClose={() => {
            setSelectedCaseDetail(null);
          }}
          onRefreshCase={handleRefreshCase}
          onCaseUpdated={() => loadData(false)}
          onShowToast={showToast}
        />
      )}

      {/* Toast Notification with aria-live */}
      <div
        aria-live="polite"
        className="fixed bottom-5 right-5 z-70 flex flex-col gap-2 pointer-events-none"
      >
        {toast && (
          <div
            role="status"
            className={`pointer-events-auto px-4 py-3 rounded-xl shadow-xl border text-xs font-medium flex items-center gap-2.5 transition-all ${
              toast.type === 'success'
                ? 'bg-emerald-950 text-emerald-100 border-emerald-800'
                : toast.type === 'error'
                ? 'bg-red-950 text-red-100 border-red-800'
                : 'bg-gray-900 text-gray-100 border-gray-700'
            }`}
          >
            {toast.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
            {toast.type === 'error' && <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />}
            {toast.type === 'info' && <Info className="w-4 h-4 text-blue-400 shrink-0" />}
            <span>{toast.message}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
