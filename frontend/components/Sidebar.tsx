"use client";

import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { signOut } from "firebase/auth";
import { auth } from "@/lib/firebase";
import {
  LayoutDashboard,
  GitMerge,
  Server,
  LogOut,
  ChevronRight,
  ShieldAlert,
  Bell,
  Cpu,
  Database,
  Activity,
  Zap,
  WifiOff,
  GitBranch,
  Shield,
  Briefcase,
  Search,
  ClipboardCheck,
} from "lucide-react";

const NAV = [
  { icon: LayoutDashboard, label: "Dashboard",       href: "/dashboard",        section: "main" },
  { icon: Bell,            label: "Alerts",           href: "/alerts",           section: "main" },
  { icon: GitMerge,        label: "Incidents",        href: "/incidents",        section: "main" },
  { icon: WifiOff,         label: "Isolation",        href: "/isolation",        section: "main" },
  { icon: GitBranch,       label: "Attack Graph",     href: "/attack-graph",     section: "main" },
  { icon: Shield,          label: "ATT&CK Coverage",  href: "/attack-heatmap",   section: "main" },
  { icon: Briefcase,       label: "Cases",             href: "/cases",            section: "main" },
  { icon: Search,          label: "Threat Hunting",    href: "/threat-hunting",   section: "main" },
  { icon: Activity,        label: "UEBA",              href: "/ueba",             section: "main" },
  { icon: ClipboardCheck,  label: "Compliance",        href: "/compliance",       section: "main" },
  { icon: Server,          label: "Connect Device",   href: "/connect",          section: "config" },
];

const PIPELINE = [
  { label: "Ingestion",     key: "ingestion",     status: "active"  },
  { label: "Detection",     key: "detection",     status: "active"  },
  { label: "Correlation",   key: "correlation",   status: "active"  },
  { label: "Investigation", key: "investigation", status: "active"  },
  { label: "Alerting",      key: "alerting",      status: "active"  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();
  const { user } = useAuth();

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);

  return (
    <aside className="sidebar fixed top-0 bottom-0 left-0 flex flex-col z-40" style={{ width: 240 }}>

      {/* ── Logo ─────────────────────────────────────────────────────── */}
      <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-3">
          {/* Hexagon logo mark */}
          <div
            style={{
              width: 38, height: 38,
              background: "var(--green-dim)",
              border: "1px solid rgba(63,214,138,0.3)",
              borderRadius: 8,
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
              boxShadow: "0 0 20px rgba(63,214,138,0.1)",
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2L21 7V17L12 22L3 17V7L12 2Z"
                stroke="#3FD68A" strokeWidth="1.5" fill="none"
              />
              <path
                d="M12 8V16M8 12H16"
                stroke="#3FD68A" strokeWidth="1.5" strokeLinecap="round"
              />
              <circle cx="12" cy="12" r="2" fill="#3FD68A" opacity="0.6" />
            </svg>
          </div>
          <div>
            <div style={{ color: "var(--white)", fontSize: 15, fontWeight: 800, letterSpacing: "-0.01em" }}>
              MCP SOC
            </div>
            <div className="mono-label" style={{ fontSize: 8, color: "var(--green)", letterSpacing: "0.15em" }}>
              THREAT DETECTION
            </div>
          </div>
        </div>
      </div>

      {/* ── Live status bar ───────────────────────────────────────────── */}
      <div
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid var(--border)",
          background: "rgba(63,214,138,0.03)",
          display: "flex", alignItems: "center", gap: 8,
        }}
      >
        <div className="live-dot" />
        <span className="mono-label" style={{ color: "var(--green)", fontSize: 9 }}>
          ALL SYSTEMS OPERATIONAL
        </span>
      </div>

      {/* ── Navigation ───────────────────────────────────────────────── */}
      <nav style={{ flex: 1, minHeight: 0, padding: "12px 10px", overflowY: "scroll", display: "flex", flexDirection: "column", gap: 2, scrollbarWidth: "thin", scrollbarColor: "var(--border-mid) transparent" }}>

        <div className="mono-label" style={{ padding: "0 6px", marginBottom: 6, fontSize: 9, color: "var(--text-faint)" }}>
          SECURITY OPS
        </div>

        {NAV.filter(n => n.section === "main").map(({ icon: Icon, label, href }) => {
          const active = isActive(href);
          return (
            <button
              key={href}
              onClick={() => router.push(href)}
              className={`nav-item ${active ? "active" : ""}`}
            >
              <Icon size={15} />
              <span style={{ flex: 1 }}>{label}</span>
              {active && <ChevronRight size={12} style={{ opacity: 0.5 }} />}
            </button>
          );
        })}

        <div style={{ height: 16 }} />
        <div className="mono-label" style={{ padding: "0 6px", marginBottom: 6, fontSize: 9, color: "var(--text-faint)" }}>
          INFRASTRUCTURE
        </div>

        {NAV.filter(n => n.section === "config").map(({ icon: Icon, label, href }) => {
          const active = isActive(href);
          return (
            <button
              key={href}
              onClick={() => router.push(href)}
              className={`nav-item ${active ? "active" : ""}`}
            >
              <Icon size={15} />
              <span style={{ flex: 1 }}>{label}</span>
              {active && <ChevronRight size={12} style={{ opacity: 0.5 }} />}
            </button>
          );
        })}

        {/* ── Pipeline Health ─────────────────────────────────────────── */}
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div className="flex items-center gap-2 mb-10px" style={{ marginBottom: 10 }}>
              <Activity size={11} style={{ color: "var(--green)" }} />
              <span className="mono-label" style={{ fontSize: 9, color: "var(--green)" }}>PIPELINE STATUS</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {PIPELINE.map(({ label, key, status }) => (
                <div key={key} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`pipeline-dot ${status}`} />
                    <span style={{ fontSize: 11, color: "var(--text-mute)", fontFamily: "JetBrains Mono, monospace" }}>
                      {label}
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: 9,
                      fontFamily: "JetBrains Mono, monospace",
                      color: status === "active" ? "var(--green)" : status === "error" ? "var(--crit)" : "var(--text-faint)",
                    }}
                  >
                    {status === "active" ? "OK" : status === "error" ? "ERR" : "—"}
                  </span>
                </div>
              ))}
            </div>

            {/* Pipeline flow line */}
            <div
              style={{
                marginTop: 10,
                height: 2,
                background: "linear-gradient(90deg, var(--green) 0%, var(--cyan) 50%, transparent 100%)",
                borderRadius: 1,
                opacity: 0.4,
              }}
            />
          </div>
        </div>

        {/* ── Storage indicators ──────────────────────────────────────── */}
        <div style={{ marginTop: 10 }}>
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div className="flex items-center gap-2" style={{ marginBottom: 10 }}>
              <Database size={11} style={{ color: "var(--text-mute)" }} />
              <span className="mono-label" style={{ fontSize: 9 }}>DATA STORES</span>
            </div>
            {[
              { label: "Redis Streams", pct: 42, color: "var(--cyan)" },
              { label: "MongoDB",       pct: 28, color: "var(--green)" },
              { label: "S3 Storage",    pct: 15, color: "var(--violet)" },
            ].map(({ label, pct, color }) => (
              <div key={label} style={{ marginBottom: 8 }}>
                <div className="flex items-center justify-between" style={{ marginBottom: 4 }}>
                  <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>{label}</span>
                  <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color }}>{pct}%</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${pct}%`, background: color, opacity: 0.8 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </nav>

      {/* ── User info ────────────────────────────────────────────────── */}
      <div style={{ padding: 10, borderTop: "1px solid var(--border)" }}>
        <div
          style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "8px 10px", marginBottom: 6,
            background: "var(--bg)", borderRadius: 8,
            border: "1px solid var(--border)",
          }}
        >
          <div
            style={{
              width: 30, height: 30, borderRadius: 8,
              background: "var(--green-dim)",
              border: "1px solid rgba(63,214,138,0.25)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 800,
              color: "var(--green)",
              fontFamily: "JetBrains Mono, monospace",
              flexShrink: 0,
            }}
          >
            {user?.email?.[0]?.toUpperCase() ?? "A"}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, color: "var(--text-dim)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user?.email ?? "analyst@soc.io"}
            </div>
            <div className="mono-label" style={{ fontSize: 8, color: "var(--green)", marginTop: 1 }}>
              SOC ANALYST · L2
            </div>
          </div>
        </div>

        <button
          onClick={() => signOut(auth).then(() => router.push("/login"))}
          className="nav-item w-full"
          style={{ color: "var(--text-mute)" }}
        >
          <LogOut size={13} style={{ color: "var(--crit)" }} />
          <span style={{ color: "var(--crit)", fontSize: 12, fontWeight: 500 }}>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
