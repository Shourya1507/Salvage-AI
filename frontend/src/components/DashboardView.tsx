import React from 'react';
import { CreditCard, PauseCircle, Copy, TrendingDown, AlertTriangle, ArrowRight, CheckCircle, ShieldAlert } from 'lucide-react';
import type { DashboardData, DemoState } from '../api/client';
import { SeverityBadge } from './Badges';

interface DashboardViewProps {
  data: DashboardData | null;
  demoState: DemoState | null;
  onSelectCase: (caseId: string) => void;
  onNavigateToCases: () => void;
  onNavigateToSettings: () => void;
}

const causeConfig: Record<string, { label: string; icon: any; experimental?: boolean }> = {
  FAILED_PAYMENT: { label: 'Failed Payments', icon: CreditCard },
  STALLED_SUSPENSION: { label: 'Stalled Suspensions', icon: PauseCircle },
  DUPLICATE_CHARGE: { label: 'Duplicate Charges', icon: Copy },
  PRICE_CHANGE_FALLOUT: { label: 'Price Fallout', icon: TrendingDown },
  AT_RISK: { label: 'At-Risk Subscribers', icon: AlertTriangle, experimental: true },
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  data,
  demoState,
  onSelectCase,
  onNavigateToCases,
  onNavigateToSettings,
}) => {
  if (!data) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const causes = Object.entries(data.mrr_at_risk_by_type || {}).sort((a, b) => b[1] - a[1]);
  const maxCauseVal = Math.max(...causes.map((c) => c[1]), 1);

  return (
    <div className="space-y-6">
      {/* Top headline money cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-xs hover:border-gray-300 transition-all">
          <div className="text-sm font-medium text-gray-500 uppercase tracking-wider">
            Monthly Revenue at Risk
          </div>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-4xl font-extrabold text-red-600 font-mono tracking-tight">
              ${data.total_mrr_at_risk.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className="text-xs text-gray-500">across {data.open_cases} open cases</span>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            Detected revenue leaks from failed rebills, stalled accounts, and churn risk.
          </p>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-xs hover:border-gray-300 transition-all">
          <div className="text-sm font-medium text-gray-500 uppercase tracking-wider">
            Recovered Revenue
          </div>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-4xl font-extrabold text-emerald-600 font-mono tracking-tight">
              ${data.total_recovered_mrr.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-medium">
              <CheckCircle className="w-3 h-3" />
              Via Approved Actions
            </span>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            Verified recovery through executed PayPal retries and reactivations.
          </p>
        </div>
      </div>

      {/* Main Grid: At risk by cause & Open cases stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* At Risk By Cause horizontal bars (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl p-6 border border-gray-200 shadow-xs">
          <div className="flex justify-between items-center mb-5">
            <div>
              <h2 className="text-base font-semibold text-gray-900">At Risk by Cause</h2>
              <p className="text-xs text-gray-500">Deterministic detection rules breakdown</p>
            </div>
            <button
              onClick={onNavigateToCases}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1"
            >
              View all cases <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="space-y-4">
            {causes.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-500">
                No revenue leaks currently flagged. Great work!
              </div>
            ) : (
              causes.map(([typeKey, amount]) => {
                const conf = causeConfig[typeKey] || { label: typeKey, icon: AlertTriangle };
                const IconComponent = conf.icon;
                const percentage = Math.round((amount / maxCauseVal) * 100);

                return (
                  <div key={typeKey} className="group cursor-pointer" onClick={onNavigateToCases}>
                    <div className="flex justify-between items-center text-sm mb-1.5">
                      <div className="flex items-center gap-2">
                        <IconComponent className="w-4 h-4 text-gray-500 group-hover:text-blue-600" />
                        <span className="font-medium text-gray-800 group-hover:text-blue-700">
                          {conf.label}
                        </span>
                        {conf.experimental && (
                          <span className="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 border border-purple-200">
                            Experimental ML
                          </span>
                        )}
                      </div>
                      <span className="font-mono font-semibold text-gray-900">
                        ${amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    </div>

                    <div className="w-full bg-gray-100 h-2.5 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out group-hover:bg-blue-500"
                        style={{ width: `${Math.max(percentage, 3)}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Case counts summary side panel */}
        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-xs flex flex-col justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-1">Queue Status</h2>
            <p className="text-xs text-gray-500 mb-5">Open vs pending merchant approval</p>

            <div className="space-y-3">
              <div className="flex justify-between items-center p-3 rounded-lg bg-gray-50 border border-gray-100">
                <span className="text-sm font-medium text-gray-700">Total Open</span>
                <span className="text-lg font-bold font-mono text-gray-900">{data.open_cases}</span>
              </div>

              <div className="flex justify-between items-center p-3 rounded-lg bg-blue-50 border border-blue-100">
                <span className="text-sm font-medium text-blue-900">AI Proposed</span>
                <span className="text-lg font-bold font-mono text-blue-700">
                  {data.case_counts_by_status?.proposed || 0}
                </span>
              </div>

              <div className="flex justify-between items-center p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                <span className="text-sm font-medium text-emerald-900">Resolved</span>
                <span className="text-lg font-bold font-mono text-emerald-700">
                  {data.case_counts_by_status?.resolved || 0}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-gray-100 mt-6">
            <button
              onClick={onNavigateToCases}
              className="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition-colors text-center shadow-xs"
            >
              Open Case Queue ({data.open_cases})
            </button>
          </div>
        </div>
      </div>

      {/* Needs Your Attention top priority cases */}
      <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-xs">
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-600" />
            <h2 className="text-base font-semibold text-gray-900">Needs Your Attention</h2>
          </div>
          <span className="text-xs text-gray-500">Highest severity cases ranked by revenue</span>
        </div>

        {data.priority_cases && data.priority_cases.length > 0 ? (
          <div className="divide-y divide-gray-100">
            {data.priority_cases.map((c) => {
              const conf = causeConfig[c.type] || { label: c.type, icon: AlertTriangle };
              const IconComp = conf.icon;
              return (
                <div
                  key={c.id}
                  onClick={() => onSelectCase(c.id)}
                  className="py-3.5 flex items-center justify-between hover:bg-gray-50 px-2 rounded-lg cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <SeverityBadge severity={c.severity} />
                    <div className="flex items-center gap-2">
                      <IconComp className="w-4 h-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-800">{conf.label}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <span className="text-sm font-semibold font-mono text-gray-900">
                      ${c.mrr_at_risk.toFixed(2)}/mo
                    </span>
                    <button className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1">
                      Review <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-6 text-center text-sm text-gray-500 bg-gray-50 rounded-lg">
            No high-priority cases at this time.
          </div>
        )}
      </div>

      {/* Real vs Simulated Data chip footer */}
      <div className="flex justify-between items-center text-xs text-gray-500 px-2">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-purple-500"></span>
          <span>
            Data mix: <strong>{demoState?.subscriber_count || 0}</strong> subscribers (
            {demoState?.is_demo_mode ? 'Simulated Sandbox Data' : 'Live PayPal Sandbox'}
            ) · <strong>{demoState?.case_count || 0}</strong> active leak cases
          </span>
        </div>
        <button
          onClick={onNavigateToSettings}
          className="text-blue-600 hover:underline font-medium"
        >
          Manage demo scenarios →
        </button>
      </div>
    </div>
  );
};
