import React, { useState } from 'react';
import { CreditCard, PauseCircle, Copy, TrendingDown, AlertTriangle, Filter, ChevronRight, Search } from 'lucide-react';
import type { CaseItem } from '../api/client';
import { SeverityBadge, SourceBadge, StatusBadge } from './Badges';

interface CasesViewProps {
  cases: CaseItem[];
  loading: boolean;
  onSelectCase: (caseId: string) => void;
}

const causeConfig: Record<string, { label: string; icon: any }> = {
  FAILED_PAYMENT: { label: 'Failed Payment', icon: CreditCard },
  STALLED_SUSPENSION: { label: 'Stalled Suspension', icon: PauseCircle },
  DUPLICATE_CHARGE: { label: 'Duplicate Charge', icon: Copy },
  PRICE_CHANGE_FALLOUT: { label: 'Price Fallout', icon: TrendingDown },
  AT_RISK: { label: 'At-Risk Subscriber', icon: AlertTriangle },
};

export const CasesView: React.FC<CasesViewProps> = ({ cases, loading, onSelectCase }) => {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredCases = cases.filter((c) => {
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (typeFilter !== 'all' && c.type !== typeFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchSubscriber = c.subscriber?.name.toLowerCase().includes(q) || c.subscriber?.email.toLowerCase().includes(q);
      const matchSubId = c.subscription?.paypal_subscription_id.toLowerCase().includes(q);
      const matchType = c.type.toLowerCase().includes(q);
      if (!matchSubscriber && !matchSubId && !matchType) return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Filters header */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-xs flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search subscriber, email, or sub ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm rounded-lg border border-gray-300 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Statuses</option>
              <option value="open">Open</option>
              <option value="proposed">Proposed</option>
              <option value="resolved">Resolved</option>
              <option value="dismissed">Dismissed</option>
              <option value="needs_review">Needs Review</option>
            </select>

            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-sm rounded-lg border border-gray-300 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Leak Types</option>
              <option value="FAILED_PAYMENT">Failed Payment</option>
              <option value="STALLED_SUSPENSION">Stalled Suspension</option>
              <option value="DUPLICATE_CHARGE">Duplicate Charge</option>
              <option value="PRICE_CHANGE_FALLOUT">Price Fallout</option>
              <option value="AT_RISK">At-Risk (ML)</option>
            </select>
          </div>
        </div>

        <div className="text-xs text-gray-500 font-medium">
          Showing <strong>{filteredCases.length}</strong> of {cases.length} cases
        </div>
      </div>

      {/* Case queue table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-gray-400">Loading cases...</div>
        ) : filteredCases.length === 0 ? (
          <div className="py-16 text-center text-gray-500 space-y-2">
            <p className="font-semibold text-gray-800 text-base">
              {cases.length === 0 ? 'No leaks found. Nice.' : 'No cases match the selected filters.'}
            </p>
            <p className="text-xs text-gray-400 max-w-sm mx-auto">
              {cases.length === 0
                ? 'Your PayPal subscription business is running clean. You can inject demo failure events or trigger a sync from Settings.'
                : 'Try adjusting your filters or search keywords to view other cases.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 border-b border-gray-200 text-xs uppercase text-gray-500 font-semibold">
                <tr>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Cause / Type</th>
                  <th className="py-3 px-4">Subscriber</th>
                  <th className="py-3 px-4">Plan & Amount</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredCases.map((c) => {
                  const conf = causeConfig[c.type] || { label: c.type, icon: AlertTriangle };
                  const IconComp = conf.icon;
                  const dateStr = new Date(c.opened_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                  });

                  return (
                    <tr
                      key={c.id}
                      onClick={() => onSelectCase(c.id)}
                      className="hover:bg-blue-50/50 cursor-pointer transition-colors group"
                    >
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <SeverityBadge severity={c.severity} />
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <IconComp className="w-4 h-4 text-gray-400 group-hover:text-blue-600" />
                          <span className="font-medium text-gray-900">{conf.label}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-gray-800">
                              {c.subscriber?.name || 'Unknown Subscriber'}
                            </span>
                            <SourceBadge source={c.subscriber?.source} />
                          </div>
                          <span className="text-xs text-gray-400">{c.subscriber?.email}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex flex-col">
                          <span className="font-mono font-semibold text-gray-900">
                            ${c.mrr_at_risk.toFixed(2)}/mo
                          </span>
                          <span className="text-xs text-gray-400">
                            {c.plan?.name || 'Standard Plan'}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap text-xs text-gray-500">
                        {dateStr}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap text-right">
                        <button className="text-blue-600 hover:text-blue-800 font-medium text-xs inline-flex items-center gap-0.5">
                          Review <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
