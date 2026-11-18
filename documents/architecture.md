# AgentTrust — System Architecture

## 1. Overview

AgentTrust is a multi-tenant SaaS platform that sits between employees, AI agents, and enterprise systems. It enforces identity, permissions, policies, and audit controls before any AI agent can retrieve data or execute an action.

```
┌─────────────────────────────────────────┐
│          Employees / AI Clients          │
└──────────────────┬──────────────────────┘
                   │ HTTPS / WebSocket
┌──────────────────▼──────────────────────┐
│           API Gateway (Kong/Nginx)       │
│   Rate limiting · TLS termination        │
│   Auth token validation                  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         AgentTrust Control Plane         │
│                                          │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  Identity   │  │  Policy Engine   │  │
│  │  Service    │  │  (OPA / custom)  │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  RAG        │  │  Agent           │  │
│  │  Service    │  │  Orchestrator    │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  Workflow   │  │  Audit Service   │  │
│  │  Engine     │  │                  │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  Connector  │  │  Semantic Layer  │  │
│  │  Gateway    │  │                  │  │
│  └─────────────┘  └──────────────────┘  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│        Connector / MCP Layer             │
│  SAP · Salesforce · M365 · SharePoint    │
│  Jira · Snowflake · PostgreSQL · REST    │
└─────────────────────────────────────────┘
```

---

## 2. Core Components

### 2.1 Identity Service

Handles all authentication and authorization for users, service accounts, and AI agents.

**Responsibilities:**
- SSO via OIDC / SAML 2.0
- MFA enforcement
- SCIM provisioning / deprovisioning
- JWT and short-lived access token issuance
- Agent identity registration and token binding
- Role-based access control (RBAC)
- Attribute-based access control (ABAC)
- Session management and revocation

**Tech:** Auth0 / Keycloak / Microsoft Entra ID, backed by PostgreSQL

---

### 2.2 Policy Engine

Evaluates every retrieval request and agent action against business rules before execution.

**Responsibilities:**
- Load and evaluate tenant-specific policies
- Support RBAC, ABAC, amount-based, time-based, and region-based rules
- Return: `allow`, `deny`, `require_approval`
- Policy versioning and rollback
- Simulation mode for testing policies before activation

**Example policy (OPA Rego):**
```rego
package agenttrust.invoice

default decision = "deny"

decision = "require_approval" {
  input.action == "approve_invoice"
  input.invoice.amount > 10000
  input.user.role == "finance_manager"
}

decision = "allow" {
  input.action == "approve_invoice"
  input.invoice.amount <= 10000
  input.user.role == "finance_manager"
}
```

**Tech:** Open Policy Agent (OPA) or custom Python rule engine

---

### 2.3 RAG Service

Permission-aware retrieval across documents and structured records.

**Responsibilities:**
- Chunk and embed documents on ingestion
- Store metadata with every chunk (tenant, owner, roles, sensitivity, dates)
- Filter chunks at retrieval time based on requesting user's identity
- Hybrid search: dense vector + BM25 keyword
- Re-rank results by source authority
- Return citations with every answer

**Data stored per chunk:**
```json
{
  "chunk_id": "chk_9f3a",
  "tenant_id": "tenant_482",
  "source_system": "SharePoint",
  "document_id": "doc_contract_v4",
  "owner": "legal@company.com",
  "department": "legal",
  "sensitivity": "confidential",
  "access_roles": ["legal_team", "finance_controller"],
  "region": "EU",
  "effective_date": "2025-01-01",
  "expiry_date": "2027-01-01",
  "embedding": [0.021, -0.14, ...]
}
```

**Tech:** pgvector (PostgreSQL) or Qdrant, LangChain retrieval chain, OpenAI / Claude embeddings

---

### 2.4 Agent Orchestrator

Manages multi-step AI workflows. Receives a natural-language request, plans steps, calls tools, and enforces constraints.

**Responsibilities:**
- Parse and classify the user's intent
- Select relevant tools from the MCP registry
- Call RAG service for context retrieval
- Validate each planned action against the policy engine
- Route actions requiring approval to the workflow engine
- Execute approved actions via the connector gateway
- Handle retries and failures
- Write the decision receipt to the audit service

**Registered agent properties:**
```json
{
  "agent_id": "invoice-agent-v1",
  "owner": "finance-team",
  "purpose": "Invoice exception investigation and approval routing",
  "allowed_tools": ["erp_read_invoice", "erp_read_po", "sharepoint_read_contract"],
  "forbidden_actions": ["delete_record", "modify_supplier"],
  "required_approvals": ["approve_invoice_over_10k"],
  "data_scope": ["finance", "procurement"],
  "risk_class": "medium",
  "max_tokens_per_call": 4000
}
```

**Tech:** LangChain Agents / LangGraph, Python

---

### 2.5 Connector Gateway

Secure proxy between AgentTrust and enterprise systems.

**Responsibilities:**
- Store and refresh OAuth 2.0 / API credentials per connector
- Route requests to the correct system
- Apply field-level permission filtering on responses
- Rate limit outbound calls
- Handle retries and circuit breaking
- Log every outbound call to the audit service
- Never expose raw credentials to AI models

**Connector interface:**
```python
class BaseConnector:
    def search(self, query: str, filters: dict, user_context: UserContext) -> list[Record]
    def read(self, record_id: str, user_context: UserContext) -> Record
    def write(self, operation: WriteOperation, user_context: UserContext) -> WriteResult
    def health_check(self) -> HealthStatus
```

**Tech:** Python FastAPI microservice, HashiCorp Vault for credential storage

---

### 2.6 Workflow Engine

Manages approval flows, escalations, timeouts, and state.

**Responsibilities:**
- Create approval tasks for humans
- Notify approvers via email, Slack, or Teams
- Track approve / reject / escalate decisions
- Handle timeouts and auto-escalation
- Resume the agent workflow after approval
- Record all decisions

**Tech:** Temporal.io or custom state machine backed by PostgreSQL

---

### 2.7 Audit Service

Immutable record of every AI interaction and action.

**Responsibilities:**
- Receive structured events from all components
- Write to append-only store
- Hash each record for tamper detection
- Support search and export
- Enforce tenant-specific retention policies
- Provide SIEM export (Splunk, Elastic)

**Tech:** PostgreSQL append-only table with hash chain, optional S3 archival

---

### 2.8 Semantic Layer

Shared business ontology that gives AI agents company-specific context.

**Responsibilities:**
- Define business entities (Customer, Invoice, Supplier, Contract, etc.)
- Map entities across systems (CRM account = ERP business partner)
- Define source-of-truth system per entity
- Store business glossary and terminology
- Reference company-specific policies and thresholds

---

## 3. Data Architecture

### 3.1 Databases

| Store | Purpose | Technology |
|---|---|---|
| Core DB | Users, tenants, agents, connectors, workflows | PostgreSQL |
| Vector DB | Document embeddings and chunk metadata | pgvector / Qdrant |
| Audit DB | Immutable event log | PostgreSQL (append-only) |
| Cache | Session tokens, policy cache, rate limit counters | Redis |
| Object store | Documents, attachments, exports | S3 / Azure Blob |
| Secrets | OAuth tokens, API keys | HashiCorp Vault |

### 3.2 Multi-tenancy model

- Every database table includes `tenant_id`
- All queries apply `WHERE tenant_id = ?` at the ORM layer
- Vector DB uses namespaced collections per tenant
- Separate encryption keys per tenant (BYOK supported)
- Admin users are scoped to a single tenant

---

## 4. Security Architecture

### 4.1 Token flow

```
User → SSO → Identity Service → JWT (user identity + roles + tenant)
                                     ↓
                           Agent Orchestrator
                                     ↓
                        Policy Engine evaluates JWT claims
                                     ↓
                      Connector Gateway uses service-account token
                      (never the user's credential directly)
```

### 4.2 AI security controls

| Threat | Control |
|---|---|
| Prompt injection | Input sanitization, untrusted-content tagging |
| Data exfiltration | Output filtering, PII redaction before response |
| Excessive permissions | Agent allowlist, least-privilege tokens |
| Unauthorized tool use | Policy engine check before every tool call |
| Model hallucination | Citation requirement, source-authority ranking |
| Credential exposure | Vault-backed secrets, tokens never sent to LLM |

---

## 5. Deployment Architecture

```
┌─────────────────────────────────────┐
│         Kubernetes Cluster           │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Frontend │  │  API Gateway     │  │
│  │ (Next.js)│  │  (Kong / Nginx)  │  │
│  └──────────┘  └──────────────────┘  │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Identity │  │  Orchestrator    │  │
│  │ Service  │  │  (Python)        │  │
│  └──────────┘  └──────────────────┘  │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ RAG      │  │  Policy Engine   │  │
│  │ Service  │  │  (OPA)           │  │
│  └──────────┘  └──────────────────┘  │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Workflow │  │  Audit Service   │  │
│  │ Engine   │  │                  │  │
│  └──────────┘  └──────────────────┘  │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │PostgreSQL│  │  Qdrant / Redis  │  │
│  │          │  │                  │  │
│  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────┘
```

**Cloud targets:** AWS (primary), Azure (EU residency option), GCP  
**CI/CD:** GitHub Actions → Docker → Helm → Kubernetes  
**Observability:** OpenTelemetry + Prometheus + Grafana
