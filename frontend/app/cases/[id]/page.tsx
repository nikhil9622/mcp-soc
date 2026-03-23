"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { useAuth } from "@/contexts/AuthContext";
import { fetchCase, updateCase, addCaseNote, addCaseTask, toggleCaseTask, deleteCase } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import { ArrowLeft, Briefcase, Plus, Check, Trash2, MessageSquare, ListTodo, Link, Send } from "lucide-react";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "#ff4d4d", high: "#ff8c00", medium: "#f5c518", low: "#22d3ee",
};
const STATUS_COLOR: Record<string, string> = {
  open: "#3fd68a", in_progress: "#f97316", resolved: "#818cf8", closed: "#8b949e",
};

export default function CaseDetailPage() {
  const { user }  = useAuth();
  const { id }    = useParams<{ id: string }>();
  const router    = useRouter();
  const [note, setNote]     = useState("");
  const [task, setTask]     = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [addingTask, setAddingTask] = useState(false);

  const { data: c, mutate } = useSWR(user ? `case-${id}` : null, () => fetchCase(id));

  if (!user) { router.push("/login"); return null; }
  if (!c) return (
    <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg-deep)", color: "var(--text-mute)", fontFamily: "JetBrains Mono, monospace" }}>
      Loading…
    </div>
  );

  const pColor = PRIORITY_COLOR[c.priority] ?? "#8b949e";
  const sColor = STATUS_COLOR[c.status] ?? "#8b949e";
  const tasksDone = (c.tasks ?? []).filter((t: any) => t.done).length;

  const handleNoteSubmit = async () => {
    if (!note.trim()) return;
    setAddingNote(true);
    try { await addCaseNote(id, note); setNote(""); mutate(); }
    finally { setAddingNote(false); }
  };

  const handleTaskSubmit = async () => {
    if (!task.trim()) return;
    setAddingTask(true);
    try { await addCaseTask(id, task); setTask(""); mutate(); }
    finally { setAddingTask(false); }
  };

  const handleStatusChange = async (status: string) => {
    await updateCase(id, { status });
    mutate();
  };

  const handleDelete = async () => {
    if (!confirm("Delete this case?")) return;
    await deleteCase(id);
    router.push("/cases");
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-deep)", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Header */}
        <div style={{ padding: "20px 28px 16px", flexShrink: 0, borderBottom: "1px solid var(--border)" }}>
          <button onClick={() => router.push("/cases")} style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", color: "var(--text-mute)", fontSize: 12, cursor: "pointer", marginBottom: 12 }}>
            <ArrowLeft size={13} /> Back to Cases
          </button>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 8, padding: "2px 8px", borderRadius: 4, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", background: sColor + "20", border: `1px solid ${sColor}40`, color: sColor }}>
                  {c.status.replace("_", " ").toUpperCase()}
                </span>
                <span style={{ fontSize: 8, padding: "2px 8px", borderRadius: 4, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", background: pColor + "15", border: `1px solid ${pColor}30`, color: pColor }}>
                  {c.priority.toUpperCase()}
                </span>
              </div>
              <h1 style={{ fontSize: 22, fontWeight: 800, color: "var(--white)", margin: 0 }}>{c.title}</h1>
              {c.description && <p style={{ fontSize: 13, color: "var(--text-mute)", marginTop: 6 }}>{c.description}</p>}
            </div>

            {/* Status changer */}
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              {["open", "in_progress", "resolved", "closed"].map(s => (
                <button
                  key={s}
                  onClick={() => handleStatusChange(s)}
                  style={{
                    padding: "6px 12px", borderRadius: 6, fontSize: 10, fontWeight: 700,
                    fontFamily: "JetBrains Mono, monospace", cursor: "pointer",
                    background: c.status === s ? STATUS_COLOR[s] + "25" : "var(--bg)",
                    border: `1px solid ${c.status === s ? STATUS_COLOR[s] + "60" : "var(--border)"}`,
                    color: c.status === s ? STATUS_COLOR[s] : "var(--text-faint)",
                  }}
                >
                  {s.replace("_", " ")}
                </button>
              ))}
              <button onClick={handleDelete} style={{ padding: "6px 10px", borderRadius: 6, background: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "#ff4d4d", cursor: "pointer" }}>
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: 28, display: "grid", gridTemplateColumns: "1fr 340px", gap: 24 }}>

          {/* Left: Notes + Tasks */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

            {/* Tasks */}
            <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10, padding: 18 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                <ListTodo size={14} style={{ color: "#f97316" }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>Tasks</span>
                <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginLeft: "auto" }}>
                  {tasksDone}/{(c.tasks ?? []).length} done
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
                {(c.tasks ?? []).map((t: any) => (
                  <div
                    key={t.task_id}
                    onClick={() => { toggleCaseTask(id, t.task_id); mutate(); }}
                    style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 6, background: t.done ? "rgba(63,214,138,0.05)" : "var(--bg-deep)", border: "1px solid var(--border)", cursor: "pointer" }}
                  >
                    <div style={{ width: 16, height: 16, borderRadius: 4, border: `2px solid ${t.done ? "#3fd68a" : "var(--border)"}`, background: t.done ? "#3fd68a20" : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      {t.done && <Check size={10} style={{ color: "#3fd68a" }} />}
                    </div>
                    <span style={{ fontSize: 13, color: t.done ? "var(--text-faint)" : "var(--white)", textDecoration: t.done ? "line-through" : "none" }}>{t.title}</span>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <input
                  value={task}
                  onChange={e => setTask(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleTaskSubmit()}
                  placeholder="Add a task…"
                  style={{ flex: 1, padding: "8px 12px", borderRadius: 6, background: "var(--bg-deep)", border: "1px solid var(--border)", color: "var(--white)", fontSize: 12, outline: "none" }}
                />
                <button onClick={handleTaskSubmit} disabled={addingTask || !task.trim()} style={{ padding: "8px 14px", borderRadius: 6, background: "rgba(249,115,22,0.12)", border: "1px solid rgba(249,115,22,0.3)", color: "#f97316", cursor: "pointer" }}>
                  <Plus size={13} />
                </button>
              </div>
            </div>

            {/* Notes */}
            <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10, padding: 18 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                <MessageSquare size={14} style={{ color: "#818cf8" }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: "var(--white)" }}>Notes</span>
                <span style={{ fontSize: 10, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginLeft: "auto" }}>
                  {(c.notes ?? []).length} entries
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
                {(c.notes ?? []).slice().reverse().map((n: any) => (
                  <div key={n.note_id} style={{ padding: 12, borderRadius: 8, background: "var(--bg-deep)", border: "1px solid var(--border)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontSize: 10, fontWeight: 700, color: "#818cf8", fontFamily: "JetBrains Mono, monospace" }}>@{n.author}</span>
                      <span style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>
                        {new Date(n.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p style={{ fontSize: 13, color: "var(--text)", margin: 0, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{n.body}</p>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <textarea
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  placeholder="Add a note…"
                  rows={2}
                  style={{ flex: 1, padding: "8px 12px", borderRadius: 6, background: "var(--bg-deep)", border: "1px solid var(--border)", color: "var(--white)", fontSize: 12, outline: "none", resize: "none", fontFamily: "inherit" }}
                />
                <button onClick={handleNoteSubmit} disabled={addingNote || !note.trim()} style={{ padding: "8px 14px", borderRadius: 6, background: "rgba(129,140,248,0.12)", border: "1px solid rgba(129,140,248,0.3)", color: "#818cf8", cursor: "pointer", alignSelf: "flex-end" }}>
                  <Send size={13} />
                </button>
              </div>
            </div>
          </div>

          {/* Right: Metadata */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 14, fontWeight: 700 }}>CASE METADATA</div>
              {[
                ["Case ID",   c.case_id?.slice(0, 8) + "…"],
                ["Priority",  c.priority],
                ["Status",    c.status.replace("_", " ")],
                ["Assignee",  c.assignee || "Unassigned"],
                ["Created",   new Date(c.created_at).toLocaleDateString()],
                ["Updated",   new Date(c.updated_at).toLocaleDateString()],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <span style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>{k}</span>
                  <span style={{ fontSize: 11, color: "var(--white)", fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>{v}</span>
                </div>
              ))}
            </div>

            {/* Linked incidents */}
            <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 12 }}>
                <Link size={12} style={{ color: "var(--cyan)" }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: "var(--white)" }}>Linked Incidents</span>
              </div>
              {(c.incident_ids ?? []).length === 0 ? (
                <p style={{ fontSize: 11, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace" }}>None linked</p>
              ) : (
                (c.incident_ids ?? []).map((iid: string) => (
                  <div
                    key={iid}
                    onClick={() => router.push(`/incidents/${iid}`)}
                    style={{ padding: "6px 10px", borderRadius: 6, background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.15)", cursor: "pointer", marginBottom: 6, fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--cyan)" }}
                  >
                    {iid.slice(0, 18)}…
                  </div>
                ))
              )}
            </div>

            {/* Tags */}
            {(c.tags ?? []).length > 0 && (
              <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
                <div style={{ fontSize: 9, color: "var(--text-faint)", fontFamily: "JetBrains Mono, monospace", marginBottom: 10, fontWeight: 700 }}>TAGS</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {c.tags.map((tag: string) => (
                    <span key={tag} style={{ fontSize: 10, padding: "3px 8px", borderRadius: 4, background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)", color: "var(--text-mute)", fontFamily: "JetBrains Mono, monospace" }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
