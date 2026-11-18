"use client";

import Keycloak from "keycloak-js";
import { createContext, useContext, useEffect, useRef, useState } from "react";

interface AuthContextValue {
  token: string | null;
  userEmail: string | null;
  roles: string[];
  tenantId: string | null;
  logout: () => void;
  ready: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  token: null,
  userEmail: null,
  roles: [],
  tenantId: null,
  logout: () => {},
  ready: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const kc = useRef<Keycloak | null>(null);
  const initialized = useRef(false);  // guard against React strict-mode double-init

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const keycloak = new Keycloak({
      url: process.env.NEXT_PUBLIC_KEYCLOAK_URL || "http://localhost:8080",
      realm: process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "agenttrust",
      clientId: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "agenttrust-frontend",
    });
    kc.current = keycloak;

    keycloak
      .init({
        onLoad: "check-sso",
        checkLoginIframe: false,
        silentCheckSsoFallback: false,
      })
      .then((authenticated) => {
        if (authenticated && keycloak.token) {
          setToken(keycloak.token);
          setUserEmail(keycloak.tokenParsed?.email ?? null);
          setRoles(keycloak.tokenParsed?.realm_access?.roles ?? []);
          setTenantId(keycloak.tokenParsed?.tenant_id ?? "default");
          setReady(true);
        } else {
          // Not authenticated — redirect to login once
          keycloak.login();
        }
      })
      .catch(() => {
        // Can't reach Keycloak — show ready so the error surfaces in the UI
        setReady(true);
      });

    // Refresh token 60 s before expiry
    const interval = setInterval(async () => {
      if (kc.current) {
        const refreshed = await kc.current.updateToken(60).catch(() => false);
        if (refreshed && kc.current.token) setToken(kc.current.token);
      }
    }, 30_000);

    return () => clearInterval(interval);
  }, []);

  const logout = () => kc.current?.logout();

  return (
    <AuthContext.Provider value={{ token, userEmail, roles, tenantId, logout, ready }}>
      {ready ? children : <LoadingScreen />}
    </AuthContext.Provider>
  );
}

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-900">
      <div className="text-center">
        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        <p className="text-slate-400 text-sm">Connecting to AgentTrust…</p>
      </div>
    </div>
  );
}

export const useAuth = () => useContext(AuthContext);
