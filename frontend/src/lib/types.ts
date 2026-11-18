export interface Citation {
  id: number;
  source_system: string;
  document_name: string;
  excerpt: string;
  similarity: number;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  unauthorized_sources_filtered: number;
  latency_ms: number;
  approval_required?: boolean;
  approval_task_id?: string | null;
  policy_name?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  filtered?: number;
  latency_ms?: number;
  timestamp: Date;
  approval_required?: boolean;
  approval_task_id?: string;
  policy_name?: string;
  pending_question?: string;
}

export interface AgentRun {
  run_id: string;
  status: string;
  answer: string | null;
  citations: Citation[];
  approval_task_id: string | null;
}

export interface ApprovalTask {
  id: string;
  run_id: string;
  approver_role: string;
  proposed_action: Record<string, unknown>;
  evidence: unknown[];
  risk_class: string;
  status: string;
  decision: string | null;
  decided_by: string | null;
  comment: string | null;
  sla_deadline: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface Document {
  id: string;
  name: string;
  source_system: string;
  file_type: string;
  sensitivity: string;
  department: string | null;
  chunk_count: number;
  indexed_at: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  run_id: string | null;
  user_id: string | null;
  agent_id: string | null;
  event_type: string;
  workflow: string | null;
  payload: Record<string, unknown>;
  event_hash: string;
  created_at: string;
}
