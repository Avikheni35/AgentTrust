"use client";

import clsx from "clsx";
import { ChevronDown, ChevronRight, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { listAuditEvents, verifyAuditChain } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuditEvent } from "@/lib/types";

const EVENT_COLORS: Record<string, string> = {
  query:              "bg-blue-100 text-blue-700",
  retrieval_complete: "bg-indigo-100 text-indigo-700",
  policy_evaluation:  "bg-amber-100 text-amber-700",
  approval_required:  "bg-orange-100 text-orange-700",
  run_completed:      "bg-green-100 text-green-700",
  approval_decision:  "bg-teal-100 text-teal-700",
};

const EVENT_TYPES = [
  "all",
  "query",
  "retrieval_complete",
  "policy_evaluation",
  "approval_required",
  "run_completed",
];

export default function AuditPage() {
  const { token } = useAuth();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const PAGE = 50;

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    const params = {
      event_type: filter === "all" ? undefined : filter,
      limit: PAGE,
      offset: page * PAGE,
    };
    listAuditEvents(token, params)
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token, filter, page]);

  async function handleVerify() {
    if (!token) return;
    const res = await verifyAuditChain(token);
    setChainValid(res.chain_valid);
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-500">Immutable, hash-chained record of every AI action</p>
        </div>
        <div className="flex items-center gap-3">
          {chainValid !== null && (
            <span className={clsx(
              "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
              chainValid ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
            )}>
              <ShieldCheck className="h-3.5 w-3.5" />
              Chain {chainValid ? "valid" : "INVALID"}
            </span>
          )}
          <button
            onClick={handleVerify}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Verify chain
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-4 flex gap-2 flex-wrap">
        {EVENT_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => { setFilter(type); setPage(0); }}
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              filter === type
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {type === "all" ? "All events" : type.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : events.length === 0 ? (
          <p className="py-12 text-center text-sm text-gray-400">No events found</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wide">
              <tr>
                <th className="w-8 px-3 py-3" />
                <th className="px-4 py-3 text-left">Event</th>
                <th className="px-4 py-3 text-left">User</th>
                <th className="px-4 py-3 text-left">Agent</th>
                <th className="px-4 py-3 text-left">Run ID</th>
                <th className="px-4 py-3 text-left">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {events.map((ev) => (
                <>
                  <tr
                    key={ev.id}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => setExpanded(expanded === ev.id ? null : ev.id)}
                  >
                    <td className="px-3 py-3 text-gray-400">
                      {expanded === ev.id
                        ? <ChevronDown className="h-4 w-4" />
                        : <ChevronRight className="h-4 w-4" />}
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        EVENT_COLORS[ev.event_type] ?? "bg-gray-100 text-gray-700"
                      )}>
                        {ev.event_type.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                      {ev.user_id ? ev.user_id.slice(0, 8) + "…" : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                      {ev.agent_id ? ev.agent_id.slice(0, 12) + "…" : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                      {ev.run_id ? ev.run_id.slice(0, 8) + "…" : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {new Date(ev.created_at).toLocaleString()}
                    </td>
                  </tr>

                  {expanded === ev.id && (
                    <tr key={`${ev.id}-detail`} className="bg-slate-50">
                      <td colSpan={6} className="px-6 py-4">
                        <div className="grid grid-cols-2 gap-4 text-xs mb-3">
                          <div>
                            <span className="text-gray-500">Event ID</span>
                            <p className="font-mono text-gray-700 mt-0.5">{ev.id}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Hash</span>
                            <p className="font-mono text-gray-700 mt-0.5 truncate">{ev.event_hash}</p>
                          </div>
                        </div>
                        <div>
                          <span className="text-xs text-gray-500">Payload</span>
                          <pre className="mt-1 rounded-lg bg-slate-900 text-green-300 p-3 text-xs overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(ev.payload, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between text-sm text-gray-500">
        <span>Showing {page * PAGE + 1}–{page * PAGE + events.length}</span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded border border-gray-300 px-3 py-1 hover:bg-gray-50 disabled:opacity-40 transition-colors"
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={events.length < PAGE}
            className="rounded border border-gray-300 px-3 py-1 hover:bg-gray-50 disabled:opacity-40 transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
