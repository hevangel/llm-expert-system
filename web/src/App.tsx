import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, Conflict, EngineHealth, ReasoningResult, VersionRecord } from './api'

export function App() {
  const [health, setHealth] = useState('connecting')
  const [engines, setEngines] = useState<EngineHealth[]>([])
  const [versions, setVersions] = useState<VersionRecord[]>([])
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [source, setSource] = useState('examples/family')
  const [predicate, setPredicate] = useState('parent')
  const [args, setArgs] = useState('alice,bob')
  const [capability, setCapability] = useState('relational')
  const [result, setResult] = useState<ReasoningResult | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [status, ready, history, activeConflicts] = await Promise.all([api.health(), api.ready(), api.versions(), api.conflicts()])
      setHealth(`${status.status} · v${status.version}`); setEngines(ready.engines); setVersions(history); setConflicts(activeConflicts); setError('')
    } catch (reason) { setError(String(reason)); setHealth('unavailable') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  async function generate(event: FormEvent) {
    event.preventDefault(); setError('')
    try { await api.generate(source); await refresh() } catch (reason) { setError(String(reason)) }
  }
  async function query(event: FormEvent) {
    event.preventDefault(); setError('')
    try { setResult(await api.query(predicate, args.split(',').map((value) => value.trim()).filter(Boolean), capability)) } catch (reason) { setError(String(reason)) }
  }

  return <main>
    <header><p className="eyebrow">Symbolic reasoning workspace</p><h1>LLM Expert System</h1><p className="lede">Local documents become validated, immutable Prolog, CLIPS, Z3, and Clingo knowledge.</p><span className={`status ${health.startsWith('ok') ? 'ok' : ''}`}>{health}</span></header>
    {error && <div role="alert" className="alert">{error}</div>}
    <section><div><h2>Engine readiness</h2><p>Native runtimes remain isolated behind a common broker.</p></div><div className="engine-grid">{engines.map((engine) => <article key={engine.engine}><strong>{engine.engine.toUpperCase()}</strong><span className={engine.available ? 'ready' : 'missing'}>{engine.available ? engine.version ?? 'ready' : engine.detail ?? 'missing'}</span></article>)}</div></section>
    <section className="split"><form onSubmit={generate}><h2>Generate a version</h2><label>Local source directory<input value={source} onChange={(event) => setSource(event.target.value)} /></label><button>Ingest, validate & activate</button></form><form onSubmit={query}><h2>Ask active knowledge</h2><label>Predicate<input value={predicate} onChange={(event) => setPredicate(event.target.value)} /></label><label>Arguments<input value={args} onChange={(event) => setArgs(event.target.value)} /></label><label>Capability<select value={capability} onChange={(event) => setCapability(event.target.value)}><option value="relational">Relational · Prolog</option><option value="forward_chaining">Forward chaining · CLIPS</option><option value="constraint">Constraint · Z3</option><option value="planning">Planning · Clingo</option></select></label><button>Run bounded query</button></form></section>
    {result && <section className={`result ${result.status}`}><div><p className="eyebrow">Reasoning result</p><h2>{result.status}</h2><p>{result.engine ? `Engine: ${result.engine}` : 'No engine result'}</p></div><pre>{JSON.stringify(result, null, 2)}</pre></section>}
    {conflicts.length > 0 && <section><div><h2>Knowledge conflicts</h2><p>Affected goals abstain until evidence is explicitly resolved.</p></div><ol className="versions">{conflicts.map((conflict) => <li key={conflict.id}><code>{conflict.category}</code><span>{conflict.affected_predicates.join(', ')}</span><small>{conflict.resolved ? 'resolved' : 'requires review'}</small>{!conflict.resolved && conflict.item_ids.map((item) => <button className="secondary" key={item} onClick={() => void api.resolveConflict(conflict.id, item).then(refresh)}>Accept {item}</button>)}</li>)}</ol></section>}
    <section><div><h2>Immutable versions</h2><p>Invalid updates never replace the last-known-good version.</p></div><ol className="versions">{versions.map((version) => <li key={version.id}><code>{version.id}</code><span>{version.state}</span><small>{new Date(version.created_at).toLocaleString()}</small>{version.state === 'superseded' && <button className="secondary" onClick={() => void api.rollback(version.id).then(refresh)}>Roll back</button>}</li>)}</ol></section>
  </main>
}
