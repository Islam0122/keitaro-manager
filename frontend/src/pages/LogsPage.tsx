import { settingsApi } from '@/api'
import { CampaignLogList } from '@/components/CampaignLogList'
import { ErrorState } from '@/components/ErrorState'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { IconRefresh } from '@/components/ui/Icons'
import { PageHeader } from '@/components/ui/PageHeader'
import { PageLoader } from '@/components/ui/Spinner'
import { useAsync } from '@/hooks/useAsync'

export default function LogsPage() {
  const { data, error, loading, reload } = useAsync(() => settingsApi.logs(), [])
  return (
    <>
      <PageHeader
        title="Журнал операций"
        description="Все изменения, выполненные через Keitaro Manager"
        actions={
          <Button variant="secondary" icon={<IconRefresh />} onClick={reload} loading={loading}>
            Обновить
          </Button>
        }
      />
      {error ? <ErrorState error={error} onRetry={reload} /> : <Card>{data ? <CampaignLogList logs={data} showCampaign /> : <PageLoader />}</Card>}
    </>
  )
}
