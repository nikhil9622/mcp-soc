"use client";
import { useState } from "react";
import { Copy, Check, ExternalLink } from "lucide-react";

export function VectorConfigCard({ config }: { config: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(config);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="sp-card" style={{ padding: 16 }}>
      <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
        <span className="mono-label" style={{ fontSize: 9 }}>VECTOR CONFIG</span>
        <button
          onClick={handleCopy}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "3px 10px",
            borderRadius: 3,
            fontSize: 11,
            fontFamily: "JetBrains Mono, monospace",
            background: copied ? "rgba(74,193,142,0.1)" : "var(--card)",
            color: copied ? "var(--green)" : "var(--text-mute)",
            border: `1px solid ${copied ? "rgba(74,193,142,0.3)" : "var(--border)"}`,
            cursor: "pointer",
          }}
        >
          {copied ? <Check size={10} /> : <Copy size={10} />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      <pre
        style={{
          fontFamily: "JetBrains Mono, monospace",
          fontSize: 11,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 4,
          padding: "12px 14px",
          color: "var(--text-dim)",
          overflowX: "auto",
          lineHeight: 1.6,
          whiteSpace: "pre",
        }}
      >
        {config}
      </pre>

      <p style={{ marginTop: 10, fontSize: 11, color: "var(--text-mute)" }}>
        Install{" "}
        <a
          href="https://vector.dev"
          target="_blank"
          rel="noopener"
          style={{ color: "var(--green)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 3 }}
        >
          Vector <ExternalLink size={10} />
        </a>{" "}
        on your device and use this config to stream logs to MCP SOC.
      </p>
    </div>
  );
}
