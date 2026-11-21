import { Badge } from '@/components/ui/Badge'
import { formatDate } from '@/lib/format'
import type { CampaignLog } from '@/types/api'

const ACTION_LABELS: Record<string, string> = {
  'campaign.create': 'Создание кампании',
  'campaign.update': 'Изменение кампании',
  'campaign.delete': 'Удаление кампании',
  'offer.add': 'Добавление оффера',
  'offer.update': 'Изменение распределения',
  'offer.remove': 'Удаление оффера',
  'offer.distribute': 'Перераспределение трафика',
  'stream.create': 'Создание потока',
  'stream.update': 'Изменение потока',
  'stream.delete': 'Удаление потока',
  'stream.enable': 'Включение потока',
  'stream.disable': 'Выключение потока',
  'settings.update': 'Изменение настроек',
}

export function CampaignLogList({ logs, showCampaign }: { logs: CampaignLog[]; showCampaign?: boolean }) {
  if (logs.length === 0) return <p className="px-5 py-6 text-sm text-slate-500">Операций пока не было.</p>
  return (
    <ul className="divide-y divide-slate-100">
      {logs.map((log) => (
        <li key={log.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:gap-4">
          <span className="w-32 shrink-0 text-xs text-slate-400">{formatDate(log.created_at)}</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-slate-800">
              {ACTION_LABELS[log.action] ?? log.action}
              {showCampaign && log.campaign_keitaro_id && <span className="ml-2 font-mono text-xs text-slate-400">#{log.campaign_keitaro_id}</span>}
            </p>
            {log.message && <p className="truncate text-xs text-slate-500" title={log.message}>{log.message}</p>}
            {log.username && <p className="text-xs text-slate-400">{log.username}</p>}
          </div>
          <Badge tone={log.status === 'success' ? 'green' : 'red'}>{log.status === 'success' ? 'успешно' : 'ошибка'}</Badge>
        </li>
      ))}
    </ul>
  )
}
