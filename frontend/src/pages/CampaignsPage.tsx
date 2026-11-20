import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { campaignsApi } from '@/api'
import { errorMessage } from '@/api/client'
import { ErrorState } from '@/components/ErrorState'
import { EmptyState } from '@/components/ui/Alert'
import { StateBadge } from '@/components/ui/Badge'
import { Button, IconButton } from '@/components/ui/Button'
import { Card, StatCard } from '@/components/ui/Card'
import { SelectInput, TextInput } from '@/components/ui/Field'
import { IconCampaigns, IconCheck, IconEdit, IconLayers, IconPlus, IconRefresh, IconSearch, IconStreams, IconTrash } from '@/components/ui/Icons'
import { ConfirmDialog } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useToast } from '@/components/ui/Toast'
import { useAsync } from '@/hooks/useAsync'
import { useDebounce } from '@/hooks/useDebounce'
import { useResources } from '@/hooks/useResources'
import { formatDate } from '@/lib/format'
import type { CampaignListItem } from '@/types/api'

export default function CampaignsPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [groupId, setGroupId] = useState('')
  const [state, setState] = useState('')
  const debouncedSearch = useDebounce(search)
  const { data: resources } = useResources()

  const { data, error, errorCode, loading, reload } = useAsync(
    () =>
      campaignsApi.list({
        search: debouncedSearch || undefined,
        group_id: groupId ? Number(groupId) : undefined,
        state: state || undefined,
      }),
    [debouncedSearch, groupId, state],
  )

  const [toDelete, setToDelete] = useState<CampaignListItem | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [toggling, setToggling] = useState<number | null>(null)

  const activeCount = useMemo(() => data?.items.filter((c) => c.state === 'active').length ?? 0, [data])

  async function confirmDelete() {
    if (!toDelete) return
    setDeleting(true)
    try {
      await campaignsApi.remove(toDelete.id)
      toast.success(`Кампания «${toDelete.name}» удалена`)
      setToDelete(null)
      await reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDeleting(false)
    }
  }

  async function toggleState(campaign: CampaignListItem) {
    setToggling(campaign.id)
    const next = campaign.state === 'active' ? 'disabled' : 'active'
    try {
      await campaignsApi.update(campaign.id, { state: next })
      toast.success(next === 'active' ? 'Кампания запущена' : 'Кампания остановлена')
      await reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setToggling(null)
    }
  }

  const actions = (c: CampaignListItem) => (
    <div className="flex items-center justify-end gap-1">
      <IconButton label="Редактировать" onClick={() => navigate(`/campaigns/${c.id}`)}>
        <IconEdit />
      </IconButton>
      <IconButton label="Потоки" onClick={() => navigate(`/campaigns/${c.id}/streams`)}>
        <IconStreams />
      </IconButton>
      {c.state !== 'deleted' && (
        <IconButton
          label={c.state === 'active' ? 'Остановить' : 'Запустить'}
          onClick={() => toggleState(c)}
          disabled={toggling === c.id}
          className={c.state === 'active' ? '' : 'text-brand-600'}
        >
          {c.state === 'active' ? (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8}><path d="M9 6v12M15 6v12" strokeLinecap="round" /></svg>
          ) : (
            <IconCheck />
          )}
        </IconButton>
      )}
      {c.state !== 'deleted' && (
        <IconButton label="Удалить" className="hover:bg-red-50 hover:text-red-600" onClick={() => setToDelete(c)}>
          <IconTrash />
        </IconButton>
      )}
    </div>
  )

  return (
    <>
      <PageHeader
        title="Кампании"
        description="Рекламные кампании Keitaro: поиск, фильтры и управление"
        actions={
          <>
            <Button variant="secondary" icon={<IconRefresh />} onClick={reload} loading={loading && !!data}>
              Обновить
            </Button>
            <Link to="/campaigns/new">
              <Button icon={<IconPlus />}>Создать кампанию</Button>
            </Link>
          </>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Кампаний" value={data?.total ?? '—'} icon={<IconCampaigns />} />
        <StatCard label="Активных" value={data ? activeCount : '—'} icon={<IconCheck />} />
        <StatCard label="Офферов в кампаниях" value={data?.offers_total ?? '—'} icon={<IconLayers />} />
      </div>

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 md:flex-row">
          <div className="relative flex-1">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
              <IconSearch />
            </span>
            <TextInput className="pl-10" placeholder="Поиск по названию или ID" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <SelectInput className="md:w-56" value={groupId} onChange={(e) => setGroupId(e.target.value)} aria-label="Группа">
            <option value="">Все группы</option>
            {resources?.groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </SelectInput>
          <SelectInput className="md:w-48" value={state} onChange={(e) => setState(e.target.value)} aria-label="Статус">
            <option value="">Все статусы</option>
            <option value="active">Активные</option>
            <option value="disabled">Остановленные</option>
            <option value="deleted">Удалённые</option>
          </SelectInput>
        </div>

        {error ? (
          <div className="p-4">
            <ErrorState error={error} code={errorCode} onRetry={reload} />
          </div>
        ) : loading && !data ? (
          <PageLoader />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title="Кампании не найдены"
            description={search || groupId || state ? 'Измените параметры поиска или фильтры.' : 'Создайте первую кампанию — она появится в Keitaro.'}
            action={
              <Link to="/campaigns/new">
                <Button icon={<IconPlus />}>Создать кампанию</Button>
              </Link>
            }
          />
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="table-th">ID</th>
                    <th className="table-th">Кампания</th>
                    <th className="table-th">Группа</th>
                    <th className="table-th">Источник</th>
                    <th className="table-th text-center">Потоки</th>
                    <th className="table-th text-center">Офферы</th>
                    <th className="table-th">Статус</th>
                    <th className="table-th">Обновлена</th>
                    <th className="table-th text-right">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/70">
                      <td className="table-td font-mono text-xs text-slate-500">#{c.id}</td>
                      <td className="table-td">
                        <Link to={`/campaigns/${c.id}`} className="font-medium text-slate-900 hover:text-brand-700">
                          {c.name}
                        </Link>
                        <p className="text-xs text-slate-400">
                          {c.alias}
                          {c.domain_name && ` · ${c.domain_name}`}
                        </p>
                      </td>
                      <td className="table-td">{c.group_name ?? '—'}</td>
                      <td className="table-td">{c.traffic_source_name ?? '—'}</td>
                      <td className="table-td text-center">{c.streams_count ?? '—'}</td>
                      <td className="table-td text-center">{c.offers_count ?? '—'}</td>
                      <td className="table-td">
                        <StateBadge state={c.state} />
                      </td>
                      <td className="table-td text-xs text-slate-500">{formatDate(c.updated_at)}</td>
                      <td className="table-td">{actions(c)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="divide-y divide-slate-100 md:hidden">
              {data.items.map((c) => (
                <li key={c.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link to={`/campaigns/${c.id}`} className="font-medium text-slate-900">
                        {c.name}
                      </Link>
                      <p className="text-xs text-slate-400">
                        #{c.id} · {c.group_name ?? 'без группы'}
                      </p>
                    </div>
                    <StateBadge state={c.state} />
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <p className="text-xs text-slate-500">
                      Потоков: {c.streams_count ?? '—'} · Офферов: {c.offers_count ?? '—'}
                    </p>
                    {actions(c)}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>

      <ConfirmDialog
        open={!!toDelete}
        title="Удалить кампанию?"
        message={
          <>
            Кампания <b>«{toDelete?.name}»</b> (#{toDelete?.id}) будет перемещена в архив Keitaro. Трафик по ней перестанет обрабатываться.
          </>
        }
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </>
  )
}
