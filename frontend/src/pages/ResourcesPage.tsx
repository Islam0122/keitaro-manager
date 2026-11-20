import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'
import { NavLink, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/ErrorState'
import { EmptyState } from '@/components/ui/Alert'
import { Badge, StateBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextInput } from '@/components/ui/Field'
import { IconRefresh, IconSearch } from '@/components/ui/Icons'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useResources, type Resources } from '@/hooks/useResources'
import { cn, payloadToText } from '@/lib/format'

type Tab = 'domains' | 'groups' | 'sources' | 'offers'

interface Column<T> {
  title: string
  render: (row: T) => ReactNode
  className?: string
}

const tabs: { key: Tab; label: string }[] = [
  { key: 'domains', label: 'Domains' },
  { key: 'groups', label: 'Groups' },
  { key: 'sources', label: 'Traffic Sources' },
  { key: 'offers', label: 'Offers' },
]

const idCol = { title: 'ID', render: (r: { id: number }) => <span className="font-mono text-xs text-slate-500">#{r.id}</span>, className: 'w-20' }

const columns: { [K in Tab]: Column<Resources[K][number]>[] } = {
  domains: [
    idCol,
    { title: 'Домен', render: (d) => <span className="font-medium text-slate-900">{d.name}</span> },
    { title: 'DNS / сеть', render: (d) => (d.network_status ? <Badge tone={d.network_status === 'active' ? 'green' : 'amber'}>{d.network_status}</Badge> : '—') },
    { title: 'SSL', render: (d) => (d.is_ssl == null ? '—' : d.is_ssl ? 'Да' : 'Нет') },
    { title: 'Кампания по умолч.', render: (d) => (d.default_campaign_id ? `#${d.default_campaign_id}` : '—') },
  ],
  groups: [idCol, { title: 'Название', render: (g) => <span className="font-medium text-slate-900">{g.name}</span> }, { title: 'Тип', render: (g) => g.type ?? '—' }],
  sources: [idCol, { title: 'Название', render: (s) => <span className="font-medium text-slate-900">{s.name}</span> }, { title: 'Статус', render: (s) => <StateBadge state={s.state} /> }],
  offers: [
    idCol,
    { title: 'Оффер', render: (o) => <span className="font-medium text-slate-900">{o.name}</span> },
    { title: 'GEO', render: (o) => (o.country.length ? o.country.join(', ') : 'Все') },
    { title: 'Выплата', render: (o) => (o.payout_value != null ? `${o.payout_value} ${o.payout_currency ?? ''}` : '—') },
    { title: 'URL', render: (o) => <span className="block max-w-xs truncate font-mono text-xs text-slate-500">{payloadToText(o.action_payload) || '—'}</span> },
    { title: 'Статус', render: (o) => <StateBadge state={o.state} /> },
  ],
}

export default function ResourcesPage() {
  const tab = (useParams().tab as Tab) ?? 'domains'
  const current: Tab = tabs.some((t) => t.key === tab) ? tab : 'domains'
  const { data, error, errorCode, loading, refresh } = useResources()
  const [search, setSearch] = useState('')

  const rows = useMemo(() => {
    const list = (data?.[current] ?? []) as { id: number; name: string }[]
    const needle = search.trim().toLowerCase()
    return needle ? list.filter((r) => r.name.toLowerCase().includes(needle) || String(r.id) === needle) : list
  }, [data, current, search])

  const cols = columns[current] as Column<{ id: number; name: string }>[]

  return (
    <>
      <PageHeader
        title="Ресурсы"
        description="Справочники Keitaro: домены, группы, источники трафика и офферы"
        actions={
          <Button variant="secondary" icon={<IconRefresh />} onClick={refresh} loading={loading}>
            Обновить
          </Button>
        }
      />
      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1">
            {tabs.map((t) => (
              <NavLink
                key={t.key}
                to={`/resources/${t.key}`}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap',
                  current === t.key ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-600 hover:text-slate-900',
                )}
              >
                {t.label}
                {data && <span className="ml-1.5 text-xs text-slate-400">{data[t.key].length}</span>}
              </NavLink>
            ))}
          </div>
          <div className="relative lg:w-72">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
              <IconSearch />
            </span>
            <TextInput className="pl-10" placeholder="Поиск по названию или ID" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>

        {error ? (
          <div className="p-4">
            <ErrorState error={error} code={errorCode} onRetry={refresh} />
          </div>
        ) : loading && !data ? (
          <PageLoader />
        ) : rows.length === 0 ? (
          <EmptyState title="Ничего не найдено" description="Создайте объекты в Keitaro или измените условия поиска." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {cols.map((c) => (
                    <th key={c.title} className={cn('table-th', c.className)}>
                      {c.title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50/70">
                    {cols.map((c) => (
                      <td key={c.title} className="table-td whitespace-nowrap">
                        {c.render(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
