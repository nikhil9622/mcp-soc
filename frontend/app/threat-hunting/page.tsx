"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { huntSearch, fetchSavedHunts, saveHunt, deleteSavedHunt } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { Search, Save, Trash2, Play, Clock, User, Globe, Zap, BarChart2, ChevronDown, ChevronUp } from "lucide-react";

const SOURCE_COLOR: Record<string, string> = {
  cloudtrail: "#f97316",
  syslog:     "#22d3ee",
  app:        "#818cf8",
};

function MiniBar({ label, count, max }: { label: string; count: number; max: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
      <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)", width: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.05)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${(count / max) * 100}%`, background: "var(--cyan)", borderRadius: 3, transition: "width 0.4s" }} />
      </div>
      <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--cyan)", width: 30, textAlign: "right", flexShrink: 0 }}>{count}</span>
    </div>
  );
}

function Timeline({ data }: { data: { hour: string; count: number }[] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 48, padding: "0 4px" }}>
      {data.map(d => (
        <div key={d.hour} title={`${d.hour}: ${d.count} events`} style={{ flex: 1, minWidth: 3, background: "var(--cyan)", borderRadius: "2px 2px 0 0", height: `${Math.max(4, (d.count / max) * 100)}%`, opacity: 0.7, transition: "height 0.3s" }} />
      ))}
    </div>
  );
}

export default function ThreatHuntingPage() {
  const { user } = useAuth();
  const router   = useRouter();

  const [query, setQuery] = useState({ user: "", ip: "", action: "", source: "", free_text: "", hours: 24 });
  const [results, setResults] = useState<any>(null);
  const [running, setRunning]   = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saving, setSaving]     = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: saved, mutate: mutateSaved } = useSWR(user ? "saved-hunts" : null, fetchSavedHunts);

  if (!user) { router.push("/login"); return null; }

  const handleRun = async () => {
    setRunning(true);
    try {
      const q = { ...query, hours: Number(query.hours) || 24 };
      const r = await huntSearch(q);
      setResults(r);
    } finally { setRunning(false); }
  };

  const handleSave = async () => {
    if (!saveName.trim()) return;
    setSaving(true);
    try { await saveHunt(saveName, query); setSaveName(""); mutateSaved(); }
    finally { setSaving(false); }
  };

  const loadSaved = (h: any) => {
    setQuery({ user: "", ip: "", action: "", source: "", free_text: "", hours: 24, ...h.query });
    setResults(null);
  };

  const inputStyle = {
    padding: "8px 12px", borderRadius: 7, background: "var(--bg-deep)",
    border: "1px solid var(--border)", color: "var(--white)", fontSize: 12,
    outline: "none", width: "100%",
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Saved hunts sidebar */}
        <div style={{ width: 220, borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", background: "var(--bg)", flexShrink: 0 }}>
          <div style={{ padding: "16px 14px 10px", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", fontWeight: 700, marginBottom: 8 }}>SAVED HUNTS</div>
            <div style={{ display: "flex", gap: 6 }}>
              <input value={saveName} onChange={e => setSaveName(e.target.value)} placeholder="Save current…" style={{ ...inputStyle, fontSize: 11 }} />
              <button onClick={handleSave} disabled={saving || !saveName.trim()} style={{ padding: "6px 10px", borderRadius: 6, background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.25)", color: "var(--cyan)", cursor: "pointer" }}>
                <Save size={11} />
              </button>
            </div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 10 }}>
            {(saved ?? []).length === 0 ? (
              <p style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", textAlign: "center", marginTop: 20 }}>No saved hunts</p>
            ) : (
              (saved ?? []).map((h: any) => (
                <div key={h.hunt_id} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <button onClick={() => loadSaved(h)} style={{ flex: 1, textAlign: "left", padding: "7px 10px", borderRadius: 6, background: "var(--bg-deep)", border: "1px solid var(--border)", color: "var(--text-dim)", fontSize: 11, cursor: "pointer", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {h.name}
                  </button>
                  <button onClick={async () => { await deleteSavedHunt(h.hunt_id); mutateSaved(); }} style={{ padding: "5px", borderRadius: 5, background: "none", border: "none", color: "var(--text-faint)", cursor: "pointer" }}>
                    <Trash2 size={10} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Main area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Header + query builder */}
          <div style={{ padding: "20px 24px 16px", flexShrink: 0, borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <Search size={18} style={{ color: "var(--cyan)" }} />
              <div>
                <h1 style={{ fontSize: 18, fontWeight: 800, color: "var(--white)", margin: 0 }}>Threat Hunting</h1>
                <p style={{ fontSize: 11, color: "var(--text-mute)", margin: 0, fontFamily: "JetBrains Mono, monospace" }}>Proactive search across all ingested events</p>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 2fr 100px", gap: 8, marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 4 }}>USER</div>
                <input value={query.user} onChange={e => setQuery(q => ({ ...q, user: e.target.value }))} placeholder="any user…" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 4 }}>IP</div>
                <input value={query.ip} onChange={e => setQuery(q => ({ ...q, ip: e.target.value }))} placeholder="any IP…" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 4 }}>ACTION</div>
                <input value={query.action} onChange={e => setQuery(q => ({ ...q, action: e.target.value }))} placeholder="any action…" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 4 }}>SOURCE</div>
                <select value={query.source} onChange={e => setQuery(q => ({ ...q, source: e.target.value }))} style={{ ...inputStyle, cursor: "pointer" }}>
                  <option value="">All</option>
                  <option value="cloudtrail">CloudTrail</option>
                  <option value="syslog">Syslog</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 4 }}>FREE TEXT SEARCH</div>
                <input value={query.free_text} onChange={e => setQuery(q => ({ ...q, free_text: e.target.value }))} onKeyDown={e => e.key === "Enter" && handleRun()} placeholder="Search across action, raw log, user…" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 4 }}>HOURS</div>
                <select value={query.hours} onChange={e => setQuery(q => ({ ...q, hours: Number(e.target.value) }))} style={{ ...inputStyle, cursor: "pointer" }}>
                  {[1, 6, 24, 48, 168, 720].map(h => <option key={h} value={h}>{h}h</option>)}
                </select>
              </div>
            </div>

            <button
              onClick={handleRun}
              disabled={running}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 20px", borderRadius: 8, background: running ? "var(--bg)" : "rgba(34,211,238,0.12)", border: "1px solid rgba(34,211,238,0.3)", color: "var(--cyan)", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
            >
              <Play size={13} /> {running ? "Hunting…" : "Run Hunt"}
            </button>
          </div>

          {/* Results */}
          <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
            {results && (
              <>
                {/* Summary row */}
                <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
                  <div style={{ padding: "8px 16px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: "var(--cyan)" }}>{results.total}</div>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>EVENTS FOUND</div>
                  </div>

                  {/* Timeline */}
                  <div style={{ flex: 1, padding: "10px 14px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 6 }}>TIMELINE</div>
                    <Timeline data={results.timeline} />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
                  {/* Top actions */}
                  <div style={{ padding: 14, borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 10, fontWeight: 700 }}>TOP ACTIONS</div>
                    {results.top_actions.map((a: any) => (
                      <MiniBar key={a.action} label={a.action} count={a.count} max={results.top_actions[0]?.count ?? 1} />
                    ))}
                  </div>
                  {/* Top users */}
                  <div style={{ padding: 14, borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 10, fontWeight: 700 }}>TOP USERS</div>
                    {results.top_users.map((u: any) => (
                      <MiniBar key={u.user} label={u.user} count={u.count} max={results.top_users[0]?.count ?? 1} />
                    ))}
                  </div>
                </div>

                {/* Events table */}
                <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
                  <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "grid", gridTemplateColumns: "160px 100px 120px 80px 1fr", gap: 8 }}>
                    {["TIMESTAMP", "USER", "IP", "SOURCE", "ACTION"].map(h => (
                      <span key={h} style={{ fontSize: 9, fontFamily: "JetBrains Mono, monospace", color: "var(--text-faint)", fontWeight: 700 }}>{h}</span>
                    ))}
                  </div>
                  {results.events.slice(0, 100).map((e: any, i: number) => {
                    const key = e.event_id ?? i;
                    const open = expanded === key;
                    return (
                      <div key={key} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                        <div
                          onClick={() => setExpanded(open ? null : key)}
                          style={{ padding: "9px 16px", display: "grid", gridTemplateColumns: "160px 100px 120px 80px 1fr", gap: 8, alignItems: "center", cursor: "pointer", background: open ? "rgba(34,211,238,0.04)" : "transparent" }}
                          onMouseEnter={e2 => (e2.currentTarget.style.background = "rgba(255,255,255,0.02)")}
                          onMouseLeave={e2 => (e2.currentTarget.style.background = open ? "rgba(34,211,238,0.04)" : "transparent")}
                        >
                          <span style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)" }}>
                            {e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}
                          </span>
                          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--white)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.user ?? "—"}</span>
                          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--cyan)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.ip ?? "—"}</span>
                          <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, fontFamily: "JetBrains Mono, monospace", fontWeight: 700, background: (SOURCE_COLOR[e.source] ?? "#8b949e") + "20", border: `1px solid ${(SOURCE_COLOR[e.source] ?? "#8b949e")}40`, color: SOURCE_COLOR[e.source] ?? "#8b949e" }}>
                            {e.source ?? "—"}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                            <span style={{ fontSize: 11, color: "var(--text-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.action ?? "—"}</span>
                            {open ? <ChevronUp size={11} style={{ color: "var(--text-faint)", flexShrink: 0 }} /> : <ChevronDown size={11} style={{ color: "var(--text-faint)", flexShrink: 0 }} />}
                          </div>
                        </div>
                        {open && (
                          <div style={{ padding: "10px 16px 14px", background: "rgba(34,211,238,0.03)" }}>
                            <pre style={{ fontSize: 10, fontFamily: "JetBrains Mono, monospace", color: "var(--text-mute)", whiteSpace: "pre-wrap", wordBreak: "break-all", margin: 0, maxHeight: 200, overflowY: "auto" }}>
                              {JSON.stringify(e.metadata, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {results.total > 100 && (
                    <div style={{ padding: "10px 16px", textAlign: "center", fontSize: 11, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                      Showing 100 of {results.total} results — refine your query to narrow down
                    </div>
                  )}
                </div>
              </>
            )}

            {!results && !running && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300, gap: 12 }}>
                <Search size={40} style={{ color: "var(--text-faint)", opacity: 0.3 }} />
                <p style={{ color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>Set filters above and click Run Hunt</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
