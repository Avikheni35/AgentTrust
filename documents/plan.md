# AgentTrust — Implementation Plan

## Project Overview

**Product:** AgentTrust — Universal AI Action Trust Layer  
**Goal:** Build a multi-tenant SaaS platform that governs AI agent access to enterprise systems  
**Stack:** Python (FastAPI), LangChain, PostgreSQL, pgvector, React/Next.js, Kubernetes  
**Timeline:** 24 months across 4 phases

---

## Phase 1: Foundation (Months 0–3)

**Goal:** MVP — employees can securely ask questions across approved documents and receive cited answers.

### Milestone 1.1 — Project Setup (Week 1–2)

- [ ] Initialize monorepo structure (backend, frontend, infrastructure)
- [ ] Set up Python FastAPI backend skeleton
- [ ] Set up Next.js frontend skeleton
- [ ] Configure PostgreSQL database (local dev + staging)
- [ ] Set up Docker Compose for local development
- [ ] Configure GitHub Actions CI pipeline (lint, test, build)
- [ ] Set up environment variable management (`.env` + Vault for secrets)
- [ ] Create base data models (Tenant, User, Role, AuditEvent)

### Milestone 1.2 — Identity and Auth (Week 3–4)

- [ ] Integrate Auth0 / Keycloak for SSO (OIDC)
- [ ] Implement JWT issuance and validation middleware
- [ ] Build RBAC: role assignment, permission checks
- [ ] Add MFA support (TOTP)
- [ ] Implement session management and token refresh
- [ ] Multi-tenant isolation: `tenant_id` enforced at ORM layer
- [ ] User invite and provisioning API

### Milestone 1.3 — Document Connector + Ingestion (Week 5–7)

- [ ] Build first connector: SharePoint / OneDrive (OAuth 2.0)
- [ ] Document ingestion pipeline:
  - File download and type detection
  - Text extraction (PDF, DOCX, XLSX, TXT)
  - Chunking (recursive text splitter, 512 tokens, 50-token overlap)
  - Embedding generation (OpenAI `text-embedding-3-small` or Claude)
  - Store chunks with metadata in pgvector
- [ ] Metadata schema: tenant_id, source_system, document_id, owner, roles, sensitivity, region, dates
- [ ] Incremental re-indexing on document update
- [ ] Admin UI: connect SharePoint, trigger sync, view indexed documents

### Milestone 1.4 — Permission-Aware RAG (Week 8–9)

- [ ] Build RAG retrieval pipeline (LangChain)
- [ ] Pre-retrieval metadata filter: apply user roles and sensitivity rules
- [ ] Hybrid search: dense vector + BM25 keyword (pgvector + tsvector)
- [ ] Re-ranking by source authority score
- [ ] Citation generation: attach source document, excerpt, confidence score
- [ ] POST /query endpoint (see api-endpoints.md)
- [ ] Response format: answer + numbered citations + unauthorized_sources_filtered count

### Milestone 1.5 — Employee Chat UI (Week 10–11)

- [ ] Chat interface: submit question, receive streamed answer with citations
- [ ] Citation panel: click citation to view source excerpt and document link
- [ ] Query history per user
- [ ] "No authorized sources found" state handling
- [ ] Mobile-responsive layout

### Milestone 1.6 — Basic Audit Logging (Week 12)

- [ ] AuditEvent model: append-only PostgreSQL table
- [ ] Log every query: user, agent, sources retrieved, answer, timestamp
- [ ] Admin UI: view audit log, filter by user and date
- [ ] SHA-256 hash chain: each record hashes previous record's hash

**Phase 1 Deliverable:** Deployed staging environment. Employees can ask natural-language questions, receive cited answers from authorized documents, and all queries are audited.

---

## Phase 2: Enterprise Integration (Months 3–6)

**Goal:** AI can retrieve cross-system context and prepare governed actions for human approval.

### Milestone 2.1 — Connector Framework (Week 13–15)

- [ ] Build `BaseConnector` abstract class with standard interface
- [ ] Connector registry: register, enable/disable, health-check
- [ ] Credential storage: Vault-backed OAuth token management
- [ ] Token refresh and revocation handling
- [ ] Rate limiter per connector
- [ ] Retry and circuit breaker per connector
- [ ] Add connectors:
  - CRM: Salesforce (read accounts, contacts, opportunities)
  - ERP: SAP or Oracle NetSuite (read invoices, POs, suppliers)
  - Email: Microsoft 365 (read emails, send approved emails)
- [ ] Field-level permission filtering on connector responses
- [ ] POST /connectors and health-check endpoints

### Milestone 2.2 — Agent Orchestrator (Week 16–18)

- [ ] Agent registration data model (see features.md F-04)
- [ ] LangChain Agent or LangGraph implementation
- [ ] Tool registry: map agent allowlist to connector methods and RAG
- [ ] Orchestration loop:
  - Intent classification
  - Tool selection
  - RAG retrieval
  - Policy check before each action
  - Draft action generation
- [ ] POST /agents/{agent_id}/run endpoint
- [ ] Run state machine: CREATED → RUNNING → AWAITING_APPROVAL / EXECUTING → COMPLETED / FAILED
- [ ] Invoice exception agent (WF-01) as first implementation

### Milestone 2.3 — Policy Engine (Week 19–20)

- [ ] Policy data model: conditions, actions, decisions, priorities
- [ ] Policy evaluation engine (Python rule engine or OPA integration)
- [ ] Supported rule types: role-based, amount-based, attribute-based, region-based
- [ ] Decision outcomes: allow, deny, require_approval
- [ ] Policy simulation endpoint (POST /policies/{id}/simulate)
- [ ] Policy versioning: draft → active → deprecated
- [ ] Admin UI: policy builder with condition editor and test runner

### Milestone 2.4 — Human Approval Inbox (Week 21–22)

- [ ] Approval task data model
- [ ] Approval inbox UI: list pending tasks, sortable by SLA and risk
- [ ] Approval detail view: evidence, citations, proposed action, policy reason
- [ ] Actions: approve, reject, escalate, request_info
- [ ] Notifications: email + in-app
- [ ] SLA timer and auto-escalation rule
- [ ] POST /approvals/{id}/decide endpoint
- [ ] Workflow resumes after approval

### Milestone 2.5 — PII Redaction and AI Security (Week 23–24)

- [ ] PII detection before AI context (regex + spaCy NER)
- [ ] Redaction: replace PII with `[REDACTED]` before sending to LLM
- [ ] Input sanitization: detect and strip prompt injection patterns
- [ ] Output filtering: scan LLM output for accidental credential or key leakage
- [ ] Tool call validator: block calls to tools not on agent allowlist
- [ ] Security alert: log and alert on detected injection attempts

**Phase 2 Deliverable:** Invoice exception workflow fully operational end-to-end. Cross-system retrieval from ERP + SharePoint + CRM. Policy evaluation and human approval inbox live.

---

## Phase 3: Enterprise Readiness (Months 6–12)

**Goal:** Companies can deploy governed AI workflows across multiple business functions.

### Milestone 3.1 — Agent Directory and Lifecycle (Month 7)

- [ ] Agent directory UI: list all agents, owner, risk class, activity
- [ ] Agent versioning: deploy new version without breaking running workflows
- [ ] Agent deactivation: soft-delete with audit history preserved
- [ ] Agent-to-agent delegation: register delegation rules, trace in audit
- [ ] Agent performance metrics: success rate, avg latency, cost per run

### Milestone 3.2 — Decision Receipts (Month 7–8)

- [ ] Full decision receipt schema (see features.md F-07)
- [ ] Hash chain verification endpoint
- [ ] Searchable receipt store
- [ ] Export to CSV, JSON, SIEM formats
- [ ] Retention policy enforcement per tenant
- [ ] Receipt viewer UI with full trace

### Milestone 3.3 — Semantic Layer (Month 8–9)

- [ ] Entity definition schema (Customer, Invoice, Supplier, Contract, etc.)
- [ ] Cross-system field mapping (CRM.AccountId ↔ ERP.BusinessPartnerNo)
- [ ] Source-of-truth configuration per entity
- [ ] Business glossary editor in admin console
- [ ] Semantic layer used by agent orchestrator for context enrichment

### Milestone 3.4 — Connector Marketplace (Month 9–10)

- [ ] Additional connectors: Google Workspace, Jira, ServiceNow, Snowflake, Confluence
- [ ] Connector SDK for custom connectors (Python class + config schema)
- [ ] Connector marketplace UI in admin console
- [ ] Connector sandbox for testing before production

### Milestone 3.5 — Observability (Month 10–11)

- [ ] OpenTelemetry instrumentation across all services
- [ ] Prometheus metrics: latency, error rate, throughput per service
- [ ] Grafana dashboards: platform health, agent performance, approval wait times
- [ ] Security dashboard: policy violations, anomaly alerts, injection attempts
- [ ] Cost tracking: LLM token usage and cost per workflow and tenant
- [ ] Alerting: PagerDuty / Slack integration

### Milestone 3.6 — Compliance and Security Hardening (Month 11–12)

- [ ] SOC 2 Type II controls documented and implemented
- [ ] ISO 27001 gap analysis and remediation
- [ ] GDPR: data subject access, deletion, and export request workflows
- [ ] Data residency: EU/Germany deployment option (separate cluster)
- [ ] BYOK: customer-managed encryption keys (AWS KMS / Azure Key Vault)
- [ ] Penetration test (external vendor)
- [ ] Security questionnaire template
- [ ] DPA (Data Processing Agreement) template

**Phase 3 Deliverable:** Enterprise-grade platform. Multiple workflows across finance, support, and procurement. Compliance documentation complete. First enterprise pilot customers onboarded.

---

## Phase 4: Scale (Months 12–24)

**Goal:** Expand to a universal platform with industry templates, autonomous actions, and partner ecosystem.

### Milestone 4.1 — Workflow Templates (Month 13–15)

- [ ] Template library: invoice approval, customer support, procurement, onboarding, contract renewal
- [ ] Template configurator: customize without code
- [ ] Industry packs: manufacturing, fintech, SaaS

### Milestone 4.2 — Advanced Agent Evaluation (Month 15–17)

- [ ] Offline evaluation suite: test agents against golden datasets
- [ ] Retrieval quality metrics: precision, recall, MRR
- [ ] Answer faithfulness scoring (LLM-as-judge)
- [ ] Regression testing before agent version deployment
- [ ] A/B testing for workflow variants

### Milestone 4.3 — Autonomous Actions with Guardrails (Month 17–20)

- [ ] Define fully autonomous action categories (low-risk, high-confidence only)
- [ ] Confidence threshold: actions below threshold auto-route to human
- [ ] Anomaly-based escalation: unusual amounts, new suppliers, geographic mismatches
- [ ] Autonomous action audit trail with higher scrutiny retention

### Milestone 4.4 — Partner Ecosystem (Month 20–22)

- [ ] Public connector SDK with documentation
- [ ] Partner portal for connector submissions
- [ ] MCP tool marketplace
- [ ] Policy template marketplace

### Milestone 4.5 — Private Cloud / On-Premises (Month 22–24)

- [ ] Helm chart for self-hosted Kubernetes deployment
- [ ] Air-gapped mode: no external LLM calls (local model support)
- [ ] Private cloud deployment option for regulated industries

---

## Technology Decisions

| Decision | Choice | Reason |
|---|---|---|
| Backend language | Python (FastAPI) | LangChain ecosystem, fast development, strong AI library support |
| LLM orchestration | LangChain / LangGraph | Mature agent framework, MCP support, active community |
| LLM provider | Anthropic Claude (primary), OpenAI fallback | Claude's strong instruction-following and safety |
| Database | PostgreSQL | Reliable, supports pgvector for embeddings, single system |
| Vector search | pgvector | Avoids separate vector DB infrastructure in early phases |
| Auth | Auth0 (Phase 1), Keycloak option for self-hosted | Fast to integrate, enterprise SSO support |
| Policy engine | Custom Python (Phase 1–2), OPA integration (Phase 3) | Custom covers 80% of cases; OPA for complex enterprise needs |
| Workflow engine | Custom state machine (Phase 1–2), Temporal.io (Phase 3) | Temporal adds durability and replay for enterprise workflows |
| Frontend | Next.js (TypeScript) | SSR, good DX, wide ecosystem |
| Container | Docker + Kubernetes | Standard, cloud-portable |
| Secrets | HashiCorp Vault | Industry standard, supports dynamic secrets |

---

## Team Structure (suggested)

| Role | Phase 1 priority |
|---|---|
| Backend / AI Engineer | Core — builds orchestrator, RAG, connectors |
| Frontend Engineer | Builds chat UI and admin console |
| DevOps / Platform Engineer | CI/CD, Kubernetes, Vault, observability |
| Product / Design | Workflow definition, UX, customer feedback |
| Enterprise Sales / BD | Pilot customer sourcing (Month 2 onward) |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Connector integration complexity | High | Medium | Allocate 2x estimated time per connector; build SDK early |
| LLM hallucination in governed workflows | Medium | High | Citation requirement; source authority scoring; human approval for all high-risk actions |
| Enterprise sales cycle > 6 months | High | High | Target pilots with existing network; offer free 60-day pilot |
| Platform vendor (Microsoft/SAP) releases competing feature | Medium | High | Focus on cross-system governance they cannot do natively; deepen EU compliance angle |
| Regulatory compliance gaps | Low | Very High | Engage external compliance consultant by Month 6 |

---

## Definition of Done (per milestone)

A milestone is complete when:
1. All checklist items are implemented and passing tests
2. API endpoints documented and tested in Postman/Bruno
3. UI changes reviewed in staging
4. Audit log entries verified for all new actions
5. No critical or high-severity open bugs
6. Demo recorded or run live for stakeholder sign-off
