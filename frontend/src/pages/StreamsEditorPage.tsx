import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { campaignsApi, settingsApi, streamsApi } from '@/api'
import { errorMessage } from '@/api/client'
import { ErrorState } from '@/components/ErrorState'
import { StreamForm } from '@/components/StreamForm'
import { EmptyState } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button, IconButton } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Toggle } from '@/components/ui/Field'
import { IconArrowLeft, IconEdit, IconPlus, IconRefresh, IconTrash } from '@/components/ui/Icons'
import { ConfirmDialog, Modal } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useToast } from '@/components/ui/Toast'
import { useAsync } from '@/hooks/useAsync'
import { useResources } from '@/hooks/useResources'
import { payloadToText } from '@/lib/format'
import { OTHER_ACTIONS, REDIRECT_ACTIONS, STREAM_SCHEMAS, filterLabel } from '@/lib/streams'
import type { Stream, StreamInput } from '@/types/api'

const typeTone = { forced: 'amber', regular: 'blue', default: 'gray' } as const

export default function StreamsEditorPage() {
  const id = Number(useParams().id)
  const toast = useToast()
  const { data: resources } = useResources()
  const campaign = useAsync(() => campaignsApi.get(id), [id])
  const settings = useAsync(() => settingsApi.get(), [])

  const [editing, setEditing] = useState<Stream | 'new' | null>(null)
  const [saving, setSaving] = useState(false)
  const [toDelete, setToDelete] = useState<Stream | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [toggling, setToggling] = useState<number | null>(null)

  const offerName = (offerId: number) => resources?.offers.find((o) => o.id === offerId)?.name ?? `Оффер #${offerId}`

  async function submit(input: StreamInput) {
    setSaving(true)
    try {
      if (editing === 'new') {
        await streamsApi.create(id, input)
        toast.success('Поток создан')
      } else if (editing) {
        await streamsApi.update(editing.id, input)
        toast.success('Поток сохранён')
      }
      setEditing(null)
      await campaign.reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(stream: Stream) {
    setToggling(stream.id)
    try {
      await streamsApi.setEnabled(stream.id, stream.state !== 'active')
      toast.success(stream.state === 'active' ? 'Поток выключен' : 'Поток включён')
      await campaign.reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setToggling(null)
    }
  }

  async function remove() {
    if (!toDelete) return
    setDeleting(true)
    try {
      await streamsApi.remove(toDelete.id)
      toast.success('Поток удалён')
      setToDelete(null)
      await campaign.reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDeleting(false)
    }
  }

  const back = (
    <Link to={`/campaigns/${id}`} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
      <IconArrowLeft className="h-4 w-4" /> К кампании
    </Link>
  )

  if (campaign.error)
    return (
      <>
        <PageHeader title="Потоки" back={back} />
        <ErrorState error={campaign.error} code={campaign.errorCode} onRetry={campaign.reload} />
      </>
    )
  if (!campaign.data) return <PageLoader />

  const streams = campaign.data.streams

  return (
    <>
      <PageHeader
        back={back}
        title="Редактор потоков"
        description={
          <>
            {campaign.data.campaign.name} · <span className="font-mono">#{id}</span> · потоки проверяются сверху вниз
          </>
        }
        actions={
          <>
            <Button variant="secondary" icon={<IconRefresh />} onClick={campaign.reload} loading={campaign.loading}>
              Обновить
            </Button>
            <Button icon={<IconPlus />} onClick={() => setEditing('new')}>
              Добавить поток
            </Button>
          </>
        }
      />

      {streams.length === 0 ? (
        <Card>
          <EmptyState title="У кампании нет потоков" action={<Button icon={<IconPlus />} onClick={() => setEditing('new')}>Добавить поток</Button>} />
        </Card>
      ) : (
        <div className="space-y-4">
          {streams.map((s, index) => {
            const actionLabel =
              REDIRECT_ACTIONS[s.action_type ?? ''] ?? OTHER_ACTIONS[s.action_type ?? ''] ?? s.action_type
            return (
              <Card key={s.id} className={s.state === 'active' ? '' : 'opacity-70'}>
                <div className="flex flex-col gap-4 p-5 md:flex-row md:items-start">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-sm font-semibold text-slate-600">
                    {index + 1}
                  </div>
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-slate-900">{s.name || `Поток #${s.id}`}</h3>
                      <span className="font-mono text-xs text-slate-400">#{s.id}</span>
                      <Badge tone={typeTone[s.type ?? 'regular'] ?? 'gray'}>{s.type}</Badge>
                      <Badge tone={s.state === 'active' ? 'green' : 'gray'}>{s.state === 'active' ? 'включён' : 'выключен'}</Badge>
                    </div>

                    <div className="grid grid-cols-1 gap-3 text-sm lg:grid-cols-2">
                      <div>
                        <p className="mb-1 text-xs font-semibold text-slate-400 uppercase">Условия {s.filters.length > 1 && (s.filter_or ? '(OR)' : '(AND)')}</p>
                        {s.filters.length === 0 ? (
                          <p className="text-slate-500">{s.type === 'default' ? 'Запасной поток' : 'Все пользователи'}</p>
                        ) : (
                          <ul className="space-y-1">
                            {s.filters.map((f, i) => (
                              <li key={i} className="text-slate-700">
                                <span className="font-medium">{filterLabel(f.name)}</span>{' '}
                                <span className={f.mode === 'reject' ? 'text-red-600' : 'text-brand-700'}>{f.mode === 'reject' ? '≠' : '='}</span>{' '}
                                <span className="font-mono text-xs">{payloadToText(f.payload)}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div>
                        <p className="mb-1 text-xs font-semibold text-slate-400 uppercase">
                          {s.schema === 'landings' ? STREAM_SCHEMAS.landings : `${STREAM_SCHEMAS[s.schema ?? 'redirect'] ?? s.schema} · ${actionLabel}`}
                        </p>
                        {s.schema === 'landings' ? (
                          <ul className="space-y-1">
                            {s.offers.map((o) => (
                              <li key={o.offer_id} className="flex items-center gap-2 text-slate-700">
                                <span className="truncate">{offerName(o.offer_id)}</span>
                                <span className="ml-auto font-medium">{o.share}%</span>
                                {o.state !== 'active' && <Badge>выкл</Badge>}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="truncate font-mono text-xs text-slate-600" title={payloadToText(s.action_payload)}>
                            {payloadToText(s.action_payload) || '—'}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 md:flex-col md:items-end">
                    <Toggle checked={s.state === 'active'} onChange={() => toggle(s)} disabled={toggling === s.id} label="Включить поток" />
                    <div className="flex">
                      <IconButton label="Редактировать" onClick={() => setEditing(s)}>
                        <IconEdit />
                      </IconButton>
                      <IconButton label="Удалить" className="hover:bg-red-50 hover:text-red-600" onClick={() => setToDelete(s)}>
                        <IconTrash />
                      </IconButton>
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <Modal open={editing !== null} title={editing === 'new' ? 'Новый поток' : `Поток #${editing ? (editing as Stream).id : ''}`} onClose={() => !saving && setEditing(null)} size="xl">
        {editing !== null && (
          <StreamForm
            key={editing === 'new' ? 'new' : editing.id}
            stream={editing === 'new' ? null : editing}
            offers={resources?.offers ?? []}
            defaultUrl={settings.data?.default_safe_url ?? 'https://www.google.com'}
            saving={saving}
            onSubmit={submit}
            onCancel={() => setEditing(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        title="Удалить поток?"
        message={<>Поток <b>«{toDelete?.name}»</b> (#{toDelete?.id}) будет удалён из кампании в Keitaro.</>}
        loading={deleting}
        onConfirm={remove}
        onClose={() => setToDelete(null)}
      />
    </>
  )
}
