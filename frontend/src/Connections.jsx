import { useEffect, useState } from 'react'
import { api } from './api.js'

const EMPTY_FORM = {
  name: '', host: 'localhost', port: '5432', db_name: '', db_user: '', db_password: '', ssl_mode: 'prefer',
}

export default function Connections({ onGoToQuestions }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const load = async () => {
    try {
      setItems(await api.listConnections())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.createConnection({
        ...form,
        port: parseInt(form.port, 10),
        ssl_mode: form.ssl_mode || null,
      })
      setForm(EMPTY_FORM)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const remove = async (c) => {
    if (!window.confirm(`Удалить подключение «${c.name}»? История запросов по нему тоже будет удалена.`)) return
    setError('')
    setDeletingId(c.id)
    try {
      await api.deleteConnection(c.id)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="two-col">
      <form className="card" onSubmit={submit}>
        <h2>Новое подключение</h2>
        {error && <div className="alert">{error}</div>}
        <label>Название<input value={form.name} onChange={set('name')} required /></label>
        <div className="row">
          <label>Host<input value={form.host} onChange={set('host')} required /></label>
          <label>Port<input value={form.port} onChange={set('port')} required /></label>
        </div>
        <label>База данных<input value={form.db_name} onChange={set('db_name')} required /></label>
        <label>Пользователь (read-only)<input value={form.db_user} onChange={set('db_user')} required /></label>
        <label>Пароль<input type="password" value={form.db_password} onChange={set('db_password')} required /></label>
        <label>
          SSL
          <select value={form.ssl_mode} onChange={set('ssl_mode')}>
            {['prefer', 'disable', 'require', 'verify-ca', 'verify-full'].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy}>{busy ? 'Проверяем…' : 'Проверить и сохранить'}</button>
      </form>
      <div className="card">
        <h2>Мои подключения</h2>
        {items.length === 0 && <p className="muted">Пока нет подключений. Добавьте PostgreSQL с read-only ролью.</p>}
        <ul className="list">
          {items.map((c) => (
            <li key={c.id}>
              <b>{c.name}</b>
              <span className="muted"> · {c.host}:{c.port}/{c.db_name}</span>
              <span className={`status ${c.status}`}>{c.status}</span>
              <button
                type="button"
                className="danger-icon"
                title="Удалить подключение"
                aria-label={`Удалить подключение ${c.name}`}
                disabled={deletingId !== null}
                onClick={() => remove(c)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        {items.length > 0 && (
          <button onClick={onGoToQuestions}>Перейти к вопросам</button>
        )}
      </div>
    </div>
  )
}
