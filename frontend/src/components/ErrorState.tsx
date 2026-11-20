import { Link } from 'react-router-dom'

import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'

export function ErrorState({ error, code, onRetry }: { error: string; code?: string | null; onRetry?: () => void }) {
  const notConfigured = code === 'keitaro_not_configured' || code === 'keitaro_auth_failed'
  return (
    <Alert
      tone={notConfigured ? 'warning' : 'error'}
      title={notConfigured ? 'Требуется настройка подключения' : 'Не удалось загрузить данные'}
      action={
        <div className="flex gap-2">
          {notConfigured && (
            <Link to="/settings" className="inline-flex h-8 items-center rounded-lg bg-brand-600 px-3 text-xs font-medium text-white hover:bg-brand-700">
              Открыть настройки
            </Link>
          )}
          {onRetry && (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Повторить
            </Button>
          )}
        </div>
      }
    >
      {error}
    </Alert>
  )
}
