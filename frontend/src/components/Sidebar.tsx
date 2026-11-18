"use client";

import clsx from "clsx";
import {
  ClipboardList,
  FileText,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const nav = [
  { href: "/chat",      label: "Ask AI",    icon: MessageSquare },
  { href: "/approvals", label: "Approvals", icon: ClipboardList },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/audit",     label: "Audit Log", icon: LayoutDashboard },
];

const UPLOAD_ROLES = new Set(["admin", "it_admin", "hr_manager", "finance_controller", "procurement_manager"]);

export function Sidebar() {
  const pathname = usePathname();
  const { userEmail, roles, logout } = useAuth();
  const canUpload = roles.some((r) => UPLOAD_ROLES.has(r));

  const visibleNav = nav.filter(({ href }) => href !== "/documents" || canUpload);

  return (
    <aside className="flex h-screen w-56 flex-col bg-slate-900 text-slate-100 shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-700">
        <ShieldCheck className="h-6 w-6 text-blue-400" />
        <span className="font-semibold text-white tracking-tight">AgentTrust</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-3">
        {visibleNav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname.startsWith(href)
                ? "bg-blue-600 text-white"
                : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-slate-700 p-4">
        <div className="mb-3 truncate text-xs text-slate-400">{userEmail}</div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
