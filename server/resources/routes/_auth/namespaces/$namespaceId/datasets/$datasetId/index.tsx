import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/$datasetId/')({
  component: RouteComponent,
})

function RouteComponent() {
  const { namespaceId, datasetId } = Route.useParams()
  return <>
    <Link
      to="/namespaces/$namespaceId/datasets/$datasetId/runs"
      params={{ namespaceId, datasetId }}
    >
      <Button>
        Browse Runs
      </Button>
    </Link>
  </>
}
