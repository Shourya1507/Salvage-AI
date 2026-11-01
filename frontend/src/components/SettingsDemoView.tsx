import React, { useState } from 'react';
import {
  Database,
  ShieldCheck,
  Bot,
  RefreshCw,
  PlusCircle,
  Play,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  CreditCard,
  PauseCircle,
  Copy,
} from 'lucide-react';
import {
  seedDemoData,
  injectScenario,
  resetDemoData,
  runSync,
} from '../api/client';
import type { HealthState, DemoState } from '../api/client';

interface SettingsDemoViewProps {
  health: HealthState | null;
  demoState: DemoState | null;
  onRefreshAll: () => void;
}

export const SettingsDemoView: React.FC<SettingsDemoViewProps> = ({
  health,
  demoState,
  onRefreshAll,
}) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const handleAction = async (name: string, fn: () => Promise<any>) => {
    try {
      setLoadingAction(name);
      setStatusMessage(null);
      const res = await fn();
      setStatusMessage({
        text: res?.message || `Successfully executed: ${name}`,
        type: 'success',
      });
      await onRefreshAll();
    } catch (err: any) {
      setStatusMessage({
        text: err.response?.data?.detail || err.message || `Failed to execute: ${name}`,
        type: 'error',
      });
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Feedback banner */}
      {statusMessage && (
        <div
          className={`p-4 rounded-xl border text-sm flex items-center gap-3 ${
            statusMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-red-50 border-red-200 text-red-800'
          }`}
        >
          {statusMessage.type === 'success' ? (
            <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
          )}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Demo Controls Card */}
      <div className="bg-white rounded-xl p-6 border border-purple-200 shadow-xs relative overflow-hidden">
        <div className="absolute top-0 right-0 px-4 py-1 bg-purple-600 text-white text-[10px] uppercase font-bold tracking-wider rounded-bl-xl">
          Demo Simulator
        </div>

        <div className="mb-6">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Play className="w-5 h-5 text-purple-600" />
            Hackathon Demo Controls
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Simulate merchant activity, inject real-time webhook failure events, and test end-to-end recovery loops.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <button
            onClick={() => handleAction('Seed Data', () => seedDemoData(25))}
            disabled={loadingAction !== null}
            className="p-4 rounded-xl border border-gray-200 hover:border-purple-300 hover:bg-purple-50/50 text-left transition-all group disabled:opacity-50"
          >
            <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center text-purple-600 mb-3 group-hover:scale-105 transition-transform">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div className="font-semibold text-sm text-gray-900">Seed Subscribers</div>
            <p className="text-xs text-gray-500 mt-1">
              Generate 25 sample subscribers with plans, payments, and churn scores.
            </p>
          </button>

          <button
            onClick={() => handleAction('Inject Failed Payment', () => injectScenario('failed_payment'))}
            disabled={loadingAction !== null}
            className="p-4 rounded-xl border border-gray-200 hover:border-red-300 hover:bg-red-50/50 text-left transition-all group disabled:opacity-50"
          >
            <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center text-red-600 mb-3 group-hover:scale-105 transition-transform">
              <CreditCard className="w-5 h-5" />
            </div>
            <div className="font-semibold text-sm text-gray-900">Inject Failed Payment</div>
            <p className="text-xs text-gray-500 mt-1">
              Simulates a webhook event for renewal card failure (Rule R1).
            </p>
          </button>

          <button
            onClick={() => handleAction('Inject Stalled Suspension', () => injectScenario('stalled_suspension'))}
            disabled={loadingAction !== null}
            className="p-4 rounded-xl border border-gray-200 hover:border-amber-300 hover:bg-amber-50/50 text-left transition-all group disabled:opacity-50"
          >
            <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-amber-600 mb-3 group-hover:scale-105 transition-transform">
              <PauseCircle className="w-5 h-5" />
            </div>
            <div className="font-semibold text-sm text-gray-900">Inject Stalled Sub</div>
            <p className="text-xs text-gray-500 mt-1">
              Sets a subscription suspended for &gt;7 days needing action (Rule R2).
            </p>
          </button>

          <button
            onClick={() => handleAction('Inject Duplicate Charge', () => injectScenario('duplicate_charge'))}
            disabled={loadingAction !== null}
            className="p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 text-left transition-all group disabled:opacity-50"
          >
            <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600 mb-3 group-hover:scale-105 transition-transform">
              <Copy className="w-5 h-5" />
            </div>
            <div className="font-semibold text-sm text-gray-900">Inject Duplicate Charge</div>
            <p className="text-xs text-gray-500 mt-1">
              Creates two identical payments within 72h window (Rule R3).
            </p>
          </button>
        </div>

        <div className="pt-4 border-t border-gray-100 flex flex-wrap justify-between items-center gap-4">
          <div className="text-xs text-gray-500">
            Database state: <strong>{demoState?.subscriber_count || 0}</strong> subscribers ·{' '}
            <strong>{demoState?.case_count || 0}</strong> cases ·{' '}
            <strong>{demoState?.action_count || 0}</strong> action logs
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => handleAction('Sync Subscriptions', runSync)}
              disabled={loadingAction !== null}
              className="px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 text-xs font-medium text-gray-700 flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Sync PayPal Subscriptions
            </button>

            <button
              onClick={() => handleAction('Reset Database', resetDemoData)}
              disabled={loadingAction !== null}
              className="px-3 py-2 rounded-lg bg-red-50 hover:bg-red-100 border border-red-200 text-xs font-semibold text-red-700 flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset All Demo Data
            </button>
          </div>
        </div>
      </div>

      {/* System Architecture & Health Card */}
      <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-xs">
        <h2 className="text-base font-bold text-gray-900 mb-1">System Health & Security Invariants</h2>
        <p className="text-xs text-gray-500 mb-5">
          Real-time status of backend microservices and security constraints
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-gray-50 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase">Database</span>
              <Database className="w-4 h-4 text-gray-400" />
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="font-semibold text-sm text-gray-800">
                {health?.db === 'ok' ? 'Connected (SQLite WAL)' : 'Disconnected'}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-gray-50 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase">PayPal Environment</span>
              <ShieldCheck className="w-4 h-4 text-gray-400" />
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              <span className="font-semibold text-sm text-gray-800">
                {health?.paypal_env === 'live' ? 'Live (Protected)' : 'Sandbox Mode'}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-gray-50 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase">AI Diagnosis Engine</span>
              <Bot className="w-4 h-4 text-gray-400" />
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="font-semibold text-sm text-gray-800">
                Claude 3.5 Sonnet (Read-Only)
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 p-4 rounded-xl bg-blue-50/70 border border-blue-200 text-xs text-blue-900 space-y-1.5">
          <div className="font-semibold flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-blue-700" />
            Non-Negotiable Architecture Invariants:
          </div>
          <ul className="list-disc list-inside space-y-1 text-blue-800">
            <li>LLM agent has read-only tools strictly; it cannot write to PayPal or databases.</li>
            <li>No PayPal mutation ever runs without explicit human approval recorded in the audit log.</li>
            <li>Detection rules R1–R5 are deterministic code, not LLM hallucinations.</li>
            <li>Simulated data and ML churn predictions are visually labelled throughout.</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
