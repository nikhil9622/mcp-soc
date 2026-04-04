"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import {
  fetchTeamMembers,
  inviteTeamMember,
  updateMemberRole,
  removeMember,
  fetchDevices,
} from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { Users, Monitor, Mail, Shield, Trash2, RefreshCw } from "lucide-react";

const ROLES = [
  { value: "soc_manager",    label: "SOC Manager"     },
  { value: "soc_analyst_l1", label: "SOC Analyst L1"  },
  { value: "soc_analyst_l2", label: "SOC Analyst L2"  },
  { value: "read_only",      label: "Read Only"        },
];

function roleBadge(role: string) {
  const map: Record<string, { label: string; color: string; bg: string; border: string }> = {
    soc_manager:    { label: "Manager",  color: "#9D78F6", bg: "rgba(157,120,246,0.12)", border: "rgba(157,120,246,0.3)"  },
    soc_analyst_l1: { label: "L1",       color: "#38BDF8", bg: "rgba(56,189,248,0.12)",  border: "rgba(56,189,248,0.3)"   },
    soc_analyst_l2: { label: "L2",       color: "#3FD68A", bg: "rgba(63,214,138,0.12)",  border: "rgba(63,214,138,0.3)"   },
    read_only:      { label: "Readonly", color: "#8B949E", bg: "rgba(139,148,158,0.12)", border: "rgba(139,148,158,0.3)"  },
  };
  const cfg = map[role] ?? map["read_only"];
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
      fontFamily: "JetBrains Mono, monospace",
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`,
    }}>
      {cfg.label}
    </span>
  );
}

function statusDot(status: string) {
  if (status === "active")  return <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "#3FD68A", boxShadow: "0 0 6px rgba(63,214,138,0.5)", flexShrink: 0 }} />Active</span>;
  if (status === "pending") return <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "#E3B341", flexShrink: 0 }} />Pending</span>;
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "#484F58", flexShrink: 0 }} />Removed</span>;
}

function isOnline(lastSeen: string | null | undefined): boolean {
  if (!lastSeen) return false;
  return (Date.now() - new Date(lastSeen).getTime()) < 2 * 60 * 1000;
}

export default function TeamPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  // Invite form
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole]   = useState("soc_analyst_l1");
  const [inviting, setInviting]       = useState(false);
  const [inviteMsg, setInviteMsg]     = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Members
  const [members, setMembers]         = useState<any[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [membersError, setMembersError]     = useState<string | null>(null);

  // Devices
  const [devices, setDevices]         = useState<any[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [devicesError, setDevicesError]     = useState<string | null>(null);

  // Role change pending map: userId -> role
  const [pendingRole, setPendingRole] = useState<Record<string, string>>({});

  if (loading) return null;
  if (!user) { router.push("/login"); return null; }

  async function loadMembers() {
    setMembersLoading(true);
    setMembersError(null);
    try {
      const data = await fetchTeamMembers();
      setMembers(Array.isArray(data) ? data : (data.members ?? []));
    } catch (e: any) {
      setMembersError(e.message ?? "Failed to load members");
    } finally {
      setMembersLoading(false);
    }
  }

  async function loadDevices() {
    setDevicesLoading(true);
    setDevicesError(null);
    try {
      const data = await fetchDevices();
      setDevices(Array.isArray(data) ? data : (data.devices ?? []));
    } catch (e: any) {
      setDevicesError(e.message ?? "Failed to load devices");
    } finally {
      setDevicesLoading(false);
    }
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    loadMembers();
    loadDevices();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleInvite() {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setInviteMsg(null);
    try {
      await inviteTeamMember(inviteEmail.trim(), inviteRole);
      setInviteMsg({ type: "ok", text: `Invite sent to ${inviteEmail.trim()}` });
      setInviteEmail("");
      loadMembers();
    } catch (e: any) {
      setInviteMsg({ type: "err", text: e.message ?? "Invite failed" });
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(userId: string, newRole: string) {
    setPendingRole(r => ({ ...r, [userId]: newRole }));
    try {
      await updateMemberRole(userId, newRole);
      loadMembers();
    } catch {
      // revert
      setPendingRole(r => { const c = { ...r }; delete c[userId]; return c; });
    }
  }

  async function handleRemove(userId: string) {
    if (!confirm("Remove this member?")) return;
    try {
      await removeMember(userId);
      loadMembers();
    } catch (e: any) {
      alert(e.message ?? "Remove failed");
    }
  }

  const inputStyle: React.CSSProperties = {
    background: "var(--bg)", border: "1px solid var(--border-mid)", borderRadius: 6,
    color: "var(--text)", fontFamily: "Inter, sans-serif", fontSize: 13,
    padding: "9px 12px", outline: "none", transition: "border-color 0.15s",
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle, cursor: "pointer", appearance: "none" as const,
  };

  const thStyle: React.CSSProperties = {
    fontSize: 9, fontFamily: "JetBrains Mono, monospace", fontWeight: 700,
    color: "var(--text-faint)", letterSpacing: "0.1em", textTransform: "uppercase",
    padding: "10px 16px",
  };

  const tdStyle: React.CSSProperties = {
    fontSize: 12, color: "var(--text-dim)", padding: "11px 16px", verticalAlign: "middle",
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Users size={20} style={{ color: "var(--green)" }} />
            <div>
              <h1 style={{ fontSize: 18, fontWeight: 800, color: "var(--white)", margin: 0 }}>Team Management</h1>
              <p style={{ fontSize: 10, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>
                Manage your SOC team members and device access
              </p>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: 28, display: "flex", flexDirection: "column", gap: 24 }}>

          {/* ── Section 1: Invite Member ──────────────────────────────── */}
          <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
            <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border)", background: "rgba(255,255,255,0.02)", display: "flex", alignItems: "center", gap: 8 }}>
              <Mail size={13} style={{ color: "var(--green)" }} />
              <span style={{ fontSize: 10, fontWeight: 800, color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.08em" }}>
                INVITE MEMBER
              </span>
            </div>
            <div style={{ padding: 18 }}>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
                <div style={{ flex: "1 1 260px", display: "flex", flexDirection: "column", gap: 6 }}>
                  <label style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>
                    EMAIL ADDRESS
                  </label>
                  <input
                    type="email"
                    placeholder="analyst@your-org.com"
                    value={inviteEmail}
                    onChange={e => setInviteEmail(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleInvite()}
                    style={{ ...inputStyle, width: "100%" }}
                    onFocus={e => (e.currentTarget.style.borderColor = "rgba(63,214,138,0.5)")}
                    onBlur={e => (e.currentTarget.style.borderColor = "var(--border-mid)")}
                  />
                </div>
                <div style={{ flex: "0 1 200px", display: "flex", flexDirection: "column", gap: 6 }}>
                  <label style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>
                    ROLE
                  </label>
                  <select
                    value={inviteRole}
                    onChange={e => setInviteRole(e.target.value)}
                    style={{ ...selectStyle, width: "100%" }}
                  >
                    {ROLES.map(r => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleInvite}
                  disabled={inviting || !inviteEmail.trim()}
                  style={{
                    padding: "9px 20px", borderRadius: 6, fontSize: 12, fontWeight: 700,
                    background: inviting || !inviteEmail.trim() ? "rgba(63,214,138,0.08)" : "rgba(63,214,138,0.15)",
                    border: "1px solid rgba(63,214,138,0.35)",
                    color: inviting || !inviteEmail.trim() ? "var(--text-faint)" : "var(--green)",
                    cursor: inviting || !inviteEmail.trim() ? "not-allowed" : "pointer",
                    transition: "all 0.15s", whiteSpace: "nowrap", flexShrink: 0,
                    alignSelf: "flex-end",
                  }}
                >
                  {inviting ? "Sending…" : "Send Invite"}
                </button>
              </div>
              {inviteMsg && (
                <div style={{
                  marginTop: 12, padding: "8px 12px", borderRadius: 6, fontSize: 12,
                  background: inviteMsg.type === "ok" ? "rgba(63,214,138,0.08)" : "rgba(255,71,87,0.08)",
                  border: `1px solid ${inviteMsg.type === "ok" ? "rgba(63,214,138,0.25)" : "rgba(255,71,87,0.25)"}`,
                  color: inviteMsg.type === "ok" ? "var(--green)" : "#FF4757",
                  fontFamily: "JetBrains Mono, monospace",
                }}>
                  {inviteMsg.text}
                </div>
              )}
            </div>
          </div>

          {/* ── Section 2: Team Members ───────────────────────────────── */}
          <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
            <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border)", background: "rgba(255,255,255,0.02)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Shield size={13} style={{ color: "var(--cyan)" }} />
                <span style={{ fontSize: 10, fontWeight: 800, color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.08em" }}>
                  TEAM MEMBERS
                </span>
                {!membersLoading && (
                  <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginLeft: 4 }}>
                    {members.length} total
                  </span>
                )}
              </div>
              <button
                onClick={loadMembers}
                style={{ padding: "5px 10px", borderRadius: 6, background: "transparent", border: "1px solid var(--border)", color: "var(--text-mute)", cursor: "pointer", display: "flex", alignItems: "center", gap: 5, fontSize: 10 }}
              >
                <RefreshCw size={10} /> Refresh
              </button>
            </div>

            {membersLoading ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                Loading members…
              </div>
            ) : membersError ? (
              <div style={{ padding: 24, textAlign: "center", color: "#FF4757", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                {membersError}
              </div>
            ) : members.length === 0 ? (
              <div style={{ padding: 48, textAlign: "center" }}>
                <Users size={32} style={{ color: "var(--text-faint)", margin: "0 auto 12px" }} />
                <div style={{ color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                  No team members yet
                </div>
                <div style={{ color: "var(--text-faint)", fontSize: 11, marginTop: 4 }}>
                  Invite someone above to get started
                </div>
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <th style={{ ...thStyle, textAlign: "left" }}>Member</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Role</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Status</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Devices</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Joined</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m: any, i: number) => {
                      const initials = (m.email ?? "?")[0].toUpperCase();
                      const currentRole = pendingRole[m.id ?? m._id] ?? m.role;
                      const userId = m.id ?? m._id;
                      return (
                        <tr
                          key={userId ?? i}
                          style={{
                            borderBottom: i < members.length - 1 ? "1px solid rgba(48,54,61,0.5)" : "none",
                            transition: "background 0.1s",
                          }}
                          onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
                          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                        >
                          {/* Avatar + Email */}
                          <td style={tdStyle}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <div style={{
                                width: 30, height: 30, borderRadius: 8,
                                background: "var(--green-dim)", border: "1px solid rgba(63,214,138,0.25)",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                fontSize: 12, fontWeight: 800, color: "var(--green)",
                                fontFamily: "JetBrains Mono, monospace", flexShrink: 0,
                              }}>
                                {initials}
                              </div>
                              <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{m.email}</span>
                            </div>
                          </td>
                          {/* Role Badge */}
                          <td style={tdStyle}>{roleBadge(currentRole)}</td>
                          {/* Status */}
                          <td style={{ ...tdStyle, fontSize: 11, color: "var(--text-mute)" }}>
                            {statusDot(m.status ?? "active")}
                          </td>
                          {/* Devices */}
                          <td style={{ ...tdStyle, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
                            {m.device_count ?? 0}
                          </td>
                          {/* Joined */}
                          <td style={{ ...tdStyle, fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--text-faint)" }}>
                            {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "—"}
                          </td>
                          {/* Actions */}
                          <td style={tdStyle}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <select
                                value={currentRole}
                                onChange={e => handleRoleChange(userId, e.target.value)}
                                style={{ ...selectStyle, fontSize: 11, padding: "5px 8px", width: "auto" }}
                              >
                                {ROLES.map(r => (
                                  <option key={r.value} value={r.value}>{r.label}</option>
                                ))}
                              </select>
                              <button
                                onClick={() => handleRemove(userId)}
                                title="Remove member"
                                style={{
                                  padding: "5px 8px", borderRadius: 5, border: "1px solid rgba(255,71,87,0.25)",
                                  background: "rgba(255,71,87,0.06)", color: "#FF4757",
                                  cursor: "pointer", display: "flex", alignItems: "center",
                                  transition: "all 0.15s",
                                }}
                                onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,71,87,0.15)")}
                                onMouseLeave={e => (e.currentTarget.style.background = "rgba(255,71,87,0.06)")}
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Section 3: Connected Devices ─────────────────────────── */}
          <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
            <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border)", background: "rgba(255,255,255,0.02)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Monitor size={13} style={{ color: "var(--violet)" }} />
                <span style={{ fontSize: 10, fontWeight: 800, color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.08em" }}>
                  CONNECTED DEVICES
                </span>
                {!devicesLoading && (
                  <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginLeft: 4 }}>
                    {devices.length} registered · {devices.filter(d => isOnline(d.last_seen)).length} online
                  </span>
                )}
              </div>
              <button
                onClick={loadDevices}
                style={{ padding: "5px 10px", borderRadius: 6, background: "transparent", border: "1px solid var(--border)", color: "var(--text-mute)", cursor: "pointer", display: "flex", alignItems: "center", gap: 5, fontSize: 10 }}
              >
                <RefreshCw size={10} /> Refresh
              </button>
            </div>

            {devicesLoading ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                Loading devices…
              </div>
            ) : devicesError ? (
              <div style={{ padding: 24, textAlign: "center", color: "#FF4757", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                {devicesError}
              </div>
            ) : devices.length === 0 ? (
              <div style={{ padding: 48, textAlign: "center" }}>
                <Monitor size={32} style={{ color: "var(--text-faint)", margin: "0 auto 12px" }} />
                <div style={{ color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                  No devices connected yet
                </div>
                <div style={{ color: "var(--text-faint)", fontSize: 11, marginTop: 4 }}>
                  Install the agent on a host to start ingesting logs
                </div>
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <th style={{ ...thStyle, textAlign: "left" }}>Device</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>OS</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>IP Address</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Status</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Events Sent</th>
                      <th style={{ ...thStyle, textAlign: "left" }}>Last Seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((d: any, i: number) => {
                      const online = isOnline(d.last_seen);
                      return (
                        <tr
                          key={d.id ?? d._id ?? i}
                          style={{
                            borderBottom: i < devices.length - 1 ? "1px solid rgba(48,54,61,0.5)" : "none",
                            transition: "background 0.1s",
                          }}
                          onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
                          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                        >
                          {/* Device name + icon */}
                          <td style={tdStyle}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <div style={{
                                width: 28, height: 28, borderRadius: 6,
                                background: online ? "rgba(63,214,138,0.1)" : "rgba(139,148,158,0.08)",
                                border: `1px solid ${online ? "rgba(63,214,138,0.2)" : "rgba(139,148,158,0.15)"}`,
                                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                              }}>
                                <Monitor size={13} style={{ color: online ? "var(--green)" : "var(--text-faint)" }} />
                              </div>
                              <span style={{ color: "var(--text-dim)", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
                                {d.hostname ?? d.name ?? d.device_id ?? "unknown"}
                              </span>
                            </div>
                          </td>
                          {/* OS */}
                          <td style={{ ...tdStyle, fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--text-mute)" }}>
                            {d.os ?? "—"}
                          </td>
                          {/* IP */}
                          <td style={{ ...tdStyle, fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "var(--cyan)" }}>
                            {d.ip ?? d.ip_address ?? "—"}
                          </td>
                          {/* Status */}
                          <td style={tdStyle}>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: online ? "var(--green)" : "var(--text-faint)" }}>
                              <span style={{
                                width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                                background: online ? "#3FD68A" : "#484F58",
                                boxShadow: online ? "0 0 6px rgba(63,214,138,0.5)" : "none",
                              }} />
                              {online ? "Online" : "Offline"}
                            </span>
                          </td>
                          {/* Events Sent */}
                          <td style={{ ...tdStyle, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
                            {(d.events_sent ?? d.event_count ?? 0).toLocaleString()}
                          </td>
                          {/* Last Seen */}
                          <td style={{ ...tdStyle, fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--text-faint)" }}>
                            {d.last_seen ? new Date(d.last_seen).toLocaleString() : "Never"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
