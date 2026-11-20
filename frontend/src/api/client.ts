import axios, { AxiosError } from 'axios'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

export class ApiError extends Error {
  status: number | null
  code: string | null
  fields: { field: string; message: string }[]

  constructor(message: string, status: number | null, code: string | null, fields: ApiError['fields'] = []) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

interface ErrorBody {
  detail?: unknown
  code?: string
  errors?: { field: string; message: string }[]
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorBody>) => {
    if (error.response) {
      const body = error.response.data
      const detail = typeof body?.detail === 'string' ? body.detail : `Ошибка сервера (${error.response.status})`
      return Promise.reject(new ApiError(detail, error.response.status, body?.code ?? null, body?.errors ?? []))
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
