"""
Keycloak one-time setup for AgentTrust.

Creates:
  - Realm: agenttrust
  - Client: agenttrust-frontend  (public, browser app)
  - Client: agenttrust-backend   (confidential, API validation)
  - Protocol mappers: tenant_id, department, region added to tokens
  - Roles: admin, finance_analyst, finance_controller, support_agent,
           procurement_manager, procurement_analyst, hr_manager, it_admin
  - Test user: admin@agenttrust.io / Admin1234!

Run: python infrastructure/keycloak/setup.py
"""

import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import os

KEYCLOAK_URL   = "http://localhost:8080"
ADMIN_USER     = "admin"
ADMIN_PASSWORD = "admin"
REALM          = "agenttrust"
ENV_FILE       = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

# ── helpers ──────────────────────────────────────────────────────────────────

def request(method, path, token=None, data=None, expected=(200, 201, 204, 409)):
    url = f"{KEYCLOAK_URL}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read()
        if e.code in expected:
            try:    return e.code, json.loads(body)
            except: return e.code, {}
        print(f"  ✗ {method} {path} → HTTP {e.code}: {body[:200]}")
        sys.exit(1)


def get_admin_token():
    data = urllib.parse.urlencode({
        "client_id":  "admin-cli",
        "username":   ADMIN_USER,
        "password":   ADMIN_PASSWORD,
        "grant_type": "password",
    }).encode()
    req = urllib.request.Request(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


def wait_for_keycloak(max_wait=120):
    print("Waiting for Keycloak to be ready", end="", flush=True)
    for _ in range(max_wait // 3):
        try:
            # Dev mode has no /health/ready — use the master realm OIDC endpoint instead
            urllib.request.urlopen(
                f"{KEYCLOAK_URL}/realms/master/.well-known/openid-configuration", timeout=5
            )
            print(" ✓")
            return
        except Exception:
            print(".", end="", flush=True)
            time.sleep(3)
    print("\n✗ Keycloak did not start in time. Is it running on port 8080?")
    sys.exit(1)


def patch_env(key, value):
    """Replace KEY=... line in .env with new value."""
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE, "r") as f:
        lines = f.readlines()
    with open(ENV_FILE, "w") as f:
        for line in lines:
            if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                f.write(f"{key}={value}\n")
            else:
                f.write(line)


# ── setup steps ──────────────────────────────────────────────────────────────

def create_realm(token):
    print("  Creating realm 'agenttrust'...")
    status, _ = request("POST", "/admin/realms", token, {
        "realm":                 REALM,
        "displayName":           "AgentTrust",
        "enabled":               True,
        "registrationAllowed":   False,
        "loginWithEmailAllowed": True,
        "accessTokenLifespan":   3600,
        "ssoSessionMaxLifespan": 36000,
    })
    print(f"    {'already exists' if status == 409 else 'created'}")


def create_roles(token):
    roles = [
        "admin", "finance_analyst", "finance_controller",
        "support_agent", "procurement_manager", "procurement_analyst",
        "hr_manager", "it_admin",
    ]
    print("  Creating realm roles...")
    for role in roles:
        status, _ = request("POST", f"/admin/realms/{REALM}/roles", token, {"name": role})
        print(f"    {role}: {'exists' if status == 409 else 'created'}")


def _get_client_uuid(token, client_id):
    _, clients = request("GET", f"/admin/realms/{REALM}/clients?clientId={client_id}", token)
    if isinstance(clients, list) and clients:
        return clients[0]["id"]
    return None


def create_frontend_client(token):
    print("  Creating client 'agenttrust-frontend' (public)...")
    status, _ = request("POST", f"/admin/realms/{REALM}/clients", token, {
        "clientId":                  "agenttrust-frontend",
        "name":                      "AgentTrust Frontend",
        "enabled":                   True,
        "publicClient":              True,
        "standardFlowEnabled":       True,
        "directAccessGrantsEnabled": True,
        "redirectUris": [
            "http://localhost:3000/*",
            "http://localhost/*",
        ],
        "webOrigins": [
            "http://localhost:3000",
            "http://localhost",
        ],
        "attributes": {"pkce.code.challenge.method": "S256"},
    })
    print(f"    {'already exists' if status == 409 else 'created'}")


def create_backend_client(token):
    print("  Creating client 'agenttrust-backend' (confidential)...")
    status, _ = request("POST", f"/admin/realms/{REALM}/clients", token, {
        "clientId":               "agenttrust-backend",
        "name":                   "AgentTrust Backend",
        "enabled":                True,
        "publicClient":           False,
        "serviceAccountsEnabled": True,
        "standardFlowEnabled":    False,
        "attributes":             {},
    })
    print(f"    {'already exists' if status == 409 else 'created'}")

    # Get client secret
    uuid = _get_client_uuid(token, "agenttrust-backend")
    if not uuid:
        print("    ✗ Could not find backend client UUID")
        return None

    _, secret_data = request("GET", f"/admin/realms/{REALM}/clients/{uuid}/client-secret", token)
    secret = secret_data.get("value")
    print(f"    client secret: {secret}")
    return secret


def add_protocol_mappers(token):
    """Add tenant_id, department, region as custom token claims."""
    uuid = _get_client_uuid(token, "agenttrust-frontend")
    if not uuid:
        return

    print("  Adding protocol mappers (tenant_id, department, region)...")
    mappers = [
        {
            "name":           "tenant_id",
            "protocol":       "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {
                "user.attribute":         "tenant_id",
                "claim.name":             "tenant_id",
                "jsonType.label":         "String",
                "id.token.claim":         "true",
                "access.token.claim":     "true",
                "userinfo.token.claim":   "true",
                "multivalued":            "false",
                "aggregate.attrs":        "false",
            },
        },
        {
            "name":           "department",
            "protocol":       "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {
                "user.attribute":       "department",
                "claim.name":           "department",
                "jsonType.label":       "String",
                "id.token.claim":       "true",
                "access.token.claim":   "true",
                "userinfo.token.claim": "true",
            },
        },
        {
            "name":           "region",
            "protocol":       "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {
                "user.attribute":       "region",
                "claim.name":           "region",
                "jsonType.label":       "String",
                "id.token.claim":       "true",
                "access.token.claim":   "true",
                "userinfo.token.claim": "true",
            },
        },
    ]
    for m in mappers:
        status, _ = request(
            "POST",
            f"/admin/realms/{REALM}/clients/{uuid}/protocol-mappers/models",
            token, m,
        )
        print(f"    {m['name']}: {'exists' if status == 409 else 'created'}")


def create_test_user(token):
    print("  Creating test user admin@agenttrust.io...")
    status, _ = request("POST", f"/admin/realms/{REALM}/users", token, {
        "username":      "admin@agenttrust.io",
        "email":         "admin@agenttrust.io",
        "firstName":     "Admin",
        "lastName":      "User",
        "enabled":       True,
        "emailVerified": True,
        "attributes": {
            "tenant_id":  ["tenant_default"],
            "department": ["it"],
            "region":     ["EU"],
        },
        "credentials": [{
            "type":      "password",
            "value":     "Admin1234!",
            "temporary": False,
        }],
    })
    print(f"    {'already exists' if status == 409 else 'created'}")

    # Assign admin role
    _, users = request("GET", f"/admin/realms/{REALM}/users?username=admin@agenttrust.io", token)
    if not isinstance(users, list) or not users:
        return
    user_id = users[0]["id"]

    _, role_rep = request("GET", f"/admin/realms/{REALM}/roles/admin", token)
    request("POST", f"/admin/realms/{REALM}/users/{user_id}/role-mappings/realm",
            token, [role_rep])
    print("    assigned role: admin")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n━━━ AgentTrust Keycloak Setup ━━━\n")

    wait_for_keycloak()

    print("Getting admin token...")
    token = get_admin_token()
    print("  ✓\n")

    print("Step 1 — Realm")
    create_realm(token)

    # Re-auth after realm creation (token still valid)
    print("\nStep 2 — Roles")
    create_roles(token)

    print("\nStep 3 — Clients")
    create_frontend_client(token)
    secret = create_backend_client(token)

    print("\nStep 4 — Protocol mappers")
    add_protocol_mappers(token)

    print("\nStep 5 — Test user")
    create_test_user(token)

    print("\nStep 6 — Patching .env")
    if secret:
        patch_env("KEYCLOAK_CLIENT_SECRET", secret)
        print(f"  KEYCLOAK_CLIENT_SECRET={secret}")
    print("  ✓")

    print(f"""
━━━ Setup complete ━━━

Realm:    {KEYCLOAK_URL}/realms/{REALM}
Admin UI: {KEYCLOAK_URL}/admin/{REALM}/console

Test login
  URL:      http://localhost:3000
  Email:    admin@agenttrust.io
  Password: Admin1234!

API docs:  http://localhost:8000/docs
""")


if __name__ == "__main__":
    main()
