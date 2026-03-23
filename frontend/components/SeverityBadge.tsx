type Severity = "critical" | "high" | "medium" | "low" | string;

const SEV: Record<string, { cls: string; dot: string }> = {
  critical: { cls: "badge badge-crit", dot: "var(--crit)" },
  high:     { cls: "badge badge-high", dot: "var(--high)" },
  medium:   { cls: "badge badge-med",  dot: "var(--med)"  },
  low:      { cls: "badge badge-low",  dot: "var(--low)"  },
};

export default function SeverityBadge({
  severity,
  showDot = true,
}: {
  severity: Severity;
  showDot?: boolean;
}) {
  const key = severity?.toLowerCase();
  const s   = SEV[key] ?? SEV.low;

  return (
    <span className={s.cls}>
      {showDot && (
        <span
          style={{
            width: 5, height: 5, borderRadius: "50%",
            background: s.dot,
            boxShadow: key === "critical" ? `0 0 6px ${s.dot}` : "none",
            display: "inline-block", flexShrink: 0,
          }}
        />
      )}
      {severity?.toUpperCase()}
    </span>
  );
}
