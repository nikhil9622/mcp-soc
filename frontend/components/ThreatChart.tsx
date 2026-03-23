"use client";

/** SVG area chart — zero dependencies, Splunk/Cortex XSIAM-style */

interface Point { x: number; y: number; }

function makePath(points: Point[], width: number, height: number): string {
  if (!points.length) return "";
  const xs = points.map(p => p.x);
  const ys = points.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 4;
  const norm = (v: number, lo: number, hi: number, size: number) =>
    hi === lo ? size / 2 : pad + ((v - lo) / (hi - lo)) * (size - pad * 2);

  const coords = points.map(p => ({
    x: norm(p.x, minX, maxX, width),
    y: height - norm(p.y, minY, maxY, height),
  }));

  // Smooth curve
  const d = coords.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x},${p.y}`;
    const prev = coords[i - 1];
    const cpx = (prev.x + p.x) / 2;
    return `${acc} C ${cpx},${prev.y} ${cpx},${p.y} ${p.x},${p.y}`;
  }, "");

  return d;
}

function makeArea(points: Point[], width: number, height: number): string {
  const line = makePath(points, width, height);
  if (!line) return "";
  const xs = points.map(p => p.x);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const pad = 4;
  const normX = (v: number) => maxX === minX ? width / 2 : pad + ((v - minX) / (maxX - minX)) * (width - pad * 2);
  const firstX = normX(points[0].x);
  const lastX  = normX(points[points.length - 1].x);
  return `${line} L ${lastX},${height} L ${firstX},${height} Z`;
}

export interface ThreatChartProps {
  data: { label: string; value: number }[];
  color?: string;
  height?: number;
  showLabels?: boolean;
  title?: string;
  subtitle?: string;
}

export default function ThreatChart({
  data,
  color = "#3FD68A",
  height = 80,
  showLabels = true,
  title,
  subtitle,
}: ThreatChartProps) {
  const width = 100; // viewBox units, scales with CSS
  const points: Point[] = data.map((d, i) => ({ x: i, y: d.value }));
  const linePath = makePath(points, width, height);
  const areaPath = makeArea(points, width, height);

  const maxVal = Math.max(...data.map(d => d.value), 1);
  const total  = data.reduce((s, d) => s + d.value, 0);
  const avg    = data.length ? Math.round(total / data.length) : 0;

  return (
    <div>
      {(title || subtitle) && (
        <div className="flex items-end justify-between" style={{ marginBottom: 10 }}>
          <div>
            {title    && <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)" }}>{title}</div>}
            {subtitle && <div className="mono-label" style={{ marginTop: 2 }}>{subtitle}</div>}
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color }}>
              {maxVal.toLocaleString()} peak
            </div>
            <div className="mono-label" style={{ fontSize: 9, marginTop: 1 }}>
              avg {avg}/hr
            </div>
          </div>
        </div>
      )}

      <div style={{ position: "relative", width: "100%", height }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
          style={{ width: "100%", height: "100%", display: "block" }}
        >
          <defs>
            <linearGradient id={`grad-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={color} stopOpacity="0.35" />
              <stop offset="100%" stopColor={color} stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0.25, 0.5, 0.75].map(frac => (
            <line
              key={frac}
              x1="0" y1={height * frac}
              x2={width} y2={height * frac}
              stroke="rgba(255,255,255,0.04)"
              strokeWidth="0.5"
            />
          ))}

          {/* Area fill */}
          {areaPath && (
            <path
              d={areaPath}
              fill={`url(#grad-${color.replace("#","")})`}
            />
          )}

          {/* Line */}
          {linePath && (
            <path
              d={linePath}
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              style={{ filter: `drop-shadow(0 0 4px ${color}60)` }}
            />
          )}

          {/* Dots on each point */}
          {points.map((p, i) => {
            const ys = data.map(d => d.value);
            const minY = Math.min(...ys), maxY = Math.max(...ys);
            const pad = 4;
            const cx = pad + (p.x / (points.length - 1 || 1)) * (width - pad * 2);
            const cy = height - (pad + ((p.y - minY) / (maxY - minY || 1)) * (height - pad * 2));
            return (
              <circle key={i} cx={cx} cy={cy} r="1.5" fill={color} opacity="0.8" />
            );
          })}
        </svg>

        {/* X-axis labels */}
        {showLabels && data.length <= 12 && (
          <div
            style={{
              position: "absolute", bottom: -16, left: 0, right: 0,
              display: "flex", justifyContent: "space-between",
            }}
          >
            {data.map((d, i) => (
              (i === 0 || i === data.length - 1 || i === Math.floor(data.length / 2)) && (
                <span
                  key={i}
                  className="mono-label"
                  style={{ fontSize: 8, position: "absolute", left: `${(i / (data.length - 1)) * 100}%`, transform: "translateX(-50%)" }}
                >
                  {d.label}
                </span>
              )
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
