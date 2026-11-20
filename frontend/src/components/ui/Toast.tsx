import type { ReactNode } from 'react'
import { createContext, useCallback, useContext, useMemo, useState } from 'react'

import { cn } from '@/lib/format'

type ToastTone = 'success' | 'error' | 'info'
interface ToastItem {
  id: number
  tone: ToastTone
  message: string
}

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const tones: Record<ToastTone, string> = {
  success: 'border-brand-200 bg-white text-slate-800 [&>span]:bg-brand-500',
  error: 'border-red-200 bg-white text-slate-800 [&>span]:bg-red-500',
  info: 'border-sky-200 bg-white text-slate-800 [&>span]:bg-sky-500',
}

let counter = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((tone: ToastTone, message: string) => {
    const id = ++counter
    setItems((list) => [...list, { id, tone, message }])
    setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), tone === 'error' ? 7000 : 4000)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 left-4 z-[60] flex flex-col items-end gap-2 sm:left-auto">
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cn('pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-lg', tones[t.tone])}
          >
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" />
            <p className="break-words">{t.message}</p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
