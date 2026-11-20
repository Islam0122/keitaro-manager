import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { campaignsApi, settingsApi } from '@/api'
import { ApiError, errorMessage } from '@/api/client'
import { ErrorState } from '@/components/ErrorState'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, SelectInput, TextInput } from '@/components/ui/Field'
import { IconArrowLeft, IconPlus, IconRefresh } from '@/components/ui/Icons'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useToast } from '@/components/ui/Toast'
import { useAsync } from '@/hooks/useAsync'
import { useResources } from '@/hooks/useResources'
import { COUNTRIES } from '@/lib/countries'

interface FormState {
  name: string
  country: string
  offer_id: string
  domain_id: string
  group_id: string
  traffic_source_id: string
}

type Errors = Partial<Record<keyof FormState, string>>

const initial: FormState = { name: '', country: '', offer_id: '', domain_id: '', group_id: '', traffic_source_id: '' }

function validate(form: FormState): Errors {
  const errors: Errors = {}
  if (!form.name.trim()) errors.name = 'Укажите название кампании'
  else if (form.name.trim().length > 255) errors.name = 'Не более 255 символов'
  if (!/^[A-Za-z]{2}$/.test(form.country.trim())) errors.country = 'Двухбуквенный ISO-код, например US'
  if (!form.offer_id) errors.offer_id = 'Выберите оффер'
  if (!form.domain_id) errors.domain_id = 'Выберите домен'
  if (!form.group_id) errors.group_id = 'Выберите группу'
  if (!form.traffic_source_id) errors.traffic_source_id = 'Выберите источник трафика'
  return errors
}

export default function CreateCampaignPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const { data: resources, error, errorCode, loading, refresh } = useResources()
  const { data: settings } = useAsync(() => settingsApi.get(), [])
  const [form, setForm] = useState<FormState>(initial)
  const [errors, setErrors] = useState<Errors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const set = (key: keyof FormState) => (value: string) => {
    setForm((f) => ({ ...f, [key]: value }))
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const found = validate(form)
    setErrors(found)
    setSubmitError(null)
    if (Object.keys(found).length) return
    setSubmitting(true)
    try {
      const created = await campaignsApi.create({
        name: form.name.trim(),
        country: form.country.trim().toUpperCase(),
        offer_id: Number(form.offer_id),
        domain_id: Number(form.domain_id),
        group_id: Number(form.group_id),
        traffic_source_id: Number(form.traffic_source_id),
      })
      toast.success(`Кампания «${created.campaign.name}» создана (#${created.campaign.id})`)
      navigate(`/campaigns/${created.campaign.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.fields.length) {
        const fieldErrors: Errors = {}
        for (const f of err.fields) if (f.field in initial) fieldErrors[f.field as keyof FormState] = f.message
        setErrors(fieldErrors)
      }
      setSubmitError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const country = form.country.trim().toUpperCase() || 'XX'
  const offerName = resources?.offers.find((o) => String(o.id) === form.offer_id)?.name

  return (
    <>
      <PageHeader
        title="Создание кампании"
        description="Кампания будет создана в Keitaro с двумя потоками"
        back={
          <Link to="/campaigns" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
            <IconArrowLeft className="h-4 w-4" /> К списку кампаний
          </Link>
        }
        actions={
          <Button variant="secondary" icon={<IconRefresh />} onClick={refresh} loading={loading && !!resources}>
            Обновить справочники
          </Button>
        }
      />

      {error ? (
        <ErrorState error={error} code={errorCode} onRetry={refresh} />
      ) : loading && !resources ? (
        <PageLoader label="Загрузка справочников Keitaro…" />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Параметры кампании" description="Все поля обязательны" />
            <form onSubmit={onSubmit} noValidate className="grid grid-cols-1 gap-5 p-5 sm:grid-cols-2">
              <Field label="Campaign Name" required error={errors.name} className="sm:col-span-2">
                {(id) => (
                  <TextInput id={id} value={form.name} invalid={!!errors.name} placeholder="Например: US | Facebook | Offer A" onChange={(e) => set('name')(e.target.value)} />
                )}
              </Field>

              <Field label="Country / GEO" required error={errors.country} hint="ISO-код страны: выберите из списка или введите вручную">
                {(id) => (
                  <>
                    <TextInput
                      id={id}
                      list="geo-list"
                      maxLength={2}
                      value={form.country}
                      invalid={!!errors.country}
                      placeholder="US"
                      className="uppercase"
                      onChange={(e) => set('country')(e.target.value.toUpperCase())}
                    />
                    <datalist id="geo-list">
                      {COUNTRIES.map(([code, name]) => (
                        <option key={code} value={code}>
                          {name}
                        </option>
                      ))}
                    </datalist>
                  </>
                )}
              </Field>

              <Field label="Offer ID" required error={errors.offer_id}>
                {(id) => (
                  <SelectInput id={id} value={form.offer_id} invalid={!!errors.offer_id} onChange={(e) => set('offer_id')(e.target.value)}>
                    <option value="">Выберите оффер</option>
                    {resources?.offers.map((o) => (
                      <option key={o.id} value={o.id}>
                        #{o.id} — {o.name}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </Field>

              <Field label="Domain" required error={errors.domain_id}>
                {(id) => (
                  <SelectInput id={id} value={form.domain_id} invalid={!!errors.domain_id} onChange={(e) => set('domain_id')(e.target.value)}>
                    <option value="">Выберите домен</option>
                    {resources?.domains.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </Field>

              <Field label="Group" required error={errors.group_id}>
                {(id) => (
                  <SelectInput id={id} value={form.group_id} invalid={!!errors.group_id} onChange={(e) => set('group_id')(e.target.value)}>
                    <option value="">Выберите группу</option>
                    {resources?.groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </Field>

              <Field label="Traffic Source" required error={errors.traffic_source_id} className="sm:col-span-2">
                {(id) => (
                  <SelectInput id={id} value={form.traffic_source_id} invalid={!!errors.traffic_source_id} onChange={(e) => set('traffic_source_id')(e.target.value)}>
                    <option value="">Выберите источник трафика</option>
                    {resources?.sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </Field>

              {submitError && (
                <div className="sm:col-span-2">
                  <Alert title="Кампания не создана">{submitError}</Alert>
                </div>
              )}

              <div className="flex flex-col-reverse gap-2 sm:col-span-2 sm:flex-row sm:justify-end">
                <Button variant="secondary" onClick={() => { setForm(initial); setErrors({}); setSubmitError(null) }} disabled={submitting}>
                  Очистить
                </Button>
                <Button type="submit" icon={<IconPlus />} loading={submitting}>
                  Create Campaign
                </Button>
              </div>
            </form>
          </Card>

          <Card className="h-fit">
            <CardHeader title="Схема потоков" description="Будет создана автоматически" />
            <ol className="space-y-4 p-5 text-sm">
              <li className="rounded-lg border border-slate-200 p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase">Поток 1 · Redirect</p>
                <p className="mt-1 text-slate-700">
                  Условие: страна <b className="font-mono">{country}</b>
                </p>
                <p className="mt-0.5 truncate text-slate-500">→ {settings?.default_safe_url ?? 'https://www.google.com'}</p>
              </li>
              <li className="rounded-lg border border-brand-200 bg-brand-50/50 p-4">
                <p className="text-xs font-semibold text-brand-700 uppercase">Поток 2 · Offers</p>
                <p className="mt-1 text-slate-700">Условие: остальные пользователи</p>
                <p className="mt-0.5 text-slate-500">→ {offerName ? `${offerName} (100%)` : 'выбранный оффер (100%)'}</p>
              </li>
            </ol>
          </Card>
        </div>
      )}
    </>
  )
}
