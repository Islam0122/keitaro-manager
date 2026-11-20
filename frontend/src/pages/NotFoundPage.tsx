import { Link } from 'react-router-dom'

import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/Alert'

export default function NotFoundPage() {
  return (
    <Card>
      <EmptyState
        title="Страница не найдена"
        description="Проверьте адрес или вернитесь к списку кампаний."
        action={<Link to="/campaigns" className="text-sm font-medium text-brand-700 hover:underline">К кампаниям</Link>}
      />
    </Card>
  )
}
