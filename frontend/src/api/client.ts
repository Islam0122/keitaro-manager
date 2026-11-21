import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'km.access_token'

/**
 * The access token lives in sessionStorage: it survives page reloads but not closing the tab, and is not sent
 * automatically by the browser (no CSRF surface). The backend never sets cookies.
 */
export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string | null) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token)
      else sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* storage disabled — token only lives in memory for this page */
    }
  },
}

export const UNAUTHORIZED_EVENT = 'km:unauthorized'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export interface RollbackReport {
  performed: boolean
  ok: boolean
  steps: { object: string; id: number; ok: boolean; error?: string; note?: string }[]
}

export class ApiError extends Error {
  status: number | null
  code: string | null
  fields: { field: string; message: string }[]
  rollback: RollbackReport | null

  constructor(
    message: string,
    status: number | null,
    code: string | null,
    fields: ApiError['fields'] = [],
    rollback: RollbackReport | null = null,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
    this.rollback = rollback
  }
}

interface ErrorBody {
  detail?: unknown
  code?: string
  errors?: { field: string; message: string }[]
  rollback?: RollbackReport
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorBody>) => {
    if (error.response) {
      const { status, data: body } = error.response
      const isLogin = error.config?.url?.includes('/auth/login')
      if (status === 401 && !isLogin) {
        tokenStore.set(null)
        window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
      }
      let detail = typeof body?.detail === 'string' ? body.detail : `Ошибка сервера (${status})`
      if (status === 429 && body?.code === 'keitaro_rate_limited') detail = `Keitaro ограничил частоту запросов. ${detail}`
      return Promise.reject(new ApiError(detail, status, body?.code ?? null, body?.errors ?? [], body?.rollback ?? null))
    }
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new ApiError('Сервер не ответил вовремя', null, 'timeout'))
    }
    return Promise.reject(new ApiError('Нет связи с сервером', null, 'network'))
  },
)

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Неизвестная ошибка'
}
