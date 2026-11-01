import React from 'react';
import { AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';

export const SeverityBadge: React.FC<{ severity: number }> = ({ severity }) => {
  if (severity >= 70) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
        <AlertCircle className="w-3.5 h-3.5 text-red-600" />
        HIGH ({severity})
      </span>
    );
  }
  if (severity >= 40) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
        MED ({severity})
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
      <Info className="w-3.5 h-3.5 text-blue-600" />
      LOW ({severity})
    </span>
  );
};

export const SourceBadge: React.FC<{ source?: string }> = ({ source }) => {
  if (source === 'simulated') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-purple-100 text-purple-700 border border-purple-200">
        simulated
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700 border border-gray-200">
      sandbox
    </span>
  );
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  switch (status) {
    case 'open':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-300">
          Open
        </span>
      );
    case 'proposed':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-300">
          Proposed
        </span>
      );
    case 'resolved':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-300">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          Resolved
        </span>
      );
    case 'dismissed':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-300">
          Dismissed
        </span>
      );
    case 'needs_review':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 border border-orange-300">
          Needs Review
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
          {status}
        </span>
      );
  }
};
