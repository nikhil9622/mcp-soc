import { auth } from "./firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function authHeaders(): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (!user) throw new Error("Not authenticated");
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

// ============================================================================
// ALERTS API
// ============================================================================

export async function fetchAlerts(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/alerts?skip=0&limit=50`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitAlertFeedback(
  alertId: string,
  feedbackType: "tp" | "fp",
  note: string = ""
) {
  const headers = await authHeaders();
  const res = await fetch(
    `${API_URL}/alerts/${alertId}/feedback?type=${feedbackType}&note=${encodeURIComponent(note)}`,
    { method: "POST", headers }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// INCIDENTS API
// ============================================================================

export async function fetchIncidents(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/incidents?skip=0&limit=50`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchIncident(id: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/incidents/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitIncidentFeedback(incidentId: string, feedback: "tp" | "fp") {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/incidents/${incidentId}/feedback`, {
    method: "POST",
    headers,
    body: JSON.stringify({ feedback }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// DETECTION RULES API
// ============================================================================

export async function fetchRules(skip = 0, limit = 50) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/rules?skip=${skip}&limit=${limit}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchRule(ruleId: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/rules/${ruleId}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchRuleStats(ruleId: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/rules/${ruleId}/stats`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// USER & API KEY MANAGEMENT
// ============================================================================

export async function upsertUser() {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/users/me`, { method: "POST", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateApiKey() {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/users/me/api-key`, { method: "POST", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getApiKey() {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/users/me/api-key`, { headers });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function revokeApiKey() {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/users/me/api-key`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// AGENT DOWNLOAD
// ============================================================================

export async function downloadAgent(apiKey?: string) {
  const headers = await authHeaders();
  const url = apiKey
    ? `${API_URL}/agent/download-configured?api_key=${encodeURIComponent(apiKey)}`
    : `${API_URL}/agent/download`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "mcp_soc_agent.py";
  a.click();
  URL.revokeObjectURL(a.href);
}

// ============================================================================
// INGEST STATS API
// ============================================================================

export async function fetchIngestStats(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/ingest/stats`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// ISOLATION API
// ============================================================================

export async function isolateEntity(incidentId: string, type: "ip" | "user", value: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/incidents/${incidentId}/isolate`, {
    method: "POST",
    headers,
    body: JSON.stringify({ type, value }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function unisolateEntity(incidentId: string, type: "ip" | "user", value: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/incidents/${incidentId}/unisolate`, {
    method: "POST",
    headers,
    body: JSON.stringify({ type, value }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchBlockedEntities(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/blocked-entities`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// CASE MANAGEMENT API
// ============================================================================

export async function fetchCases(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchCase(id: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases/${id}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createCase(data: { title: string; description?: string; priority?: string; incident_ids?: string[] }) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases`, { method: "POST", headers, body: JSON.stringify(data) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateCase(id: string, data: Record<string, any>) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases/${id}`, { method: "PATCH", headers, body: JSON.stringify(data) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addCaseNote(id: string, body: string, author = "analyst") {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases/${id}/notes`, { method: "POST", headers, body: JSON.stringify({ body, author }) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addCaseTask(id: string, title: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases/${id}/tasks`, { method: "POST", headers, body: JSON.stringify({ title }) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function toggleCaseTask(caseId: string, taskId: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases/${caseId}/tasks/${taskId}`, { method: "PATCH", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteCase(id: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/cases/${id}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// IOC ENRICHMENT API
// ============================================================================

export async function enrichIoc(ip: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/ioc/enrich?ip=${encodeURIComponent(ip)}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function bulkEnrichIoc(ips: string[]) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/ioc/bulk?ips=${encodeURIComponent(ips.join(","))}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// UEBA API
// ============================================================================

export async function fetchUebaEntities(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/ueba/entities`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchUebaEntity(entity: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/ueba/entity/${encodeURIComponent(entity)}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// THREAT HUNTING API
// ============================================================================

export async function huntSearch(query: Record<string, any>) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/hunt/search`, { method: "POST", headers, body: JSON.stringify(query) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchSavedHunts(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/hunt/saved`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function saveHunt(name: string, query: Record<string, any>) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/hunt/saved`, { method: "POST", headers, body: JSON.stringify({ name, query }) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteSavedHunt(id: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/hunt/saved/${id}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// MITRE ATT&CK COVERAGE API
// ============================================================================

export async function fetchMitreCoverage(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/mitre/coverage`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// ATTACK GRAPH API
// ============================================================================

export async function fetchAttackGraph(_key?: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/graph/attack`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============================================================================
// COMPLIANCE API
// ============================================================================

export async function fetchComplianceReport(framework: string) {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/compliance/report/${framework}`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function exportComplianceReport(framework: string): Promise<string> {
  const headers = await authHeaders();
  const res = await fetch(`${API_URL}/compliance/report/${framework}/export`, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.text();
}

// ============================================================================
// HEALTH CHECK
// ============================================================================

export async function checkHealth() {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error("API unhealthy");
  return res.json();
}
