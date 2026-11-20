export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.includes('T') || value.includes('Z') ? value : value.replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export function payloadToText(payload: unknown): string {
  if (payload == null) return ''
  if (Array.isArray(payload)) return payload.join(', ')
  if (typeof payload === 'object') return JSON.stringify(payload)
  return String(payload)
}

export function parseList(text: string): string[] {
  return text
    .split(/[,\n;]/)
    .map((v) => v.trim())
    .filter(Boolean)
}

/** Equal integer split totalling 100 (remainder goes to the first items). */
export function equalSplit(count: number): number[] {
  if (count <= 0) return []
  const base = Math.floor(100 / count)
  const rest = 100 - base * count
  return Array.from({ length: count }, (_, i) => base + (i < rest ? 1 : 0))
}

/** Proportional rescale of integer values to 100 using the largest remainder method. */
export function scaleTo100(values: number[]): number[] {
  const total = values.reduce((a, b) => a + b, 0)
  if (values.length === 0) return []
  if (total <= 0) return equalSplit(values.length)
  const raw = values.map((v) => (v * 100) / total)
  const result = raw.map(Math.floor)
  let missing = 100 - result.reduce((a, b) => a + b, 0)
  const order = raw.map((r, i) => [r - result[i], i] as const).sort((a, b) => b[0] - a[0])
  for (const [, i] of order) {
    if (missing <= 0) break
    result[i] += 1
    missing -= 1
  }
  return result
}
