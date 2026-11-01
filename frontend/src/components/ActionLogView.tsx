import React from 'react';
import { CheckCircle2, XCircle, ShieldCheck } from 'lucide-react';
import type { ActionLogItem } from '../api/client';

interface ActionLogViewProps {
  logs: ActionLogItem[];
  loading: boolean;
}

export const ActionLogView: React.FC<ActionLogViewProps> = ({ logs, loading }) => {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-xs flex justify-between items-center">
        <div>
          <h2 className="text-base font-bold text-gray-900">Audit & Action Log</h2>
          <p className="text-xs text-gray-500">
            Immutable log of all human-approved executions and PayPal API mutations
          </p>
        </div>
        <span className="text-xs font-mono font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          Total actions: {logs.length}
        </span>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-gray-400">Loading audit log...</div>
        ) : logs.length === 0 ? (
          <div className="py-16 text-center text-gray-500 space-y-2">
            <p className="font-semibold text-gray-700">No actions executed yet.</p>
            <p className="text-xs text-gray-400">
              Approved proposals will appear here along with their PayPal transaction responses.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 border-b border-gray-200 text-xs uppercase text-gray-500 font-semibold">
                <tr>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Executed At</th>
                  <th className="py-3 px-4">Approved By</th>
                  <th className="py-3 px-4">PayPal Status</th>
                  <th className="py-3 px-4 text-right">Recovered MRR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map((log) => {
                  const dateStr = new Date(log.executed_at).toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  });

                  return (
                    <tr key={log.id} className="hover:bg-gray-50/70">
                      <td className="py-3 px-4 whitespace-nowrap">
                        {log.success ? (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            Success
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 px-2 py-0.5 rounded-full border border-red-200">
                            <XCircle className="w-3.5 h-3.5 text-red-600" />
                            Failed
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="font-semibold font-mono text-xs text-gray-900 bg-gray-100 px-2 py-1 rounded">
                          {log.action_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap text-xs text-gray-500">
                        {dateStr}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap text-xs text-gray-700">
                        <span className="inline-flex items-center gap-1">
                          <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                          {log.executed_by || 'merchant'}
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap text-xs font-mono text-gray-600">
                        {log.paypal_response_code ? (
                          <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-gray-800">
                            HTTP {log.paypal_response_code}
                          </span>
                        ) : log.error_message ? (
                          <span className="text-red-600 truncate max-w-xs block" title={log.error_message}>
                            {log.error_message}
                          </span>
                        ) : (
                          <span className="text-gray-400">Advisory / Local</span>
                        )}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap text-right font-mono font-bold text-gray-900">
                        {log.recovered_mrr ? (
                          <span className="text-emerald-600">
                            +${log.recovered_mrr.toFixed(2)}/mo
                          </span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
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
