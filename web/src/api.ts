export type EngineHealth = { engine: string; available: boolean; version?: string; detail?: string }
export type VersionRecord = { id: string; state: string; digest: string; created_at: string }
export type Conflict = { id: string; category: string; item_ids: string[]; affected_predicates: string[]; resolved: boolean; resolution_note?: string }
export type ReasoningResult = { status: 'answered' | 'unknown' | 'unsat' | 'abstained' | 'error' | 'timeout'; engine?: string; diagnostics: string[]; conflict_ids: string[]; bindings: Record<string, unknown>[]; models: string[][] }

const token = import.meta.env.VITE_API_TOKEN as string | undefined
const headers = (): HeadersInit => ({ 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) })

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { ...headers(), ...init?.headers } })
  if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText)
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),
  ready: () => request<{ active_version: VersionRecord | null; engines: EngineHealth[] }>('/ready'),
  versions: () => request<VersionRecord[]>('/api/v1/versions'),
  conflicts: () => request<Conflict[]>('/api/v1/conflicts'),
  generate: (sourceRoot: string) => request<{ version_id: string; active: boolean }>('/api/v1/generate', { method: 'POST', body: JSON.stringify({ source_root: sourceRoot, activate: true }) }),
  query: (predicate: string, args: string[], capability: string) => request<ReasoningResult>('/api/v1/query', { method: 'POST', body: JSON.stringify({ goal: { predicate, arguments: args, negated: false }, capabilities: [capability], max_results: 10, timeout_seconds: 10, require_proof: false, require_models: false, optimize: false }) }),
  rollback: (versionId: string) => request<{ active_version: string }>('/api/v1/rollback', { method: 'POST', body: JSON.stringify({ version_id: versionId }) }),
  resolveConflict: (conflictId: string, acceptedItem: string) => request<{ version_id: string }>(`/api/v1/conflicts/${conflictId}/resolve`, { method: 'POST', body: JSON.stringify({ accepted_item_ids: [acceptedItem], note: 'Resolved through web review', activate: true }) }),
}
