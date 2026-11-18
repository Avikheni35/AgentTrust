# AgentTrust — Business Workflows

## Overview

Each workflow describes a complete business process from user request to audited outcome. Every workflow runs through the AgentTrust control plane: identity check → RAG retrieval → policy evaluation → human approval (if required) → execution → audit receipt.

---

## WF-01: Invoice Exception Investigation and Approval

**Department:** Finance / Accounts Payable  
**Trigger:** Employee asks about a blocked or disputed supplier invoice  
**Agent:** `invoice-processing-agent`  
**Risk class:** Medium  
**Integration:** ERP, Document Management (SharePoint/OneDrive), Finance Policy

### Step-by-step flow

```
1. Employee submits request
   "Why is invoice INV-4821 blocked?"

2. Identity check
   AgentTrust authenticates the employee via SSO
   Loads user roles: [finance_analyst, procurement_viewer]

3. Intent classification
   Workflow: invoice_exception
   Required data: invoice record, purchase order, supplier contract, finance policy

4. Data retrieval (permission-filtered)
   → ERP: invoice INV-4821 (amount, status, supplier, PO reference)
   → ERP: purchase order PO-992 (approved amount, item match)
   → SharePoint: Supplier ABC contract v4 (payment terms, approved supplier)
   → RAG: Finance Policy v12 (approval thresholds)

5. Analysis
   Agent detects:
   - Invoice amount EUR 18,400 exceeds PO approved amount EUR 15,000
   - Amount exceeds finance policy approval threshold EUR 10,000
   - Policy requires finance controller approval

6. Answer generation
   AI generates explanation with citations from steps 4–5

7. Policy evaluation
   Action: approve_invoice
   Policy: invoice_approval_threshold
   Decision: require_approval (amount > EUR 10,000)

8. Approval task created
   Sent to: finance_controller role
   Contents: invoice details, PO comparison, contract excerpt, policy rule, risk level
   SLA: 4 hours

9. Finance controller reviews and decides
   Decision: approved
   Comment: "Variance explained by scope change, PO amendment incoming"

10. ERP update
    Agent calls ERP connector: approve_invoice(INV-4821)
    ERP marks invoice as approved and schedules payment

11. Notification
    Employee notified: "Invoice INV-4821 approved for payment"

12. Audit receipt created
    Contains: all steps, sources, policy result, approval, action, timestamps, hash
```

### Outcome metrics
- Invoice resolution time: target < 2 hours vs. previous 2–3 days
- Manual searches eliminated: ~6 per invoice
- 100% of invoices over threshold have approval record

---

## WF-02: Customer Support Resolution

**Department:** Customer Support  
**Trigger:** Customer submits a support request  
**Agent:** `support-agent`  
**Risk class:** Low–Medium  
**Integration:** CRM, Ticketing (Jira/ServiceNow), Documentation (Confluence), Email (M365)

### Step-by-step flow

```
1. Customer submits request
   "My order #ORD-8821 hasn't arrived and I was charged twice"

2. Ticket created in ticketing system
   AgentTrust receives webhook event

3. Identity and permission check
   Support agent authenticated and authorized for this customer account

4. Data retrieval (permission-filtered)
   → CRM: customer account, tier (enterprise), account manager
   → ERP/OMS: order ORD-8821 (status, shipping, billing)
   → Billing: payment records (detect duplicate charge)
   → Confluence: return and refund policy documentation
   → Prior tickets: similar cases for this customer in last 90 days

5. Analysis
   Agent detects:
   - Order shipped 3 days ago, tracking shows in transit
   - Duplicate charge confirmed: USD 149.00 charged twice on 2026-11-15
   - Refund policy: duplicate charges refunded within 2 business days

6. Response draft generation
   AI drafts:
   - Explanation of shipping status with tracking link
   - Acknowledgement of duplicate charge
   - Refund commitment per policy
   - Apology appropriate for enterprise-tier customer

7. Policy evaluation
   Action: issue_refund (USD 149.00)
   Policy: refund_auto_approval_limit (threshold: USD 500)
   Decision: allow (amount within limit)

   Action: send_customer_email (enterprise tier)
   Policy: enterprise_email_approval
   Decision: require_approval (account_manager must review)

8. Approval task created for account manager
   Contents: draft email, refund details, customer history

9. Account manager approves with minor edit to tone

10. Actions executed
    → Billing system: initiate refund USD 149.00
    → Email: send approved response to customer
    → CRM: log interaction and update case status
    → Ticket: mark as resolved

11. Audit receipt created
```

### Outcome metrics
- First response time: target < 30 minutes vs. previous 4–8 hours
- Manual system lookups eliminated: ~5 per ticket
- Refund SLA compliance tracked automatically

---

## WF-03: Procurement and Purchase Requisition

**Department:** Procurement / Supply Chain  
**Trigger:** ERP detects low inventory or procurement team initiates a replenishment request  
**Agent:** `procurement-agent`  
**Risk class:** Medium–High  
**Integration:** ERP, Document Management, Supplier Database, Approval Workflow

### Step-by-step flow

```
1. Trigger: low inventory alert
   ERP event: Product SKU-4421 stock < 50 units (reorder point: 100)
   Or: Procurement manager submits: "Reorder SKU-4421 from approved suppliers"

2. Identity check
   Procurement analyst authenticated
   Role: procurement_analyst — can prepare requisitions, cannot approve

3. Supplier and contract check
   → ERP: approved supplier list for SKU-4421
   → SharePoint: supplier contracts (lead times, pricing, minimum order)
   → ERP: historical purchase orders (last 3 orders, actual vs. lead time)
   → ERP: current stock levels across all warehouses

4. Analysis
   Agent compares:
   - Supplier A: EUR 12/unit, 10-day lead time, approved, contract valid
   - Supplier B: EUR 11/unit, 15-day lead time, approved, contract valid
   - Current stock: 42 units, expected depletion in 8 days
   Recommendation: Supplier A (faster lead time matches depletion timeline)

5. Purchase requisition prepared
   Supplier: Supplier A
   Quantity: 300 units
   Unit price: EUR 12.00
   Total: EUR 3,600
   Delivery: 10 days
   Justification: stock depletion within lead time window

6. Policy evaluation
   Action: create_purchase_order (EUR 3,600)
   Policy: po_approval_by_amount
   Decision: require_approval (amount > EUR 1,000, procurement_manager required)

7. Approval task created
   Sent to: procurement_manager
   Contents: requisition details, supplier comparison, stock analysis, citations

8. Procurement manager approves

9. Purchase order created in ERP
   Agent calls ERP connector: create_purchase_order(...)
   PO number assigned: PO-1041

10. Supplier notification (optional)
    Email drafted and sent to Supplier A with PO reference

11. Audit receipt created
```

### Outcome metrics
- Procurement cycle time: target < 4 hours vs. previous 2–3 days
- Stockout incidents: target reduction of 40%
- Policy-compliant POs: 100% with approval records

---

## WF-04: Employee Onboarding

**Department:** HR, IT, Management  
**Trigger:** HR creates a new employee record in HRIS  
**Agent:** `onboarding-agent`  
**Risk class:** Low  
**Integration:** HRIS, Identity Provider, Ticketing (Jira/ServiceNow), Email, Document Management

### Step-by-step flow

```
1. Trigger: new employee record created
   HRIS event: employee_created (name, role, department, start_date, manager)

2. Role-based access mapping
   Agent loads the access matrix for the new employee's role
   Determines required systems and permission levels
   Example for "Finance Analyst":
   - ERP: read-only finance module
   - SharePoint: finance team folder
   - Jira: finance project viewer
   - Slack: #finance channel

3. IT provisioning tasks created
   ServiceNow tickets automatically created:
   - Create Microsoft 365 account
   - Assign ERP access (finance_viewer role)
   - Provision laptop and ship to employee address
   - Set up Slack workspace access

4. Onboarding document package prepared
   → SharePoint: company handbook (latest version)
   → SharePoint: role-specific onboarding checklist
   → HR policy documents (tailored to country/region)
   AI generates a personalized welcome message

5. Notifications sent
   → Manager: "New team member starting on [date]. Onboarding tasks assigned."
   → Employee: Welcome email with first-day instructions and checklist
   → IT: Provisioning ticket with laptop delivery address

6. Progress tracking
   Agent monitors ticket completion status daily
   Day 1: check laptop delivered, accounts active
   Day 3: check onboarding checklist completion
   Day 7: escalate any incomplete tasks to manager

7. Escalation (if overdue)
   If IT ticket not resolved by start date - 2 days:
   Auto-escalate to IT manager with priority flag

8. Completion
   All tasks completed → onboarding record closed
   Audit receipt created with full task trail

9. Audit receipt created
```

### Outcome metrics
- Missed onboarding steps: target reduction of 90%
- Time to fully provisioned: target < 3 days vs. previous 5–7 days
- HR coordination emails: target reduction of 70%

---

## WF-05: Contract Renewal Monitoring

**Department:** Legal / Procurement  
**Trigger:** Scheduled scan 90 days before contract expiry dates  
**Agent:** `contract-monitoring-agent`  
**Risk class:** Low  
**Integration:** Document Management, CRM, ERP, Email

### Step-by-step flow

```
1. Scheduled trigger
   Agent runs daily: scan all contracts expiring within 90 days

2. Contract retrieval
   → SharePoint: all active supplier and customer contracts
   → ERP: contract values and payment history
   → CRM: customer relationship and strategic importance

3. Analysis per contract
   - Days until expiry
   - Contract value
   - Relationship history (payment, disputes, NPS if available)
   - Auto-renewal clause (yes/no)
   - Owner (account manager or procurement manager)

4. Prioritization
   High priority: > EUR 100,000 value, no auto-renewal, < 60 days
   Medium: EUR 10,000–100,000, < 90 days
   Low: < EUR 10,000 or auto-renewal enabled

5. Notifications sent
   Each contract owner receives:
   - Contract name, counterparty, expiry date
   - Recommended action (renew / renegotiate / review)
   - Link to contract document
   - Link to initiate renewal workflow

6. Renewal workflow initiated (optional)
   Owner clicks "Start renewal" → creates task in Jira/ServiceNow
   Contract manager assigned
   Deadline set: 30 days before expiry

7. Audit receipt created for each notification batch
```

---

## WF-06: Break-Glass Emergency Access

**Department:** IT Security / Operations  
**Trigger:** Critical incident requiring access beyond normal permissions  
**Agent:** N/A (human-initiated)  
**Risk class:** High  
**Integration:** Identity Service, Audit Service, Notification System

### Step-by-step flow

```
1. Break-glass access requested
   IT admin or on-call engineer submits:
   - Reason for access
   - System and resource required
   - Expected duration

2. Automatic notification
   CISO and IT manager notified immediately via email + Slack

3. Access granted (time-limited)
   Elevated permissions granted for specified duration (default: 2 hours)
   Every action during break-glass session is logged with elevated-access flag

4. Session monitoring
   All queries and actions monitored in real time
   Anomaly detection active

5. Access expiry
   Permissions automatically revoked at end of duration
   Extension requires new request

6. Post-access review
   Full session audit report generated
   Sent to CISO within 24 hours
   Review task created in ticketing system

7. Audit receipt created
   Marked as BREAK_GLASS — flagged in compliance dashboard
```

---

## Workflow State Machine

All workflows share the same state lifecycle:

```
CREATED
   │
   ▼
RUNNING (agent retrieving data and planning)
   │
   ├──► AWAITING_APPROVAL (policy requires human review)
   │         │
   │    APPROVED ──► EXECUTING
   │    REJECTED ──► CANCELLED
   │    ESCALATED ──► AWAITING_APPROVAL (next approver)
   │
   ├──► EXECUTING (agent calling connectors)
   │
   ├──► COMPLETED (success)
   │
   └──► FAILED (connector error, timeout, or unrecoverable error)
         │
         └──► RETRYING (up to 3 attempts)
```

Every state transition is recorded in the audit receipt.
