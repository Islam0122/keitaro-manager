import type { FormEvent } from 'react'
import { useEffect, useState } from 'react'

import { settingsApi } from '@/api'
import { errorMessage } from '@/api/client'
import { ErrorState } from '@/components/ErrorState'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, TextInput } from '@/components/ui/Field'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useToast } from '@/components/ui/Toast'
import { useAsync } from '@/hooks/useAsync'
import { invalidateResources } from '@/hooks/useResources'
import { formatDate } from '@/lib/format'
import type { ConnectionTestResult } from '@/types/api'

const sourceLabels = { database: 'Сохранено в БД', environment: 'Из переменных окружения', none: 'Не настроено' }

export default function SettingsPage() {
  const toast = useToast()
  const settings = useAsync(() => settingsApi.get(), [])
  const health = useAsync(() => settingsApi.health(), [])
  const [form, setForm] = useState({ api_url: '', api_key: '', timeout: '15', default_safe_url: 'https://www.google.com' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [test, setTest] = useState<ConnectionTestResult | null>(null)

  useEffect(() => {
    const s = settings.data
    if (s) setForm((f) => ({ ...f, api_url: s.api_url ?? '', timeout: String(s.timeout), default_safe_url: s.default_safe_url, api_key: '' }))
  }, [settings.data])

  function validate() {
    const e: Record<string, string> = {}
    if (!/^https?:\/\/.+/.test(form.api_url.trim())) e.api_url = 'Укажите URL трекера, например https://tracker.example.com'
    if (!settings.data?.api_key_set && !form.api_key.trim()) e.api_key = 'Укажите API-ключ'
    const t = Number(form.timeout)
    if (!(t > 0 && t <= 120)) e.timeout = 'От 1 до 120 секунд'
    if (!/^https?:\/\/.+/.test(form.default_safe_url.trim())) e.default_safe_url = 'Укажите корректный URL'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const saved = await settingsApi.update({
        api_url: form.api_url.trim(),
        api_key: form.api_key.trim() || null,
        timeout: Number(form.timeout),
        default_safe_url: form.default_safe_url.trim(),
      })
      settings.setData(saved)
      invalidateResources()
      void health.reload()
      toast.success('Настройки сохранены')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function runTest() {
    setTesting(true)
    setTest(null)
    try {
      setTest(await settingsApi.test({ api_url: form.api_url.trim() || undefined, api_key: form.api_key.trim() || undefined }))
    } catch (err) {
      setTest({ ok: false, message: errorMessage(err), latency_ms: null, campaigns_count: null })
    } finally {
      setTesting(false)
    }
  }

  if (settings.error) return <ErrorState error={settings.error} onRetry={settings.reload} />
  if (!settings.data) return <PageLoader />

  return (
    <>
      <PageHeader title="Настройки" description="Подключение к Keitaro Admin API и параметры приложения" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Подключение к Keitaro"
            description="API-ключ хранится в базе данных в зашифрованном виде и никогда не возвращается в интерфейс"
            actions={<Badge tone={settings.data.source === 'none' ? 'amber' : 'green'}>{sourceLabels[settings.data.source]}</Badge>}
          />
          <form onSubmit={save} noValidate className="space-y-5 p-5">
            <Field label="Keitaro API URL" required error={errors.api_url} hint="Адрес трекера; путь /admin_api/v1 добавляется автоматически">
              {(id) => <TextInput id={id} value={form.api_url} invalid={!!errors.api_url} placeholder="https://tracker.example.com" onChange={(e) => setForm({ ...form, api_url: e.target.value })} />}
            </Field>
            <Field
              label="API Key"
              required={!settings.data.api_key_set}
              error={errors.api_key}
              hint={settings.data.api_key_set ? `Текущий ключ: ${settings.data.api_key_masked}. Оставьте поле пустым, чтобы не менять его.` : 'Keitaro → Maintenance → Users → API keys'}
            >
              {(id) => (
                <TextInput id={id} type="password" autoComplete="new-password" value={form.api_key} invalid={!!errors.api_key} placeholder={settings.data?.api_key_set ? '••••••••' : 'Вставьте API-ключ'} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
              )}
            </Field>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <Field label="Таймаут запросов, сек" error={errors.timeout}>
                {(id) => <TextInput id={id} type="number" min={1} max={120} value={form.timeout} invalid={!!errors.timeout} onChange={(e) => setForm({ ...form, timeout: e.target.value })} />}
              </Field>
              <Field label="Redirect URL для GEO-потока" error={errors.default_safe_url} hint="Используется при создании кампаний (поток 1)">
                {(id) => <TextInput id={id} value={form.default_safe_url} invalid={!!errors.default_safe_url} onChange={(e) => setForm({ ...form, default_safe_url: e.target.value })} />}
              </Field>
            </div>

            {test && (
              <Alert tone={test.ok ? 'success' : 'error'} title={test.ok ? 'Подключение установлено' : 'Ошибка подключения'}>
                {test.message}
                {test.ok && ` · ${test.latency_ms} мс · кампаний: ${test.campaigns_count}`}
              </Alert>
            )}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="secondary" onClick={runTest} loading={testing}>
                Проверить подключение
              </Button>
              <Button type="submit" loading={saving}>
                Сохранить
              </Button>
            </div>
          </form>
        </Card>

        <Card className="h-fit">
          <CardHeader title="Состояние системы" />
          <dl className="divide-y divide-slate-100 px-5 py-2 text-sm">
            <div className="flex justify-between py-2">
              <dt className="text-slate-500">Backend</dt>
              <dd>{health.data ? <Badge tone="green">{health.data.status}</Badge> : health.error ? <Badge tone="red">недоступен</Badge> : '…'}</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-slate-500">База данных</dt>
              <dd>{health.data ? <Badge tone={health.data.database === 'ok' ? 'green' : 'red'}>{health.data.database}</Badge> : '…'}</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-slate-500">Keitaro</dt>
              <dd>{health.data ? <Badge tone={health.data.keitaro_configured ? 'green' : 'amber'}>{health.data.keitaro_configured ? 'настроен' : 'не настроен'}</Badge> : '…'}</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-slate-500">Версия</dt>
              <dd className="font-medium">{health.data?.version ?? '—'}</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-slate-500">Изменено</dt>
              <dd className="font-medium">{formatDate(settings.data.updated_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </>
  )
}
