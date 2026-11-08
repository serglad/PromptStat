import { useState } from 'react'
import { getToken, setToken } from './api.js'
import Login from './Login.jsx'
import Connections from './Connections.jsx'
import Workspace from './Workspace.jsx'

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()))
  const [view, setView] = useState('workspace')

  if (!authed) {
    return <Login onSuccess={() => { setAuthed(true); setView('workspace') }} />
  }

  const logout = () => {
    setToken(null)
    setAuthed(false)
  }

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">PromptStat</span>
        <nav>
          <button
            className={view === 'workspace' ? 'nav active' : 'nav'}
            onClick={() => setView('workspace')}
          >
            Вопросы
          </button>
          <button
            className={view === 'connections' ? 'nav active' : 'nav'}
            onClick={() => setView('connections')}
          >
            Подключения
          </button>
          <button className="nav" onClick={logout}>Выйти</button>
        </nav>
      </header>
      <main>
        {view === 'workspace'
          ? <Workspace onManageConnections={() => setView('connections')} />
          : <Connections onGoToQuestions={() => setView('workspace')} />}
      </main>
    </div>
  )
}
