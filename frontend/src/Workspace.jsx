import { useEffect, useRef, useState } from 'react'
import Chart from 'chart.js/auto'
import { api } from './api.js'

export default function Workspace({ onManageConnections }) {
  const [connections, setConnections] = useState([])
  const [connectionId, setConnectionId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [phase, setPhase] = useState('')
  const [busy, setBusy] = useState(false)
  const conversationIdRef = useRef(null)

  useEffect(() => {
    api.listConnections().then((list) => {
      setConnections(list)
      if (list.length && !connectionId) setConnectionId(list[0].id)
    }).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!connectionId) return
    api.history(connectionId).then(setHistory).catch(() => setHistory([]))
  }, [connectionId])

  const ask = async (text) => {
    const q = (text ?? prompt).trim()
    if (!q || !connectionId || busy) return
    setBusy(true)
    setError('')
    setResult(null)
    setPhase('ИИ подбирает запрос…')
    try {
      const resp = await api.query(connectionId, q, conversationIdRef.current)
      conversationIdRef.current = resp.conversation_id
      setResult(resp)
      setHistory(await api.history(connectionId))
    } catch (err) {
      setError(err.message)
    } finally {
      setPhase('')
      setBusy(false)
    }
  }

  return (
    <div className="workspace">
      <div className="card ask-card">
        <div className="row">
          <select value={connectionId} onChange={(e) => { setConnectionId(e.target.value); conversationIdRef.current = null }}>
            {connections.length === 0 && <option value="">— нет подключений —</option>}
            {connections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          {connections.length === 0 && (
            <button className="link" onClick={onManageConnections}>Добавить подключение</button>
          )}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); ask() }}>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Задайте вопрос к базе на русском"
            maxLength={2000}
            rows={2}
          />
          <button type="submit" disabled={busy || !connectionId || !prompt.trim()}>
            {busy ? 'Работаем…' : 'Спросить'}
          </button>
        </form>
      </div>

      {error && <div className="alert">{error}</div>}
      {phase && <div className="loading"><div className="spinner" /> {phase}</div>}

      {result && (
        <>
          <ResultTable columns={result.columns} data={result.data} row_count={result.row_count} truncated={result.truncated} />
          <ChartView spec={result.chart_spec} columns={result.columns} data={result.data} />
          <SqlBlock sql={result.sql} />
        </>
      )}

      <div className="card">
        <h3>История</h3>
        {history.length === 0 && <p className="muted">Пусто.</p>}
        <ul className="list">
          {history.slice(0, 10).map((h) => (
            <li key={h.id}>
              <button
                className="link history-item"
                onClick={() => { setPrompt(h.prompt_text); ask(h.prompt_text) }}
                title={h.generated_sql || ''}
              >
                {h.prompt_text}
              </button>
              <span className={`status ${h.execution_status}`}>{h.execution_status}</span>
              {h.row_count != null && <span className="muted"> · {h.row_count} строк</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function ResultTable({ columns, data, row_count, truncated }) {
  return (
    <div className="card">
      <div className="result-meta">
        <span>{row_count} строк</span>
        {truncated && <span className="warn">результат усечён</span>}
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>{row.map((v, j) => <td key={j}>{v === null ? '' : String(v)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ChartView({ spec, columns, data }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!spec || !canvasRef.current || !data.length) return
    if (chartRef.current) chartRef.current.destroy()

    const xi = columns.indexOf(spec.x)
    const yi = columns.indexOf(spec.y)
    if (xi < 0 || yi < 0) return

    const labels = data.map((r) => String(r[xi]))
    const values = data.map((r) => Number(r[yi]) || 0)

    chartRef.current = new Chart(canvasRef.current, {
      type: spec.type === 'pie' ? 'doughnut' : spec.type,
      data: {
        labels,
        datasets: [{
          label: spec.y,
          data: values,
          borderColor: '#4f7cff',
          backgroundColor: spec.type === 'pie'
            ? ['#4f7cff', '#34c77b', '#f5a623', '#e5484d', '#8e4ec6', '#00b2c9']
            : 'rgba(79,124,255,0.35)',
        }],
      },
      options: { responsive: true, plugins: { title: { display: !!spec.title, text: spec.title || '' } } },
    })
    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null } }
  }, [spec, columns, data])

  if (!spec || spec.type === 'table' || !data.length) return null
  return (
    <div className="card">
      <canvas ref={canvasRef} height="220" />
    </div>
  )
}

function SqlBlock({ sql }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }

  return (
    <div className="card sql-block">
      <button className="link" onClick={() => setOpen(!open)}>
        {open ? 'Свернуть SQL ▾' : 'Показать SQL ▸'}
      </button>
      {open && (
        <>
          <pre>{sql}</pre>
          <button onClick={copy}>{copied ? 'Скопировано ✓' : 'Копировать'}</button>
        </>
      )}
    </div>
  )
}
