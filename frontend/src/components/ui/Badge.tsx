import type { ReactNode } from 'react'

import { cn } from '@/lib/format'

type Tone = 'green' | 'gray' | 'red' | 'amber' | 'blue'

const tones: Record<Tone, string> = {
  green: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  gray: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  red: 'bg-red-50 text-red-700 ring-red-600/20',
  amber: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  blue: 'bg-sky-50 text-sky-700 ring-sky-600/20',
}

export function Badge({ tone = 'gray', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', tones[tone])}>
      {children}
    </span>
  )
}

const stateLabels: Record<string, [string, Tone]> = {
  active: ['Активна', 'green'],
  disabled: ['Остановлена', 'gray'],
  deleted: ['Удалена', 'red'],
}

export function StateBadge({ state }: { state: string | null | undefined }) {
  const [label, tone] = stateLabels[state ?? ''] ?? [state ?? '—', 'gray']
  return (
    <Badge tone={tone}>
      <span className={cn('h-1.5 w-1.5 rounded-full', tone === 'green' ? 'bg-brand-500' : tone === 'red' ? 'bg-red-500' : 'bg-slate-400')} />
      {label}
    </Badge>
  )
}
