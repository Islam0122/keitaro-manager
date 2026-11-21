import { useEffect, useMemo, useState } from 'react'

import { offersApi } from '@/api'
import { ApiError, errorMessage } from '@/api/client'
import { EmptyState } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button, IconButton } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { SelectInput, TextInput, Toggle } from '@/components/ui/Field'
import { IconPlus, IconTrash } from '@/components/ui/Icons'
import { ConfirmDialog } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import { cn, equalSplit, scaleTo100 } from '@/lib/format'
import type { CampaignOffersResponse, ItemState, Offer } from '@/types/api'

interface Row {
  offer_id: number
  offer_name: string | null
  share: number
  state: ItemState
}

interface Props {
  campaignId: number
  data: CampaignOffersResponse
  catalog: Offer[]
  onChange: (data: CampaignOffersResponse) => void
  onReload: () => void
}

export function OffersManager({ campaignId, data, catalog, onChange, onReload }: Props) {
  const toast = useToast()
  const [streamId, setStreamId] = useState<number | null>(data.streams[0]?.stream_id ?? null)
  const [rows, setRows] = useState<Row[]>([])
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [newOffer, setNewOffer] = useState('')
  const [newShare, setNewShare] = useState('')
  const [adding, setAdding] = useState(false)
  const [toRemove, setToRemove] = useState<Row | null>(null)
  const [removing, setRemoving] = useState(false)

  useEffect(() => {
    if (!data.streams.some((s) => s.stream_id === streamId)) setStreamId(data.streams[0]?.stream_id ?? null)
  }, [data, streamId])

  useEffect(() => {
    setRows(
      data.items
        .filter((i) => i.stream_id === streamId)
        .map(({ offer_id, offer_name, share, state }) => ({ offer_id, offer_name, share, state })),
    )
    setDirty(false)
  }, [data, streamId])

  const activeTotal = useMemo(() => rows.filter((r) => r.state === 'active').reduce((sum, r) => sum + r.share, 0), [rows])
  const valid = rows.some((r) => r.state === 'active') && activeTotal === 100
  const available = catalog.filter((o) => !rows.some((r) => r.offer_id === o.id))
  const hasActive = rows.some((r) => r.state === 'active')
  // offer ids as loaded from Keitaro — sent with the update so the backend can detect concurrent edits
  const loadedIds = useMemo(() => data.items.filter((i) => i.stream_id === streamId).map((i) => i.offer_id), [data, streamId])

  function handleError(e: unknown) {
    if (e instanceof ApiError && e.code === 'stale_stream') {
      toast.error('Поток изменён в другом месте — данные обновлены, повторите изменения')
      onReload()
      return
    }
    toast.error(errorMessage(e))
  }

  function update(index: number, patch: Partial<Row>) {
    setRows((list) => list.map((r, i) => (i === index ? { ...r, ...patch } : r)))
    setDirty(true)
  }

  function redistribute(mode: 'equal' | 'normalize') {
    setRows((list) => {
      const active = list.map((r, i) => [r, i] as const).filter(([r]) => r.state === 'active')
      const shares = mode === 'equal' ? equalSplit(active.length) : scaleTo100(active.map(([r]) => r.share))
      const next = list.map((r) => ({ ...r }))
      active.forEach(([, i], k) => (next[i].share = shares[k]))
      return next
    })
    setDirty(true)
  }

  async function save() {
    if (!streamId) return
    setSaving(true)
    try {
      const result = await offersApi.update(
        campaignId,
        streamId,
        rows.map(({ offer_id, share, state }) => ({ offer_id, share, state })),
        loadedIds,
      )
      onChange(result)
      toast.success('Распределение трафика сохранено')
    } catch (e) {
      handleError(e)
    } finally {
      setSaving(false)
    }
  }

  async function add() {
    if (!newOffer || !streamId) return
    const share = newShare ? Number(newShare) : undefined
    if (share !== undefined && (!Number.isInteger(share) || share < 1 || share > 100)) {
      toast.error('Доля должна быть целым числом от 1 до 100')
      return
    }
    setAdding(true)
    try {
      const result = await offersApi.add(campaignId, { offer_id: Number(newOffer), stream_id: streamId, share })
      onChange(result)
      setNewOffer('')
      setNewShare('')
      toast.success('Оффер добавлен, доли пересчитаны')
    } catch (e) {
      handleError(e)
    } finally {
      setAdding(false)
    }
  }

  async function remove() {
    if (!toRemove || !streamId) return
    setRemoving(true)
    try {
      const result = await offersApi.remove(campaignId, toRemove.offer_id, streamId)
      onChange(result)
      setToRemove(null)
      toast.success('Оффер удалён, доли пересчитаны')
    } catch (e) {
      handleError(e)
    } finally {
      setRemoving(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Офферы и распределение трафика"
        description="Сумма долей активных офферов потока должна составлять 100%"
        actions={
          data.streams.length > 1 && (
            <SelectInput className="w-56" value={streamId ?? ''} onChange={(e) => setStreamId(Number(e.target.value))} aria-label="Поток">
              {data.streams.map((s) => (
                <option key={s.stream_id} value={s.stream_id}>
                  #{s.stream_id} {s.name ?? 'Поток'}
                </option>
              ))}
            </SelectInput>
          )
        }
      />

      {!streamId ? (
        <EmptyState title="Нет потока с офферами" description="Создайте в редакторе потоков поток со схемой «Офферы», чтобы управлять распределением." />
      ) : (
        <>
          {rows.length === 0 ? (
            <EmptyState title="В потоке нет офферов" description="Добавьте оффер ниже." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {rows.map((row, index) => (
                <li key={row.offer_id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-slate-400">#{row.offer_id}</span>
                      <span className="truncate font-medium text-slate-900">{row.offer_name ?? 'Оффер'}</span>
                      {row.state !== 'active' && <Badge>выключен</Badge>}
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={cn('h-full rounded-full transition-all', row.state === 'active' ? 'bg-brand-500' : 'bg-slate-300')}
                        style={{ width: `${Math.min(row.share, 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="relative w-24">
                      <TextInput
                        type="number"
                        min={0}
                        max={100}
                        value={row.share}
                        aria-label="Доля трафика"
                        className="pr-7 text-right"
                        onChange={(e) => update(index, { share: Math.max(0, Math.min(100, Math.round(Number(e.target.value) || 0))) })}
                      />
                      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-slate-400">%</span>
                    </div>
                    <Toggle checked={row.state === 'active'} label="Оффер активен" onChange={(on) => update(index, { state: on ? 'active' : 'disabled' })} />
                    <IconButton label="Удалить оффер" className="hover:bg-red-50 hover:text-red-600" onClick={() => setToRemove(row)}>
                      <IconTrash />
                    </IconButton>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50/60 px-5 py-3 md:flex-row md:items-center md:justify-between">
            <p className={cn('text-sm font-medium', valid ? 'text-brand-700' : 'text-red-600')}>
              {!hasActive && rows.length > 0
                ? 'Нужен хотя бы один активный оффер'
                : `Итого по активным: ${activeTotal}% ${valid ? '✓' : `— должно быть 100% (${activeTotal > 100 ? 'лишние' : 'не хватает'} ${Math.abs(100 - activeTotal)}%)`}`}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => redistribute('equal')} disabled={rows.length === 0}>
                Поровну
              </Button>
              <Button size="sm" variant="secondary" onClick={() => redistribute('normalize')} disabled={rows.length === 0}>
                Пересчитать до 100%
              </Button>
              {dirty && (
                <Button size="sm" variant="ghost" onClick={() => onChange({ ...data })} disabled={saving}>
                  Отменить
                </Button>
              )}
              <Button size="sm" onClick={save} loading={saving} disabled={!dirty || !valid || rows.length === 0}>
                Сохранить распределение
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-2 border-t border-slate-200 px-5 py-4 sm:flex-row">
            <SelectInput className="flex-1" value={newOffer} onChange={(e) => setNewOffer(e.target.value)} aria-label="Новый оффер">
              <option value="">Выберите оффер для добавления</option>
              {available.map((o) => (
                <option key={o.id} value={o.id}>
                  #{o.id} — {o.name}
                </option>
              ))}
            </SelectInput>
            <TextInput
              type="number"
              min={1}
              max={100}
              className="sm:w-36"
              placeholder="Доля, % (авто)"
              value={newShare}
              onChange={(e) => setNewShare(e.target.value)}
              aria-label="Доля нового оффера"
            />
            <Button icon={<IconPlus />} onClick={add} loading={adding} disabled={!newOffer || dirty} title={dirty ? 'Сначала сохраните изменения' : undefined}>
              Добавить оффер
            </Button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={!!toRemove}
        title="Удалить оффер из потока?"
        message={
          <>
            Оффер <b>#{toRemove?.offer_id} {toRemove?.offer_name}</b> будет удалён из потока, доли оставшихся офферов пересчитаются пропорционально.
          </>
        }
        loading={removing}
        onConfirm={remove}
        onClose={() => setToRemove(null)}
      />
    </Card>
  )
}
