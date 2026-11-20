import type { FormEvent, ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { campaignsApi, offersApi, settingsApi } from '@/api'
import { errorMessage } from '@/api/client'
import { CampaignLogList } from '@/components/CampaignLogList'
import { ErrorState } from '@/components/ErrorState'
import { OffersManager } from '@/components/OffersManager'
import { StateBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, SelectInput, TextInput } from '@/components/ui/Field'
import { IconArrowLeft, IconRefresh, IconStreams, IconTrash } from '@/components/ui/Icons'
import { ConfirmDialog } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useToast } from '@/components/ui/Toast'
import { useAsync } from '@/hooks/useAsync'
import { useResources } from '@/hooks/useResources'
import { formatDate } from '@/lib/format'
import type { CampaignDetail, CampaignOffersResponse } from '@/types/api'

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-2 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="truncate text-right font-medium text-slate-800">{value}</dd>
    </div>
  )
}

export default function CampaignEditorPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const toast = useToast()
  const { data: resources } = useResources()

  const detail = useAsync(() => campaignsApi.get(id), [id])
  const offers = useAsync(() => offersApi.list(id), [id])
  const logs = useAsync(() => settingsApi.logs(id), [id])

  const [form, setForm] = useState({ name: '', group_id: '', traffic_source_id: '', domain_id: '' })
  const [saving, setSaving] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const c = detail.data?.campaign
    if (c)
      setForm({
        name: c.name,
        group_id: c.group_id ? String(c.group_id) : '',
        traffic_source_id: c.traffic_source_id ? String(c.traffic_source_id) : '',
        domain_id: c.domain_id ? String(c.domain_id) : '',
      })
  }, [detail.data])

  function applyDetail(data: CampaignDetail) {
    detail.setData(data)
    void logs.reload()
  }

  function onOffersChange(data: CampaignOffersResponse) {
    offers.setData(data)
    void detail.reload()
    void logs.reload()
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!form.name.trim()) {
      toast.error('Название кампании не может быть пустым')
      return
    }
    setSaving(true)
    try {
      applyDetail(
        await campaignsApi.update(id, {
          name: form.name.trim(),
          group_id: form.group_id ? Number(form.group_id) : undefined,
          traffic_source_id: form.traffic_source_id ? Number(form.traffic_source_id) : undefined,
          domain_id: form.domain_id ? Number(form.domain_id) : undefined,
        }),
      )
      toast.success('Кампания сохранена')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function toggle() {
    const c = detail.data?.campaign
    if (!c) return
    setToggling(true)
    try {
      applyDetail(await campaignsApi.update(id, { state: c.state === 'active' ? 'disabled' : 'active' }))
      toast.success(c.state === 'active' ? 'Кампания остановлена' : 'Кампания запущена')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setToggling(false)
    }
  }

  async function remove() {
    setDeleting(true)
    try {
      await campaignsApi.remove(id)
      toast.success('Кампания удалена')
      navigate('/campaigns')
    } catch (err) {
      toast.error(errorMessage(err))
      setDeleting(false)
    }
  }

  const back = (
    <Link to="/campaigns" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
      <IconArrowLeft className="h-4 w-4" /> К списку кампаний
    </Link>
  )

  if (detail.error) {
    return (
      <>
        <PageHeader title={`Кампания #${id}`} back={back} />
        <ErrorState error={detail.error} code={detail.errorCode} onRetry={detail.reload} />
      </>
    )
  }
  if (!detail.data) return <PageLoader />

  const { campaign, streams, local } = detail.data
  const reloadAll = () => {
    void detail.reload()
    void offers.reload()
    void logs.reload()
  }

  return (
    <>
      <PageHeader
        back={back}
        title={campaign.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono">ID #{campaign.id}</span>
            <span>·</span>
            <span>{campaign.alias}</span>
            <StateBadge state={campaign.state} />
          </span>
        }
        actions={
          <>
            <Button variant="secondary" icon={<IconRefresh />} onClick={reloadAll} loading={detail.loading}>
              Обновить
            </Button>
            <Link to={`/campaigns/${id}/streams`}>
              <Button variant="secondary" icon={<IconStreams />}>
                Потоки ({streams.length})
              </Button>
            </Link>
            {campaign.state !== 'deleted' && (
              <>
                <Button variant="secondary" onClick={toggle} loading={toggling}>
                  {campaign.state === 'active' ? 'Остановить' : 'Запустить'}
                </Button>
                <Button variant="danger" icon={<IconTrash />} onClick={() => setConfirmDelete(true)}>
                  Удалить
                </Button>
              </>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader title="Основные параметры" />
            <form onSubmit={save} className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2">
              <Field label="Название" required className="sm:col-span-2">
                {(fid) => <TextInput id={fid} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
              </Field>
              <Field label="Группа">
                {(fid) => (
                  <SelectInput id={fid} value={form.group_id} onChange={(e) => setForm({ ...form, group_id: e.target.value })}>
                    <option value="">—</option>
                    {resources?.groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </SelectInput>
                )}
              </Field>
              <Field label="Источник трафика">
                {(fid) => (
                  <SelectInput id={fid} value={form.traffic_source_id} onChange={(e) => setForm({ ...form, traffic_source_id: e.target.value })}>
                    <option value="">—</option>
                    {resources?.sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </SelectInput>
                )}
              </Field>
              <Field label="Домен" className="sm:col-span-2">
                {(fid) => (
                  <SelectInput id={fid} value={form.domain_id} onChange={(e) => setForm({ ...form, domain_id: e.target.value })}>
                    <option value="">—</option>
                    {resources?.domains.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </SelectInput>
                )}
              </Field>
              <div className="flex justify-end sm:col-span-2">
                <Button type="submit" loading={saving}>
                  Сохранить
                </Button>
              </div>
            </form>
          </Card>

          {offers.error ? (
            <ErrorState error={offers.error} code={offers.errorCode} onRetry={offers.reload} />
          ) : !offers.data ? (
            <Card><PageLoader label="Загрузка офферов…" /></Card>
          ) : (
            <OffersManager campaignId={id} data={offers.data} catalog={resources?.offers ?? []} onChange={onOffersChange} />
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Информация" />
            <dl className="divide-y divide-slate-100 px-5 py-2">
              <InfoRow label="ID кампании" value={<span className="font-mono">#{campaign.id}</span>} />
              <InfoRow label="Alias" value={campaign.alias ?? '—'} />
              <InfoRow label="Тип ротации" value={campaign.type === 'weight' ? 'По весу' : 'По позиции'} />
              <InfoRow label="Домен" value={campaign.domain_name ?? '—'} />
              <InfoRow label="Группа" value={campaign.group_name ?? '—'} />
              <InfoRow label="Источник" value={campaign.traffic_source_name ?? '—'} />
              <InfoRow label="Потоков" value={campaign.streams_count ?? '—'} />
              <InfoRow label="Офферов" value={campaign.offers_count ?? '—'} />
              {local && <InfoRow label="GEO при создании" value={local.country} />}
              <InfoRow label="Обновлена" value={formatDate(campaign.updated_at)} />
            </dl>
          </Card>
          <Card>
            <CardHeader title="История операций" />
            {logs.data ? <CampaignLogList logs={logs.data.slice(0, 15)} /> : <PageLoader />}
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Удалить кампанию?"
        message={<>Кампания <b>«{campaign.name}»</b> будет перемещена в архив Keitaro.</>}
        loading={deleting}
        onConfirm={remove}
        onClose={() => setConfirmDelete(false)}
      />
    </>
  )
}
