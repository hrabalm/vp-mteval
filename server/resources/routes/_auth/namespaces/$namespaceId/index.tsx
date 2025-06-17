import { createFileRoute, Link } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/')({
  component: RouteComponent,
})

function RouteComponent() {
  const { namespaceId } = Route.useParams()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Namespace: {namespaceId}</h1>

      <div className="flex space-x-4 mb-6">
        <Link
          to="/namespaces/$namespaceId/runs"
          params={{ namespaceId }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md"
        >
          View Runs
        </Link>
        <Link
          to="/namespaces/$namespaceId/datasets"
          params={{ namespaceId }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md"
        >
          View Datasets
        </Link>
      </div>

      <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Namespace Details</h2>
        <p>Namespace ID: {namespaceId}</p>
      </div>
    </div>
  )
}
