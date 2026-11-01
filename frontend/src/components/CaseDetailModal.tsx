import React, { useState } from 'react';
import {
  X,
  Bot,
  Copy,
  Check,
  Mail,
  AlertCircle,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  RotateCcw,
} from 'lucide-react';
import { runAgentForCase, approveProposal, dismissProposal } from '../api/client';
import type { CaseItem, Proposal } from '../api/client';
import { SeverityBadge, SourceBadge, StatusBadge } from './Badges';

interface CaseDetailModalProps {
  caseData: CaseItem;
  onClose: () => void;
  onRefreshCase: (caseId: string) => void;
  onCaseUpdated: () => void;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({
  caseData,
  onClose,
  onRefreshCase,
  onCaseUpdated,
}) => {
  const [runningAgent, setRunningAgent] = useState<boolean>(false);
  const [executing, setExecuting] = useState<boolean>(false);
  const [copiedMessage, setCopiedMessage] = useState<boolean>(false);
  const [showConfirm, setShowConfirm] = useState<boolean>(false);
  const [dismissReason, setDismissReason] = useState<string>('');
  const [showDismissModal, setShowDismissModal] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Latest proposal (if any)
  const proposal: Proposal | undefined = caseData.proposals && caseData.proposals.length > 0
    ? caseData.proposals[caseData.proposals.length - 1]
    : undefined;

  const handleRunAgent = async () => {
    try {
      setRunningAgent(true);
      setErrorMsg(null);
      await runAgentForCase(caseData.id);
      await onRefreshCase(caseData.id);
      onCaseUpdated();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to generate proposal');
    } finally {
      setRunningAgent(false);
    }
  };

  const handleApprove = async () => {
    if (!proposal) return;
    try {
      setExecuting(true);
      setErrorMsg(null);
      await approveProposal(proposal.id);
      setShowConfirm(false);
      await onRefreshCase(caseData.id);
      onCaseUpdated();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Approval / Execution failed');
    } finally {
      setExecuting(false);
    }
  };

  const handleDismiss = async () => {
    if (!proposal) return;
    try {
      setExecuting(true);
      setErrorMsg(null);
      await dismissProposal(proposal.id, dismissReason || 'Dismissed by merchant');
      setShowDismissModal(false);
      await onRefreshCase(caseData.id);
      onCaseUpdated();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to dismiss proposal');
    } finally {
      setExecuting(false);
    }
  };

  const copyDraft = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMessage(true);
    setTimeout(() => setCopiedMessage(false), 2000);
  };

  const getActionDescription = (actionType: string) => {
    switch (actionType) {
      case 'RETRY_PAYMENT':
        return 'Call PayPal Subscriptions API to retry capturing the outstanding failed balance.';
      case 'REACTIVATE_SUBSCRIPTION':
        return 'Call PayPal Subscriptions API to reactivate the suspended subscription.';
      case 'SUSPEND_SUBSCRIPTION':
        return 'Call PayPal Subscriptions API to suspend the subscription.';
      case 'CANCEL_SUBSCRIPTION':
        return 'Call PayPal Subscriptions API to permanently cancel this subscription.';
      case 'REVIEW_DUPLICATE_FOR_REFUND':
        return 'Flag the transaction for manual PayPal refund review.';
      case 'SEND_DUNNING_MESSAGE':
        return 'Send automated dunning email reminder to customer.';
      case 'WIN_BACK_OFFER':
        return 'Send tailored retention offer with discounted pricing link.';
      default:
        return 'Record resolution in audit log without PayPal state change.';
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-5xl w-full shadow-2xl border border-gray-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Top Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/70">
          <div className="flex items-center gap-3">
            <SeverityBadge severity={caseData.severity} />
            <h2 className="text-lg font-bold text-gray-900">
              {caseData.type.replace(/_/g, ' ')}
            </h2>
            <StatusBadge status={caseData.status} />
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body: Two column layout (Left facts, Right proposal) */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-2 gap-8 divide-y md:divide-y-0 md:divide-x divide-gray-200">
          {/* Left Column: Facts & Evidence */}
          <div className="space-y-6">
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Subscriber & Subscription
              </h3>
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-200/80 space-y-2.5">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Name</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-gray-900">
                      {caseData.subscriber?.name || 'Unknown'}
                    </span>
                    <SourceBadge source={caseData.subscriber?.source} />
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Email</span>
                  <span className="text-sm font-medium text-gray-800 font-mono">
                    {caseData.subscriber?.email}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">PayPal Subscription ID</span>
                  <span className="text-xs font-mono font-medium text-gray-700 bg-white px-2 py-0.5 rounded border border-gray-200">
                    {caseData.subscription?.paypal_subscription_id}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Plan</span>
                  <span className="text-sm font-medium text-gray-800">
                    {caseData.plan?.name || 'Standard'} (${caseData.plan?.price} / {caseData.plan?.interval})
                  </span>
                </div>

                <div className="flex justify-between items-center pt-2 border-t border-gray-200/80">
                  <span className="text-sm font-semibold text-red-600">Monthly Revenue at Risk</span>
                  <span className="text-lg font-bold font-mono text-red-600">
                    ${caseData.mrr_at_risk.toFixed(2)}/mo
                  </span>
                </div>
              </div>
            </div>

            {/* Evidence & Detection Details */}
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Detection Evidence
              </h3>
              <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3 text-xs">
                {caseData.evidence ? (
                  <pre className="p-3 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto font-mono text-[11px] leading-relaxed">
                    {JSON.stringify(caseData.evidence, null, 2)}
                  </pre>
                ) : (
                  <p className="text-gray-400">No raw evidence payload available.</p>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: AI Proposal & Human Approval */}
          <div className="space-y-6 md:pl-8">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Bot className="w-4 h-4 text-blue-600" />
                AI Diagnosis & Suggested Action
              </h3>
              {proposal && (
                <span className="text-[11px] text-gray-400 font-mono">
                  Confidence: {Math.round(proposal.confidence * 100)}%
                </span>
              )}
            </div>

            {errorMsg && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            {!proposal ? (
              <div className="bg-blue-50/50 rounded-xl p-8 border border-blue-100 text-center space-y-4">
                <Sparkles className="w-8 h-8 text-blue-600 mx-auto" />
                <div>
                  <h4 className="text-sm font-semibold text-gray-900">No Proposal Generated Yet</h4>
                  <p className="text-xs text-gray-500 mt-1">
                    Have the Salvage AI read-only agent inspect the subscriber history and formulate a recovery plan.
                  </p>
                </div>
                <button
                  onClick={handleRunAgent}
                  disabled={runningAgent}
                  className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs shadow-xs transition-colors disabled:opacity-50 inline-flex items-center gap-2"
                >
                  {runningAgent ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Analyzing Case with Claude...
                    </>
                  ) : (
                    <>
                      <Bot className="w-4 h-4" />
                      Run AI Diagnosis
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div className="space-y-5">
                {/* Proposed Action Box */}
                <div className="p-4 rounded-xl bg-blue-50/60 border border-blue-200">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-bold text-blue-900 uppercase tracking-wide">
                      Action: {proposal.action_type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-semibold font-mono">
                      {proposal.status}
                    </span>
                  </div>
                  <p className="text-xs text-blue-800 mt-1">
                    {getActionDescription(proposal.action_type)}
                  </p>
                </div>

                {/* Diagnosis & Reasoning */}
                <div className="space-y-3">
                  <div>
                    <h4 className="text-xs font-semibold text-gray-700 mb-1">Diagnosis</h4>
                    <p className="text-sm text-gray-800 bg-gray-50 p-3 rounded-lg border border-gray-200/80 leading-relaxed">
                      {proposal.diagnosis}
                    </p>
                  </div>

                  <div>
                    <h4 className="text-xs font-semibold text-gray-700 mb-1">Reasoning</h4>
                    <p className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200/80 leading-relaxed">
                      {proposal.reasoning}
                    </p>
                  </div>
                </div>

                {/* Customer Message Draft */}
                {proposal.customer_message && (
                  <div>
                    <div className="flex justify-between items-center mb-1.5">
                      <h4 className="text-xs font-semibold text-gray-700">Drafted Customer Message</h4>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => copyDraft(proposal.customer_message)}
                          className="text-xs text-blue-600 hover:text-blue-800 inline-flex items-center gap-1 font-medium"
                        >
                          {copiedMessage ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-600" /> Copied!
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" /> Copy
                            </>
                          )}
                        </button>
                        <a
                          href={`mailto:${caseData.subscriber?.email}?subject=Important update regarding your subscription&body=${encodeURIComponent(
                            proposal.customer_message
                          )}`}
                          className="text-xs text-gray-600 hover:text-gray-900 inline-flex items-center gap-1 font-medium"
                        >
                          <Mail className="w-3.5 h-3.5" /> Open in Mail
                        </a>
                      </div>
                    </div>
                    <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200 text-xs text-gray-800 font-sans leading-relaxed">
                      {proposal.customer_message}
                    </div>
                  </div>
                )}

                {/* Human Approval Button Bar */}
                {proposal.status === 'pending' && (
                  <div className="pt-4 border-t border-gray-200 flex items-center justify-between gap-3">
                    <button
                      onClick={() => setShowDismissModal(true)}
                      className="text-xs font-medium text-gray-500 hover:text-red-600 transition-colors"
                    >
                      Dismiss Proposal
                    </button>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleRunAgent}
                        disabled={runningAgent}
                        className="px-3 py-2 text-xs font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-1.5"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        Re-run Agent
                      </button>

                      <button
                        onClick={() => setShowConfirm(true)}
                        disabled={executing}
                        className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors flex items-center gap-1.5"
                      >
                        <ShieldCheck className="w-4 h-4" />
                        Approve & Execute
                      </button>
                    </div>
                  </div>
                )}

                {proposal.status === 'approved' || proposal.status === 'executed' ? (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>
                      Executed on {proposal.decided_at ? new Date(proposal.decided_at).toLocaleString() : 'recently'}{' '}
                      by {proposal.decided_by || 'merchant'}.
                    </span>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>

        {/* Confirmation Modal (Human-In-The-Loop Guard) */}
        {showConfirm && proposal && (
          <div className="fixed inset-0 z-60 bg-black/40 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-gray-200 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900">Approve PayPal Action</h3>
                  <p className="text-xs text-gray-500">Human-in-the-loop verification</p>
                </div>
              </div>

              <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-700 space-y-2">
                <p className="font-semibold text-gray-900">Planned API call:</p>
                <p className="text-gray-800 font-mono text-[11px] bg-white p-2 rounded border border-gray-200">
                  {proposal.action_type} for subscription {caseData.subscription?.paypal_subscription_id}
                </p>
                <p className="text-gray-600">{getActionDescription(proposal.action_type)}</p>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowConfirm(false)}
                  disabled={executing}
                  className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleApprove}
                  disabled={executing}
                  className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center gap-2"
                >
                  {executing ? 'Executing via PayPal...' : 'Confirm & Execute'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Dismiss Reason Modal */}
        {showDismissModal && proposal && (
          <div className="fixed inset-0 z-60 bg-black/40 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-gray-200 space-y-4">
              <h3 className="text-base font-bold text-gray-900">Dismiss Proposal</h3>
              <p className="text-xs text-gray-500">
                Please provide a reason for dismissing this AI proposal. The case will be marked for review.
              </p>

              <textarea
                value={dismissReason}
                onChange={(e) => setDismissReason(e.target.value)}
                placeholder="e.g. Customer notified us they want to cancel manually..."
                rows={3}
                className="w-full text-xs p-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowDismissModal(false)}
                  className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDismiss}
                  disabled={executing}
                  className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-lg"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
