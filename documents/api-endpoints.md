# AgentTrust — API Endpoints

Base URL: `https://api.agenttrust.io/v1`  
Auth: Bearer JWT (issued by Identity Service via SSO)  
All endpoints require `X-Tenant-ID` header.

---

## Authentication

### POST /auth/token
Exchange SSO code or credentials for a platform JWT.

**Request:**
```json
{
  "grant_type": "authorization_code",
  "code": "sso_callback_code",
  "redirect_uri": "https://app.agenttrust.io/callback"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "ref_...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "scope": "read write approve"
}
```

---

### POST /auth/refresh
Refresh an expired access token.

**Request:**
```json
{
  "refresh_token": "ref_..."
}
```

---

### POST /auth/revoke
Revoke a token (user logout or agent deactivation).

**Request:**
```json
{
  "token": "eyJ...",
  "token_type_hint": "access_token"
}
```

---

## Agents

### GET /agents
List all registered agents for the tenant.

**Query params:** `status`, `risk_class`, `owner`, `page`, `limit`

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "invoice-agent-v1",
      "name": "Invoice Processing Agent",
      "version": "1.3",
      "owner": "finance-team",
      "purpose": "Invoice exception investigation and approval routing",
      "risk_class": "medium",
      "status": "active",
      "allowed_tools": ["erp_read_invoice", "erp_read_po"],
      "created_at": "2026-01-15T09:00:00Z"
    }
  ],
  "total": 12,
  "page": 1
}
```

---

### POST /agents
Register a new agent.

**Request:**
```json
{
  "name": "Invoice Processing Agent",
  "version": "1.3",
  "owner": "finance-team",
  "purpose": "Invoice exception investigation",
  "allowed_tools": ["erp_read_invoice", "erp_read_po", "sharepoint_read_contract"],
  "forbidden_actions": ["delete_record"],
  "required_approvals": ["approve_invoice_over_10k"],
  "data_scope": ["finance", "procurement"],
  "risk_class": "medium",
  "max_tokens_per_call": 4000,
  "max_calls_per_minute": 20
}
```

**Response:** `201 Created` with the created agent object.

---

### GET /agents/{agent_id}
Get a specific agent's details.

---

### PATCH /agents/{agent_id}
Update agent configuration (e.g., add allowed tool, change risk class).

---

### DELETE /agents/{agent_id}
Deactivate an agent (soft delete — audit history preserved).

---

### POST /agents/{agent_id}/run
Trigger an agent workflow.

**Request:**
```json
{
  "request": "Why is invoice INV-4821 blocked?",
  "context": {
    "workflow": "invoice_exception",
    "user_id": "user_maria",
    "session_id": "sess_7f2a"
  }
}
```

**Response:**
```json
{
  "run_id": "run_9a3b",
  "status": "running",
  "agent_id": "invoice-agent-v1",
  "created_at": "2026-11-18T16:00:00Z"
}
```

---

### GET /agents/{agent_id}/runs/{run_id}
Get the status and result of an agent run.

**Response:**
```json
{
  "run_id": "run_9a3b",
  "status": "awaiting_approval",
  "answer": "Invoice INV-4821 is blocked because it exceeds the EUR 10,000 approval threshold...",
  "citations": [
    { "id": 1, "source": "ERP.invoice.INV-4821", "excerpt": "Amount: EUR 18,400" },
    { "id": 2, "source": "FinancePolicy.v12", "excerpt": "Invoices over EUR 10,000 require controller approval" }
  ],
  "approval_task_id": "appr_7c2d",
  "receipt_id": "dec_9f3a81"
}
```

---

## Query (RAG)

### POST /query
Ask a natural-language question. Returns a permission-filtered answer with citations.

**Request:**
```json
{
  "question": "What are the payment terms in our contract with Supplier ABC?",
  "filters": {
    "source_systems": ["SharePoint", "ERP"],
    "departments": ["procurement"]
  },
  "max_sources": 5
}
```

**Response:**
```json
{
  "answer": "The contract with Supplier ABC specifies net-30 payment terms...",
  "citations": [
    {
      "id": 1,
      "source_system": "SharePoint",
      "document_id": "contract_abc_v3",
      "document_name": "Supplier ABC Master Agreement v3",
      "excerpt": "Payment shall be made within 30 days of invoice receipt.",
      "confidence": 0.94
    }
  ],
  "unauthorized_sources_filtered": 2,
  "latency_ms": 1240
}
```

---

### POST /query/structured
Query structured data (ERP, CRM) with natural language, returned as a table.

**Request:**
```json
{
  "question": "Show all open invoices over EUR 5,000 for supplier ABC",
  "source_system": "ERP",
  "entity": "Invoice"
}
```

**Response:**
```json
{
  "columns": ["invoice_id", "amount", "currency", "status", "due_date"],
  "rows": [
    ["INV-4821", 18400, "EUR", "blocked", "2026-12-01"],
    ["INV-4902", 7200,  "EUR", "pending", "2026-12-15"]
  ],
  "total_rows": 2,
  "source": "ERP",
  "receipt_id": "dec_a1b2"
}
```

---

## Connectors

### GET /connectors
List all configured connectors.

**Response:**
```json
{
  "connectors": [
    {
      "connector_id": "conn_sap_01",
      "type": "SAP_ERP",
      "display_name": "SAP Production",
      "status": "healthy",
      "last_checked": "2026-11-18T16:00:00Z",
      "permissions": ["read", "search", "write_approved"]
    }
  ]
}
```

---

### POST /connectors
Add a new connector.

**Request:**
```json
{
  "type": "SALESFORCE_CRM",
  "display_name": "Salesforce Production",
  "auth": {
    "method": "oauth2",
    "client_id": "sf_client_id",
    "client_secret": "sf_client_secret",
    "token_url": "https://login.salesforce.com/services/oauth2/token",
    "scopes": ["api", "refresh_token"]
  },
  "field_permissions": {
    "denied_fields": ["SSN", "BankAccount"]
  }
}
```

---

### POST /connectors/{connector_id}/test
Test a connector's health and authentication.

**Response:**
```json
{
  "status": "healthy",
  "latency_ms": 240,
  "auth_valid": true,
  "sample_read": "success"
}
```

---

### DELETE /connectors/{connector_id}
Remove a connector. Existing audit records are preserved.

---

## Policies

### GET /policies
List all policies for the tenant.

---

### POST /policies
Create a new policy.

**Request:**
```json
{
  "name": "invoice_approval_threshold",
  "description": "Invoices over EUR 10,000 require finance controller approval",
  "condition": {
    "entity": "Invoice",
    "action": "approve_invoice",
    "rules": [
      { "field": "amount", "operator": "greater_than", "value": 10000 }
    ]
  },
  "decision": "require_approval",
  "approver_role": "finance_controller",
  "priority": 10
}
```

---

### POST /policies/{policy_id}/simulate
Test a policy against sample data without activating it.

**Request:**
```json
{
  "inputs": [
    { "action": "approve_invoice", "amount": 15000, "user_role": "finance_manager" },
    { "action": "approve_invoice", "amount": 800,   "user_role": "finance_manager" }
  ]
}
```

**Response:**
```json
{
  "results": [
    { "input_index": 0, "decision": "require_approval", "reason": "Amount exceeds EUR 10,000" },
    { "input_index": 1, "decision": "allow", "reason": "Amount within threshold" }
  ]
}
```

---

### PATCH /policies/{policy_id}/activate
Activate a policy version.

### PATCH /policies/{policy_id}/deactivate
Deactivate a policy (kept in history).

---

## Approvals

### GET /approvals
List pending approval tasks for the current user.

**Query params:** `status=pending`, `workflow`, `risk_class`, `page`, `limit`

**Response:**
```json
{
  "approvals": [
    {
      "approval_id": "appr_7c2d",
      "workflow": "invoice_exception",
      "requested_by": "maria@company.com",
      "agent": "invoice-agent-v1.3",
      "proposed_action": "Approve invoice INV-4821 for EUR 18,400",
      "risk_class": "medium",
      "policy_triggered": "invoice_approval_threshold",
      "citations": [...],
      "sla_deadline": "2026-11-18T20:00:00Z",
      "created_at": "2026-11-18T16:00:00Z"
    }
  ],
  "total": 3
}
```

---

### POST /approvals/{approval_id}/decide
Submit an approval decision.

**Request:**
```json
{
  "decision": "approved",
  "comment": "Verified against PO and contract. Amount is correct."
}
```

Decision options: `approved`, `rejected`, `escalated`

**Response:** `200 OK` — workflow resumes if approved.

---

### POST /approvals/{approval_id}/request_info
Ask the requesting employee for more information before deciding.

**Request:**
```json
{
  "question": "Can you confirm the delivery has been received for this invoice?"
}
```

---

## Audit

### GET /audit/receipts
Search decision receipts.

**Query params:** `user_id`, `agent_id`, `workflow`, `action`, `from_date`, `to_date`, `status`, `page`, `limit`

**Response:**
```json
{
  "receipts": [
    {
      "receipt_id": "dec_9f3a81",
      "workflow": "invoice_exception",
      "requested_by": "maria@company.com",
      "agent": "invoice-agent-v1.3",
      "final_action": "approve_invoice",
      "status": "completed",
      "timestamp_end": "2026-11-18T16:32:00Z",
      "audit_hash": "sha256:9f3a81c7..."
    }
  ],
  "total": 148
}
```

---

### GET /audit/receipts/{receipt_id}
Get the full detail of a single decision receipt.

---

### POST /audit/receipts/export
Export receipts to CSV or JSON for a date range.

**Request:**
```json
{
  "from_date": "2026-01-01",
  "to_date": "2026-11-18",
  "format": "csv",
  "filters": { "workflow": "invoice_exception" }
}
```

**Response:** `202 Accepted` with a job ID. Poll `GET /audit/exports/{job_id}` for the download URL.

---

### GET /audit/receipts/{receipt_id}/verify
Verify the hash chain integrity of a receipt.

**Response:**
```json
{
  "receipt_id": "dec_9f3a81",
  "hash_valid": true,
  "chain_valid": true,
  "verified_at": "2026-11-18T17:00:00Z"
}
```

---

## Users & Roles

### GET /users
List users in the tenant.

### POST /users/invite
Invite a user by email.

### PATCH /users/{user_id}/roles
Assign or remove roles.

**Request:**
```json
{
  "add_roles": ["finance_controller"],
  "remove_roles": ["finance_viewer"]
}
```

### DELETE /users/{user_id}
Deactivate a user and revoke their tokens.

---

## MCP

### GET /.well-known/mcp-configuration
MCP protected-resource metadata discovery endpoint (OAuth 2.1).

**Response:**
```json
{
  "resource": "https://api.agenttrust.io",
  "authorization_servers": ["https://auth.agenttrust.io"],
  "scopes_supported": ["tools:read", "tools:invoke", "data:read"],
  "token_endpoint_auth_methods_supported": ["client_secret_basic"]
}
```

---

### GET /mcp/tools
List available MCP tools for the authenticated agent.

**Response:**
```json
{
  "tools": [
    {
      "name": "erp_read_invoice",
      "description": "Read an invoice record from the ERP system",
      "input_schema": {
        "type": "object",
        "properties": {
          "invoice_id": { "type": "string" }
        },
        "required": ["invoice_id"]
      }
    }
  ]
}
```

---

### POST /mcp/tools/{tool_name}/invoke
Invoke a registered MCP tool. Policy is evaluated before execution.

**Request:**
```json
{
  "parameters": {
    "invoice_id": "INV-4821"
  },
  "agent_id": "invoice-agent-v1",
  "run_id": "run_9a3b"
}
```

**Response:**
```json
{
  "result": {
    "invoice_id": "INV-4821",
    "amount": 18400,
    "currency": "EUR",
    "status": "blocked",
    "supplier": "Supplier ABC",
    "purchase_order": "PO-992"
  },
  "policy_decision": "allow",
  "audit_event_id": "evt_3f9a"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "POLICY_DENIED",
    "message": "Action denied by policy: invoice_approval_threshold",
    "details": {
      "policy_id": "policy_inv_001",
      "reason": "Invoice amount EUR 18,400 exceeds threshold EUR 10,000"
    },
    "request_id": "req_8a2f",
    "timestamp": "2026-11-18T16:00:00Z"
  }
}
```

### Error codes
| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | Valid token but insufficient permissions |
| `POLICY_DENIED` | 403 | Action blocked by policy engine |
| `APPROVAL_REQUIRED` | 202 | Action paused, pending human approval |
| `NOT_FOUND` | 404 | Resource does not exist for this tenant |
| `RATE_LIMITED` | 429 | Too many requests |
| `CONNECTOR_ERROR` | 502 | Downstream system returned an error |
| `VALIDATION_ERROR` | 422 | Request body failed validation |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
