"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  signInWithPopup, GoogleAuthProvider,
  signInWithEmailAndPassword, createUserWithEmailAndPassword,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { Mail, Lock, Eye, EyeOff, AlertCircle, Shield } from "lucide-react";

const FEATURES = [
  { label: "5 Sigma detection rules",            color: "var(--green)" },
  { label: "Redis Streams event pipeline",        color: "var(--green)" },
  { label: "Claude AI investigation engine",      color: "var(--cyan)"  },
  { label: "MITRE ATT&CK auto-mapping",           color: "var(--violet)"},
  { label: "NetworkX correlation graph",          color: "var(--violet)"},
  { label: "TP / FP analyst feedback loop",       color: "var(--high)"  },
];

const STATS = [
  { value: "< 2s",  label: "Detection latency" },
  { value: "99.9%", label: "Pipeline uptime"   },
  { value: "5",     label: "Sigma rules"        },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [mode, setMode]         = useState<"login" | "register">("login");
  const [tick, setTick]         = useState(0);

  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 2000);
    return () => clearInterval(t);
  }, []);

  const handleGoogle = async () => {
    setLoading(true); setError("");
    try { await signInWithPopup(auth, new GoogleAuthProvider()); router.push("/dashboard"); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleEmail = async () => {
    if (!email || !password) { setError("Email and password required."); return; }
    setLoading(true); setError("");
    try {
      if (mode === "login") await signInWithEmailAndPassword(auth, email, password);
      else                  await createUserWithEmailAndPassword(auth, email, password);
      router.push("/dashboard");
    } catch (e: any) {
      const code = e.code ?? "";
      if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found")
        setError("Invalid email or password.");
      else if (code === "auth/email-already-in-use")
        setError("An account with this email already exists.");
      else if (code === "auth/too-many-requests")
        setError("Too many attempts. Please wait a moment and try again.");
      else if (code === "auth/weak-password")
        setError("Password must be at least 6 characters.");
      else if (code === "auth/invalid-email")
        setError("Please enter a valid email address.");
      else
        setError(e.message?.replace("Firebase: ", "").replace(/ \(auth\/[^)]+\)\.?/, "") || "Authentication failed.");
    }
    finally { setLoading(false); }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        background: "var(--bg)",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* ═══════════════════════════════════════════════════════════
          LEFT PANEL — Brand / hero
          ═══════════════════════════════════════════════════════════ */}
      <div
        className="grid-bg"
        style={{
          width: "55%",
          display: "none",
          flexDirection: "column",
          position: "relative",
          overflow: "hidden",
          background: "var(--surface)",
          borderRight: "1px solid var(--border)",
        }}
        // Show on lg screens via media query override below
      >
        {/* Radial glow in corner */}
        <div style={{
          position: "absolute", top: -100, left: -100,
          width: 400, height: 400, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(63,214,138,0.08) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", bottom: -80, right: -60,
          width: 300, height: 300, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(56,189,248,0.06) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />

        {/* Scan line animation */}
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: "2px",
          background: "linear-gradient(90deg, transparent, rgba(63,214,138,0.6), transparent)",
          animation: "scanline 4s linear infinite",
          pointerEvents: "none",
        }} />

        <div style={{ position: "relative", zIndex: 10, flex: 1, padding: 52, display: "flex", flexDirection: "column" }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 60 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: "var(--green-dim)",
              border: "1px solid rgba(63,214,138,0.3)",
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 0 30px rgba(63,214,138,0.15)",
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L21 7V17L12 22L3 17V7L12 2Z" stroke="#3FD68A" strokeWidth="1.5" fill="none" />
                <path d="M12 8V16M8 12H16" stroke="#3FD68A" strokeWidth="1.5" strokeLinecap="round" />
                <circle cx="12" cy="12" r="2.5" fill="#3FD68A" opacity="0.5" />
              </svg>
            </div>
            <div>
              <div style={{ color: "var(--white)", fontSize: 18, fontWeight: 900, letterSpacing: "-0.02em" }}>MCP SOC</div>
              <div className="mono-label" style={{ fontSize: 8, color: "var(--green)", letterSpacing: "0.2em", marginTop: 1 }}>
                THREAT DETECTION PLATFORM
              </div>
            </div>
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ marginBottom: 6 }}>
              <span className="mono-label" style={{ color: "var(--green)", fontSize: 10 }}>ENTERPRISE SOC</span>
            </div>
            <h2 style={{ fontSize: 42, fontWeight: 900, color: "var(--white)", lineHeight: 1.1, marginBottom: 20, letterSpacing: "-0.03em" }}>
              Detect. Correlate.
              <br />
              <span style={{ color: "var(--green)" }} className="glow-green">Respond.</span>
            </h2>
            <p style={{ color: "var(--text-mute)", fontSize: 14, lineHeight: 1.7, maxWidth: 380, marginBottom: 36 }}>
              AI-powered multi-tenant Security Operations Center with MITRE ATT&CK
              correlation, Sigma detection rules, and automated incident investigation.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 40 }}>
              {FEATURES.map(({ label, color }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 5, height: 5, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}`, flexShrink: 0 }} />
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "var(--text-dim)" }}>
                    {label}
                  </span>
                </div>
              ))}
            </div>

            {/* Stats row */}
            <div style={{ display: "flex", gap: 0, borderRadius: 10, overflow: "hidden", border: "1px solid var(--border)" }}>
              {STATS.map(({ value, label }, i) => (
                <div
                  key={label}
                  style={{
                    flex: 1, padding: "14px 12px", textAlign: "center",
                    background: "var(--card)",
                    borderRight: i < STATS.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <div style={{ fontSize: 18, fontWeight: 800, color: "var(--green)", fontFamily: "JetBrains Mono, monospace", lineHeight: 1 }}>
                    {value}
                  </div>
                  <div className="mono-label" style={{ fontSize: 8, marginTop: 5 }}>{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Status bar */}
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "10px 14px", borderRadius: 8,
            background: "var(--card)", border: "1px solid var(--border)",
          }}>
            <div className="live-dot" />
            <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "var(--text-mute)" }}>
              ALL SYSTEMS OPERATIONAL
            </span>
            <span style={{ marginLeft: "auto", fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--green)" }}>
              {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════
          RIGHT PANEL — Auth form
          ═══════════════════════════════════════════════════════════ */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 32 }}>
        <div style={{ width: "100%", maxWidth: 380 }}>

          {/* Mobile logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 36 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: "var(--green-dim)", border: "1px solid rgba(63,214,138,0.3)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Shield size={16} style={{ color: "var(--green)" }} />
            </div>
            <div>
              <div style={{ color: "var(--white)", fontSize: 16, fontWeight: 800 }}>MCP SOC</div>
              <div className="mono-label" style={{ fontSize: 8, color: "var(--green)" }}>DETECTION PLATFORM</div>
            </div>
          </div>

          {/* Heading */}
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: "var(--white)", marginBottom: 6, letterSpacing: "-0.01em" }}>
              {mode === "login" ? "Analyst Sign In" : "Create Account"}
            </h2>
            <p style={{ fontSize: 13, color: "var(--text-mute)" }}>
              {mode === "login"
                ? "Access the threat detection platform"
                : "Register to start monitoring your infrastructure"}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 8,
              marginBottom: 18, padding: "10px 14px", borderRadius: 8,
              background: "var(--crit-dim)", border: "1px solid var(--crit-mid)",
              color: "var(--crit)", fontSize: 12,
            }}>
              <AlertCircle size={13} style={{ marginTop: 1, flexShrink: 0 }} />
              {error}
            </div>
          )}

          {/* Email */}
          <div style={{ marginBottom: 14 }}>
            <label className="mono-label" style={{ display: "block", marginBottom: 7, fontSize: 8 }}>
              EMAIL ADDRESS
            </label>
            <div style={{ position: "relative" }}>
              <Mail size={13} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-mute)" }} />
              <input
                className="sp-input"
                type="email"
                placeholder="analyst@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleEmail()}
                style={{ paddingLeft: 36 }}
              />
            </div>
          </div>

          {/* Password */}
          <div style={{ marginBottom: 22 }}>
            <label className="mono-label" style={{ display: "block", marginBottom: 7, fontSize: 8 }}>
              PASSWORD
            </label>
            <div style={{ position: "relative" }}>
              <Lock size={13} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-mute)" }} />
              <input
                className="sp-input"
                type={showPw ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleEmail()}
                style={{ paddingLeft: 36, paddingRight: 38 }}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-mute)", background: "none", border: "none", cursor: "pointer" }}
              >
                {showPw ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
          </div>

          {/* Primary CTA */}
          <button
            className="btn-primary"
            onClick={handleEmail}
            disabled={loading}
            style={{ width: "100%", marginBottom: 12 }}
          >
            {loading ? "Authenticating…" : mode === "login" ? "Sign In to SOC Platform" : "Create Account"}
          </button>

          {/* Divider */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            <span className="mono-label" style={{ fontSize: 8 }}>OR</span>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          </div>

          {/* Google */}
          <button
            onClick={handleGoogle}
            disabled={loading}
            className="btn-outline"
            style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 22 }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </button>

          {/* Toggle mode */}
          <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-mute)" }}>
            {mode === "login" ? "No account? " : "Already registered? "}
            <button
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
              style={{ color: "var(--green)", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontSize: 12, fontFamily: "Inter, sans-serif" }}
            >
              {mode === "login" ? "Sign up free" : "Sign in"}
            </button>
          </p>

          {/* Security note */}
          <div style={{ marginTop: 24, padding: "10px 14px", borderRadius: 8, background: "var(--card)", border: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
            <Shield size={12} style={{ color: "var(--green)", flexShrink: 0 }} />
            <span className="mono-label" style={{ fontSize: 8, color: "var(--text-mute)" }}>
              SECURED · MULTI-TENANT · SOC2 READY
            </span>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes scanline {
          0%   { transform: translateY(-4px); opacity: 0; }
          5%   { opacity: 1; }
          95%  { opacity: 1; }
          100% { transform: translateY(100vh); opacity: 0; }
        }
        @media (min-width: 1024px) {
          div[style*="55%"] { display: flex !important; }
        }
      `}</style>
    </div>
  );
}
