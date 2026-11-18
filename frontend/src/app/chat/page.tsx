"use client";

import { BookOpen, Clock, Loader2, RefreshCw, Send, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { listMyRequests, query as apiQuery } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApprovalTask } from "@/lib/types";
import type { ChatMessage, Citation } from "@/lib/types";

const nextId = () => crypto.randomUUID();

function storageKey(email?: string) {
  return `agenttrust_chat_${email ?? "default"}`;
}

function loadHistory(email?: string): ChatMessage[] {
  if (typeof window === "undefined") return [];           // SSR guard
  try {
    const raw = localStorage.getItem(storageKey(email));
    if (!raw) return [];
    return (JSON.parse(raw) as ChatMessage[]).map((m) => ({
      ...m,
      timestamp: new Date(m.timestamp),
    }));
  } catch {
    return [];
  }
}

function saveHistory(msgs: ChatMessage[], email?: string) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(storageKey(email), JSON.stringify(msgs.slice(-100)));
  } catch {}
}

export default function ChatPageWrapper() {
  return <Suspense fallback={null}><ChatPage /></Suspense>;
}

function ChatPage() {
  const { token, userEmail } = useAuth();
  const searchParams = useSearchParams();
  const retryTaskId = searchParams.get("retry");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeCitations, setActiveCitations] = useState<Citation[] | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalTask[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const loaded = useRef(false);

  // Load history client-side only (after mount) — avoids SSR/hydration mismatch
  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    const history = loadHistory(userEmail ?? undefined);
    if (history.length > 0) setMessages(history);
  }, [userEmail]);

  // Persist on change
  useEffect(() => {
    if (!loaded.current) return;
    saveHistory(messages, userEmail ?? undefined);
  }, [messages, userEmail]);

  function dismissedKey(email?: string) {
    return `agenttrust_dismissed_approvals_${email ?? "default"}`;
  }

  function getDismissed(email?: string): Set<string> {
    try {
      const raw = localStorage.getItem(dismissedKey(email));
      return new Set(raw ? JSON.parse(raw) : []);
    } catch { return new Set(); }
  }

  function saveDismissed(ids: Set<string>, email?: string) {
    try {
      localStorage.setItem(dismissedKey(email), JSON.stringify([...ids]));
    } catch {}
  }

  // Auto-submit when navigated here with ?retry=<taskId>
  const retried = useRef(false);
  useEffect(() => {
    if (!token || !retryTaskId || retried.current) return;
    retried.current = true;
    listMyRequests(token).then((tasks) => {
      const task = tasks.find((t) => t.id === retryTaskId && t.decision === "approve");
      if (task) {
        const question = String(task.proposed_action?.question ?? "");
        if (question) submitQuestion(question, task.id);
      }
    }).catch(() => {});
  }, [token, retryTaskId]);

  // Load approved-but-unretried tasks for the banner
  useEffect(() => {
    if (!token) return;
    listMyRequests(token)
      .then((tasks) => {
        const dismissed = getDismissed(userEmail ?? undefined);
        setPendingApprovals(
          tasks.filter((t) => t.decision === "approve" && !dismissed.has(t.id))
        );
      })
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function dismissApproval(taskId: string) {
    setPendingApprovals((prev) => prev.filter((t) => t.id !== taskId));
    const dismissed = getDismissed(userEmail ?? undefined);
    dismissed.add(taskId);
    saveDismissed(dismissed, userEmail ?? undefined);
  }

  async function submitQuestion(question: string, approvedTaskId?: string) {
    if (!question || loading || !token) return;
    setActiveCitations(null);

    const userMsg: ChatMessage = {
      id: nextId(), role: "user", content: question, timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await apiQuery(token, question, { approvedTaskId });
      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        filtered: res.unauthorized_sources_filtered,
        latency_ms: res.latency_ms,
        timestamp: new Date(),
        approval_required: res.approval_required,
        approval_task_id: res.approval_task_id ?? undefined,
        policy_name: res.policy_name ?? undefined,
        // Store original question so the Retry button can re-submit it
        pending_question: res.approval_required ? question : undefined,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (res.citations.length > 0) setActiveCitations(res.citations);
    } catch (err: unknown) {
      const errorMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question) return;
    setInput("");
    await submitQuestion(question);
  }

  async function handleRetry(msg: ChatMessage) {
    if (!msg.pending_question || !msg.approval_task_id) return;
    await submitQuestion(msg.pending_question, msg.approval_task_id);
  }

  return (
    <div className="flex h-full">
      {/* Chat column */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <div className="border-b border-gray-200 bg-white px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Ask AI</h1>
            <p className="text-sm text-gray-500">Ask questions across your authorized enterprise systems</p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => { setMessages([]); saveHistory([]); setActiveCitations(null); }}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
            >
              Clear history
            </button>
          )}
        </div>

        {/* Approved-task banner — fallback if history was cleared */}
        {pendingApprovals.length > 0 && (
          <div className="border-b border-green-200 bg-green-50 px-6 py-3 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-green-800 uppercase tracking-wide">Approved requests — ready to answer</p>
              <button
                onClick={() => pendingApprovals.forEach((t) => dismissApproval(t.id))}
                className="text-xs text-green-700 hover:text-green-900 underline"
              >
                Dismiss all
              </button>
            </div>
            {pendingApprovals.map((task) => (
              <div key={task.id} className="flex items-center justify-between gap-3">
                <span className="text-sm text-green-900 truncate flex-1">
                  {String(task.proposed_action?.question ?? "Query")}
                </span>
                <button
                  onClick={() => {
                    dismissApproval(task.id);
                    submitQuestion(
                      String(task.proposed_action?.question ?? ""),
                      task.id
                    );
                  }}
                  className="shrink-0 flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Retry
                </button>
                <button
                  onClick={() => dismissApproval(task.id)}
                  title="Dismiss"
                  className="shrink-0 rounded p-1 text-green-700 hover:bg-green-100 transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-4 space-y-4">
          {messages.length === 0 && <EmptyState onExampleClick={(q) => { setInput(q); }} />}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationClick={() => msg.citations ? setActiveCitations(msg.citations) : null}
              onRetry={() => handleRetry(msg)}
            />
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching authorized sources…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question across your systems…"
              disabled={loading}
              className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm shadow-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
            >
              <Send className="h-4 w-4" />
              Send
            </button>
          </form>
        </div>
      </div>

      {/* Citations panel */}
      {activeCitations && (
        <CitationsPanel citations={activeCitations} onClose={() => setActiveCitations(null)} />
      )}
    </div>
  );
}

function EmptyState({ onExampleClick }: { onExampleClick: (q: string) => void }) {
  const examples = [
    "What is the data protection policy?",
    "Can I install software on my work laptop?",
    "What are the remote work security rules?",
    "How do I report a security incident?",
  ];
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 rounded-full bg-blue-50 p-4">
        <BookOpen className="h-8 w-8 text-blue-500" />
      </div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">Ask anything</h2>
      <p className="mb-6 max-w-sm text-sm text-gray-500">
        Your questions are answered using only the data you are authorized to access.
        Every answer includes citations.
      </p>
      <div className="grid gap-2 w-full max-w-lg">
        {examples.map((ex) => (
          <button
            key={ex}
            onClick={() => onExampleClick(ex)}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2.5 text-left text-sm text-gray-600 hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({
  message, onCitationClick, onRetry,
}: {
  message: ChatMessage;
  onCitationClick: () => void;
  onRetry: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-xl rounded-2xl bg-blue-600 px-4 py-3 text-sm text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const isPending = message.approval_required;

  return (
    <div className="flex gap-3">
      <div className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${isPending ? "bg-amber-500" : "bg-slate-800"}`}>
        {isPending
          ? <Clock className="h-4 w-4 text-white" />
          : <span className="text-xs font-bold text-white">AI</span>}
      </div>
      <div className="flex-1">
        <div className={`rounded-2xl border px-4 py-3 text-sm shadow-sm whitespace-pre-wrap ${
          isPending
            ? "border-amber-200 bg-amber-50 text-amber-900"
            : "border-gray-200 bg-white text-gray-800"
        }`}>
          {message.content}

          {/* Retry button — shown after approval */}
          {isPending && message.approval_task_id && (
            <div className="mt-3 pt-3 border-t border-amber-200">
              <p className="text-xs text-amber-700 mb-2">
                Once approved in the <strong>Approvals</strong> tab, click below to get the answer:
              </p>
              <button
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
                Retry after approval
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-1.5 flex items-center gap-3 pl-1">
          {message.citations && message.citations.length > 0 && (
            <button onClick={onCitationClick} className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
              <BookOpen className="h-3 w-3" />
              {message.citations.length} source{message.citations.length > 1 ? "s" : ""}
            </button>
          )}
          {!!message.filtered && message.filtered > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <ShieldAlert className="h-3 w-3" />
              {message.filtered} restricted
            </span>
          )}
          {isPending && (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <ShieldCheck className="h-3 w-3" />
              {message.policy_name}
            </span>
          )}
          {message.latency_ms && (
            <span className="text-xs text-gray-400">{message.latency_ms}ms</span>
          )}
        </div>
      </div>
    </div>
  );
}

function CitationsPanel({ citations, onClose }: { citations: Citation[]; onClose: () => void }) {
  return (
    <div className="w-80 shrink-0 border-l border-gray-200 bg-white flex flex-col">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <span className="text-sm font-semibold text-gray-900">Sources</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin divide-y divide-gray-100">
        {citations.map((c) => (
          <div key={c.id} className="px-4 py-3">
            <div className="flex items-start justify-between gap-2 mb-1">
              <span className="text-xs font-medium text-gray-900 leading-snug">{c.document_name}</span>
              <span className="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">[{c.id}]</span>
            </div>
            <div className="text-xs text-blue-600 mb-2">{c.source_system}</div>
            <p className="text-xs text-gray-600 leading-relaxed line-clamp-4">{c.excerpt}</p>
            <div className="mt-1.5 text-xs text-gray-400">Relevance: {Math.round(c.similarity * 100)}%</div>
          </div>
        ))}
      </div>
    </div>
  );
}
 
