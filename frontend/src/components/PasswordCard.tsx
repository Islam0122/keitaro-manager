import type { FormEvent } from 'react'
import { useState } from 'react'

import { authApi } from '@/api'
import { ApiError, errorMessage } from '@/api/client'
import { useAuth } from '@/auth/AuthContext'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, TextInput } from '@/components/ui/Field'
import { useToast } from '@/components/ui/Toast'

const empty = { current: '', next: '', repeat: '' }

export function PasswordCard() {
  const { user } = useAuth()
  const toast = useToast()
  const [form, setForm] = useState(empty)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found: Record<string, string> = {}
    if (!form.current) found.current = 'Введите текущий пароль'
    if (form.next.length < 10) found.next = 'Не короче 10 символов'
    if (form.next !== form.repeat) found.repeat = 'Пароли не совпадают'
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    try {
      await authApi.changePassword(form.current, form.next)
      setForm(empty)
      toast.success('Пароль изменён')
    } catch (err) {
      if (err instanceof ApiError && err.fields.length) {
        const map: Record<string, string> = { current_password: 'current', new_password: 'next' }
        setErrors(Object.fromEntries(err.fields.map((f) => [map[f.field] ?? f.field, f.message])))
      }
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="lg:col-span-2">
      <CardHeader title="Учётная запись" description={user ? `Вы вошли как ${user.username}` : undefined} />
      <form onSubmit={submit} noValidate className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-3">
        <Field label="Текущий пароль" error={errors.current}>
          {(id) => (
            <TextInput id={id} type="password" autoComplete="current-password" value={form.current} invalid={!!errors.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
          )}
        </Field>
        <Field label="Новый пароль" error={errors.next} hint="Минимум 10 символов, буквы и цифры">
          {(id) => (
            <TextInput id={id} type="password" autoComplete="new-password" value={form.next} invalid={!!errors.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
          )}
        </Field>
        <Field label="Повторите пароль" error={errors.repeat}>
          {(id) => (
            <TextInput id={id} type="password" autoComplete="new-password" value={form.repeat} invalid={!!errors.repeat} onChange={(e) => setForm({ ...form, repeat: e.target.value })} />
          )}
        </Field>
        <div className="flex justify-end sm:col-span-3">
          <Button type="submit" loading={saving}>
            Сменить пароль
          </Button>
        </div>
      </form>
    </Card>
  )
}
