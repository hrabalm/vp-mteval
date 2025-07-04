import VirtualizedJSON from '@/components/virtualized-json';
import { fetchDatasets } from '@/datasets'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/namespaces/$namespaceId/datasets/')({
  component: RouteComponent,
  loader: ({ params }) => fetchDatasets(params.namespaceId),
})

function RouteComponent() {
  const datasets = Route.useLoaderData();
  console.log('Datasets:', datasets);
  return <VirtualizedJSON json={datasets} />
}
