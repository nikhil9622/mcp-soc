export type Severity = "critical" | "high" | "medium" | "low";
export type Feedback = "pending" | "tp" | "fp";
export type Source = "cloudtrail" | "syslog" | "app";

export interface Alert {
  alert_id: string;
  tenant_id: string;
  incident_id: string;
  title: string;
  severity: Severity;
  affected_entity: string;
  source_ip: string;
  location: string;
  source_type: Source;
  incident_summary: string;
  recommended_action: string;
  sent_at: string;
  feedback: Feedback;
}

export interface IncidentSummary {
  summary: string;
  what_happened: string;
  why_suspicious: string;
  impact: string;
  recommended_action: string;
  severity: Severity;
}

export interface Detection {
  detection_id: string;
  rule_name: string;
  mitre_technique_id: string;
  mitre_tactic: string;
  severity: Severity;
  risk_score: number;
  detected_at: string;
}

export interface Incident {
  incident_id: string;
  tenant_id: string;
  detection_ids: string[];
  status: "open" | "investigating" | "closed";
  severity: Severity;
  created_at: string;
  summary: IncidentSummary | null;
  detections: Detection[];
}
