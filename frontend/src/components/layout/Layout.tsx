import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { settingsApi } from '@/api'
import { IconCampaigns, IconClose, IconLayers, IconLog, IconMenu, IconPlus, IconSettings } from '@/components/ui/Icons'
import { cn } from '@/lib/format'
import type { Health } from '@/types/api'

const nav = [
  { to: '/campaigns', label: 'Кампании', icon: IconCampaigns, end: true },
  { to: '/campaigns/new', label: 'Создать кампанию', icon: IconPlus, end: true },
  { to: '/resources', label: 'Ресурсы', icon: IconLayers, end: false },
  { to: '/logs', label: 'Журнал', icon: IconLog, end: false },
  { to: '/settings', label: 'Настройки', icon: IconSettings, end: false },
]

function Sidebar({ onNavigate, health }: { onNavigate?: () => void; health: Health | null }) {
  return (
    <div className="flex h-full flex-col bg-sidebar text-slate-300">
      <div className="flex h-16 items-center gap-3 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-lg font-bold text-white">K</div>
        <div>
          <p className="text-sm font-semibold text-white">Keitaro Manager</p>
          <p className="text-xs text-slate-500">Campaign control panel</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive ? 'bg-brand-600/15 text-brand-500' : 'hover:bg-sidebar-hover hover:text-white',
              )
            }
          >
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-800 px-5 py-4 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              !health ? 'bg-slate-500' : health.keitaro_configured && health.database === 'ok' ? 'bg-brand-500' : 'bg-amber-400',
            )}
          />
          <span className="text-slate-400">
            {!health ? 'Проверка…' : health.keitaro_configured ? 'Keitaro подключён' : 'Keitaro не настроен'}
          </span>
        </div>
        {health && <p className="mt-1 text-slate-600">v{health.version}</p>}
      </div>
    </div>
  )
}

export function Layout() {
  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const location = useLocation()

  useEffect(() => {
    settingsApi.health().then(setHealth).catch(() => setHealth(null))
  }, [location.pathname])

  return (
    <div className="flex h-full">
      <aside className="hidden w-64 shrink-0 lg:block">
        <div className="fixed inset-y-0 w-64">
          <Sidebar health={health} />
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/60" onClick={() => setOpen(false)} />
          <div className="relative h-full w-64">
            <Sidebar health={health} onNavigate={() => setOpen(false)} />
            <button className="absolute top-4 -right-11 rounded-lg bg-white p-1.5 text-slate-700" onClick={() => setOpen(false)} aria-label="Закрыть меню">
              <IconClose />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 lg:hidden">
          <button className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100" onClick={() => setOpen(true)} aria-label="Открыть меню">
            <IconMenu />
          </button>
          <span className="font-semibold text-slate-900">Keitaro Manager</span>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
