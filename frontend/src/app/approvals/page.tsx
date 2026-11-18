"use client";

import clsx from "clsx";
import { AlertTriangle, CheckCircle, ChevronRight, Clock, RefreshCw, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { decide, listApprovals, listMyRequests } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApprovalTask } from "@/lib/types";

const RISK_COLORS: Record<string, string> = {
  low:    "bg-green-100 text-green-700",
  medium: "bg-amber-100 text-amber-700",
  high:   "bg-red-100 text-red-700",
};

const DECISION_COLORS: Record<string, string> = {
  approve:  "text-green-700",
  reject:   "text-red-700",
  escalate: "text-amber-700",
};

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  decided: "bg-blue-100 text-blue-700",
};

export default function ApprovalsPage() {
  const { token } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"pending" | "decided" | "mine">("pending");
  const [tasks, setTasks] = useState<ApprovalTask[]>([]);
  const [selected, setSelected] = useState<ApprovalTask | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setSelected(null);
    const fetcher =
      tab === "mine"
        ? listMyRequests(token)
        : listApprovals(token, tab === "pending" ? "pending" : "decided");
    fetcher
      .then(setTasks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token, tab]);

  async function handleDecide(decision: "approved" | "rejected" | "escalated") {
    if (!selected || !token) return;
    setSubmitting(true);
    setError(null);
    try {
      await decide(token, selected.id, decision, comment);
      setTasks((prev) => prev.filter((t) => t.id !== selected.id));
      setSelected(null);
      setComment("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  const pendingCount = tab === "pending" ? tasks.length : null;

  return (
    <div className="flex h-full">
      {/* List */}
      <div className="w-80 shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <div className="border-b border-gray-200 px-5 py-4">
          <h1 className="text-lg font-semibold text-gray-900">Approvals</h1>
          {pendingCount !== null && (
            <p className="text-sm text-gray-500">{pendingCount} pending</p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          {(["pending", "decided", "mine"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={clsx(
                "flex-1 py-2.5 text-xs font-medium capitalize transition-colors",
                tab === t
                  ? "border-b-2 border-blue-500 text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              {t === "mine" ? "My Requests" : t}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin divide-y divide-gray-100">
          {loading && <p className="px-5 py-6 text-sm text-gray-400">Loading…</p>}
          {!loading && tasks.length === 0 && (
            <div className="px-5 py-10 text-center">
              <CheckCircle className="mx-auto mb-3 h-8 w-8 text-green-400" />
              <p className="text-sm text-gray-500">
                {tab === "pending" ? "No pending approvals" : tab === "mine" ? "You have no submitted requests" : "No decided requests yet"}
              </p>
            </div>
          )}
          {tasks.map((task) => (
            <button
              key={task.id}
              onClick={() => { setSelected(task); setComment(""); setError(null); }}
              className={clsx(
                "w-full text-left px-5 py-4 hover:bg-gray-50 transition-colors",
                selected?.id === task.id && "bg-blue-50 border-r-2 border-blue-500"
              )}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="text-sm font-medium text-gray-900 leading-snug line-clamp-2">
                  {String(task.proposed_action?.question ?? task.proposed_action?.type ?? "Action")}
                </span>
                <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={clsx("rounded-full px-2 py-0.5 text-xs font-medium", RISK_COLORS[task.risk_class] ?? RISK_COLORS.medium)}>
                  {task.risk_class}
                </span>
                {task.decision && (
                  <span className={clsx("text-xs font-medium capitalize", DECISION_COLORS[task.decision] ?? "text-gray-600")}>
                    {task.decision}d
                  </span>
                )}
                {tab === "pending" && task.sla_deadline && (
                  <span className="flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    {new Date(task.sla_deadline).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-y-auto">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-center">
            <div>
              <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-gray-300" />
              <p className="text-sm text-gray-400">Select a request to review</p>
            </div>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto px-8 py-8">
            {/* Title */}
            <div className="mb-6">
              <span className={clsx("inline-block rounded-full px-2.5 py-0.5 text-xs font-medium mb-2", RISK_COLORS[selected.risk_class] ?? RISK_COLORS.medium)}>
                {selected.risk_class} risk
              </span>
              <h2 className="text-xl font-semibold text-gray-900">
                {String(selected.proposed_action?.question ?? "Review Action")}
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Required role: <span className="font-medium text-gray-700">{selected.approver_role}</span>
              </p>
              {selected.decision && (
                <p className={clsx("mt-1 text-sm font-medium capitalize", DECISION_COLORS[selected.decision] ?? "text-gray-600")}>
                  Decision: {selected.decision}d
                  {selected.decided_by && ` by ${selected.decided_by}`}
                  {selected.decided_at && ` · ${new Date(selected.decided_at).toLocaleString()}`}
                </p>
              )}
            </div>

            {/* Proposed action */}
            <Section title="Proposed Action">
              <pre className="rounded-lg bg-gray-50 border border-gray-200 p-4 text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(selected.proposed_action, null, 2)}
              </pre>
            </Section>

            {/* Evidence */}
            {selected.evidence && selected.evidence.length > 0 && (
              <Section title="Evidence — Retrieved Chunks">
                {selected.evidence.map((e, i) => (
                  <div key={i} className="rounded-lg border border-gray-200 bg-gray-50 p-3 mb-2 text-xs text-gray-700">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(e, null, 2)}</pre>
                  </div>
                ))}
              </Section>
            )}

            {/* Timeline */}
            <Section title="Timeline">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-gray-500">Requested</dt>
                <dd className="text-gray-900">{new Date(selected.created_at).toLocaleString()}</dd>
                {selected.sla_deadline && (
                  <>
                    <dt className="text-gray-500">SLA Deadline</dt>
                    <dd className="text-amber-700 font-medium">{new Date(selected.sla_deadline).toLocaleString()}</dd>
                  </>
                )}
                {selected.decided_at && (
                  <>
                    <dt className="text-gray-500">Decided</dt>
                    <dd className="text-gray-900">{new Date(selected.decided_at).toLocaleString()}</dd>
                  </>
                )}
              </dl>
            </Section>

            {/* Comment */}
            {selected.comment && (
              <Section title="Comment">
                <p className="text-sm text-gray-700 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                  {selected.comment}
                </p>
              </Section>
            )}

            {error && (
              <p className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</p>
            )}

            {/* Actions — only for pending tasks */}
            {selected.status === "pending" && (
              <>
                <Section title="Comment (optional)">
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                    placeholder="Add a comment or reason…"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none"
                  />
                </Section>
                <div className="flex gap-3">
                  <button
                    onClick={() => handleDecide("approved")}
                    disabled={submitting}
                    className="flex items-center gap-2 rounded-lg bg-green-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    <CheckCircle className="h-4 w-4" /> Approve
                  </button>
                  <button
                    onClick={() => handleDecide("rejected")}
                    disabled={submitting}
                    className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    <XCircle className="h-4 w-4" /> Reject
                  </button>
                  <button
                    onClick={() => handleDecide("escalated")}
                    disabled={submitting}
                    className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                  >
                    Escalate
                  </button>
                </div>
              </>
            )}

            {/* Approved — show Go to chat button */}
            {selected.decision === "approve" && (
              <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 flex items-center justify-between">
                <p className="text-sm text-green-800">
                  This request was approved. Go to chat and click <strong>Retry after approval</strong>.
                </p>
                <button
                  onClick={() => router.push(`/chat?retry=${selected.id}`)}
                  className="ml-4 shrink-0 flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Go to chat
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">{title}</h3>
      {children}
    </div>
  );
}
