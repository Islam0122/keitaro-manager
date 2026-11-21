import type { FormEvent } from 'react'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError, errorMessage } from '@/api/client'
import { useAuth } from '@/auth/AuthContext'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Field, TextInput } from '@/components/ui/Field'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/campaigns'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to={from} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Введите логин и пароль')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError && err.code === 'invalid_credentials' ? 'Неверный логин или пароль' : errorMessage(err))
      setPassword('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-xl font-bold text-white">K</div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Keitaro Manager</h1>
            <p className="mt-1 text-sm text-slate-500">Войдите, чтобы управлять кампаниями</p>
          </div>
        </div>
        <form onSubmit={onSubmit} noValidate className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <Field label="Логин" required>
            {(id) => (
              <TextInput id={id} autoComplete="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
            )}
          </Field>
          <Field label="Пароль" required>
            {(id) => (
              <TextInput
                id={id}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          {error && <Alert title="Не удалось войти">{error}</Alert>}
          <Button type="submit" className="w-full" loading={submitting}>
            Войти
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-slate-400">
          Нет учётной записи? Администратор создаёт её командой <code className="font-mono">python -m app.cli create-user</code>
        </p>
      </div>
    </div>
  )
}
