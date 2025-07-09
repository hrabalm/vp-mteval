import { createFileRoute, Link } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/')({
  component: RouteComponent,
})

function RouteComponent() {
  const { namespaceId } = Route.useParams()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Namespace: {namespaceId}</h1>
      <Link
        to="/namespaces/$namespaceId/datasets"
        params={{ namespaceId }}
      >
        <Button>
          Browse Datasets
        </Button>
      </Link>

      <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Namespace Details</h2>
        <p>Namespace ID: {namespaceId}</p>
      </div>
    </div>
  )
}
