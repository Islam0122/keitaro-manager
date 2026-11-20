import { useMemo, useState } from 'react'

import { Alert } from '@/components/ui/Alert'
import { Button, IconButton } from '@/components/ui/Button'
import { Field, SelectInput, TextArea, TextInput, Toggle } from '@/components/ui/Field'
import { IconPlus, IconTrash } from '@/components/ui/Icons'
import { cn, equalSplit, parseList, payloadToText } from '@/lib/format'
import { LIST_FILTERS, OTHER_ACTIONS, REDIRECT_ACTIONS, STREAM_SCHEMAS, STREAM_TYPES, filterLabel } from '@/lib/streams'
import type { ItemState, Offer, Stream, StreamInput, StreamSchema, StreamType } from '@/types/api'

interface FilterRow {
  name: string
  mode: 'accept' | 'reject'
  text: string
  /** Original payload for filters we don't edit as a list — sent back unchanged. */
  raw?: unknown
}

interface OfferRow {
  offer_id: string
  share: number
  state: ItemState
}

interface FormState {
  name: string
  type: StreamType
  state: ItemState
  schema: StreamSchema
  action_type: string
  action_payload: string
  filter_or: boolean
  collect_clicks: boolean
  comments: string
  geoEnabled: boolean
  geoMode: 'accept' | 'reject'
  geoCodes: string
  filters: FilterRow[]
  offers: OfferRow[]
}

function fromStream(stream: Stream | null, defaultUrl: string): FormState {
  const geo = stream?.filters.find((f) => f.name === 'country')
  return {
    name: stream?.name ?? '',
    type: stream?.type ?? 'regular',
    state: stream?.state ?? 'active',
    schema: stream?.schema ?? 'redirect',
    action_type: stream?.action_type ?? 'http',
    action_payload: typeof stream?.action_payload === 'string' ? stream.action_payload : stream ? '' : defaultUrl,
    filter_or: stream?.filter_or ?? false,
    collect_clicks: stream?.collect_clicks ?? true,
    comments: stream?.comments ?? '',
    geoEnabled: !!geo,
    geoMode: geo?.mode ?? 'accept',
    geoCodes: geo ? payloadToText(geo.payload) : '',
    filters: (stream?.filters ?? [])
      .filter((f) => f.name !== 'country')
      .map((f) =>
        Array.isArray(f.payload) || typeof f.payload === 'string'
          ? { name: f.name, mode: f.mode, text: payloadToText(f.payload) }
          : { name: f.name, mode: f.mode, text: payloadToText(f.payload), raw: f.payload },
      ),
    offers: (stream?.offers ?? []).map((o) => ({ offer_id: String(o.offer_id), share: o.share, state: o.state })),
  }
}

function toInput(form: FormState): { input?: StreamInput; error?: string } {
  if (!form.name.trim()) return { error: 'Укажите название потока' }
  const filters: StreamInput['filters'] = []
  if (form.geoEnabled) {
    const codes = parseList(form.geoCodes).map((c) => c.toUpperCase())
    if (!codes.length || codes.some((c) => !/^[A-Z]{2}$/.test(c))) return { error: 'GEO-фильтр: укажите ISO-коды стран через запятую (US, CA)' }
    filters.push({ name: 'country', mode: form.geoMode, payload: codes })
  }
  for (const f of form.filters) {
    if (f.raw !== undefined) {
      filters.push({ name: f.name, mode: f.mode, payload: f.raw })
      continue
    }
    const values = parseList(f.text)
    if (!values.length) return { error: `Фильтр «${filterLabel(f.name)}»: укажите значения` }
    filters.push({ name: f.name, mode: f.mode, payload: values })
  }
  if (form.type === 'default' && filters.length) return { error: 'Запасной (default) поток не может иметь фильтров' }

  let offers: StreamInput['offers'] = []
  if (form.schema === 'landings') {
    if (!form.offers.length) return { error: 'Добавьте хотя бы один оффер' }
    if (form.offers.some((o) => !o.offer_id)) return { error: 'Выберите оффер в каждой строке' }
    const ids = form.offers.map((o) => o.offer_id)
    if (new Set(ids).size !== ids.length) return { error: 'Оффер выбран дважды' }
    const total = form.offers.filter((o) => o.state === 'active').reduce((s, o) => s + o.share, 0)
    if (form.offers.some((o) => o.state === 'active') && total !== 100) return { error: `Сумма долей активных офферов: ${total}%, должна быть 100%` }
    offers = form.offers.map((o) => ({ offer_id: Number(o.offer_id), share: o.share, state: o.state }))
  }
  if (form.schema === 'redirect' && !/^https?:\/\/.+/.test(form.action_payload.trim()))
    return { error: 'Укажите целевой URL (http:// или https://)' }
  if (form.schema === 'action' && ['show_text', 'show_html'].includes(form.action_type) && !form.action_payload.trim())
    return { error: 'Укажите содержимое для показа' }

  return {
    input: {
      name: form.name.trim(),
      type: form.type,
      state: form.state,
      schema: form.schema,
      action_type: form.action_type,
      action_payload: form.schema === 'landings' || !form.action_payload.trim() ? null : form.action_payload.trim(),
      filter_or: form.filter_or,
      collect_clicks: form.collect_clicks,
      comments: form.comments.trim() || null,
      filters,
      offers,
    },
  }
}

interface Props {
  stream: Stream | null
  offers: Offer[]
  defaultUrl: string
  saving: boolean
  onSubmit: (input: StreamInput) => void
  onCancel: () => void
}

export function StreamForm({ stream, offers, defaultUrl, saving, onSubmit, onCancel }: Props) {
  const [form, setForm] = useState<FormState>(() => fromStream(stream, defaultUrl))
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }))

  const actions = form.schema === 'action' ? OTHER_ACTIONS : REDIRECT_ACTIONS
  const offerTotal = useMemo(() => form.offers.filter((o) => o.state === 'active').reduce((s, o) => s + o.share, 0), [form.offers])

  function changeSchema(schema: StreamSchema) {
    setForm((f) => ({
      ...f,
      schema,
      action_type: schema === 'action' ? 'status404' : f.action_type in REDIRECT_ACTIONS ? f.action_type : 'http',
    }))
  }

  function patchOffer(index: number, patch: Partial<OfferRow>) {
    set('offers', form.offers.map((o, i) => (i === index ? { ...o, ...patch } : o)))
  }

  function equalize() {
    const active = form.offers.filter((o) => o.state === 'active').length
    const shares = equalSplit(active)
    let k = 0
    set('offers', form.offers.map((o) => (o.state === 'active' ? { ...o, share: shares[k++] } : o)))
  }

  function submit() {
    const { input, error: err } = toInput(form)
    setError(err ?? null)
    if (input) onSubmit(input)
  }

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Название потока" required className="sm:col-span-2">
          {(id) => <TextInput id={id} value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Например: GEO US → Safe" />}
        </Field>
        <Field label="Тип потока">
          {(id) => (
            <SelectInput id={id} value={form.type} onChange={(e) => set('type', e.target.value as StreamType)}>
              {Object.entries(STREAM_TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </SelectInput>
          )}
        </Field>
        <div className="flex items-end gap-6 pb-2">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <Toggle checked={form.state === 'active'} onChange={(v) => set('state', v ? 'active' : 'disabled')} label="Поток включён" />
            Включён
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <Toggle checked={form.collect_clicks} onChange={(v) => set('collect_clicks', v)} label="Собирать клики" />
            Собирать клики
          </label>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-semibold text-slate-900">Условия (фильтры)</h4>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Логика:</span>
            {(['AND', 'OR'] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => set('filter_or', l === 'OR')}
                className={cn('rounded-md px-2 py-1 font-medium', (l === 'OR') === form.filter_or ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600')}
              >
                {l === 'AND' ? 'Все условия (AND)' : 'Любое (OR)'}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-3">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <Toggle checked={form.geoEnabled} onChange={(v) => set('geoEnabled', v)} label="GEO-фильтр" disabled={form.type === 'default'} />
            GEO-фильтр (страна)
          </label>
          {form.geoEnabled && (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[180px_1fr]">
              <SelectInput value={form.geoMode} onChange={(e) => set('geoMode', e.target.value as 'accept' | 'reject')} aria-label="Режим GEO">
                <option value="accept">Только из стран</option>
                <option value="reject">Кроме стран</option>
              </SelectInput>
              <TextInput value={form.geoCodes} onChange={(e) => set('geoCodes', e.target.value.toUpperCase())} placeholder="US, CA, GB" aria-label="Страны" />
            </div>
          )}
        </div>

        {form.filters.map((f, i) => (
          <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[180px_150px_1fr_auto]">
            <SelectInput
              value={f.name}
              disabled={f.raw !== undefined}
              onChange={(e) => set('filters', form.filters.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)))}
              aria-label="Фильтр"
            >
              {!(f.name in LIST_FILTERS) && <option value={f.name}>{f.name}</option>}
              {Object.entries(LIST_FILTERS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </SelectInput>
            <SelectInput
              value={f.mode}
              onChange={(e) => set('filters', form.filters.map((x, k) => (k === i ? { ...x, mode: e.target.value as 'accept' | 'reject' } : x)))}
              aria-label="Режим"
            >
              <option value="accept">Совпадает</option>
              <option value="reject">Не совпадает</option>
            </SelectInput>
            <TextInput
              value={f.text}
              disabled={f.raw !== undefined}
              title={f.raw !== undefined ? 'Сложный фильтр Keitaro — сохраняется без изменений' : undefined}
              onChange={(e) => set('filters', form.filters.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)))}
              placeholder="Значения через запятую"
              aria-label="Значения"
            />
            <IconButton label="Удалить фильтр" onClick={() => set('filters', form.filters.filter((_, k) => k !== i))}>
              <IconTrash />
            </IconButton>
          </div>
        ))}
        <Button
          size="sm"
          variant="secondary"
          icon={<IconPlus className="h-4 w-4" />}
          disabled={form.type === 'default'}
          onClick={() => set('filters', [...form.filters, { name: 'language', mode: 'accept', text: '' }])}
        >
          Добавить фильтр
        </Button>
        {form.type === 'default' && <p className="text-xs text-slate-500">Запасной поток срабатывает, когда не подошёл ни один другой поток, — фильтры недоступны.</p>}
      </section>

      <section className="space-y-4 rounded-xl border border-slate-200 p-4">
        <h4 className="text-sm font-semibold text-slate-900">Перенаправление</h4>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Схема">
            {(id) => (
              <SelectInput id={id} value={form.schema} onChange={(e) => changeSchema(e.target.value as StreamSchema)}>
                {Object.entries(STREAM_SCHEMAS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </SelectInput>
            )}
          </Field>
          <Field label={form.schema === 'action' ? 'Действие' : 'Способ редиректа'}>
            {(id) => (
              <SelectInput id={id} value={form.action_type} onChange={(e) => set('action_type', e.target.value)}>
                {Object.entries(actions).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </SelectInput>
            )}
          </Field>
        </div>

        {form.schema === 'redirect' && (
          <Field label="Целевой URL" required>
            {(id) => <TextInput id={id} value={form.action_payload} onChange={(e) => set('action_payload', e.target.value)} placeholder="https://www.google.com" />}
          </Field>
        )}
        {form.schema === 'action' && ['show_text', 'show_html'].includes(form.action_type) && (
          <Field label="Содержимое" required>
            {(id) => <TextArea id={id} value={form.action_payload} onChange={(e) => set('action_payload', e.target.value)} />}
          </Field>
        )}

        {form.schema === 'landings' && (
          <div className="space-y-2">
            {form.offers.map((o, i) => (
              <div key={i} className="grid grid-cols-[1fr_96px_auto_auto] items-center gap-2">
                <SelectInput value={o.offer_id} onChange={(e) => patchOffer(i, { offer_id: e.target.value })} aria-label="Оффер">
                  <option value="">Выберите оффер</option>
                  {offers.map((of) => <option key={of.id} value={of.id}>#{of.id} — {of.name}</option>)}
                </SelectInput>
                <div className="relative">
                  <TextInput
                    type="number"
                    min={0}
                    max={100}
                    value={o.share}
                    className="pr-7 text-right"
                    onChange={(e) => patchOffer(i, { share: Math.max(0, Math.min(100, Math.round(Number(e.target.value) || 0))) })}
                    aria-label="Доля"
                  />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-slate-400">%</span>
                </div>
                <Toggle checked={o.state === 'active'} onChange={(v) => patchOffer(i, { state: v ? 'active' : 'disabled' })} label="Оффер активен" />
                <IconButton label="Удалить оффер" onClick={() => set('offers', form.offers.filter((_, k) => k !== i))}>
                  <IconTrash />
                </IconButton>
              </div>
            ))}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<IconPlus className="h-4 w-4" />}
                  onClick={() => {
                    const next = [...form.offers, { offer_id: '', share: 0, state: 'active' as ItemState }]
                    const shares = equalSplit(next.filter((x) => x.state === 'active').length)
                    let k = 0
                    set('offers', next.map((x) => (x.state === 'active' ? { ...x, share: shares[k++] } : x)))
                  }}
                >
                  Добавить оффер
                </Button>
                <Button size="sm" variant="ghost" onClick={equalize} disabled={!form.offers.length}>
                  Поровну
                </Button>
              </div>
              <span className={cn('text-sm font-medium', offerTotal === 100 ? 'text-brand-700' : 'text-red-600')}>Итого: {offerTotal}%</span>
            </div>
          </div>
        )}
      </section>

      <Field label="Комментарий">
        {(id) => <TextInput id={id} value={form.comments} onChange={(e) => set('comments', e.target.value)} />}
      </Field>

      {error && <Alert>{error}</Alert>}

      <div className="flex flex-col-reverse gap-2 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          Отмена
        </Button>
        <Button onClick={submit} loading={saving}>
          {stream ? 'Сохранить поток' : 'Создать поток'}
        </Button>
      </div>
    </div>
  )
}
