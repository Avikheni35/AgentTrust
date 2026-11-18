import type { ApprovalTask, AuditEvent, Document, QueryResponse } from "./types";

const BASE = "/api";

async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

// ── Query ─────────────────────────────────────────────────────────────────────

export async function query(
  token: string,
  question: string,
  opts?: { sourceSystems?: string[]; approvedTaskId?: string }
): Promise<QueryResponse> {
  return request("/query", token, {
    method: "POST",
    body: JSON.stringify({
      question,
      source_systems: opts?.sourceSystems,
      approved_task_id: opts?.approvedTaskId,
    }),
  });
}

// ── Documents ─────────────────────────────────────────────────────────────────

export async function listDocuments(token: string): Promise<Document[]> {
  return request("/documents", token);
}

export async function uploadDocument(
  token: string,
  file: File,
  meta: { sensitivity: string; department?: string; access_roles?: string }
): Promise<{ document_id: string; chunk_count: number }> {
  const form = new FormData();
  form.append("file", file);
  form.append("sensitivity", meta.sensitivity);
  if (meta.department) form.append("department", meta.department);
  if (meta.access_roles) form.append("access_roles", meta.access_roles);

  const res = await fetch(`${BASE}/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function deleteDocument(token: string, id: string): Promise<void> {
  await request(`/documents/${id}`, token, { method: "DELETE" });
}

export async function updateSensitivity(token: string, id: string, sensitivity: string): Promise<void> {
  await request(`/documents/${id}/sensitivity`, token, {
    method: "PATCH",
    body: JSON.stringify({ sensitivity }),
  });
}

// ── Approvals ─────────────────────────────────────────────────────────────────

export async function listApprovals(token: string, status?: string): Promise<ApprovalTask[]> {
  const qs = status ? `?task_status=${status}` : "";
  return request(`/approvals${qs}`, token);
}

export async function listMyRequests(token: string): Promise<ApprovalTask[]> {
  return request("/approvals/mine", token);
}

export async function decide(
  token: string,
  approvalId: string,
  decision: "approved" | "rejected" | "escalated",
  comment?: string
): Promise<void> {
  await request(`/approvals/${approvalId}/decide`, token, {
    method: "POST",
    body: JSON.stringify({ decision, comment }),
  });
}

// ── Audit ─────────────────────────────────────────────────────────────────────

export async function listAuditEvents(
  token: string,
  params?: { event_type?: string; limit?: number; offset?: number }
): Promise<AuditEvent[]> {
  const qs = new URLSearchParams();
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.limit)      qs.set("limit", String(params.limit));
  if (params?.offset)     qs.set("offset", String(params.offset));
  return request(`/audit/receipts?${qs}`, token);
}

export async function verifyAuditChain(token: string) {
  return request<{ chain_valid: boolean }>("/audit/verify", token);
}
