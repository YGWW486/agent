import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell() {
  return (
    <div className="flex h-screen">
      <button
        type="button"
        className="skip-link"
        onClick={() => document.getElementById('main-content')?.focus()}
      >
        跳到内容区
      </button>
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <TopBar />
        <main id="main-content" className="flex-1 overflow-y-auto" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
