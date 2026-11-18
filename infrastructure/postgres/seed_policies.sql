-- AgentTrust demo policies — role-aware, sensitivity-driven
-- Logic: WHO is asking + WHAT sensitivity they're accessing → decision

INSERT INTO policies (id, tenant_id, name, description, rules, decision, approver_role, priority, is_active, version, created_at)
VALUES

-- ── Priority 110: Hard deny — no one may extract credentials ──────────────────
-- Even admins can't ask the AI to output passwords, API keys, or secrets.
(
  'pol-deny-credentials',
  'default',
  'Block Credential Extraction',
  'Block any question that tries to extract passwords, API keys, or secrets from documents.',
  '{
    "action": "rag_query",
    "conditions": [
      {"field": "topic", "operator": "in", "value": ["credentials", "passwords", "secrets", "api_keys"]}
    ]
  }',
  'deny',
  null,
  110,
  true,
  1,
  NOW()
),

-- ── Priority 100: Restricted docs → only admin/it_admin may read freely ───────
-- Everyone else gets an approval gate. Restricted = highest sensitivity.
(
  'pol-restricted-non-admin',
  'default',
  'Restricted Data — Non-Admin Approval',
  'Non-admin employees need manager sign-off to read restricted-sensitivity documents.',
  '{
    "action": "rag_query",
    "conditions": [
      {"field": "max_sensitivity", "operator": "equals", "value": "restricted"},
      {"source": "user", "field": "role", "operator": "not_in", "value": ["admin", "it_admin"]}
    ]
  }',
  'require_approval',
  'it_admin',
  100,
  true,
  1,
  NOW()
),

-- ── Priority 80: Confidential docs → support agents need approval ─────────────
-- Support agents have customer-facing access but shouldn''t freely browse
-- confidential internal docs (contracts, financials, HR data).
(
  'pol-confidential-support-agents',
  'default',
  'Confidential Data — Support Agent Restriction',
  'Support agents must get approval before accessing confidential documents.',
  '{
    "action": "rag_query",
    "conditions": [
      {"field": "max_sensitivity", "operator": "in", "value": ["confidential", "restricted"]},
      {"source": "user", "field": "role", "operator": "in", "value": ["support_agent"]}
    ]
  }',
  'require_approval',
  'finance_controller',
  80,
  true,
  1,
  NOW()
),

-- ── Priority 70: Confidential docs → procurement analysts need approval ────────
-- Procurement analysts may access supplier data but not financial/HR confidential docs.
(
  'pol-confidential-procurement',
  'default',
  'Confidential Data — Procurement Analyst Restriction',
  'Procurement analysts need approval for confidential documents outside their domain.',
  '{
    "action": "rag_query",
    "conditions": [
      {"field": "max_sensitivity", "operator": "equals", "value": "confidential"},
      {"source": "user", "field": "role", "operator": "in", "value": ["procurement_analyst"]}
    ]
  }',
  'require_approval',
  'procurement_manager',
  70,
  true,
  1,
  NOW()
)

ON CONFLICT (id) DO NOTHING;
